"""Checkout.

Produces the authoritative quote for a basket delivered to an address: what it
costs, and whether the order can actually be placed. Order creation itself
arrives with the order system and will reuse this same pricing, so a customer
can never be quoted one figure and charged another.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.address import Address
from app.models.cart import Cart
from app.models.user import User
from app.services.address_service import AddressService
from app.services.cart_service import CartService
from app.services.pricing import PricedBasket


class CheckoutValidation:
    """The outcome of the pre-flight checks, with the reasons attached."""

    def __init__(
        self,
        *,
        cart: Cart,
        basket: PricedBasket,
        address: Address,
        blockers: list[str],
    ) -> None:
        self.cart = cart
        self.basket = basket
        self.address = address
        self.blockers = blockers

    @property
    def can_place_order(self) -> bool:
        return not self.blockers


class CheckoutService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.carts = CartService(db)
        self.addresses = AddressService(db)

    def quote(self, user: User, address_id: int) -> CheckoutValidation:
        """Run every pre-flight check and price the basket.

        The order of checks mirrors the order they must hold in: a customer who
        can buy, a basket with something in it, an address to send it to, and
        stock to satisfy every line.
        """
        cart = self.carts.get_or_create(user)
        basket = self.carts.price(cart)
        # Raises NotFoundError if the address is missing or belongs to someone
        # else, so an unusable address never reaches the quote.
        address = self.addresses.get(user, address_id)

        blockers: list[str] = []

        if not user.is_active:
            blockers.append("This account is not able to place orders.")

        if basket.is_empty:
            blockers.append("Your basket is empty.")

        # Stock and availability problems, one message per offending line.
        blockers.extend(basket.problems)

        return CheckoutValidation(cart=cart, basket=basket, address=address, blockers=blockers)

    def default_address(self, user: User) -> Address | None:
        """The address checkout should preselect."""
        return self.addresses.get_default(user)
