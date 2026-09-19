"""Dashboard aggregation for the admin desktop application."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.enums import RoleName
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.schemas.dashboard import (
    CatalogueStats,
    CategoryProductCount,
    CustomerStats,
    DashboardStats,
    InventoryStats,
)
from app.schemas.product import ProductListItem


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.products = ProductRepository(db)
        self.categories = CategoryRepository(db)
        self.users = UserRepository(db)

    def build(self) -> DashboardStats:
        total_products = self.products.count_all()
        active_products = self.products.count_all(is_active=True)

        return DashboardStats(
            catalogue=CatalogueStats(
                total_products=total_products,
                active_products=active_products,
                inactive_products=total_products - active_products,
                total_categories=self.categories.count_all(),
                active_categories=self.categories.count_all(active_only=True),
            ),
            inventory=InventoryStats(
                low_stock_count=self.products.count_low_stock(),
                out_of_stock_count=self.products.count_out_of_stock(),
                inventory_retail_value=self.products.inventory_value(),
            ),
            customers=CustomerStats(
                total_customers=self.users.count_by_role(RoleName.CUSTOMER),
                active_customers=self.users.count_by_role(RoleName.CUSTOMER, is_active=True),
            ),
            products_per_category=[
                CategoryProductCount(category=name, product_count=count)
                for name, count in self.products.count_by_category()
            ],
            recent_products=[
                ProductListItem.model_validate(product) for product in self.products.recent(limit=5)
            ],
            # Flipped to True in Milestone 6, once orders exist to measure.
            sales_metrics_available=False,
        )
