"""Shopping basket models.

Deliberately, a cart item stores **no price**. It records what the shopper
wants and how many, and nothing about what it costs. Every total is recomputed
from the live `products` row whenever the cart is read, so a price change
between adding an item and checking out is reflected immediately and a client
can never influence what is charged.

Price is only ever frozen at the moment an order is placed, into the order's
own line items.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.product import Product
    from app.models.user import User


class Cart(Base, TimestampMixin):
    """One basket per customer, created on first use."""

    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user: Mapped[User] = relationship(back_populates="cart")

    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        order_by="CartItem.id",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Cart id={self.id} user_id={self.user_id} items={len(self.items)}>"


class CartItem(Base, TimestampMixin):
    """A product and a quantity. No price - see the module docstring."""

    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        # Adding the same product twice increases the quantity of one row
        # rather than creating a duplicate line.
        UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_id_product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cart: Mapped[Cart] = relationship(back_populates="items")

    # RESTRICT: a product sitting in someone's basket must not be deletable
    # out from under them. Deactivate it instead.
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product: Mapped[Product] = relationship(lazy="joined")

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CartItem product_id={self.product_id} quantity={self.quantity}>"
