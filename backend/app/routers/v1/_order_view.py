"""Maps order domain objects onto their API representation.

Shared by the customer and admin routers so both render an order identically.
"""

from __future__ import annotations

from app.enums import ALLOWED_STATUS_TRANSITIONS, OrderStatus
from app.models.order import Order
from app.schemas.order import (
    AdminOrderDetail,
    AdminOrderSummary,
    DeliveryAddressSnapshot,
    OrderDetail,
    OrderItemRead,
    OrderStatusEvent,
    OrderSummary,
    OrderTotals,
    build_timeline,
)


def _address(order: Order) -> DeliveryAddressSnapshot:
    return DeliveryAddressSnapshot(
        full_name=order.delivery_full_name,
        phone=order.delivery_phone,
        house_number=order.delivery_house_number,
        street=order.delivery_street,
        area=order.delivery_area,
        city=order.delivery_city,
        state=order.delivery_state,
        pincode=order.delivery_pincode,
        instructions=order.delivery_instructions,
        single_line=order.delivery_address_line,
    )


def _totals(order: Order) -> OrderTotals:
    return OrderTotals(
        subtotal=order.subtotal,
        discount=order.discount,
        items_total=order.items_total,
        delivery_charge=order.delivery_charge,
        total=order.total,
        currency=order.currency,
    )


def _detail_fields(order: Order) -> dict:
    return {
        "order_number": order.order_number,
        "status": order.status_enum,
        "total": order.total,
        "currency": order.currency,
        "item_count": order.item_count,
        "placed_at": order.placed_at,
        "items": [OrderItemRead.model_validate(item) for item in order.items],
        "totals": _totals(order),
        "delivery_address": _address(order),
        "timeline": build_timeline(order.status_enum, order.status_history),
        "status_history": [
            OrderStatusEvent.model_validate(event) for event in order.status_history
        ],
        "is_cancellable_by_customer": order.is_cancellable_by_customer,
        "delivered_at": order.delivered_at,
        "cancelled_at": order.cancelled_at,
        "cancellation_reason": order.cancellation_reason,
    }


def to_summary(order: Order) -> OrderSummary:
    return OrderSummary(
        order_number=order.order_number,
        status=order.status_enum,
        total=order.total,
        currency=order.currency,
        item_count=order.item_count,
        placed_at=order.placed_at,
    )


def to_detail(order: Order) -> OrderDetail:
    return OrderDetail(**_detail_fields(order))


def to_admin_summary(order: Order) -> AdminOrderSummary:
    return AdminOrderSummary(
        order_number=order.order_number,
        status=order.status_enum,
        total=order.total,
        currency=order.currency,
        item_count=order.item_count,
        placed_at=order.placed_at,
        customer_name=order.user.full_name,
        customer_email=order.user.email,
        customer_phone=order.user.phone,
    )


def to_admin_detail(order: Order) -> AdminOrderDetail:
    current: OrderStatus = order.status_enum
    return AdminOrderDetail(
        **_detail_fields(order),
        customer_name=order.user.full_name,
        customer_email=order.user.email,
        customer_phone=order.user.phone,
        # Telling the client what is possible keeps its buttons honest; the
        # server still re-checks every move.
        allowed_transitions=sorted(ALLOWED_STATUS_TRANSITIONS[current], key=lambda s: s.value),
    )
