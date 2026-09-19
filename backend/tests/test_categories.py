"""Tests for `/api/v1/categories`."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.category import Category
from tests.conftest import make_category, make_product

CATEGORIES = "/api/v1/categories"


class TestPublicCategoryReads:
    def test_listing_is_public(self, client: TestClient, category: Category) -> None:
        """The mobile home screen loads categories before sign-in."""
        response = client.get(CATEGORIES)
        assert response.status_code == 200
        names = [item["name"] for item in response.json()]
        assert category.name in names

    def test_seeded_categories_are_present(self, client: TestClient) -> None:
        """The baseline catalogue ships with the shop's categories."""
        names = {item["name"] for item in client.get(CATEGORIES).json()}
        assert {"Sparklers", "Rockets", "Flower Pots", "Gift Packs"} <= names

    def test_listing_is_ordered_by_display_order(self, client: TestClient, db: Session) -> None:
        make_category(db, name="Zeta Last", display_order=99)
        make_category(db, name="Alpha First", display_order=0)
        orders = [item["display_order"] for item in client.get(CATEGORIES).json()]
        assert orders == sorted(orders)

    def test_inactive_categories_are_hidden(self, client: TestClient, db: Session) -> None:
        make_category(db, name="Retired Line", is_active=False)
        names = {item["name"] for item in client.get(CATEGORIES).json()}
        assert "Retired Line" not in names

    def test_customer_cannot_reveal_inactive_via_query_parameter(
        self, client: TestClient, db: Session, customer_headers: dict[str, str]
    ) -> None:
        """include_inactive must not be a back door for non-staff callers."""
        make_category(db, name="Retired Line", is_active=False)
        response = client.get(f"{CATEGORIES}?include_inactive=true", headers=customer_headers)
        assert response.status_code == 200
        assert "Retired Line" not in {item["name"] for item in response.json()}

    def test_anonymous_cannot_reveal_inactive_via_query_parameter(
        self, client: TestClient, db: Session
    ) -> None:
        make_category(db, name="Retired Line", is_active=False)
        response = client.get(f"{CATEGORIES}?include_inactive=true")
        assert "Retired Line" not in {item["name"] for item in response.json()}

    def test_staff_may_see_inactive_categories(
        self, client: TestClient, db: Session, staff_headers: dict[str, str]
    ) -> None:
        make_category(db, name="Retired Line", is_active=False)
        response = client.get(f"{CATEGORIES}?include_inactive=true", headers=staff_headers)
        assert "Retired Line" in {item["name"] for item in response.json()}

    def test_product_counts_are_returned(
        self, client: TestClient, db: Session, category: Category
    ) -> None:
        make_product(db, category=category, name="Counted One", sku="CNT-1")
        make_product(db, category=category, name="Counted Two", sku="CNT-2")
        body = client.get(CATEGORIES).json()
        entry = next(item for item in body if item["id"] == category.id)
        assert entry["product_count"] == 2

    def test_get_by_slug(self, client: TestClient, category: Category) -> None:
        response = client.get(f"{CATEGORIES}/{category.slug}")
        assert response.status_code == 200
        assert response.json()["name"] == category.name

    def test_unknown_slug_returns_404(self, client: TestClient) -> None:
        assert client.get(f"{CATEGORIES}/no-such-category").status_code == 404

    def test_inactive_category_is_404_for_the_public(self, client: TestClient, db: Session) -> None:
        hidden = make_category(db, name="Hidden Line", is_active=False)
        assert client.get(f"{CATEGORIES}/{hidden.slug}").status_code == 404


class TestCategoryAuthorization:
    def test_anonymous_cannot_create(self, client: TestClient) -> None:
        assert client.post(CATEGORIES, json={"name": "Nope"}).status_code == 401

    def test_customer_cannot_create(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(CATEGORIES, json={"name": "Nope"}, headers=customer_headers)
        assert response.status_code == 403

    def test_staff_cannot_create(self, client: TestClient, staff_headers: dict[str, str]) -> None:
        """Catalogue structure is an ADMIN decision, not day-to-day staff work."""
        response = client.post(CATEGORIES, json={"name": "Nope"}, headers=staff_headers)
        assert response.status_code == 403

    def test_customer_cannot_delete(
        self, client: TestClient, category: Category, customer_headers: dict[str, str]
    ) -> None:
        response = client.delete(f"{CATEGORIES}/{category.id}", headers=customer_headers)
        assert response.status_code == 403


class TestCategoryAdmin:
    def test_admin_creates_a_category_with_a_derived_slug(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            CATEGORIES,
            json={"name": "Aerial  Shells & Fountains", "display_order": 3},
            headers=admin_headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Aerial Shells & Fountains"
        assert body["slug"] == "aerial-shells-fountains"

    def test_duplicate_name_is_rejected(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(CATEGORIES, json={"name": category.name}, headers=admin_headers)
        assert response.status_code == 409

    def test_duplicate_name_differing_in_case_is_rejected(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            CATEGORIES, json={"name": category.name.upper()}, headers=admin_headers
        )
        assert response.status_code == 409

    def test_slug_collisions_get_a_suffix(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        """Two different names can slugify identically; both must still work."""
        first = client.post(CATEGORIES, json={"name": "Ground Spinner"}, headers=admin_headers)
        second = client.post(CATEGORIES, json={"name": "Ground  Spinner!"}, headers=admin_headers)
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["slug"] != second.json()["slug"]

    def test_rename_updates_the_slug(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            f"{CATEGORIES}/{category.id}", json={"name": "Renamed Line"}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["slug"] == "renamed-line"

    def test_deactivate_hides_it_from_the_storefront(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        client.patch(
            f"{CATEGORIES}/{category.id}", json={"is_active": False}, headers=admin_headers
        )
        names = {item["name"] for item in client.get(CATEGORIES).json()}
        assert category.name not in names

    def test_empty_category_can_be_deleted(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        response = client.delete(f"{CATEGORIES}/{category.id}", headers=admin_headers)
        assert response.status_code == 200
        assert client.get(f"{CATEGORIES}/{category.slug}").status_code == 404

    def test_category_with_products_cannot_be_deleted(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        """Deleting it would take the catalogue and order history with it."""
        make_product(db, category=category, name="Blocker", sku="BLK-1")

        response = client.delete(f"{CATEGORIES}/{category.id}", headers=admin_headers)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    def test_unknown_category_returns_404(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        assert client.delete(f"{CATEGORIES}/999999", headers=admin_headers).status_code == 404

    def test_short_name_is_rejected(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(CATEGORIES, json={"name": "X"}, headers=admin_headers)
        assert response.status_code == 422
