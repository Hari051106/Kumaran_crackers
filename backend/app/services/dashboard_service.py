"""Dashboard aggregation for the admin desktop application."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.enums import OrderStatus, RoleName
from app.repositories.category import CategoryRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.routers.v1._order_view import to_summary
from app.schemas.dashboard import (
    BestSeller,
    CatalogueStats,
    CategoryProductCount,
    CustomerStats,
    DashboardStats,
    InventoryStats,
    OrderStatusCount,
    SalesStats,
)
from app.schemas.product import ProductListItem

ZERO = Decimal("0.00")

#: Statuses that still need somebody to do something.
PENDING_STATUSES = (OrderStatus.PLACED, OrderStatus.CONFIRMED)


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.products = ProductRepository(db)
        self.categories = CategoryRepository(db)
        self.users = UserRepository(db)
        self.orders = OrderRepository(db)

    def build(self) -> DashboardStats:
        total_products = self.products.count_all()
        active_products = self.products.count_all(is_active=True)

        by_status = self.orders.count_by_status()
        total_orders = sum(by_status.values())

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
            sales=self._sales(),
            orders_by_status=self._orders_by_status(by_status),
            best_sellers=[
                BestSeller(product_name=name, units_sold=units, revenue=revenue)
                for name, units, revenue in self.orders.best_selling(limit=5)
            ],
            recent_orders=[to_summary(order) for order in self.orders.recent(limit=5)],
            pending_orders=sum(by_status.get(status.value, 0) for status in PENDING_STATUSES),
            # Only true once something has actually been ordered.
            sales_metrics_available=total_orders > 0,
        )

    def _sales(self) -> SalesStats:
        now = datetime.now(UTC)
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        today_count, today_revenue = self.orders.revenue_since(start_of_today)
        week_count, week_revenue = self.orders.revenue_since(now - timedelta(days=7))
        month_count, month_revenue = self.orders.revenue_since(now - timedelta(days=30))
        # The epoch stands in for "all time".
        all_count, all_revenue = self.orders.revenue_since(datetime(1970, 1, 1, tzinfo=UTC))

        lifetime = Decimal(str(all_revenue or 0))
        # Guarded: dividing by zero orders would be an error, not a zero.
        average = (lifetime / Decimal(all_count)).quantize(Decimal("0.01")) if all_count else ZERO

        return SalesStats(
            orders_today=today_count,
            revenue_today=Decimal(str(today_revenue or 0)),
            orders_this_week=week_count,
            revenue_this_week=Decimal(str(week_revenue or 0)),
            orders_this_month=month_count,
            revenue_this_month=Decimal(str(month_revenue or 0)),
            total_orders=all_count,
            lifetime_revenue=lifetime,
            average_order_value=average,
        )

    @staticmethod
    def _orders_by_status(counts: dict[str, int]) -> list[OrderStatusCount]:
        # Every status is listed, including those at zero, so the chart keeps a
        # stable shape rather than reordering as orders move.
        return [
            OrderStatusCount(
                status=status.value,
                label=status.label,
                count=counts.get(status.value, 0),
            )
            for status in OrderStatus
        ]
