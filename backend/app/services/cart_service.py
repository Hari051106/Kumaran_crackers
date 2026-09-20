"""Cart business logic.

Two rules govern everything here:

1. The client supplies a product id and a quantity. Nothing else it sends about
   price, stock or totals is read.
2. Stock is checked against the live product row on every mutation, and again
   at checkout, because the shelf can empty between the two.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.user import User
from app.repositories.cart import CartRepository
from app.repositories.product import ProductRepository
from app.schemas.cart import MAX_LINE_QUANTITY, CartItemAdd
from app.services.pricing import PricedBasket, price_basket
from app.utils.errors import BusinessRuleError, NotFoundError


class CartService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.carts = CartRepository(db)
        self.products = ProductRepository(db)

    # ---- Reads --------------------------------------------------------------
    def get_or_create(self, user: User) -> Cart:
        """Every customer has exactly one basket, made on first use."""
        cart = self.carts.get_for_user(user.id)
        if cart is None:
            cart = self.carts.create_for_user(user.id)
            self.db.commit()
            cart = self.carts.get_for_user(user.id)
            assert cart is not None  # noqa: S101 - just created it
        return cart

    def price(self, cart: Cart) -> PricedBasket:
        """Cost this basket from live product rows."""
        return price_basket(list(cart.items))

    # ---- Mutations ----------------------------------------------------------
    def add_item(self, user: User, payload: CartItemAdd) -> Cart:
        """Add a product, or increase the quantity if it is already there."""
        cart = self.get_or_create(user)
        product = self._require_purchasable_product(payload.product_id)

        existing = self.carts.find_item(cart.id, product.id)
        # Adding what is already in the basket tops up that line rather than
        # creating a duplicate.
        desired = (existing.quantity if existing else 0) + payload.quantity

        if desired > MAX_LINE_QUANTITY:
            raise BusinessRuleError(
                f"You can order at most {MAX_LINE_QUANTITY} of one item at a time."
            )
        self._require_stock(product, desired)

        if existing is not None:
            existing.quantity = desired
            self.db.commit()
            return self._reload(user)

        try:
            self.db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=desired))
            self.db.commit()
        except IntegrityError:
            # Two taps on "add" can race: both see an empty line and both
            # insert, and the unique constraint rejects the loser. Recover by
            # topping up the row the winner created rather than failing.
            self.db.rollback()
            return self._top_up_existing(user, cart.id, product, payload.quantity)

        return self._reload(user)

    def _top_up_existing(self, user: User, cart_id: int, product: Product, extra: int) -> Cart:
        """Add to a line that another request created a moment ago."""
        existing = self.carts.find_item(cart_id, product.id)
        if existing is None:  # pragma: no cover - the row provably exists
            raise BusinessRuleError("Could not add that item. Please try again.")

        desired = existing.quantity + extra
        if desired > MAX_LINE_QUANTITY:
            raise BusinessRuleError(
                f"You can order at most {MAX_LINE_QUANTITY} of one item at a time."
            )
        self._require_stock(product, desired)

        existing.quantity = desired
        self.db.commit()
        return self._reload(user)

    def update_quantity(self, user: User, item_id: int, quantity: int) -> Cart:
        cart = self.get_or_create(user)
        item = self.carts.get_item_for_cart(item_id, cart.id)
        if item is None:
            raise NotFoundError("That item is not in your basket.")

        self._require_stock(item.product, quantity)
        item.quantity = quantity
        self.db.commit()
        return self._reload(user)

    def remove_item(self, user: User, item_id: int) -> Cart:
        cart = self.get_or_create(user)
        item = self.carts.get_item_for_cart(item_id, cart.id)
        if item is None:
            raise NotFoundError("That item is not in your basket.")

        self.db.delete(item)
        self.db.commit()
        return self._reload(user)

    def clear(self, user: User) -> Cart:
        cart = self.get_or_create(user)
        self.carts.clear(cart.id)
        self.db.commit()
        return self._reload(user)

    # ---- Helpers ------------------------------------------------------------
    def _reload(self, user: User) -> Cart:
        """Re-read the basket so lines and products are fresh after a write."""
        cart = self.carts.get_for_user(user.id)
        if cart is None:  # pragma: no cover - the cart was just used
            raise NotFoundError("Basket not found.")
        return cart

    def _require_purchasable_product(self, product_id: int) -> Product:
        product = self.products.get(product_id)
        if product is None:
            raise NotFoundError("That product does not exist.")
        # A product in a retired category is not on sale, however active the
        # product row itself looks.
        if not product.is_active or not product.category.is_active:
            raise BusinessRuleError(f"{product.name} is no longer available.")
        return product

    @staticmethod
    def _require_stock(product: Product, wanted: int) -> None:
        if product.stock_quantity <= 0:
            raise BusinessRuleError(f"{product.name} is out of stock.")
        if wanted > product.stock_quantity:
            unit = "unit" if product.stock_quantity == 1 else "units"
            raise BusinessRuleError(
                f"Only {product.stock_quantity} {unit} of {product.name} remain."
            )

    @property
    def currency(self) -> str:
        return settings.currency
