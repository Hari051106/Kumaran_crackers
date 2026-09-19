"""Admin and staff product management: CRUD, stock, images, authorisation."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from tests.conftest import make_product

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


class TestProductAuthorization:
    def test_anonymous_cannot_create(self, client: TestClient, category: Category) -> None:
        assert client.post(PRODUCTS, json=_payload(category.id)).status_code == 401

    def test_customer_cannot_create(
        self, client: TestClient, category: Category, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(PRODUCTS, json=_payload(category.id), headers=customer_headers)
        assert response.status_code == 403

    def test_staff_cannot_create(
        self, client: TestClient, category: Category, staff_headers: dict[str, str]
    ) -> None:
        """Adding catalogue items is an ADMIN action."""
        response = client.post(PRODUCTS, json=_payload(category.id), headers=staff_headers)
        assert response.status_code == 403

    def test_customer_cannot_delete(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        response = client.delete(f"{PRODUCTS}/id/{product.id}", headers=customer_headers)
        assert response.status_code == 403

    def test_customer_cannot_adjust_stock(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        """Stock is never writable by a shopper."""
        response = client.post(
            f"{PRODUCTS}/id/{product.id}/stock", json={"set_to": 9999}, headers=customer_headers
        )
        assert response.status_code == 403

    def test_customer_cannot_read_the_low_stock_report(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        assert client.get(f"{PRODUCTS}/low-stock", headers=customer_headers).status_code == 403

    def test_staff_can_adjust_stock(
        self, client: TestClient, product: Product, staff_headers: dict[str, str]
    ) -> None:
        """Inventory is day-to-day operations work, so STAFF is enough."""
        response = client.post(
            f"{PRODUCTS}/id/{product.id}/stock", json={"set_to": 42}, headers=staff_headers
        )
        assert response.status_code == 200
        assert response.json()["stock_quantity"] == 42


class TestProductCreate:
    def test_admin_creates_a_product(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(PRODUCTS, json=_payload(category.id), headers=admin_headers)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Colour Sparkler 30cm"
        assert body["slug"] == "colour-sparkler-30cm"
        assert body["category"]["id"] == category.id

    def test_sku_is_generated_when_omitted(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        body = client.post(PRODUCTS, json=_payload(category.id), headers=admin_headers).json()
        assert body["sku"]
        assert body["sku"] == body["sku"].upper()

    def test_explicit_sku_is_kept_and_upper_cased(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        body = client.post(
            PRODUCTS, json=_payload(category.id, sku="spk-001"), headers=admin_headers
        ).json()
        assert body["sku"] == "SPK-001"

    def test_duplicate_sku_is_rejected(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        make_product(db, category=category, name="Existing", sku="DUP-1")
        response = client.post(
            PRODUCTS, json=_payload(category.id, sku="DUP-1"), headers=admin_headers
        )
        assert response.status_code == 409

    def test_generated_skus_stay_unique_for_identical_names(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        first = client.post(PRODUCTS, json=_payload(category.id), headers=admin_headers)
        second = client.post(PRODUCTS, json=_payload(category.id), headers=admin_headers)
        assert first.status_code == second.status_code == 201
        assert first.json()["sku"] != second.json()["sku"]
        assert first.json()["slug"] != second.json()["slug"]

    def test_unknown_category_is_rejected(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(PRODUCTS, json=_payload(999999), headers=admin_headers)
        assert response.status_code == 404

    def test_product_can_be_created_with_images(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            PRODUCTS,
            json=_payload(
                category.id,
                images=[
                    {"image_url": "https://cdn.example.com/a.jpg", "alt_text": "Front"},
                    {"image_url": "https://cdn.example.com/b.jpg"},
                ],
            ),
            headers=admin_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert len(body["images"]) == 2
        # The first image becomes primary by default.
        assert body["primary_image_url"] == "https://cdn.example.com/a.jpg"

    def test_two_primary_images_are_rejected(
        self, client: TestClient, category: Category, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            PRODUCTS,
            json=_payload(
                category.id,
                images=[
                    {"image_url": "https://cdn.example.com/a.jpg", "is_primary": True},
                    {"image_url": "https://cdn.example.com/b.jpg", "is_primary": True},
                ],
            ),
            headers=admin_headers,
        )
        assert response.status_code == 422


class TestProductUpdate:
    def test_admin_updates_a_product(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            f"{PRODUCTS}/id/{product.id}", json={"name": "Renamed Item"}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed Item"
        assert response.json()["slug"] == "renamed-item"

    def test_partial_update_leaves_other_fields_alone(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        original_sku = product.sku
        response = client.patch(
            f"{PRODUCTS}/id/{product.id}", json={"is_featured": True}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["sku"] == original_sku
        assert response.json()["is_featured"] is True

    def test_moving_to_an_unknown_category_is_rejected(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            f"{PRODUCTS}/id/{product.id}", json={"category_id": 999999}, headers=admin_headers
        )
        assert response.status_code == 404

    def test_unknown_product_returns_404(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            f"{PRODUCTS}/id/999999", json={"name": "Ghost"}, headers=admin_headers
        )
        assert response.status_code == 404


class TestActivation:
    def test_deactivate_removes_it_from_the_catalogue(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(f"{PRODUCTS}/id/{product.id}/deactivate", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["is_active"] is False
        assert product.sku not in {p["sku"] for p in client.get(PRODUCTS).json()["items"]}

    def test_activate_restores_it(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        hidden = make_product(db, category=category, name="Hidden", sku="HID-1", is_active=False)
        response = client.post(f"{PRODUCTS}/id/{hidden.id}/activate", headers=admin_headers)
        assert response.status_code == 200
        assert "HID-1" in {p["sku"] for p in client.get(PRODUCTS).json()["items"]}


class TestDeletion:
    def test_admin_deletes_a_product(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        assert (
            client.delete(f"{PRODUCTS}/id/{product.id}", headers=admin_headers).status_code == 200
        )
        assert client.get(f"{PRODUCTS}/{product.slug}").status_code == 404

    def test_deleting_a_product_removes_its_images(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        """Images cascade with the product rather than being orphaned."""
        from app.models.product import ProductImage

        item = make_product(
            db,
            category=category,
            name="With Images",
            sku="IMG-1",
            image_urls=["https://cdn.example.com/x.jpg"],
        )
        image_id = item.images[0].id

        client.delete(f"{PRODUCTS}/id/{item.id}", headers=admin_headers)
        assert db.get(ProductImage, image_id) is None


class TestStockManagement:
    def test_set_absolute_stock(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            f"{PRODUCTS}/id/{product.id}/stock", json={"set_to": 7}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["stock_quantity"] == 7

    def test_positive_delta_adds_stock(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        before = product.stock_quantity
        response = client.post(
            f"{PRODUCTS}/id/{product.id}/stock", json={"delta": 25}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["stock_quantity"] == before + 25

    def test_negative_delta_removes_stock(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        before = product.stock_quantity
        response = client.post(
            f"{PRODUCTS}/id/{product.id}/stock", json={"delta": -10}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["stock_quantity"] == before - 10

    def test_delta_cannot_drive_stock_negative(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        """The guard is in the UPDATE itself, so a race cannot slip past it."""
        response = client.post(
            f"{PRODUCTS}/id/{product.id}/stock", json={"delta": -99999}, headers=admin_headers
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "business_rule_violation"

    def test_stock_is_unchanged_after_a_refused_adjustment(
        self, client: TestClient, product: Product, db: Session, admin_headers: dict[str, str]
    ) -> None:
        before = product.stock_quantity
        client.post(
            f"{PRODUCTS}/id/{product.id}/stock", json={"delta": -99999}, headers=admin_headers
        )
        db.refresh(product)
        assert product.stock_quantity == before

    def test_supplying_both_set_to_and_delta_is_rejected(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            f"{PRODUCTS}/id/{product.id}/stock",
            json={"set_to": 10, "delta": 5},
            headers=admin_headers,
        )
        assert response.status_code == 422

    def test_supplying_neither_is_rejected(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(f"{PRODUCTS}/id/{product.id}/stock", json={}, headers=admin_headers)
        assert response.status_code == 422


class TestStockReports:
    def test_low_stock_report(
        self, client: TestClient, db: Session, category: Category, staff_headers: dict[str, str]
    ) -> None:
        make_product(
            db,
            category=category,
            name="Running Out",
            sku="LOW-1",
            stock_quantity=3,
            low_stock_threshold=10,
        )
        make_product(
            db,
            category=category,
            name="Plenty Left",
            sku="OK-1",
            stock_quantity=500,
            low_stock_threshold=10,
        )

        skus = {p["sku"] for p in client.get(f"{PRODUCTS}/low-stock", headers=staff_headers).json()}
        assert "LOW-1" in skus and "OK-1" not in skus

    def test_low_stock_excludes_products_with_no_stock(
        self, client: TestClient, db: Session, category: Category, staff_headers: dict[str, str]
    ) -> None:
        """Zero stock belongs in the out-of-stock report, not low stock."""
        make_product(db, category=category, name="Gone", sku="ZERO-1", stock_quantity=0)
        skus = {p["sku"] for p in client.get(f"{PRODUCTS}/low-stock", headers=staff_headers).json()}
        assert "ZERO-1" not in skus

    def test_out_of_stock_report(
        self, client: TestClient, db: Session, category: Category, staff_headers: dict[str, str]
    ) -> None:
        make_product(db, category=category, name="Gone", sku="ZERO-1", stock_quantity=0)
        response = client.get(f"{PRODUCTS}/out-of-stock", headers=staff_headers)
        assert "ZERO-1" in {p["sku"] for p in response.json()}


class TestProductImages:
    def test_add_an_image(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            f"{PRODUCTS}/id/{product.id}/images",
            json={"image_url": "https://cdn.example.com/new.jpg", "alt_text": "Side"},
            headers=admin_headers,
        )
        assert response.status_code == 201
        assert len(response.json()["images"]) == 1

    def test_marking_a_new_primary_demotes_the_previous_one(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        """The database allows only one primary per product."""
        item = make_product(
            db,
            category=category,
            name="Gallery",
            sku="GAL-1",
            image_urls=["https://cdn.example.com/first.jpg"],
        )
        response = client.post(
            f"{PRODUCTS}/id/{item.id}/images",
            json={"image_url": "https://cdn.example.com/second.jpg", "is_primary": True},
            headers=admin_headers,
        )
        assert response.status_code == 201
        body = response.json()
        primaries = [image for image in body["images"] if image["is_primary"]]
        assert len(primaries) == 1
        assert primaries[0]["image_url"] == "https://cdn.example.com/second.jpg"
        assert body["primary_image_url"] == "https://cdn.example.com/second.jpg"

    def test_delete_an_image(
        self, client: TestClient, db: Session, category: Category, admin_headers: dict[str, str]
    ) -> None:
        item = make_product(
            db,
            category=category,
            name="Gallery",
            sku="GAL-1",
            image_urls=["https://cdn.example.com/a.jpg", "https://cdn.example.com/b.jpg"],
        )
        image_id = item.images[0].id
        response = client.delete(
            f"{PRODUCTS}/id/{item.id}/images/{image_id}", headers=admin_headers
        )
        assert response.status_code == 200
        assert len(response.json()["images"]) == 1

    def test_deleting_an_unknown_image_returns_404(
        self, client: TestClient, product: Product, admin_headers: dict[str, str]
    ) -> None:
        response = client.delete(f"{PRODUCTS}/id/{product.id}/images/999999", headers=admin_headers)
        assert response.status_code == 404

    def test_customer_cannot_add_an_image(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(
            f"{PRODUCTS}/id/{product.id}/images",
            json={"image_url": "https://cdn.example.com/x.jpg"},
            headers=customer_headers,
        )
        assert response.status_code == 403
