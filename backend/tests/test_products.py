"""Tests for `/api/v1/products` - catalogue, pricing, stock and admin CRUD."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from tests.conftest import make_category, make_product

PRODUCTS = "/api/v1/products"


def _payload(category_id: int, **overrides: object) -> dict:
    payload = {
        "name": "Colour Sparkler 30cm",
        "description": "A long-burning colour sparkler.",
        "category_id": category_id,
        "mrp": "250.00",
        "selling_price": "199.00",
        "stock_quantity": 100,
        "low_stock_threshold": 10,
    }
    payload.update(overrides)
    return payload


class TestPricing:
    """Money must stay exact and the discount must never drift from the prices."""

    def test_discount_is_derived_from_mrp_and_selling_price(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(
            db,
            category=category,
            name="Quarter Off",
            sku="Q-1",
            mrp="400.00",
            selling_price="300.00",
        )
        item = next(p for p in client.get(PRODUCTS).json()["items"] if p["sku"] == "Q-1")
        assert Decimal(item["discount_percentage"]) == Decimal("25.0")
        assert Decimal(item["discount_amount"]) == Decimal("100.00")

    def test_zero_discount_when_priced_at_mrp(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(
            db,
            category=category,
            name="Full Price",
            sku="FP-1",
            mrp="150.00",
            selling_price="150.00",
        )
        item = next(p for p in client.get(PRODUCTS).json()["items"] if p["sku"] == "FP-1")
        assert Decimal(item["discount_percentage"]) == Decimal("0.0")

    def test_money_is_serialised_exactly(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        """A float round-trip would turn 1999.99 into 1999.9899999... ."""
        make_product(
            db,
            category=category,
            name="Awkward Price",
            sku="AWK-1",
            mrp="1999.99",
            selling_price="1099.95",
        )
        item = next(p for p in client.get(PRODUCTS).json()["items"] if p["sku"] == "AWK-1")
        assert item["mrp"] == "1999.99"
        assert item["selling_price"] == "1099.95"

    def test_updating_discount_recomputes_it(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            f"{PRODUCTS}/id/{product.id}",
            json={"selling_price": "50.00"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert Decimal(response.json()["discount_percentage"]) == Decimal("50.0")

    def test_selling_price_above_mrp_is_rejected_on_create(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            PRODUCTS,
            json=_payload(category.id, mrp="100.00", selling_price="150.00"),
            headers=admin_headers,
        )
        assert response.status_code == 422

    def test_selling_price_above_stored_mrp_is_rejected_on_update(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        """Only one side changes, so the check must use the stored MRP."""
        response = client.patch(
            f"{PRODUCTS}/id/{product.id}",
            json={"selling_price": "9999.00"},
            headers=admin_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "business_rule_violation"

    def test_negative_price_is_rejected(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            PRODUCTS, json=_payload(category.id, selling_price="-1.00"), headers=admin_headers
        )
        assert response.status_code == 422


class TestStockStatus:
    def test_in_stock_when_above_threshold(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(
            db,
            category=category,
            name="Plenty",
            sku="ST-1",
            stock_quantity=50,
            low_stock_threshold=10,
        )
        item = next(p for p in client.get(PRODUCTS).json()["items"] if p["sku"] == "ST-1")
        assert item["stock_status"] == "IN_STOCK"
        assert item["in_stock"] is True

    def test_low_stock_at_the_threshold_boundary(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(
            db,
            category=category,
            name="Boundary",
            sku="ST-2",
            stock_quantity=10,
            low_stock_threshold=10,
        )
        item = next(p for p in client.get(PRODUCTS).json()["items"] if p["sku"] == "ST-2")
        assert item["stock_status"] == "LOW_STOCK"

    def test_out_of_stock_at_zero(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(db, category=category, name="Empty", sku="ST-3", stock_quantity=0)
        item = next(p for p in client.get(PRODUCTS).json()["items"] if p["sku"] == "ST-3")
        assert item["stock_status"] == "OUT_OF_STOCK"
        assert item["in_stock"] is False


class TestCatalogueVisibility:
    def test_catalogue_is_public(self, client: TestClient, product: Product) -> None:
        response = client.get(PRODUCTS)
        assert response.status_code == 200
        assert product.sku in {p["sku"] for p in response.json()["items"]}

    def test_inactive_products_are_hidden(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(db, category=category, name="Discontinued", sku="OFF-1", is_active=False)
        assert "OFF-1" not in {p["sku"] for p in client.get(PRODUCTS).json()["items"]}

    def test_products_in_an_inactive_category_are_hidden(
        self, client: TestClient, db: Session
    ) -> None:
        """An active product in a retired category must not leak into the shop."""
        retired = make_category(db, name="Retired Range", is_active=False)
        make_product(db, category=retired, name="Orphan", sku="ORP-1", is_active=True)

        assert "ORP-1" not in {p["sku"] for p in client.get(PRODUCTS).json()["items"]}

    def test_detail_of_a_product_in_an_inactive_category_is_404(
        self, client: TestClient, db: Session
    ) -> None:
        retired = make_category(db, name="Retired Range", is_active=False)
        orphan = make_product(db, category=retired, name="Orphan", sku="ORP-1")
        assert client.get(f"{PRODUCTS}/{orphan.slug}").status_code == 404

    def test_customer_cannot_reveal_inactive_via_query_parameter(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        make_product(db, category=category, name="Discontinued", sku="OFF-1", is_active=False)
        response = client.get(f"{PRODUCTS}?include_inactive=true", headers=customer_headers)
        assert "OFF-1" not in {p["sku"] for p in response.json()["items"]}

    def test_staff_may_see_inactive_products(
        self, client: TestClient, db: Session, category: Category, staff_headers: dict[str, str]
    ) -> None:
        make_product(db, category=category, name="Discontinued", sku="OFF-1", is_active=False)
        response = client.get(f"{PRODUCTS}?include_inactive=true", headers=staff_headers)
        assert "OFF-1" in {p["sku"] for p in response.json()["items"]}


class TestCatalogueSearchAndFilter:
    def test_search_matches_name(self, client: TestClient, db: Session, category: Category) -> None:
        make_product(db, category=category, name="Golden Fountain Deluxe", sku="GF-1")
        make_product(db, category=category, name="Red Rocket", sku="RR-1")
        skus = {p["sku"] for p in client.get(f"{PRODUCTS}?query=fountain").json()["items"]}
        assert skus == {"GF-1"}

    def test_search_matches_sku(self, client: TestClient, db: Session, category: Category) -> None:
        make_product(db, category=category, name="Anything", sku="UNIQUESKU9")
        skus = {p["sku"] for p in client.get(f"{PRODUCTS}?query=uniquesku9").json()["items"]}
        assert skus == {"UNIQUESKU9"}

    def test_filter_by_category_slug(self, client: TestClient, db: Session) -> None:
        rockets = make_category(db, name="Rockets Only")
        pots = make_category(db, name="Pots Only")
        make_product(db, category=rockets, name="Sky Rocket", sku="SR-1")
        make_product(db, category=pots, name="Clay Pot", sku="CP-1")

        skus = {p["sku"] for p in client.get(f"{PRODUCTS}?category={rockets.slug}").json()["items"]}
        assert skus == {"SR-1"}

    def test_filter_by_price_range(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(
            db, category=category, name="Cheap", sku="P-50", mrp="50.00", selling_price="50.00"
        )
        make_product(
            db, category=category, name="Mid", sku="P-500", mrp="500.00", selling_price="500.00"
        )
        make_product(
            db,
            category=category,
            name="Costly",
            sku="P-5000",
            mrp="5000.00",
            selling_price="5000.00",
        )

        skus = {
            p["sku"] for p in client.get(f"{PRODUCTS}?min_price=100&max_price=1000").json()["items"]
        }
        assert skus == {"P-500"}

    def test_inverted_price_range_is_rejected(self, client: TestClient) -> None:
        response = client.get(f"{PRODUCTS}?min_price=900&max_price=100")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "business_rule_violation"

    def test_filter_in_stock_only(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(db, category=category, name="Available", sku="AV-1", stock_quantity=5)
        make_product(db, category=category, name="Sold Out", sku="SO-1", stock_quantity=0)
        skus = {p["sku"] for p in client.get(f"{PRODUCTS}?in_stock=true").json()["items"]}
        assert "AV-1" in skus and "SO-1" not in skus

    def test_filter_featured_only(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(db, category=category, name="Hero", sku="HE-1", is_featured=True)
        make_product(db, category=category, name="Ordinary", sku="OR-1", is_featured=False)
        skus = {p["sku"] for p in client.get(f"{PRODUCTS}?featured=true").json()["items"]}
        assert skus == {"HE-1"}

    def test_filter_discounted_only(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(
            db, category=category, name="Reduced", sku="DI-1", mrp="100.00", selling_price="75.00"
        )
        make_product(
            db, category=category, name="Full", sku="FU-1", mrp="100.00", selling_price="100.00"
        )
        skus = {p["sku"] for p in client.get(f"{PRODUCTS}?discounted=true").json()["items"]}
        assert skus == {"DI-1"}


class TestCatalogueSorting:
    def _seeded(self, db: Session, category: Category) -> None:
        make_product(
            db,
            category=category,
            name="B Mid",
            sku="S-2",
            mrp="200.00",
            selling_price="200.00",
            sold_quantity=5,
        )
        make_product(
            db,
            category=category,
            name="A Cheap",
            sku="S-1",
            mrp="100.00",
            selling_price="100.00",
            sold_quantity=99,
        )
        make_product(
            db,
            category=category,
            name="C Dear",
            sku="S-3",
            mrp="600.00",
            selling_price="300.00",
            sold_quantity=0,
        )

    def test_sort_price_ascending(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        self._seeded(db, category)
        prices = [
            Decimal(p["selling_price"])
            for p in client.get(f"{PRODUCTS}?sort=price_asc").json()["items"]
        ]
        assert prices == sorted(prices)

    def test_sort_price_descending(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        self._seeded(db, category)
        prices = [
            Decimal(p["selling_price"])
            for p in client.get(f"{PRODUCTS}?sort=price_desc").json()["items"]
        ]
        assert prices == sorted(prices, reverse=True)

    def test_sort_by_name(self, client: TestClient, db: Session, category: Category) -> None:
        self._seeded(db, category)
        names = [p["name"] for p in client.get(f"{PRODUCTS}?sort=name_asc").json()["items"]]
        assert names == sorted(names)

    def test_sort_by_discount_puts_the_biggest_saving_first(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        self._seeded(db, category)
        items = client.get(f"{PRODUCTS}?sort=discount").json()["items"]
        assert items[0]["sku"] == "S-3"  # 50% off; the others are at MRP

    def test_sort_by_popularity_uses_units_sold(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        self._seeded(db, category)
        items = client.get(f"{PRODUCTS}?sort=popularity").json()["items"]
        assert items[0]["sku"] == "S-1"

    def test_unknown_sort_is_rejected(self, client: TestClient) -> None:
        assert client.get(f"{PRODUCTS}?sort=nonsense").status_code == 422


class TestPagination:
    def test_pagination_metadata(self, client: TestClient, db: Session, category: Category) -> None:
        for index in range(7):
            make_product(db, category=category, name=f"Bulk {index}", sku=f"BK-{index}")

        body = client.get(f"{PRODUCTS}?page=1&page_size=3").json()
        assert len(body["items"]) == 3
        assert body["meta"]["total"] >= 7
        assert body["meta"]["has_next"] is True
        assert body["meta"]["has_previous"] is False

    def test_second_page_differs_from_first(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        for index in range(7):
            make_product(db, category=category, name=f"Bulk {index}", sku=f"BK-{index}")

        first = {p["sku"] for p in client.get(f"{PRODUCTS}?page=1&page_size=3").json()["items"]}
        second = {p["sku"] for p in client.get(f"{PRODUCTS}?page=2&page_size=3").json()["items"]}
        assert first.isdisjoint(second)

    def test_page_size_is_capped(self, client: TestClient) -> None:
        assert client.get(f"{PRODUCTS}?page_size=5000").status_code == 422


class TestProductDetail:
    def test_detail_by_slug(self, client: TestClient, product: Product) -> None:
        response = client.get(f"{PRODUCTS}/{product.slug}")
        assert response.status_code == 200
        body = response.json()
        assert body["sku"] == product.sku
        assert "description" in body
        assert "stock_quantity" in body

    def test_detail_hides_operational_fields_from_customers(
        self, client: TestClient, product: Product
    ) -> None:
        """Threshold and units-sold are internal; the public view omits them."""
        body = client.get(f"{PRODUCTS}/{product.slug}").json()
        assert "low_stock_threshold" not in body
        assert "sold_quantity" not in body

    def test_unknown_slug_is_404(self, client: TestClient) -> None:
        assert client.get(f"{PRODUCTS}/no-such-product").status_code == 404

    def test_listing_route_is_not_shadowed_by_the_slug_route(
        self, client: TestClient, staff_headers: dict[str, str]
    ) -> None:
        """`/products/low-stock` must not be parsed as a product slug."""
        assert client.get(f"{PRODUCTS}/low-stock", headers=staff_headers).status_code == 200
