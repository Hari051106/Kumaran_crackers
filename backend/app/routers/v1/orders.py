"""Customer order endpoints - `/api/v1/orders`."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.dependencies.auth import CurrentUser, DbSession
from app.routers.v1._order_view import to_detail, to_summary
from app.schemas.common import Page
from app.schemas.order import (
    CancelOrderRequest,
    OrderDetail,
    OrderSummary,
    PlaceOrderRequest,
)
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "",
    response_model=OrderDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Place my order",
)
def place_order(
    payload: PlaceOrderRequest, current_user: CurrentUser, db: DbSession
) -> OrderDetail:
    """Turn the basket into an order.

    Every checkout check is re-run first, because the quote the customer saw
    may be seconds old and stock can move in that time. The order, its lines,
    the stock reservation and emptying the basket all happen in one
    transaction: either the whole order exists, or none of it does.

    The prices written to the order are computed here, never taken from the
    request.
    """
    return to_detail(OrderService(db).place(current_user, payload.address_id))


@router.get("", response_model=Page[OrderSummary], summary="My orders")
def my_orders(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> Page[OrderSummary]:
    rows, total = OrderService(db).history(current_user, page=page, page_size=page_size)
    return Page[OrderSummary].build(
        items=[to_summary(order) for order in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{order_number}", response_model=OrderDetail, summary="One of my orders")
def my_order(order_number: str, current_user: CurrentUser, db: DbSession) -> OrderDetail:
    """Full detail and the tracking timeline. Scoped to the owner."""
    return to_detail(OrderService(db).get_for_user(current_user, order_number))


@router.post(
    "/{order_number}/cancel",
    response_model=OrderDetail,
    summary="Cancel one of my orders",
)
def cancel_my_order(
    order_number: str,
    payload: CancelOrderRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> OrderDetail:
    """Withdraw an order before it is packed. Stock goes back on the shelf."""
    order = OrderService(db).cancel_as_customer(current_user, order_number, payload.reason)
    return to_detail(order)
