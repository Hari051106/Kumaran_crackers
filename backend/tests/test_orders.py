"""Tests for the order system.

Placing an order is the one operation that must be all-or-nothing: it writes an
order and its lines, takes stock off the shelf, and empties the basket. These
tests exist to prove that either all of that happens or none of it does, and
that a placed order is an immutable record of what was actually bought.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import OrderStatus, RoleName
from app.models.category import Category
from app.models.order import Order
from app.models.product import Product
from tests.conftest import (
    ADDRESSES_URL,
    ADMIN_CUSTOMERS_URL,
    ADMIN_ORDERS_URL,
    CART_ITEMS_URL,
    ORDERS_URL,
    address_payload,
    advance_to,
    auth_header,
    login,
    make_product,
    make_user,
    move,
    order_now,
    place,
    ready_to_order,
)


class TestPlacingAnOrder:
    def test_places_an_order(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        address_id = ready_to_order(client, customer_headers, product)
        response = place(client, customer_headers, address_id)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "PLACED"
        assert body["order_number"].startswith("KC-")
        assert body["item_count"] == 2

    def test_anonymous_cannot_place_an_order(self, client: TestClient) -> None:
        assert client.post(ORDERS_URL, json={"address_id": 1}).status_code == 401

    def test_the_order_total_matches_the_quote_exactly(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """A customer must be charged the figure they were shown."""
        item = make_product(
            db,
            category=category,
            name="Quoted",
            sku="QU-1",
            mrp="1000.00",
            selling_price="800.00",
            stock_quantity=50,
        )
        address_id = ready_to_order(client, customer_headers, item, quantity=2)

        quote = client.post(
            "/api/v1/checkout/quote", json={"address_id": address_id}, headers=customer_headers
        ).json()
        order = place(client, customer_headers, address_id).json()

        assert order["totals"]["total"] == quote["cart"]["totals"]["total"]
        assert order["totals"]["subtotal"] == quote["cart"]["totals"]["subtotal"]
        assert order["totals"]["discount"] == quote["cart"]["totals"]["discount"]

    def test_the_invoice_adds_up(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(
            db,
            category=category,
            name="Maths",
            sku="MA-1",
            mrp="333.33",
            selling_price="111.11",
            stock_quantity=50,
        )
        address_id = ready_to_order(client, customer_headers, item, quantity=3)
        totals = place(client, customer_headers, address_id).json()["totals"]

        subtotal = Decimal(totals["subtotal"])
        discount = Decimal(totals["discount"])
        items_total = Decimal(totals["items_total"])
        delivery = Decimal(totals["delivery_charge"])

        assert items_total == subtotal - discount
        assert Decimal(totals["total"]) == items_total + delivery

    def test_the_lines_sum_to_the_items_total(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        for index in range(4):
            extra = make_product(
                db,
                category=category,
                name=f"Odd {index}",
                sku=f"OD-{index}",
                mrp="19.99",
                selling_price="13.37",
                stock_quantity=50,
            )
            client.post(
                CART_ITEMS_URL,
                json={"product_id": extra.id, "quantity": index + 1},
                headers=customer_headers,
            )
        address = client.post(
            ADDRESSES_URL, json=address_payload(), headers=customer_headers
        ).json()

        order = place(client, customer_headers, address["id"]).json()
        lines = sum(Decimal(item["line_total"]) for item in order["items"])
        assert lines == Decimal(order["totals"]["items_total"])

    def test_the_basket_is_emptied(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        """The basket became the order; it must not survive as both."""
        address_id = ready_to_order(client, customer_headers, product)
        place(client, customer_headers, address_id)

        cart = client.get("/api/v1/cart", headers=customer_headers).json()
        assert cart["is_empty"] is True

    def test_an_empty_basket_cannot_be_ordered(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        address = client.post(
            ADDRESSES_URL, json=address_payload(), headers=customer_headers
        ).json()
        response = place(client, customer_headers, address["id"])
        assert response.status_code == 422
        assert "basket is empty" in response.json()["error"]["message"]

    def test_cannot_order_to_someone_elses_address(
        self,
        client: TestClient,
        db: Session,
        product: Product,
        customer_headers: dict[str, str],
    ) -> None:
        address_id = ready_to_order(client, customer_headers, product)

        other = make_user(db, email="other@example.com", role=RoleName.CUSTOMER)
        other_headers = auth_header(login(client, other.email))
        client.post(
            CART_ITEMS_URL, json={"product_id": product.id, "quantity": 1}, headers=other_headers
        )

        assert place(client, other_headers, address_id).status_code == 404

    def test_order_numbers_are_unique(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        numbers = set()
        for index in range(3):
            item = make_product(
                db,
                category=category,
                name=f"Rep {index}",
                sku=f"RP-{index}",
                stock_quantity=50,
            )
            address_id = ready_to_order(client, customer_headers, item, quantity=1)
            numbers.add(place(client, customer_headers, address_id).json()["order_number"])
        assert len(numbers) == 3


class TestStockMovesWithTheOrder:
    def test_stock_is_taken_off_the_shelf(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Stocked", sku="ST-1", stock_quantity=20)
        address_id = ready_to_order(client, customer_headers, item, quantity=5)

        place(client, customer_headers, address_id)

        db.refresh(item)
        assert item.stock_quantity == 15
        assert item.sold_quantity == 5

    def test_ordering_the_last_unit_is_allowed(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Last One", sku="LA-1", stock_quantity=3)
        address_id = ready_to_order(client, customer_headers, item, quantity=3)

        assert place(client, customer_headers, address_id).status_code == 201
        db.refresh(item)
        assert item.stock_quantity == 0

    def test_an_order_is_refused_when_stock_vanishes_after_the_quote(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """Someone else took the last of it while this customer was deciding."""
        item = make_product(db, category=category, name="Contested", sku="CO-1", stock_quantity=10)
        address_id = ready_to_order(client, customer_headers, item, quantity=8)

        item.stock_quantity = 2
        db.commit()

        response = place(client, customer_headers, address_id)
        assert response.status_code == 422
        assert "Only 2 units" in response.json()["error"]["message"]

    def test_a_refused_order_leaves_no_trace(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """All-or-nothing: no order row, no stock taken, basket untouched."""
        item = make_product(db, category=category, name="Contested", sku="CO-1", stock_quantity=10)
        address_id = ready_to_order(client, customer_headers, item, quantity=8)

        item.stock_quantity = 2
        db.commit()
        before = item.stock_quantity

        place(client, customer_headers, address_id)

        db.refresh(item)
        assert item.stock_quantity == before
        assert db.query(Order).count() == 0
        # The basket is still there to be fixed.
        assert client.get("/api/v1/cart", headers=customer_headers).json()["is_empty"] is False

    def test_a_multi_line_order_takes_all_stock_or_none(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """The decisive test: one bad line must not leave the others reserved."""
        good = make_product(db, category=category, name="Plenty", sku="PL-1", stock_quantity=100)
        scarce = make_product(db, category=category, name="Scarce", sku="SC-1", stock_quantity=10)
        client.post(
            CART_ITEMS_URL, json={"product_id": good.id, "quantity": 5}, headers=customer_headers
        )
        client.post(
            CART_ITEMS_URL, json={"product_id": scarce.id, "quantity": 8}, headers=customer_headers
        )
        address = client.post(
            ADDRESSES_URL, json=address_payload(), headers=customer_headers
        ).json()

        # The scarce line becomes impossible after the basket was built.
        scarce.stock_quantity = 1
        db.commit()

        response = place(client, customer_headers, address["id"])
        assert response.status_code == 422

        db.refresh(good)
        db.refresh(scarce)
        # The good line's stock was never taken, even though it was processed.
        assert good.stock_quantity == 100
        assert good.sold_quantity == 0
        assert scarce.stock_quantity == 1


class TestAnOrderIsAnImmutableRecord:
    def test_prices_are_frozen_at_purchase(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """Re-pricing the catalogue must not rewrite a past invoice."""
        item = make_product(
            db,
            category=category,
            name="Repriced",
            sku="RE-1",
            mrp="500.00",
            selling_price="400.00",
            stock_quantity=50,
        )
        address_id = ready_to_order(client, customer_headers, item, quantity=2)
        order = place(client, customer_headers, address_id).json()
        original_total = order["totals"]["total"]

        item.selling_price = Decimal("50.00")
        item.mrp = Decimal("60.00")
        db.commit()

        after = client.get(f"{ORDERS_URL}/{order['order_number']}", headers=customer_headers).json()
        assert after["totals"]["total"] == original_total
        assert after["items"][0]["unit_price"] == "400.00"
        assert after["items"][0]["unit_mrp"] == "500.00"

    def test_the_product_name_is_frozen_too(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(
            db, category=category, name="Original Name", sku="ON-1", stock_quantity=50
        )
        address_id = ready_to_order(client, customer_headers, item, quantity=1)
        order = place(client, customer_headers, address_id).json()

        item.name = "Renamed Later"
        db.commit()

        after = client.get(f"{ORDERS_URL}/{order['order_number']}", headers=customer_headers).json()
        assert after["items"][0]["product_name"] == "Original Name"

    def test_the_delivery_address_is_frozen(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        """Editing a saved address must not change where a past order went."""
        address_id = ready_to_order(client, customer_headers, product)
        order = place(client, customer_headers, address_id).json()

        client.patch(
            f"{ADDRESSES_URL}/{address_id}",
            json={"city": "Madurai", "pincode": "625001"},
            headers=customer_headers,
        )

        after = client.get(f"{ORDERS_URL}/{order['order_number']}", headers=customer_headers).json()
        assert after["delivery_address"]["city"] == "Chennai"
        assert after["delivery_address"]["pincode"] == "600017"

    def test_deleting_the_address_leaves_the_order_intact(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        address_id = ready_to_order(client, customer_headers, product)
        order = place(client, customer_headers, address_id).json()

        client.delete(f"{ADDRESSES_URL}/{address_id}", headers=customer_headers)

        after = client.get(f"{ORDERS_URL}/{order['order_number']}", headers=customer_headers)
        assert after.status_code == 200
        assert after.json()["delivery_address"]["city"] == "Chennai"


class TestOrderHistory:
    def test_lists_my_orders_newest_first(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        numbers = []
        for index in range(3):
            item = make_product(
                db,
                category=category,
                name=f"Hist {index}",
                sku=f"HI-{index}",
                stock_quantity=50,
            )
            address_id = ready_to_order(client, customer_headers, item, quantity=1)
            numbers.append(place(client, customer_headers, address_id).json()["order_number"])

        listing = client.get(ORDERS_URL, headers=customer_headers).json()
        assert listing["meta"]["total"] == 3
        assert listing["items"][0]["order_number"] == numbers[-1]

    def test_one_customer_cannot_read_anothers_order(
        self,
        client: TestClient,
        db: Session,
        product: Product,
        customer_headers: dict[str, str],
    ) -> None:
        address_id = ready_to_order(client, customer_headers, product)
        order = place(client, customer_headers, address_id).json()

        other = make_user(db, email="other@example.com", role=RoleName.CUSTOMER)
        other_headers = auth_header(login(client, other.email))

        response = client.get(f"{ORDERS_URL}/{order['order_number']}", headers=other_headers)
        assert response.status_code == 404

    def test_another_customers_orders_are_not_listed(
        self,
        client: TestClient,
        db: Session,
        product: Product,
        customer_headers: dict[str, str],
    ) -> None:
        address_id = ready_to_order(client, customer_headers, product)
        place(client, customer_headers, address_id)

        other = make_user(db, email="other@example.com", role=RoleName.CUSTOMER)
        other_headers = auth_header(login(client, other.email))

        assert client.get(ORDERS_URL, headers=other_headers).json()["meta"]["total"] == 0

    def test_the_tracking_timeline_starts_at_placed(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        address_id = ready_to_order(client, customer_headers, product)
        order = place(client, customer_headers, address_id).json()

        timeline = order["timeline"]
        assert [step["status"] for step in timeline] == [
            "PLACED",
            "CONFIRMED",
            "PACKING",
            "OUT_FOR_DELIVERY",
            "DELIVERED",
        ]
        assert timeline[0]["reached"] is True
        assert timeline[0]["is_current"] is True
        assert timeline[1]["reached"] is False

    def test_placing_writes_the_first_audit_entry(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        address_id = ready_to_order(client, customer_headers, product)
        order = place(client, customer_headers, address_id).json()

        history = order["status_history"]
        assert len(history) == 1
        assert history[0]["from_status"] is None
        assert history[0]["to_status"] == "PLACED"


class TestMovingAnOrderOn:
    """The workflow runs forwards only, one stage at a time, and is recorded."""

    def test_staff_confirm_a_placed_order(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)

        response = move(client, staff_headers, number, OrderStatus.CONFIRMED)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "CONFIRMED"
        assert body["status_label"] == "Confirmed"

    def test_an_order_cannot_skip_a_stage(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)

        response = move(client, staff_headers, number, OrderStatus.OUT_FOR_DELIVERY)

        assert response.status_code == 422
        message = response.json()["error"]["message"]
        assert "can only move to" in message
        # The refusal names the moves that *are* open.
        assert "Confirmed" in message and "Cancelled" in message

    def test_an_order_never_goes_backwards(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        move(client, staff_headers, number, OrderStatus.CONFIRMED)

        response = move(client, staff_headers, number, OrderStatus.PLACED)

        assert response.status_code == 422
        detail = client.get(f"{ADMIN_ORDERS_URL}/{number}", headers=staff_headers).json()
        assert detail["status"] == "CONFIRMED"

    def test_repeating_the_current_status_is_refused(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        """A double-click must not write a second identical audit entry."""
        number = order_now(client, customer_headers, product)

        response = move(client, staff_headers, number, OrderStatus.PLACED)

        assert response.status_code == 422
        assert 'already "Order placed"' in response.json()["error"]["message"]
        detail = client.get(f"{ADMIN_ORDERS_URL}/{number}", headers=staff_headers).json()
        assert len(detail["status_history"]) == 1

    def test_a_delivered_order_is_final(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        advance_to(client, staff_headers, number, OrderStatus.DELIVERED)

        response = move(client, staff_headers, number, OrderStatus.CANCELLED)

        assert response.status_code == 422
        assert "can no longer be changed" in response.json()["error"]["message"]

    def test_delivery_is_timestamped(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        advance_to(client, staff_headers, number, OrderStatus.OUT_FOR_DELIVERY)

        before = client.get(f"{ADMIN_ORDERS_URL}/{number}", headers=staff_headers).json()
        assert before["delivered_at"] is None

        after = move(client, staff_headers, number, OrderStatus.DELIVERED).json()
        assert after["delivered_at"] is not None

    def test_every_move_records_who_made_it(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        move(client, staff_headers, number, OrderStatus.CONFIRMED, note="Stock checked")

        history = client.get(f"{ADMIN_ORDERS_URL}/{number}", headers=staff_headers).json()[
            "status_history"
        ]
        assert [event["to_status"] for event in history] == ["PLACED", "CONFIRMED"]
        latest = history[-1]
        assert latest["from_status"] == "PLACED"
        assert latest["changed_by_name"] == "Staff Member"
        assert latest["note"] == "Stock checked"

    def test_the_customer_timeline_follows_the_status(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        advance_to(client, staff_headers, number, OrderStatus.PACKING)

        timeline = client.get(f"{ORDERS_URL}/{number}", headers=customer_headers).json()["timeline"]
        reached = [step["status"] for step in timeline if step["reached"]]
        current = [step["status"] for step in timeline if step["is_current"]]
        assert reached == ["PLACED", "CONFIRMED", "PACKING"]
        assert current == ["PACKING"]
        # Each reached stage carries the moment it happened.
        assert all(step["reached_at"] is not None for step in timeline[:3])
        assert timeline[3]["reached_at"] is None

    def test_a_customer_cannot_move_their_own_order_on(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)

        response = move(client, customer_headers, number, OrderStatus.DELIVERED)

        assert response.status_code == 403

    def test_moving_an_order_that_does_not_exist(
        self, client: TestClient, staff_headers: dict[str, str]
    ) -> None:
        assert move(client, staff_headers, "KC-999999", OrderStatus.CONFIRMED).status_code == 404


class TestCancellation:
    """Cancelling withdraws the order and puts its stock back on the shelf."""

    def test_a_customer_cancels_a_fresh_order(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        number = order_now(client, customer_headers, product)

        response = client.post(
            f"{ORDERS_URL}/{number}/cancel",
            json={"reason": "Changed my mind"},
            headers=customer_headers,
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "CANCELLED"
        assert body["cancellation_reason"] == "Changed my mind"
        assert body["cancelled_at"] is not None
        assert body["is_cancellable_by_customer"] is False

    def test_cancelling_puts_the_stock_back(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Returned", sku="RE-1", stock_quantity=20)
        number = order_now(client, customer_headers, item, quantity=5)

        db.refresh(item)
        assert (item.stock_quantity, item.sold_quantity) == (15, 5)

        client.post(f"{ORDERS_URL}/{number}/cancel", json={}, headers=customer_headers)

        db.refresh(item)
        # A cancelled order was never a sale.
        assert (item.stock_quantity, item.sold_quantity) == (20, 0)

    def test_stock_is_returned_only_once(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
    ) -> None:
        """Cancelling twice must not conjure stock out of nothing."""
        item = make_product(db, category=category, name="Twice", sku="TW-1", stock_quantity=20)
        number = order_now(client, customer_headers, item, quantity=5)
        client.post(f"{ORDERS_URL}/{number}/cancel", json={}, headers=customer_headers)

        second = client.post(f"{ORDERS_URL}/{number}/cancel", json={}, headers=customer_headers)

        assert second.status_code == 422
        assert "already been cancelled" in second.json()["error"]["message"]
        db.refresh(item)
        assert item.stock_quantity == 20

    def test_a_customer_cannot_cancel_once_it_is_packed(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        advance_to(client, staff_headers, number, OrderStatus.PACKING)

        response = client.post(f"{ORDERS_URL}/{number}/cancel", json={}, headers=customer_headers)

        assert response.status_code == 403
        assert "contact us" in response.json()["error"]["message"]

    def test_the_cancel_action_is_advertised_honestly(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        """The flag the app uses to show its button must match the rule."""
        number = order_now(client, customer_headers, product)
        fresh = client.get(f"{ORDERS_URL}/{number}", headers=customer_headers).json()
        assert fresh["is_cancellable_by_customer"] is True

        advance_to(client, staff_headers, number, OrderStatus.PACKING)

        packed = client.get(f"{ORDERS_URL}/{number}", headers=customer_headers).json()
        assert packed["is_cancellable_by_customer"] is False

    def test_staff_can_cancel_after_packing(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        item = make_product(db, category=category, name="Pulled", sku="PU-1", stock_quantity=30)
        number = order_now(client, customer_headers, item, quantity=4)
        advance_to(client, staff_headers, number, OrderStatus.PACKING)

        response = move(
            client, staff_headers, number, OrderStatus.CANCELLED, note="Damaged in the warehouse"
        )

        assert response.status_code == 200, response.text
        assert response.json()["cancellation_reason"] == "Damaged in the warehouse"
        db.refresh(item)
        assert item.stock_quantity == 30

    def test_a_cancelled_order_shows_no_current_stage(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        client.post(f"{ORDERS_URL}/{number}/cancel", json={}, headers=customer_headers)

        timeline = client.get(f"{ORDERS_URL}/{number}", headers=customer_headers).json()["timeline"]
        assert all(step["is_current"] is False for step in timeline)
        # What did happen is still shown; what never happened is not invented.
        assert timeline[0]["reached"] is True
        assert [step["reached"] for step in timeline[1:]] == [False, False, False, False]

    def test_cancelling_is_written_to_the_audit_trail(
        self, client: TestClient, product: Product, customer_headers: dict[str, str]
    ) -> None:
        number = order_now(client, customer_headers, product)

        client.post(
            f"{ORDERS_URL}/{number}/cancel",
            json={"reason": "Ordered twice"},
            headers=customer_headers,
        )

        history = client.get(f"{ORDERS_URL}/{number}", headers=customer_headers).json()[
            "status_history"
        ]
        assert [event["to_status"] for event in history] == ["PLACED", "CANCELLED"]
        assert history[-1]["changed_by_name"] == "Ravi Kumar"
        assert history[-1]["note"] == "Ordered twice"

    def test_one_customer_cannot_cancel_anothers_order(
        self,
        client: TestClient,
        db: Session,
        product: Product,
        customer_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        other = make_user(db, email="other@example.com", role=RoleName.CUSTOMER)
        other_headers = auth_header(login(client, other.email))

        response = client.post(f"{ORDERS_URL}/{number}/cancel", json={}, headers=other_headers)

        assert response.status_code == 404
        assert client.get(f"{ORDERS_URL}/{number}", headers=customer_headers).json()["status"] == (
            "PLACED"
        )


class TestTheBackOffice:
    """Staff see every order, filtered and searchable."""

    def test_staff_see_orders_placed_by_customers(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)

        listing = client.get(ADMIN_ORDERS_URL, headers=staff_headers).json()

        assert listing["meta"]["total"] == 1
        row = listing["items"][0]
        assert row["order_number"] == number
        assert row["customer_name"] == "Ravi Kumar"
        assert row["customer_email"] == "customer@example.com"
        assert row["customer_phone"] == "9876543210"

    def test_orders_can_be_filtered_by_status(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        first = make_product(db, category=category, name="Filter A", sku="FA-1")
        second = make_product(db, category=category, name="Filter B", sku="FB-1")
        confirmed = order_now(client, customer_headers, first, quantity=1)
        order_now(client, customer_headers, second, quantity=1)
        move(client, staff_headers, confirmed, OrderStatus.CONFIRMED)

        response = client.get(
            ADMIN_ORDERS_URL, params={"status": "CONFIRMED"}, headers=staff_headers
        ).json()

        assert response["meta"]["total"] == 1
        assert response["items"][0]["order_number"] == confirmed

    def test_orders_can_be_searched_by_number(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        first = make_product(db, category=category, name="Search A", sku="SA-1")
        second = make_product(db, category=category, name="Search B", sku="SB-1")
        wanted = order_now(client, customer_headers, first, quantity=1)
        order_now(client, customer_headers, second, quantity=1)

        response = client.get(
            ADMIN_ORDERS_URL, params={"query": wanted}, headers=staff_headers
        ).json()

        assert [row["order_number"] for row in response["items"]] == [wanted]

    def test_orders_can_be_searched_by_recipient(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        order_now(client, customer_headers, product)

        found = client.get(
            ADMIN_ORDERS_URL, params={"query": "priya"}, headers=staff_headers
        ).json()
        missing = client.get(
            ADMIN_ORDERS_URL, params={"query": "zzz"}, headers=staff_headers
        ).json()

        assert found["meta"]["total"] == 1
        assert missing["meta"]["total"] == 0

    def test_the_detail_view_publishes_the_moves_that_remain(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        """The desktop app offers only these, and the server re-checks anyway."""
        number = order_now(client, customer_headers, product)

        detail = client.get(f"{ADMIN_ORDERS_URL}/{number}", headers=staff_headers).json()

        assert detail["allowed_transitions"] == ["CANCELLED", "CONFIRMED"]

    def test_a_delivered_order_offers_no_further_moves(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        advance_to(client, staff_headers, number, OrderStatus.DELIVERED)

        detail = client.get(f"{ADMIN_ORDERS_URL}/{number}", headers=staff_headers).json()

        assert detail["allowed_transitions"] == []

    def test_staff_read_an_order_they_did_not_place(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)

        response = client.get(f"{ADMIN_ORDERS_URL}/{number}", headers=staff_headers)

        assert response.status_code == 200
        assert response.json()["delivery_address"]["single_line"].endswith("600017")

    def test_customers_cannot_reach_the_back_office(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        assert client.get(ADMIN_ORDERS_URL, headers=customer_headers).status_code == 403

    def test_anonymous_callers_cannot_reach_the_back_office(self, client: TestClient) -> None:
        assert client.get(ADMIN_ORDERS_URL).status_code == 401


class TestCustomerRecords:
    """`/admin/customers`: accounts with what they have actually bought."""

    def test_a_customer_shows_their_real_order_figures(
        self,
        client: TestClient,
        db: Session,
        category: Category,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        first = make_product(db, category=category, name="Spend A", sku="SPA")
        second = make_product(db, category=category, name="Spend B", sku="SPB")
        totals = [
            Decimal(
                client.get(
                    f"{ORDERS_URL}/{order_now(client, customer_headers, first, quantity=1)}",
                    headers=customer_headers,
                ).json()["total"]
            ),
            Decimal(
                client.get(
                    f"{ORDERS_URL}/{order_now(client, customer_headers, second, quantity=1)}",
                    headers=customer_headers,
                ).json()["total"]
            ),
        ]

        listing = client.get(ADMIN_CUSTOMERS_URL, headers=staff_headers).json()

        row = next(item for item in listing["items"] if item["email"] == "customer@example.com")
        assert row["order_count"] == 2
        assert Decimal(row["total_spent"]) == sum(totals)
        assert row["last_order_at"] is not None

    def test_a_customer_who_has_never_ordered_shows_zero(
        self, client: TestClient, customer_headers: dict[str, str], staff_headers: dict[str, str]
    ) -> None:
        """Absent from the aggregate is not absent from the list."""
        listing = client.get(ADMIN_CUSTOMERS_URL, headers=staff_headers).json()

        row = next(item for item in listing["items"] if item["email"] == "customer@example.com")
        assert row["order_count"] == 0
        assert Decimal(row["total_spent"]) == Decimal("0.00")
        assert row["last_order_at"] is None

    def test_cancelled_orders_are_not_counted_as_spend(
        self,
        client: TestClient,
        product: Product,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        number = order_now(client, customer_headers, product)
        client.post(f"{ORDERS_URL}/{number}/cancel", json={}, headers=customer_headers)

        listing = client.get(ADMIN_CUSTOMERS_URL, headers=staff_headers).json()

        row = next(item for item in listing["items"] if item["email"] == "customer@example.com")
        assert row["order_count"] == 0
        assert Decimal(row["total_spent"]) == Decimal("0.00")

    def test_staff_accounts_are_not_listed_as_customers(
        self, client: TestClient, customer_headers: dict[str, str], staff_headers: dict[str, str]
    ) -> None:
        listing = client.get(ADMIN_CUSTOMERS_URL, headers=staff_headers).json()

        emails = {item["email"] for item in listing["items"]}
        assert "customer@example.com" in emails
        assert "staff@example.com" not in emails

    def test_customers_can_be_searched(
        self,
        client: TestClient,
        db: Session,
        customer_headers: dict[str, str],
        staff_headers: dict[str, str],
    ) -> None:
        make_user(db, email="meena@example.com", role=RoleName.CUSTOMER, full_name="Meena R")

        found = client.get(
            ADMIN_CUSTOMERS_URL, params={"query": "meena"}, headers=staff_headers
        ).json()

        assert [item["email"] for item in found["items"]] == ["meena@example.com"]

    def test_no_password_material_is_returned(
        self, client: TestClient, customer_headers: dict[str, str], staff_headers: dict[str, str]
    ) -> None:
        body = client.get(ADMIN_CUSTOMERS_URL, headers=staff_headers).text

        assert "hashed_password" not in body
        assert "$2b$" not in body

    def test_customers_cannot_read_the_customer_list(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        assert client.get(ADMIN_CUSTOMERS_URL, headers=customer_headers).status_code == 403

    def test_anonymous_cannot_read_the_customer_list(self, client: TestClient) -> None:
        assert client.get(ADMIN_CUSTOMERS_URL).status_code == 401
