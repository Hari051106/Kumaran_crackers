"""Cart data access."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.repositories.base import BaseRepository


class CartRepository(BaseRepository[Cart]):
    model = Cart

    def get_for_user(self, user_id: int) -> Cart | None:
        stmt = (
            select(Cart)
            .where(Cart.user_id == user_id)
            .options(
                # Pricing touches every line's product and its category, so
                # they are loaded up front rather than N+1 at calculation time.
                selectinload(Cart.items).joinedload(CartItem.product).joinedload(Product.category)
            )
            # Without populate_existing, a Cart already in the session's
            # identity map comes back with the `items` collection it was first
            # loaded with. Re-reading the basket in the same request that just
            # changed it would then show the state from before the change.
            .execution_options(populate_existing=True)
        )
        return self.db.scalar(stmt)

    def create_for_user(self, user_id: int) -> Cart:
        cart = Cart(user_id=user_id)
        self.db.add(cart)
        self.db.flush()
        return cart

    def find_item(self, cart_id: int, product_id: int) -> CartItem | None:
        stmt = select(CartItem).where(
            CartItem.cart_id == cart_id, CartItem.product_id == product_id
        )
        return self.db.scalar(stmt)

    def get_item_for_cart(self, item_id: int, cart_id: int) -> CartItem | None:
        """Scoped by cart, so one customer cannot touch another's line."""
        stmt = (
            select(CartItem)
            .where(CartItem.id == item_id, CartItem.cart_id == cart_id)
            .options(joinedload(CartItem.product).joinedload(Product.category))
        )
        return self.db.scalar(stmt)

    def clear(self, cart_id: int) -> int:
        """Remove every line. Returns how many were removed."""
        result = self.db.execute(delete(CartItem).where(CartItem.cart_id == cart_id))
        self.db.flush()
        return result.rowcount or 0
