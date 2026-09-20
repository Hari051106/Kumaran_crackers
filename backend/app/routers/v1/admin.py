"""Back-office endpoints - `/api/v1/admin`.

Everything here requires STAFF or ADMIN; nothing is public.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import DbSession, StaffUser, require_staff
from app.enums import OrderStatus
from app.routers.v1._order_view import to_admin_detail, to_admin_summary
from app.schemas.common import Page
from app.schemas.dashboard import DashboardStats
from app.schemas.order import (
    AdminOrderDetail,
    AdminOrderSummary,
    UpdateOrderStatusRequest,
)
from app.schemas.user import CustomerSummary
from app.services.customer_service import CustomerService
from app.services.dashboard_service import DashboardService
from app.services.order_service import OrderService

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_staff)])


@router.get("/dashboard", response_model=DashboardStats, summary="Dashboard statistics")
def dashboard(db: DbSession) -> DashboardStats:
    """Live counts for the admin desktop home screen.

    Sales figures appear here only once there are orders to measure;
    `sales_metrics_available` says whether they are real yet.
    """
    return DashboardService(db).build()


# ---- Orders -----------------------------------------------------------------
@router.get("/orders", response_model=Page[AdminOrderSummary], summary="All orders")
def list_orders(
    db: DbSession,
    query: str | None = Query(
        default=None, description="Match order number, recipient name, phone or email."
    ),
    status: OrderStatus | None = Query(default=None, description="Filter by status."),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[AdminOrderSummary]:
    rows, total = OrderService(db).search(
        query=query, status=status, page=page, page_size=page_size
    )
    return Page[AdminOrderSummary].build(
        items=[to_admin_summary(order) for order in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/orders/{order_number}",
    response_model=AdminOrderDetail,
    summary="One order in full",
)
def get_order(order_number: str, db: DbSession) -> AdminOrderDetail:
    """Includes the customer, the audit trail, and which moves remain open."""
    return to_admin_detail(OrderService(db).get_for_staff(order_number))


@router.post(
    "/orders/{order_number}/status",
    response_model=AdminOrderDetail,
    summary="Move an order on",
)
def update_order_status(
    order_number: str,
    payload: UpdateOrderStatusRequest,
    current_user: StaffUser,
    db: DbSession,
) -> AdminOrderDetail:
    """Advance an order through the workflow.

    Only the moves the state machine permits are accepted, an order never goes
    backwards, and every change is written to the audit trail with who made it.
    Cancelling returns the stock to the shelf.
    """
    order = OrderService(db).update_status(
        order_number, payload.status, actor=current_user, note=payload.note
    )
    return to_admin_detail(order)


# ---- Customers --------------------------------------------------------------
@router.get(
    "/customers",
    response_model=Page[CustomerSummary],
    summary="Customers and what they have bought",
)
def list_customers(
    db: DbSession,
    query: str | None = Query(default=None, description="Match name, email or phone."),
    is_active: bool | None = Query(default=None, description="Filter by account status."),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[CustomerSummary]:
    """Customer accounts with their real order count and spend.

    Staff-visible rather than admin-only: whoever is working an order needs to
    be able to look the customer up. It is read-only, and exposes nothing that
    the order screens do not already show. Changing an account still requires
    ADMIN, through `/users`.
    """
    rows, total = CustomerService(db).search(
        query=query, is_active=is_active, page=page, page_size=page_size
    )
    return Page[CustomerSummary].build(items=rows, total=total, page=page, page_size=page_size)
