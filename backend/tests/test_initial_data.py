"""Tests for the first-admin bootstrap script.

These cover the misconfiguration that silently produced an unusable admin
account: an address the API rejects at login must fail the bootstrap loudly.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.initial_data import create_first_admin
from app.models.user import User
from tests.conftest import DEFAULT_PASSWORD


@pytest.fixture
def bootstrap_env(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the script's own session factory at the test transaction."""
    factory = sessionmaker(
        bind=db.get_bind(),
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    monkeypatch.setattr("app.initial_data.SessionLocal", factory)
    monkeypatch.setattr(settings, "first_admin_email", "boot.admin@kumarancrackers.com")
    monkeypatch.setattr(settings, "first_admin_password", DEFAULT_PASSWORD)
    monkeypatch.setattr(settings, "first_admin_full_name", "Boot Admin")


def _find(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).one_or_none()


class TestBootstrapAdmin:
    def test_creates_an_admin_account(self, db: Session, bootstrap_env: None) -> None:
        assert create_first_admin() == 0

        admin = _find(db, "boot.admin@kumarancrackers.com")
        assert admin is not None
        assert admin.role.name == "ADMIN"
        assert admin.is_active is True
        assert admin.is_verified is True

    def test_password_is_hashed_not_stored_plain(self, db: Session, bootstrap_env: None) -> None:
        create_first_admin()
        admin = _find(db, "boot.admin@kumarancrackers.com")
        assert admin is not None
        assert admin.hashed_password != DEFAULT_PASSWORD
        assert admin.hashed_password.startswith("$2b$")

    def test_is_idempotent_and_does_not_reset_the_password(
        self, db: Session, bootstrap_env: None
    ) -> None:
        assert create_first_admin() == 0
        admin = _find(db, "boot.admin@kumarancrackers.com")
        assert admin is not None
        original_digest = admin.hashed_password

        assert create_first_admin() == 0

        db.refresh(admin)
        assert admin.hashed_password == original_digest
        assert db.query(User).filter(User.email == "boot.admin@kumarancrackers.com").count() == 1

    def test_created_admin_can_actually_log_in(
        self, client, db: Session, bootstrap_env: None
    ) -> None:
        """The whole point of the bootstrap: the account must be usable."""
        create_first_admin()

        response = client.post(
            "/api/v1/auth/admin/login",
            json={
                "email": "boot.admin@kumarancrackers.com",
                "password": DEFAULT_PASSWORD,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["user"]["role"]["name"] == "ADMIN"


class TestBootstrapValidation:
    def test_missing_password_aborts(
        self, bootstrap_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "first_admin_password", None)
        assert create_first_admin() == 1

    def test_reserved_domain_is_refused(
        self, db: Session, bootstrap_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`.local` is rejected by EmailStr, so the account could never log in."""
        monkeypatch.setattr(settings, "first_admin_email", "admin@kumarancrackers.local")

        assert create_first_admin() == 1
        assert _find(db, "admin@kumarancrackers.local") is None

    def test_malformed_email_is_refused(
        self, db: Session, bootstrap_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "first_admin_email", "not-an-email")
        assert create_first_admin() == 1
