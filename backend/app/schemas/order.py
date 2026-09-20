"""Order API schemas.

Money is serialised as an exact decimal string, and every figure here is a
snapshot taken when the order was placed — not a live lookup.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.enums import ORDER_TIMELINE, OrderStatus


# ---- Requests ---------------------------------------------------------------
class PlaceOrderRequest(BaseModel):
    """The client chooses an address. Everything else comes from the basket."""

    address_id: int = Field(gt=0)


class CancelOrderRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class UpdateOrderStatusRequest(BaseModel):
    status: OrderStatus
    note: str | None = Field(default=None, max_length=300)


# ---- Responses --------------------------------------------------------------
class OrderItemRead(BaseModel):
    """A line as it was at purchase."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    product_sku: str
    product_image_url: str | None = None
    quantity: int
    unit_mrp: Decimal
    unit_price: Decimal
    line_total: Decimal
    line_discount: Decimal


class OrderStatusEvent(BaseModel):
    """One entry from the audit trail."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: str | None = None
    to_status: str
    changed_by_name: str | None = None
    note: str | None = None
    created_at: datetime


class DeliveryAddressSnapshot(BaseModel):
    full_name: str
    phone: str
    house_number: str
    street: str
    area: str
    city: str
    state: str
    pincode: str
    instructions: str | None = None
    single_line: str


class OrderTotals(BaseModel):
    subtotal: Decimal
    discount: Decimal
    items_total: Decimal
    delivery_charge: Decimal
    total: Decimal
    currency: str


class TimelineStep(BaseModel):
    """One stage of the customer's tracking view."""

    status: OrderStatus
    label: str
    reached: bool
    is_current: bool
    reached_at: datetime | None = None


class OrderSummary(BaseModel):
    """List projection: enough for a history row."""

    model_config = ConfigDict(from_attributes=True)

    order_number: str
    status: OrderStatus
    total: Decimal
    currency: str
    item_count: int
    placed_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_label(self) -> str:
        return self.status.label


class OrderDetail(OrderSummary):
    """Everything about one order."""

    items: list[OrderItemRead]
    totals: OrderTotals
    delivery_address: DeliveryAddressSnapshot
    timeline: list[TimelineStep]
    status_history: list[OrderStatusEvent]

    is_cancellable_by_customer: bool
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None


class AdminOrderSummary(OrderSummary):
    """Adds who placed it, for the back-office list."""

    customer_name: str
    customer_email: str
    customer_phone: str | None = None


class AdminOrderDetail(OrderDetail):
    customer_name: str
    customer_email: str
    customer_phone: str | None = None
    #: The moves this order may still make, so the client offers only those.
    allowed_transitions: list[OrderStatus] = Field(default_factory=list)


def build_timeline(order_status: OrderStatus, history: list) -> list[TimelineStep]:
    """Work out which stages an order has reached.

    A cancelled order shows no progress on the happy path; the cancellation is
    shown separately from the timeline.
    """
    reached_at: dict[str, datetime] = {}
    for event in history:
        reached_at.setdefault(event.to_status, event.created_at)

    if order_status is OrderStatus.CANCELLED:
        return [
            TimelineStep(
                status=step,
                label=step.label,
                reached=step.value in reached_at,
                is_current=False,
                reached_at=reached_at.get(step.value),
            )
            for step in ORDER_TIMELINE
        ]

    position = ORDER_TIMELINE.index(order_status)
    return [
        TimelineStep(
            status=step,
            label=step.label,
            reached=index <= position,
            is_current=index == position,
            reached_at=reached_at.get(step.value),
        )
        for index, step in enumerate(ORDER_TIMELINE)
    ]
