"""End-to-end tests for the `/api/v1/auth` endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import RoleName
from app.models.user import User
from tests.conftest import DEFAULT_PASSWORD, auth_header, login, make_user

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ADMIN_LOGIN = "/api/v1/auth/admin/login"
REFRESH = "/api/v1/auth/refresh"
ME = "/api/v1/auth/me"


def _registration_payload(**overrides: object) -> dict:
    payload = {
        "email": "new.customer@example.com",
        "full_name": "New Customer",
        "phone": "9812345678",
        "password": DEFAULT_PASSWORD,
    }
    payload.update(overrides)
    return payload


class TestRegistration:
    def test_registers_a_customer_and_returns_tokens(self, client: TestClient) -> None:
        response = client.post(REGISTER, json=_registration_payload())

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["user"]["email"] == "new.customer@example.com"
        assert body["user"]["role"]["name"] == "CUSTOMER"
        assert body["tokens"]["access_token"]
        assert body["tokens"]["refresh_token"]
        assert body["tokens"]["token_type"] == "bearer"

    def test_response_never_contains_the_password(self, client: TestClient) -> None:
        response = client.post(REGISTER, json=_registration_payload())

        # Neither the plaintext nor the digest may appear anywhere in the body.
        assert DEFAULT_PASSWORD not in response.text
        assert "$2b$" not in response.text
        user_block = response.json()["user"]
        assert "password" not in user_block
        assert "hashed_password" not in user_block

    def test_password_is_stored_hashed(self, client: TestClient, db: Session) -> None:
        client.post(REGISTER, json=_registration_payload())
        user = db.query(User).filter(User.email == "new.customer@example.com").one()
        assert user.hashed_password != DEFAULT_PASSWORD
        assert user.hashed_password.startswith("$2b$")

    def test_email_is_normalised_to_lowercase(self, client: TestClient) -> None:
        response = client.post(REGISTER, json=_registration_payload(email="MiXeD@Example.COM"))
        assert response.status_code == 201
        assert response.json()["user"]["email"] == "mixed@example.com"

    def test_duplicate_email_is_rejected(self, client: TestClient, customer: User) -> None:
        response = client.post(REGISTER, json=_registration_payload(email=customer.email))
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    def test_duplicate_email_differing_in_case_is_rejected(
        self, client: TestClient, customer: User
    ) -> None:
        response = client.post(REGISTER, json=_registration_payload(email=customer.email.upper()))
        assert response.status_code == 409

    def test_duplicate_phone_is_rejected(self, client: TestClient, customer: User) -> None:
        response = client.post(REGISTER, json=_registration_payload(phone=customer.phone))
        assert response.status_code == 409

    def test_client_cannot_self_assign_the_admin_role(self, client: TestClient) -> None:
        """A privilege-escalation attempt must be ignored, not honoured."""
        response = client.post(REGISTER, json=_registration_payload(role="ADMIN"))
        assert response.status_code == 201
        assert response.json()["user"]["role"]["name"] == "CUSTOMER"

    def test_weak_password_without_digit_is_rejected(self, client: TestClient) -> None:
        response = client.post(REGISTER, json=_registration_payload(password="onlyletters"))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_short_password_is_rejected(self, client: TestClient) -> None:
        response = client.post(REGISTER, json=_registration_payload(password="Ab1"))
        assert response.status_code == 422

    def test_invalid_email_is_rejected(self, client: TestClient) -> None:
        response = client.post(REGISTER, json=_registration_payload(email="not-an-email"))
        assert response.status_code == 422

    def test_invalid_phone_is_rejected(self, client: TestClient) -> None:
        response = client.post(REGISTER, json=_registration_payload(phone="12345"))
        assert response.status_code == 422


class TestLogin:
    def test_valid_credentials_return_tokens(self, client: TestClient, customer: User) -> None:
        response = client.post(LOGIN, json={"email": customer.email, "password": DEFAULT_PASSWORD})
        assert response.status_code == 200, response.text
        assert response.json()["tokens"]["access_token"]

    def test_login_is_case_insensitive_on_email(self, client: TestClient, customer: User) -> None:
        response = client.post(
            LOGIN, json={"email": customer.email.upper(), "password": DEFAULT_PASSWORD}
        )
        assert response.status_code == 200

    def test_wrong_password_is_rejected(self, client: TestClient, customer: User) -> None:
        response = client.post(LOGIN, json={"email": customer.email, "password": "Wrong@12345"})
        assert response.status_code == 401

    def test_unknown_email_gives_the_same_error_as_a_wrong_password(
        self, client: TestClient, customer: User
    ) -> None:
        """Distinct messages would let an attacker enumerate registered accounts."""
        unknown = client.post(
            LOGIN, json={"email": "nobody@example.com", "password": DEFAULT_PASSWORD}
        )
        wrong_password = client.post(
            LOGIN, json={"email": customer.email, "password": "Wrong@12345"}
        )
        assert unknown.status_code == wrong_password.status_code == 401
        assert unknown.json()["error"] == wrong_password.json()["error"]

    def test_deactivated_account_cannot_log_in(self, client: TestClient, db: Session) -> None:
        user = make_user(db, email="banned@example.com", role=RoleName.CUSTOMER, is_active=False)
        response = client.post(LOGIN, json={"email": user.email, "password": DEFAULT_PASSWORD})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "inactive_account"

    def test_login_records_last_login_timestamp(
        self, client: TestClient, customer: User, db: Session
    ) -> None:
        assert customer.last_login_at is None
        client.post(LOGIN, json={"email": customer.email, "password": DEFAULT_PASSWORD})
        db.refresh(customer)
        assert customer.last_login_at is not None


class TestAdminLogin:
    def test_admin_can_sign_in_to_the_back_office(self, client: TestClient, admin: User) -> None:
        response = client.post(
            ADMIN_LOGIN, json={"email": admin.email, "password": DEFAULT_PASSWORD}
        )
        assert response.status_code == 200
        assert response.json()["user"]["role"]["name"] == "ADMIN"

    def test_staff_can_sign_in_to_the_back_office(self, client: TestClient, staff: User) -> None:
        response = client.post(
            ADMIN_LOGIN, json={"email": staff.email, "password": DEFAULT_PASSWORD}
        )
        assert response.status_code == 200

    def test_customer_is_rejected_even_with_valid_credentials(
        self, client: TestClient, customer: User
    ) -> None:
        """A stolen customer password must not open the admin application."""
        response = client.post(
            ADMIN_LOGIN, json={"email": customer.email, "password": DEFAULT_PASSWORD}
        )
        assert response.status_code == 401


class TestRefresh:
    def test_refresh_token_yields_a_new_pair(self, client: TestClient, customer: User) -> None:
        tokens = client.post(
            LOGIN, json={"email": customer.email, "password": DEFAULT_PASSWORD}
        ).json()["tokens"]

        response = client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
        assert response.status_code == 200
        assert response.json()["tokens"]["access_token"]

    def test_access_token_cannot_be_used_to_refresh(
        self, client: TestClient, customer: User
    ) -> None:
        tokens = client.post(
            LOGIN, json={"email": customer.email, "password": DEFAULT_PASSWORD}
        ).json()["tokens"]

        response = client.post(REFRESH, json={"refresh_token": tokens["access_token"]})
        assert response.status_code == 401

    def test_garbage_refresh_token_is_rejected(self, client: TestClient) -> None:
        response = client.post(REFRESH, json={"refresh_token": "not.a.token"})
        assert response.status_code == 401


class TestCurrentUser:
    def test_returns_the_authenticated_user(self, client: TestClient, customer: User) -> None:
        response = client.get(ME, headers=auth_header(login(client, customer.email)))
        assert response.status_code == 200
        assert response.json()["email"] == customer.email

    def test_requires_a_token(self, client: TestClient) -> None:
        assert client.get(ME).status_code == 401

    def test_rejects_a_malformed_token(self, client: TestClient) -> None:
        response = client.get(ME, headers=auth_header("garbage"))
        assert response.status_code == 401

    def test_deactivating_an_account_invalidates_its_live_token(
        self, client: TestClient, customer: User, db: Session
    ) -> None:
        """The role/status is re-read per request, so revocation is immediate."""
        headers = auth_header(login(client, customer.email))
        assert client.get(ME, headers=headers).status_code == 200

        customer.is_active = False
        db.commit()

        assert client.get(ME, headers=headers).status_code == 403


class TestLogout:
    def test_logout_requires_authentication(self, client: TestClient) -> None:
        assert client.post("/api/v1/auth/logout").status_code == 401

    def test_logout_acknowledges(self, client: TestClient, customer: User) -> None:
        response = client.post(
            "/api/v1/auth/logout", headers=auth_header(login(client, customer.email))
        )
        assert response.status_code == 200
        assert "message" in response.json()
