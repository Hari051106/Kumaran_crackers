"""Order models.

Where a cart item deliberately stores no price, an order line stores
**everything**: the price paid, the MRP it was compared against, and even the
product's name and SKU as they read at the time.

An invoice is a record of what happened. If the catalogue is re-priced, a
product renamed, or a category retired, a past order must still show what the
customer actually bought and paid. Nothing here is a live lookup.

The delivery address is snapshotted for the same reason: editing a saved
address must not silently rewrite where a past order was sent.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin
from app.enums import ORDER_TIMELINE, OrderStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.product import Product
    from app.models.user import User

MONEY = Numeric(10, 2)


class Order(Base, TimestampMixin):
    """A placed order."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="subtotal_non_negative"),
        CheckConstraint("discount >= 0", name="discount_non_negative"),
        CheckConstraint("items_total >= 0", name="items_total_non_negative"),
        CheckConstraint("delivery_charge >= 0", name="delivery_charge_non_negative"),
        CheckConstraint("total >= 0", name="total_non_negative"),
        # The invoice must add up. If these ever disagree the arithmetic was
        # wrong, and the database refuses the row rather than storing a lie.
        CheckConstraint(
            "items_total = subtotal - discount", name="items_total_is_subtotal_less_discount"
        ),
        CheckConstraint(
            "total = items_total + delivery_charge", name="total_is_items_plus_delivery"
        ),
        # The admin list is almost always "newest first, optionally by status".
        Index("ix_orders_status_placed_at", "status", "placed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    #: Human-readable reference, e.g. KC-000123. What a customer quotes on the phone.
    order_number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)

    # RESTRICT: a customer with order history cannot simply vanish.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user: Mapped[User] = relationship(back_populates="orders")

    # server_default as well as the Python default, so a row inserted outside
    # the ORM (a migration, a data fix, psql) is still valid.
    status: Mapped[str] = mapped_column(
        String(32),
        default=OrderStatus.PLACED.value,
        server_default=text(f"'{OrderStatus.PLACED.value}'"),
        nullable=False,
        index=True,
    )

    # ---- Money, frozen at placement ----------------------------------------
    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    items_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    delivery_charge: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), default="INR", server_default=text("'INR'"), nullable=False
    )

    # ---- Delivery address, snapshotted -------------------------------------
    delivery_full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    delivery_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery_house_number: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_street: Mapped[str] = mapped_column(String(200), nullable=False)
    delivery_area: Mapped[str] = mapped_column(String(150), nullable=False)
    delivery_city: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_state: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    delivery_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Lifecycle ----------------------------------------------------------
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
    )
    status_history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.id",
    )

    # ---- Derived ------------------------------------------------------------
    @property
    def status_enum(self) -> OrderStatus:
        return OrderStatus(self.status)

    @property
    def item_count(self) -> int:
        """Total units ordered, not lines."""
        return sum(item.quantity for item in self.items)

    @property
    def is_cancellable_by_customer(self) -> bool:
        from app.enums import CUSTOMER_CANCELLABLE

        return self.status_enum in CUSTOMER_CANCELLABLE

    @property
    def delivery_address_line(self) -> str:
        parts = [
            self.delivery_house_number,
            self.delivery_street,
            self.delivery_area,
            self.delivery_city,
            self.delivery_state,
            self.delivery_pincode,
        ]
        return ", ".join(part.strip() for part in parts if part and part.strip())

    @property
    def timeline_position(self) -> int:
        """How far along the happy path this order is, for the tracking view.

        A cancelled order has no position on that path.
        """
        status = self.status_enum
        if status is OrderStatus.CANCELLED:
            return -1
        return ORDER_TIMELINE.index(status)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Order {self.order_number} status={self.status} total={self.total}>"


class OrderItem(Base, TimestampMixin):
    """One line of an order, with its price frozen at purchase."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("unit_mrp >= 0", name="unit_mrp_non_negative"),
        CheckConstraint("line_total >= 0", name="line_total_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order: Mapped[Order] = relationship(back_populates="items")

    # RESTRICT: a product that has ever been sold cannot be deleted, or the
    # order history would lose what it refers to.
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product: Mapped[Product] = relationship(lazy="joined")

    # ---- Snapshotted product details ---------------------------------------
    # Kept so a renamed product does not rewrite an old invoice.
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(64), nullable=False)
    product_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # ---- Snapshotted money --------------------------------------------------
    unit_mrp: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    line_discount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<OrderItem {self.product_sku} x{self.quantity} @ {self.unit_price}>"


class OrderStatusHistory(Base):
    """An audit trail entry: who moved this order, when, and to what.

    Append-only. Rows are never updated or deleted, so the record of how an
    order progressed cannot be quietly rewritten.
    """

    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order: Mapped[Order] = relationship(back_populates="status_history")

    #: Null for the very first entry, which records the order being placed.
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)

    # SET NULL: if a staff account is ever removed, the audit entry survives
    # without its author rather than disappearing.
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: Snapshotted so the trail still reads sensibly if that account is gone.
    changed_by_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<OrderStatusHistory {self.from_status} -> {self.to_status}>"
