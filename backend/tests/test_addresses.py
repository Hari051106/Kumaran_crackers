"""Tests for `/api/v1/addresses`."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import RoleName
from app.models.user import User
from tests.conftest import auth_header, login, make_user

ADDRESSES = "/api/v1/addresses"


def payload(**overrides: object) -> dict:
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


class TestAuthorization:
    def test_anonymous_cannot_list(self, client: TestClient) -> None:
        assert client.get(ADDRESSES).status_code == 401

    def test_anonymous_cannot_create(self, client: TestClient) -> None:
        assert client.post(ADDRESSES, json=payload()).status_code == 401

    def test_one_customer_cannot_read_anothers_address(
        self, client: TestClient, db: Session, customer_headers: dict[str, str]
    ) -> None:
        """Addresses are private. Guessing an id must not reveal one."""
        other = make_user(db, email="other@example.com", role=RoleName.CUSTOMER)
        created = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()

        other_headers = auth_header(login(client, other.email))
        response = client.get(f"{ADDRESSES}/{created['id']}", headers=other_headers)

        # 404 rather than 403: a probe cannot tell "not yours" from "no such row".
        assert response.status_code == 404

    def test_one_customer_cannot_delete_anothers_address(
        self, client: TestClient, db: Session, customer_headers: dict[str, str]
    ) -> None:
        other = make_user(db, email="other@example.com", role=RoleName.CUSTOMER)
        created = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()

        other_headers = auth_header(login(client, other.email))
        assert (
            client.delete(f"{ADDRESSES}/{created['id']}", headers=other_headers).status_code == 404
        )
        # Still there for its owner.
        assert (
            client.get(f"{ADDRESSES}/{created['id']}", headers=customer_headers).status_code == 200
        )


class TestCreate:
    def test_creates_an_address(self, client: TestClient, customer_headers: dict[str, str]) -> None:
        response = client.post(ADDRESSES, json=payload(), headers=customer_headers)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["city"] == "Chennai"
        assert body["pincode"] == "600017"

    def test_the_first_address_becomes_the_default(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        """So checkout always has something preselected."""
        body = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()
        assert body["is_default"] is True

    def test_a_later_address_is_not_default_unless_asked(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        client.post(ADDRESSES, json=payload(), headers=customer_headers)
        second = client.post(ADDRESSES, json=payload(area="Adyar"), headers=customer_headers).json()
        assert second["is_default"] is False

    def test_builds_a_single_line_address(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        body = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()
        assert body["single_line"] == "12A, Anna Salai, T Nagar, Chennai, Tamil Nadu, 600017"

    def test_normalises_whitespace_and_phone(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        body = client.post(
            ADDRESSES,
            json=payload(full_name="  Priya   Selvam  ", phone="+91 98765-43210"),
            headers=customer_headers,
        ).json()
        assert body["full_name"] == "Priya Selvam"
        assert body["phone"] == "9876543210"

    def test_rejects_a_bad_pincode(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        for bad in ["012345", "12345", "1234567", "abcdef"]:
            response = client.post(ADDRESSES, json=payload(pincode=bad), headers=customer_headers)
            assert response.status_code == 422, f"{bad} should be rejected"

    def test_rejects_a_bad_phone(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(ADDRESSES, json=payload(phone="12345"), headers=customer_headers)
        assert response.status_code == 422

    def test_rejects_blank_required_fields(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(ADDRESSES, json=payload(city="   "), headers=customer_headers)
        assert response.status_code == 422


class TestDefaults:
    def test_only_one_address_is_ever_default(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        first = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()
        second = client.post(
            ADDRESSES, json=payload(area="Adyar", is_default=True), headers=customer_headers
        ).json()

        listing = client.get(ADDRESSES, headers=customer_headers).json()
        defaults = [a for a in listing if a["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["id"] == second["id"]
        assert defaults[0]["id"] != first["id"]

    def test_promoting_an_address_demotes_the_previous_default(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        client.post(ADDRESSES, json=payload(), headers=customer_headers)
        second = client.post(ADDRESSES, json=payload(area="Adyar"), headers=customer_headers).json()

        promoted = client.post(f"{ADDRESSES}/{second['id']}/default", headers=customer_headers)
        assert promoted.status_code == 200
        assert promoted.json()["is_default"] is True

        defaults = [
            a for a in client.get(ADDRESSES, headers=customer_headers).json() if a["is_default"]
        ]
        assert len(defaults) == 1

    def test_the_default_is_listed_first(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        client.post(ADDRESSES, json=payload(), headers=customer_headers)
        second = client.post(ADDRESSES, json=payload(area="Adyar"), headers=customer_headers).json()
        client.post(f"{ADDRESSES}/{second['id']}/default", headers=customer_headers)

        listing = client.get(ADDRESSES, headers=customer_headers).json()
        assert listing[0]["id"] == second["id"]

    def test_cannot_simply_unset_the_only_default(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        """Leaving a customer with addresses but no default would break checkout."""
        created = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()
        response = client.patch(
            f"{ADDRESSES}/{created['id']}", json={"is_default": False}, headers=customer_headers
        )
        assert response.status_code == 422


class TestUpdateAndDelete:
    def test_updates_a_field(self, client: TestClient, customer_headers: dict[str, str]) -> None:
        created = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()
        response = client.patch(
            f"{ADDRESSES}/{created['id']}",
            json={"delivery_instructions": "Ring the bell twice"},
            headers=customer_headers,
        )
        assert response.status_code == 200
        assert response.json()["delivery_instructions"] == "Ring the bell twice"

    def test_a_partial_update_leaves_other_fields_alone(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        created = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()
        updated = client.patch(
            f"{ADDRESSES}/{created['id']}", json={"city": "Madurai"}, headers=customer_headers
        ).json()
        assert updated["city"] == "Madurai"
        assert updated["street"] == "Anna Salai"

    def test_deletes_an_address(self, client: TestClient, customer_headers: dict[str, str]) -> None:
        created = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()
        assert (
            client.delete(f"{ADDRESSES}/{created['id']}", headers=customer_headers).status_code
            == 200
        )
        assert (
            client.get(f"{ADDRESSES}/{created['id']}", headers=customer_headers).status_code == 404
        )

    def test_deleting_the_default_promotes_another(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        """A customer with addresses should never be left without a default."""
        first = client.post(ADDRESSES, json=payload(), headers=customer_headers).json()
        client.post(ADDRESSES, json=payload(area="Adyar"), headers=customer_headers)

        client.delete(f"{ADDRESSES}/{first['id']}", headers=customer_headers)

        remaining = client.get(ADDRESSES, headers=customer_headers).json()
        assert len(remaining) == 1
        assert remaining[0]["is_default"] is True

    def test_unknown_address_returns_404(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        assert client.get(f"{ADDRESSES}/999999", headers=customer_headers).status_code == 404


class TestStaffCanAlsoHoldAddresses:
    def test_a_staff_account_manages_its_own_addresses(
        self, client: TestClient, staff: User, staff_headers: dict[str, str]
    ) -> None:
        """Addresses belong to accounts, not to the CUSTOMER role."""
        response = client.post(ADDRESSES, json=payload(), headers=staff_headers)
        assert response.status_code == 201
