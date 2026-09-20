"""Tests for `/api/v1/cart` and `/api/v1/checkout`.

These are the money tests. The rule they exist to defend: a client supplies
product ids and quantities, and nothing else it sends about price, discount,
delivery or totals is ever read.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import RoleName
from app.models.category import Category
from app.models.product import Product
from tests.conftest import auth_header, login, make_category, make_product, make_user

CART = "/api/v1/cart"
ITEMS = "/api/v1/cart/items"
ADDRESSES = "/api/v1/addresses"
QUOTE = "/api/v1/checkout/quote"


def address_payload(**overrides: object) -> dict:
    body = {
        "full_name": "Priya Selvam",
        "phone": "9876543210",
        "house_number": "12A",
        "street": "Anna Salai",
        "area": "T Nagar",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "pincode": "600017",
    }
    body.update(overrides)
    return body


def add(client: TestClient, headers: dict[str, str], product_id: int, quantity: int = 1):
    return client.post(
        ITEMS, json={"product_id": product_id, "quantity": quantity}, headers=headers
    )


class TestCartAuthorization:
    def test_anonymous_has_no_basket(self, client: TestClient) -> None:
        assert client.get(CART).status_code == 401

    def test_anonymous_cannot_add(self, client: TestClient, product: Product) -> None:
        assert add(client, {}, product.id).status_code == 401

    def test_baskets_are_private(
        self,
        client: TestClient,
        db: Session,
        product: Product,
        customer_headers: dict[str, str],
    ) -> None:
        add(client, customer_headers, product.id, 2)

        other = make_user(db, email="other@example.com", role=RoleName.CUSTOMER)
        other_headers = auth_header(login(client, other.email))

        assert client.get(CART, headers=other_headers).json()["is_empty"] is True

    def test_one_customer_cannot_change_anothers_line(
        self,
        client: TestClient,
        db: Session,
        product: Product,
        customer_headers: dict[str, str],
    ) -> None:
        line_id = add(client, customer_headers, product.id, 2).json()["lines"][0]["id"]

        other = make_user(db, email="other@example.com", role=RoleName.CUSTOMER)
        other_headers = auth_header(login(client, other.email))

        response = client.patch(f"{ITEMS}/{line_id}", json={"quantity": 99}, headers=other_headers)
        assert response.status_code == 404


class TestCartMutations:
    def test_starts_empty(self, client: TestClient, customer_headers: dict[str, str]) -> None:
        body = client.get(CART, headers=customer_headers).json()
        assert body["is_empty"] is True
        assert body["item_count"] == 0
        assert body["is_purchasable"] is False

    def test_adds_an_item(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        response = add(client, customer_headers, product.id, 2)
        assert response.status_code == 201
        body = response.json()
        assert body["item_count"] == 2
        assert len(body["lines"]) == 1

    def test_adding_the_same_product_again_tops_up_one_line(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        add(client, customer_headers, product.id, 2)
        body = add(client, customer_headers, product.id, 3).json()

        assert len(body["lines"]) == 1
        assert body["lines"][0]["quantity"] == 5

    def test_updates_a_quantity(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        line_id = add(client, customer_headers, product.id, 2).json()["lines"][0]["id"]
        body = client.patch(
            f"{ITEMS}/{line_id}", json={"quantity": 7}, headers=customer_headers
        ).json()
        assert body["lines"][0]["quantity"] == 7

    def test_removes_a_line(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        line_id = add(client, customer_headers, product.id, 2).json()["lines"][0]["id"]
        body = client.delete(f"{ITEMS}/{line_id}", headers=customer_headers).json()
        assert body["is_empty"] is True

    def test_clears_the_whole_basket(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        for index in range(3):
            item = make_product(db, category=category, name=f"Item {index}", sku=f"C-{index}")
            add(client, customer_headers, item.id, 1)

        body = client.delete(CART, headers=customer_headers).json()
        assert body["is_empty"] is True
        assert body["item_count"] == 0

    def test_quantity_must_be_at_least_one(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        assert add(client, customer_headers, product.id, 0).status_code == 422
        line_id = add(client, customer_headers, product.id, 1).json()["lines"][0]["id"]
        response = client.patch(
            f"{ITEMS}/{line_id}", json={"quantity": 0}, headers=customer_headers
        )
        assert response.status_code == 422

    def test_a_single_line_is_capped(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """One tap must not be able to reserve the entire shelf."""
        item = make_product(db, category=category, name="Plenty", sku="PL-1", stock_quantity=500)
        assert add(client, customer_headers, item.id, 100).status_code == 422

    def test_topping_up_past_the_cap_is_refused(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Plenty", sku="PL-1", stock_quantity=500)
        add(client, customer_headers, item.id, 60)
        response = add(client, customer_headers, item.id, 60)
        assert response.status_code == 422
        assert "at most" in response.json()["error"]["message"]

    def test_unknown_product_is_rejected(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        assert add(client, customer_headers, 999999, 1).status_code == 404


class TestStockIsNeverTrustedToTheClient:
    def test_cannot_add_more_than_is_in_stock(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Scarce", sku="SC-1", stock_quantity=3)
        response = add(client, customer_headers, item.id, 5)
        assert response.status_code == 422
        assert "Only 3 units" in response.json()["error"]["message"]

    def test_exactly_the_remaining_stock_is_allowed(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Scarce", sku="SC-1", stock_quantity=3)
        assert add(client, customer_headers, item.id, 3).status_code == 201

    def test_cannot_add_an_out_of_stock_product(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Gone", sku="GO-1", stock_quantity=0)
        response = add(client, customer_headers, item.id, 1)
        assert response.status_code == 422
        assert "out of stock" in response.json()["error"]["message"]

    def test_cannot_add_a_withdrawn_product(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Hidden", sku="HI-1", is_active=False)
        response = add(client, customer_headers, item.id, 1)
        assert response.status_code == 422

    def test_cannot_add_a_product_from_a_retired_category(
        self, client: TestClient, db: Session, customer_headers: dict[str, str]
    ) -> None:
        retired = make_category(db, name="Retired Line", is_active=False)
        item = make_product(db, category=retired, name="Orphan", sku="OR-1")
        assert add(client, customer_headers, item.id, 1).status_code == 422

    def test_a_basket_notices_stock_lost_after_the_item_was_added(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """The shelf can empty between adding and checking out."""
        item = make_product(db, category=category, name="Scarce", sku="SC-1", stock_quantity=10)
        add(client, customer_headers, item.id, 8)

        item.stock_quantity = 2
        db.commit()

        body = client.get(CART, headers=customer_headers).json()
        assert body["is_purchasable"] is False
        assert "Only 2 units" in body["problems"][0]
        # The line is still priced, so the shopper can see what is wrong.
        assert body["lines"][0]["quantity"] == 8
        assert body["lines"][0]["available_quantity"] == 2

    def test_a_basket_notices_a_product_withdrawn_after_it_was_added(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Doomed", sku="DO-1")
        add(client, customer_headers, item.id, 1)

        item.is_active = False
        db.commit()

        body = client.get(CART, headers=customer_headers).json()
        assert body["is_purchasable"] is False
        assert "no longer available" in body["problems"][0]


class TestPricingIsServerSide:
    def test_totals_are_computed_from_the_catalogue(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(
            db,
            category=category,
            name="Priced",
            sku="PR-1",
            mrp="250.00",
            selling_price="199.00",
            stock_quantity=50,
        )
        body = add(client, customer_headers, item.id, 3).json()

        totals = body["totals"]
        assert Decimal(totals["subtotal"]) == Decimal("750.00")
        assert Decimal(totals["items_total"]) == Decimal("597.00")
        assert Decimal(totals["discount"]) == Decimal("153.00")

    def test_a_client_supplied_price_is_ignored(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """The decisive test: sending a price must change nothing."""
        item = make_product(
            db,
            category=category,
            name="Priced",
            sku="PR-1",
            mrp="250.00",
            selling_price="199.00",
            stock_quantity=50,
        )
        response = client.post(
            ITEMS,
            json={
                "product_id": item.id,
                "quantity": 2,
                # All of this is noise. None of it is read.
                "unit_price": "0.01",
                "selling_price": "0.01",
                "line_total": "0.02",
                "total": "0.02",
                "discount": "999.00",
            },
            headers=customer_headers,
        )
        assert response.status_code == 201

        totals = response.json()["totals"]
        assert Decimal(totals["items_total"]) == Decimal("398.00")
        assert Decimal(totals["total"]) == Decimal("398.00") + settings.delivery_charge

    def test_a_price_change_shows_up_immediately(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """Nothing about price is frozen into the basket."""
        item = make_product(
            db,
            category=category,
            name="Priced",
            sku="PR-1",
            mrp="100.00",
            selling_price="100.00",
            stock_quantity=50,
        )
        add(client, customer_headers, item.id, 2)

        item.selling_price = Decimal("60.00")
        db.commit()

        totals = client.get(CART, headers=customer_headers).json()["totals"]
        assert Decimal(totals["items_total"]) == Decimal("120.00")
        assert Decimal(totals["discount"]) == Decimal("80.00")

    def test_money_crosses_the_wire_as_exact_strings(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(
            db,
            category=category,
            name="Awkward",
            sku="AW-1",
            mrp="1999.99",
            selling_price="1099.95",
            stock_quantity=50,
        )
        body = add(client, customer_headers, item.id, 1).json()
        assert body["lines"][0]["unit_price"] == "1099.95"
        assert body["totals"]["items_total"] == "1099.95"

    def test_the_lines_sum_exactly_to_the_total(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        for index in range(5):
            item = make_product(
                db,
                category=category,
                name=f"Odd {index}",
                sku=f"OD-{index}",
                mrp="19.99",
                selling_price="13.37",
                stock_quantity=50,
            )
            add(client, customer_headers, item.id, index + 1)

        body = client.get(CART, headers=customer_headers).json()
        lines_total = sum(Decimal(line["line_total"]) for line in body["lines"])
        assert lines_total == Decimal(body["totals"]["items_total"])


class TestDelivery:
    def test_charged_on_a_small_basket(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(
            db,
            category=category,
            name="Small",
            sku="SM-1",
            mrp="100.00",
            selling_price="100.00",
            stock_quantity=50,
        )
        totals = add(client, customer_headers, item.id, 1).json()["totals"]

        assert Decimal(totals["delivery_charge"]) == settings.delivery_charge
        assert totals["free_delivery_applied"] is False
        assert Decimal(totals["total"]) == Decimal("100.00") + settings.delivery_charge

    def test_free_once_the_threshold_is_reached(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(
            db,
            category=category,
            name="Big",
            sku="BI-1",
            mrp="2500.00",
            selling_price="2500.00",
            stock_quantity=50,
        )
        totals = add(client, customer_headers, item.id, 1).json()["totals"]

        assert Decimal(totals["delivery_charge"]) == Decimal("0.00")
        assert totals["free_delivery_applied"] is True
        assert Decimal(totals["total"]) == Decimal("2500.00")

    def test_reports_how_much_more_earns_free_delivery(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(
            db,
            category=category,
            name="Mid",
            sku="MI-1",
            mrp="1500.00",
            selling_price="1500.00",
            stock_quantity=50,
        )
        totals = add(client, customer_headers, item.id, 1).json()["totals"]
        expected = settings.free_delivery_threshold - Decimal("1500.00")
        assert Decimal(totals["amount_to_free_delivery"]) == expected

    def test_an_empty_basket_is_not_charged_delivery(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        totals = client.get(CART, headers=customer_headers).json()["totals"]
        assert Decimal(totals["delivery_charge"]) == Decimal("0.00")
        assert Decimal(totals["total"]) == Decimal("0.00")


class TestCheckoutQuote:
    def _ready(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        headers: dict[str, str],
        **product_kwargs,
    ) -> tuple[int, dict]:
        item = make_product(
            db,
            category=category,
            name="Quoted",
            sku="QU-1",
            mrp="1000.00",
            selling_price="800.00",
            stock_quantity=50,
            **product_kwargs,
        )
        add(client, headers, item.id, 2)
        address = client.post(ADDRESSES, json=address_payload(), headers=headers).json()
        return address["id"], {"item_id": item.id}

    def test_anonymous_cannot_get_a_quote(self, client: TestClient) -> None:
        assert client.post(QUOTE, json={"address_id": 1}).status_code == 401

    def test_quotes_a_ready_basket(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        address_id, _ = self._ready(client, db, category, customer_headers)

        response = client.post(QUOTE, json={"address_id": address_id}, headers=customer_headers)
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["can_place_order"] is True
        assert body["blockers"] == []
        assert body["delivery_address"]["city"] == "Chennai"
        assert Decimal(body["cart"]["totals"]["items_total"]) == Decimal("1600.00")

    def test_the_quote_matches_the_basket_exactly(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """A customer must never be quoted one figure and shown another."""
        address_id, _ = self._ready(client, db, category, customer_headers)

        cart = client.get(CART, headers=customer_headers).json()
        quote = client.post(QUOTE, json={"address_id": address_id}, headers=customer_headers).json()

        assert quote["cart"]["totals"] == cart["totals"]

    def test_refuses_an_empty_basket(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        address = client.post(ADDRESSES, json=address_payload(), headers=customer_headers).json()

        body = client.post(
            QUOTE, json={"address_id": address["id"]}, headers=customer_headers
        ).json()
        assert body["can_place_order"] is False
        assert "Your basket is empty." in body["blockers"]

    def test_refuses_when_an_item_sold_out_after_it_was_added(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Vanishing", sku="VA-1", stock_quantity=10)
        add(client, customer_headers, item.id, 5)
        address = client.post(ADDRESSES, json=address_payload(), headers=customer_headers).json()

        item.stock_quantity = 1
        db.commit()

        body = client.post(
            QUOTE, json={"address_id": address["id"]}, headers=customer_headers
        ).json()
        assert body["can_place_order"] is False
        assert any("Only 1 unit" in blocker for blocker in body["blockers"])

    def test_cannot_quote_against_someone_elses_address(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        address_id, _ = self._ready(client, db, category, customer_headers)

        other = make_user(db, email="other@example.com", role=RoleName.CUSTOMER)
        other_headers = auth_header(login(client, other.email))

        response = client.post(QUOTE, json={"address_id": address_id}, headers=other_headers)
        assert response.status_code == 404

    def test_unknown_address_is_rejected(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(QUOTE, json={"address_id": 999999}, headers=customer_headers)
        assert response.status_code == 404
