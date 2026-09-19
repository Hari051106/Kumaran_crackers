"""Tests for `/api/v1/admin/dashboard`."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import RoleName
from app.models.category import Category
from tests.conftest import make_category, make_product, make_user

DASHBOARD = "/api/v1/admin/dashboard"


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
    def test_sales_metrics_are_declared_unavailable(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        """Until orders exist there are no sales; the flag says so explicitly."""
        assert (
            client.get(DASHBOARD, headers=admin_headers).json()["sales_metrics_available"] is False
        )

    def test_no_fabricated_sales_fields_are_returned(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        body = client.get(DASHBOARD, headers=admin_headers).json()
        for invented in ("today_sales", "revenue", "pending_orders", "total_orders"):
            assert invented not in body
