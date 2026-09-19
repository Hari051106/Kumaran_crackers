"""Dashboard schemas for the admin desktop application.

Only metrics the system can actually compute today appear here. Sales, revenue
and order counts arrive with the order system in Milestone 6; inventing
placeholder figures now would put fiction on a screen a shopkeeper makes
decisions from.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

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


class DashboardStats(BaseModel):
    """Everything the admin dashboard renders from real data."""

    catalogue: CatalogueStats
    inventory: InventoryStats
    customers: CustomerStats
    products_per_category: list[CategoryProductCount]
    recent_products: list[ProductListItem]

    # Named explicitly so the desktop client can show an honest "arriving in
    # Milestone 6" state rather than a zero that looks like real trading data.
    sales_metrics_available: bool = Field(
        default=False,
        description="False until the order system lands; no sales figures exist yet.",
    )
