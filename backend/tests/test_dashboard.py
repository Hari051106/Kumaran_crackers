"""Tests for `/api/v1/admin/dashboard`."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import OrderStatus, RoleName
from app.models.category import Category
from tests.conftest import (
    advance_to,
    make_category,
    make_product,
    make_user,
    order_now,
)

DASHBOARD = "/api/v1/admin/dashboard"


def order_total(client: TestClient, headers: dict[str, str], product, quantity: int = 1) -> str:
    """Place an order and return what it was actually charged."""
    number = order_now(client, headers, product, quantity=quantity)
    return client.get(f"/api/v1/orders/{number}", headers=headers).json()["total"]


class TestDashboardAuthorization:
    def test_anonymous_is_rejected(self, client: TestClient) -> None:
        assert client.get(DASHBOARD).status_code == 401

    def test_customer_is_rejected(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        assert client.get(DASHBOARD, headers=customer_headers).status_code == 403

    def test_staff_may_read_it(self, client: TestClient, staff_headers: dict[str, str]) -> None:
        assert client.get(DASHBOARD, headers=staff_headers).status_code == 200

    def test_admin_may_read_it(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        assert client.get(DASHBOARD, headers=admin_headers).status_code == 200


class TestCatalogueStats:
    def test_counts_active_and_inactive_products(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        make_product(db, category=category, name="Live One", sku="A-1", is_active=True)
        make_product(db, category=category, name="Live Two", sku="A-2", is_active=True)
        make_product(db, category=category, name="Hidden", sku="A-3", is_active=False)

        stats = client.get(DASHBOARD, headers=admin_headers).json()["catalogue"]
        assert stats["total_products"] == 3
        assert stats["active_products"] == 2
        assert stats["inactive_products"] == 1

    def test_counts_categories(
        self, client: TestClient, db: Session, admin_headers: dict[str, str]
    ) -> None:
        make_category(db, name="Extra Active", is_active=True)
        make_category(db, name="Extra Retired", is_active=False)

        stats = client.get(DASHBOARD, headers=admin_headers).json()["catalogue"]
        # Eight categories are seeded by the baseline migration.
        assert stats["total_categories"] == stats["active_categories"] + 1


class TestInventoryStats:
    def test_low_and_out_of_stock_counts(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        make_product(
            db,
            category=category,
            name="Running Low",
            sku="I-1",
            stock_quantity=2,
            low_stock_threshold=10,
        )
        make_product(db, category=category, name="Gone", sku="I-2", stock_quantity=0)
        make_product(
            db,
            category=category,
            name="Plenty",
            sku="I-3",
            stock_quantity=500,
            low_stock_threshold=10,
        )

        stats = client.get(DASHBOARD, headers=admin_headers).json()["inventory"]
        assert stats["low_stock_count"] == 1
        assert stats["out_of_stock_count"] == 1

    def test_inventory_value_is_exact(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        """Stock value must not drift; it is money."""
        make_product(
            db,
            category=category,
            name="Priced",
            sku="V-1",
            mrp="19.99",
            selling_price="19.99",
            stock_quantity=3,
        )
        make_product(
            db,
            category=category,
            name="Other",
            sku="V-2",
            mrp="100.50",
            selling_price="100.50",
            stock_quantity=2,
        )

        value = client.get(DASHBOARD, headers=admin_headers).json()["inventory"][
            "inventory_retail_value"
        ]
        # 3 x 19.99 + 2 x 100.50 = 59.97 + 201.00
        assert Decimal(value) == Decimal("260.97")

    def test_inactive_products_are_excluded_from_value(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        make_product(
            db,
            category=category,
            name="Shelved",
            sku="V-3",
            mrp="500.00",
            selling_price="500.00",
            stock_quantity=10,
            is_active=False,
        )
        value = client.get(DASHBOARD, headers=admin_headers).json()["inventory"][
            "inventory_retail_value"
        ]
        assert Decimal(value) == Decimal("0.00")


class TestCustomerStats:
    def test_counts_only_customers(
        self, client: TestClient, db: Session, admin_headers: dict[str, str]
    ) -> None:
        make_user(db, email="c1@example.com", role=RoleName.CUSTOMER)
        make_user(db, email="c2@example.com", role=RoleName.CUSTOMER, is_active=False)
        make_user(db, email="s1@example.com", role=RoleName.STAFF)

        stats = client.get(DASHBOARD, headers=admin_headers).json()["customers"]
        assert stats["total_customers"] == 2
        assert stats["active_customers"] == 1


class TestChartsAndRecent:
    def test_products_per_category(
        self, client: TestClient, db: Session, admin_headers: dict[str, str]
    ) -> None:
        busy = make_category(db, name="Busy Line")
        quiet = make_category(db, name="Quiet Line")
        for index in range(3):
            make_product(db, category=busy, name=f"Busy {index}", sku=f"B-{index}")
        make_product(db, category=quiet, name="Quiet One", sku="Q-1")

        rows = client.get(DASHBOARD, headers=admin_headers).json()["products_per_category"]
        counts = {row["category"]: row["product_count"] for row in rows}
        assert counts["Busy Line"] == 3
        assert counts["Quiet Line"] == 1
        # Ordered by count, biggest first.
        assert rows[0]["product_count"] >= rows[-1]["product_count"]

    def test_recent_products_are_newest_first_and_capped(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        for index in range(8):
            make_product(db, category=category, name=f"Item {index}", sku=f"R-{index}")

        recent = client.get(DASHBOARD, headers=admin_headers).json()["recent_products"]
        assert len(recent) == 5
        assert recent[0]["sku"] == "R-7"


class TestHonestyAboutMissingData:
    def test_sales_are_flagged_unavailable_before_any_order_exists(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        """Distinguishes "nothing sold yet" from "a quiet trading day"."""
        body = client.get(DASHBOARD, headers=admin_headers).json()
        assert body["sales_metrics_available"] is False

    def test_sales_figures_are_all_zero_before_any_order_exists(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        """Real fields, honestly zero - not invented numbers."""
        sales = client.get(DASHBOARD, headers=admin_headers).json()["sales"]

        assert sales["total_orders"] == 0
        assert Decimal(sales["lifetime_revenue"]) == Decimal("0.00")
        # Dividing by zero orders would be an error, not a number.
        assert Decimal(sales["average_order_value"]) == Decimal("0.00")

    def test_every_status_appears_even_at_zero(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        """A stable chart shape: rows do not appear and vanish as orders move."""
        rows = client.get(DASHBOARD, headers=admin_headers).json()["orders_by_status"]
        statuses = {row["status"] for row in rows}
        assert statuses == {status.value for status in OrderStatus}
        assert all(row["count"] == 0 for row in rows)


class TestSalesFigures:
    """Once orders exist the figures are real, and they add up."""

    def test_sales_become_available_after_the_first_order(
        self,
        client: TestClient,
        product,
        customer_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        order_now(client, customer_headers, product, quantity=1)

        body = client.get(DASHBOARD, headers=admin_headers).json()

        assert body["sales_metrics_available"] is True
        assert body["sales"]["total_orders"] == 1

    def test_revenue_is_the_sum_of_the_orders(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        first = make_product(
            db, category=category, name="Rev A", sku="RVA", mrp="300.00", selling_price="250.00"
        )
        second = make_product(
            db, category=category, name="Rev B", sku="RVB", mrp="150.00", selling_price="125.50"
        )
        totals = [
            Decimal(order_total(client, customer_headers, first, quantity=2)),
            Decimal(order_total(client, customer_headers, second, quantity=1)),
        ]

        sales = client.get(DASHBOARD, headers=admin_headers).json()["sales"]

        assert sales["total_orders"] == 2
        assert Decimal(sales["lifetime_revenue"]) == sum(totals)
        assert Decimal(sales["revenue_today"]) == sum(totals)

    def test_the_average_order_value_is_revenue_over_orders(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        for index in range(2):
            item = make_product(db, category=category, name=f"Avg {index}", sku=f"AV{index}")
            order_now(client, customer_headers, item, quantity=1)

        sales = client.get(DASHBOARD, headers=admin_headers).json()["sales"]

        expected = Decimal(sales["lifetime_revenue"]) / Decimal(sales["total_orders"])
        assert Decimal(sales["average_order_value"]) == expected.quantize(Decimal("0.01"))

    def test_cancelled_orders_are_not_counted_as_revenue(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        """A withdrawn order is not a sale, however it was withdrawn."""
        kept = make_product(db, category=category, name="Kept", sku="KP-1")
        dropped = make_product(db, category=category, name="Dropped", sku="DR-1")
        kept_number = order_now(client, customer_headers, kept, quantity=1)
        dropped_number = order_now(client, customer_headers, dropped, quantity=1)
        client.post(f"/api/v1/orders/{dropped_number}/cancel", json={}, headers=customer_headers)

        sales = client.get(DASHBOARD, headers=admin_headers).json()["sales"]

        kept_total = client.get(f"/api/v1/orders/{kept_number}", headers=customer_headers).json()[
            "total"
        ]
        assert sales["total_orders"] == 1
        assert Decimal(sales["lifetime_revenue"]) == Decimal(kept_total)

    def test_a_cancelled_order_still_appears_in_the_status_chart(
        self,
        client: TestClient,
        product,
        customer_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        """Excluded from revenue, but not hidden from the operator."""
        number = order_now(client, customer_headers, product, quantity=1)
        client.post(f"/api/v1/orders/{number}/cancel", json={}, headers=customer_headers)

        rows = {
            row["status"]: row["count"]
            for row in client.get(DASHBOARD, headers=admin_headers).json()["orders_by_status"]
        }

        assert rows["CANCELLED"] == 1
        assert rows["PLACED"] == 0


class TestOperationalCounts:
    def test_orders_by_status_follows_the_workflow(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        first = make_product(db, category=category, name="Flow A", sku="FLA")
        second = make_product(db, category=category, name="Flow B", sku="FLB")
        order_now(client, customer_headers, first, quantity=1)
        moved = order_now(client, customer_headers, second, quantity=1)
        advance_to(client, staff_headers, moved, OrderStatus.PACKING)

        rows = {
            row["status"]: row["count"]
            for row in client.get(DASHBOARD, headers=admin_headers).json()["orders_by_status"]
        }

        assert rows["PLACED"] == 1
        assert rows["PACKING"] == 1
        assert rows["CONFIRMED"] == 0

    def test_pending_orders_counts_what_still_needs_doing(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        waiting = make_product(db, category=category, name="Waiting", sku="WT-1")
        packed = make_product(db, category=category, name="Packed", sku="PK-1")
        order_now(client, customer_headers, waiting, quantity=1)
        busy = order_now(client, customer_headers, packed, quantity=1)

        before = client.get(DASHBOARD, headers=admin_headers).json()["pending_orders"]
        assert before == 2

        # Once it is being packed it is no longer waiting on anybody.
        advance_to(client, staff_headers, busy, OrderStatus.PACKING)

        after = client.get(DASHBOARD, headers=admin_headers).json()["pending_orders"]
        assert after == 1

    def test_best_sellers_rank_by_units_sold(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        popular = make_product(db, category=category, name="Popular", sku="PO-1")
        quiet = make_product(db, category=category, name="Quiet", sku="QU-1")
        order_now(client, customer_headers, popular, quantity=7)
        order_now(client, customer_headers, quiet, quantity=2)

        best = client.get(DASHBOARD, headers=admin_headers).json()["best_sellers"]

        assert [row["product_name"] for row in best] == ["Popular", "Quiet"]
        assert best[0]["units_sold"] == 7

    def test_best_sellers_ignore_cancelled_orders(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Ghost", sku="GH-1")
        number = order_now(client, customer_headers, item, quantity=9)
        client.post(f"/api/v1/orders/{number}/cancel", json={}, headers=customer_headers)

        best = client.get(DASHBOARD, headers=admin_headers).json()["best_sellers"]

        assert best == []

    def test_recent_orders_are_newest_first_and_capped(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        numbers = []
        for index in range(6):
            item = make_product(db, category=category, name=f"Recent {index}", sku=f"RC{index}")
            numbers.append(order_now(client, customer_headers, item, quantity=1))

        recent = client.get(DASHBOARD, headers=admin_headers).json()["recent_orders"]

        assert len(recent) == 5
        assert recent[0]["order_number"] == numbers[-1]

    def test_a_cancelled_order_is_not_shown_as_pending(
        self,
        client: TestClient,
        product,
        customer_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product, quantity=1)
        client.post(f"/api/v1/orders/{number}/cancel", json={}, headers=customer_headers)

        assert client.get(DASHBOARD, headers=admin_headers).json()["pending_orders"] == 0
