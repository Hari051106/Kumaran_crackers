"""Tests for `/api/v1/users` - self-service profile and admin administration."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import RoleName
from app.models.user import User
from tests.conftest import DEFAULT_PASSWORD, auth_header, login, make_user

USERS = "/api/v1/users"
ME = "/api/v1/users/me"
CHANGE_PASSWORD = "/api/v1/users/me/change-password"


class TestProfileSelfService:
    def test_get_my_profile(
        self, client: TestClient, customer: User, customer_headers: dict[str, str]
    ) -> None:
        response = client.get(ME, headers=customer_headers)
        assert response.status_code == 200
        assert response.json()["email"] == customer.email

    def test_profile_requires_authentication(self, client: TestClient) -> None:
        assert client.get(ME).status_code == 401

    def test_update_my_name_and_phone(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            ME,
            headers=customer_headers,
            json={"full_name": "Ravi  Kumar  S", "phone": "9876500011"},
        )
        assert response.status_code == 200
        body = response.json()
        # Whitespace inside the name is collapsed by the schema validator.
        assert body["full_name"] == "Ravi Kumar S"
        assert body["phone"] == "9876500011"

    def test_phone_prefix_is_normalised(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.patch(ME, headers=customer_headers, json={"phone": "+91 98765-00022"})
        assert response.status_code == 200
        assert response.json()["phone"] == "9876500022"

    def test_cannot_take_another_users_phone(
        self, client: TestClient, db: Session, customer_headers: dict[str, str]
    ) -> None:
        make_user(db, email="other@example.com", role=RoleName.CUSTOMER, phone="9998887776")
        response = client.patch(ME, headers=customer_headers, json={"phone": "9998887776"})
        assert response.status_code == 409

    def test_profile_update_cannot_change_role_or_status(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        """Unknown fields are ignored - a customer cannot promote itself."""
        response = client.patch(
            ME,
            headers=customer_headers,
            json={"full_name": "Still A Customer", "role": "ADMIN", "is_active": False},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["role"]["name"] == "CUSTOMER"
        assert body["is_active"] is True


class TestPasswordChange:
    def test_change_password_succeeds_and_new_password_works(
        self, client: TestClient, customer: User, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(
            CHANGE_PASSWORD,
            headers=customer_headers,
            json={"current_password": DEFAULT_PASSWORD, "new_password": "Brand@New99"},
        )
        assert response.status_code == 200

        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": customer.email, "password": "Brand@New99"},
            ).status_code
            == 200
        )

    def test_old_password_stops_working(
        self, client: TestClient, customer: User, customer_headers: dict[str, str]
    ) -> None:
        client.post(
            CHANGE_PASSWORD,
            headers=customer_headers,
            json={"current_password": DEFAULT_PASSWORD, "new_password": "Brand@New99"},
        )
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": customer.email, "password": DEFAULT_PASSWORD},
            ).status_code
            == 401
        )

    def test_wrong_current_password_is_rejected(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(
            CHANGE_PASSWORD,
            headers=customer_headers,
            json={"current_password": "Wrong@12345", "new_password": "Brand@New99"},
        )
        assert response.status_code == 401

    def test_reusing_the_current_password_is_rejected(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(
            CHANGE_PASSWORD,
            headers=customer_headers,
            json={"current_password": DEFAULT_PASSWORD, "new_password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 422

    def test_weak_new_password_is_rejected(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(
            CHANGE_PASSWORD,
            headers=customer_headers,
            json={"current_password": DEFAULT_PASSWORD, "new_password": "weak"},
        )
        assert response.status_code == 422


class TestAdminAuthorization:
    """The backend enforces roles; client-side route guards are cosmetic."""

    def test_customer_cannot_list_users(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.get(USERS, headers=customer_headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    def test_staff_cannot_list_users(
        self, client: TestClient, staff_headers: dict[str, str]
    ) -> None:
        """User administration is ADMIN-only, not merely staff-level."""
        assert client.get(USERS, headers=staff_headers).status_code == 403

    def test_anonymous_cannot_list_users(self, client: TestClient) -> None:
        assert client.get(USERS).status_code == 401

    def test_admin_can_list_users(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        response = client.get(USERS, headers=admin_headers)
        assert response.status_code == 200
        assert "items" in response.json()

    def test_customer_cannot_create_a_privileged_user(
        self, client: TestClient, customer_headers: dict[str, str]
    ) -> None:
        response = client.post(
            USERS,
            headers=customer_headers,
            json={
                "email": "sneaky@example.com",
                "full_name": "Sneaky",
                "password": DEFAULT_PASSWORD,
                "role": "ADMIN",
            },
        )
        assert response.status_code == 403

    def test_customer_cannot_read_another_users_record(
        self, client: TestClient, admin: User, customer_headers: dict[str, str]
    ) -> None:
        assert client.get(f"{USERS}/{admin.id}", headers=customer_headers).status_code == 403


class TestAdminUserManagement:
    def test_admin_creates_a_staff_account(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            USERS,
            headers=admin_headers,
            json={
                "email": "newstaff@example.com",
                "full_name": "New Staff",
                "password": DEFAULT_PASSWORD,
                "role": "STAFF",
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["role"]["name"] == "STAFF"

    def test_created_staff_can_sign_in_to_the_back_office(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        client.post(
            USERS,
            headers=admin_headers,
            json={
                "email": "newstaff@example.com",
                "full_name": "New Staff",
                "password": DEFAULT_PASSWORD,
                "role": "STAFF",
            },
        )
        response = client.post(
            "/api/v1/auth/admin/login",
            json={"email": "newstaff@example.com", "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 200

    def test_pagination_metadata_is_correct(
        self, client: TestClient, db: Session, admin_headers: dict[str, str]
    ) -> None:
        for index in range(5):
            make_user(db, email=f"bulk{index}@example.com", role=RoleName.CUSTOMER)

        response = client.get(f"{USERS}?page=1&page_size=2", headers=admin_headers)
        assert response.status_code == 200
        meta = response.json()["meta"]
        assert meta["page"] == 1
        assert meta["page_size"] == 2
        assert meta["total"] >= 6  # 5 bulk customers + the admin
        assert meta["has_next"] is True
        assert meta["has_previous"] is False
        assert len(response.json()["items"]) == 2

    def test_search_by_name(
        self, client: TestClient, db: Session, admin_headers: dict[str, str]
    ) -> None:
        make_user(db, email="deepa@example.com", role=RoleName.CUSTOMER, full_name="Deepa Nair")
        response = client.get(f"{USERS}?query=deepa", headers=admin_headers)
        assert response.status_code == 200
        emails = [item["email"] for item in response.json()["items"]]
        assert "deepa@example.com" in emails

    def test_filter_by_role(
        self, client: TestClient, staff: User, admin_headers: dict[str, str]
    ) -> None:
        response = client.get(f"{USERS}?role=STAFF", headers=admin_headers)
        assert response.status_code == 200
        roles = {item["role"]["name"] for item in response.json()["items"]}
        assert roles == {"STAFF"}

    def test_admin_can_deactivate_a_customer(
        self, client: TestClient, customer: User, admin_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            f"{USERS}/{customer.id}", headers=admin_headers, json={"is_active": False}
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_deactivated_customer_can_no_longer_log_in(
        self, client: TestClient, customer: User, admin_headers: dict[str, str]
    ) -> None:
        client.patch(f"{USERS}/{customer.id}", headers=admin_headers, json={"is_active": False})
        response = client.post(
            "/api/v1/auth/login",
            json={"email": customer.email, "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 403

    def test_admin_can_promote_a_customer_to_staff(
        self, client: TestClient, customer: User, admin_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            f"{USERS}/{customer.id}", headers=admin_headers, json={"role": "STAFF"}
        )
        assert response.status_code == 200
        assert response.json()["role"]["name"] == "STAFF"

    def test_admin_cannot_change_their_own_role(
        self, client: TestClient, admin: User, admin_headers: dict[str, str]
    ) -> None:
        """Guards against an admin accidentally removing the last admin."""
        response = client.patch(
            f"{USERS}/{admin.id}", headers=admin_headers, json={"role": "CUSTOMER"}
        )
        assert response.status_code == 422

    def test_admin_cannot_deactivate_themselves(
        self, client: TestClient, admin: User, admin_headers: dict[str, str]
    ) -> None:
        response = client.patch(
            f"{USERS}/{admin.id}", headers=admin_headers, json={"is_active": False}
        )
        assert response.status_code == 422

    def test_unknown_user_returns_404(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.get(f"{USERS}/999999", headers=admin_headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_promoted_user_immediately_gains_access(
        self, client: TestClient, customer: User, admin_headers: dict[str, str]
    ) -> None:
        """Role is read from the database per request, not from the stale token."""
        customer_token = auth_header(login(client, customer.email))
        assert client.get(USERS, headers=customer_token).status_code == 403

        client.patch(f"{USERS}/{customer.id}", headers=admin_headers, json={"role": "ADMIN"})

        # Same token, no re-login needed.
        assert client.get(USERS, headers=customer_token).status_code == 200
