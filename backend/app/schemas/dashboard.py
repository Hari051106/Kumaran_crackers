"""Dashboard schemas for the admin desktop application.

Only metrics the system can actually compute appear here. Sales figures are
reported once there are orders to measure; until the first order is placed,
`sales_metrics_available` is False and the client says so rather than showing a
zero that reads like a quiet trading day.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.order import OrderSummary
from app.schemas.product import ProductListItem


class CatalogueStats(BaseModel):
    total_products: int
    active_products: int
    inactive_products: int
    total_categories: int
    active_categories: int


class InventoryStats(BaseModel):
    low_stock_count: int
    out_of_stock_count: int
    inventory_retail_value: Decimal = Field(
        description="Sum of stock_quantity x selling_price over active products."
    )


class CustomerStats(BaseModel):
    total_customers: int
    active_customers: int


class CategoryProductCount(BaseModel):
    """One bar of the category distribution chart."""

    category: str
    product_count: int


class SalesStats(BaseModel):
    """Trading figures. Cancelled orders are excluded from every total."""

    orders_today: int
    revenue_today: Decimal
    orders_this_week: int
    revenue_this_week: Decimal
    orders_this_month: int
    revenue_this_month: Decimal

    total_orders: int = Field(description="Orders ever placed, cancelled ones excluded.")
    lifetime_revenue: Decimal
    average_order_value: Decimal = Field(
        description="Lifetime revenue divided by those orders; zero when there are none."
    )


class OrderStatusCount(BaseModel):
    status: str
    label: str
    count: int


class BestSeller(BaseModel):
    product_name: str
    units_sold: int
    revenue: Decimal


class DashboardStats(BaseModel):
    """Everything the admin dashboard renders from real data."""

    catalogue: CatalogueStats
    inventory: InventoryStats
    customers: CustomerStats
    products_per_category: list[CategoryProductCount]
    recent_products: list[ProductListItem]

    # ---- Trading ------------------------------------------------------------
    sales: SalesStats
    orders_by_status: list[OrderStatusCount]
    best_sellers: list[BestSeller]
    recent_orders: list[OrderSummary]
    pending_orders: int = Field(description="Placed or confirmed, i.e. waiting to be acted on.")

    #: False until the first order is placed, so the client can distinguish
    #: "nothing has been sold yet" from "a quiet day".
    sales_metrics_available: bool = Field(
        description="True once at least one order exists.",
    )
