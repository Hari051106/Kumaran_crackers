"""Shared pytest fixtures.

The suite runs against a real PostgreSQL database (not SQLite) so that server
defaults, constraints and cascade behaviour are exercised exactly as they are
in production. The schema is built by running the Alembic migrations, which
means every test run also verifies that the migrations themselves are valid.
"""

from __future__ import annotations

# NOTE: the environment must be redirected at the test database *before* any
# `app.*` module is imported, because `app.database` builds the engine at
# import time from the settings singleton.
import os
from pathlib import Path

from dotenv import dotenv_values

BACKEND_ROOT = Path(__file__).resolve().parents[1]

_env = {**dotenv_values(BACKEND_ROOT / ".env"), **os.environ}
_test_db_url = _env.get("TEST_DATABASE_URL")
if not _test_db_url:
    raise RuntimeError("TEST_DATABASE_URL is not configured. Copy .env.example to .env and set it.")

os.environ["DATABASE_URL"] = _test_db_url
os.environ["APP_ENV"] = "development"
# Keep SQL echo off so test output stays readable.
os.environ["DEBUG"] = "false"
os.environ.setdefault("SECRET_KEY", _env.get("SECRET_KEY", "test-secret-" + "x" * 40))

# ruff: noqa: E402 - imports must follow the environment redirection above.
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config
from app.database import engine, get_db
from app.enums import RoleName
from app.main import create_app
from app.models.role import Role
from app.models.user import User
from app.utils.security import hash_password

DEFAULT_PASSWORD = "Test@12345"


# ---- Schema lifecycle -------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> Generator[None, None, None]:
    """Rebuild the test schema once per session by running the migrations."""
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    os.environ["ALEMBIC_DATABASE_URL"] = os.environ["DATABASE_URL"]
    command.upgrade(alembic_cfg, "head")

    yield

    engine.dispose()


# ---- Per-test transaction isolation ----------------------------------------
@pytest.fixture
def db(_prepare_database: None) -> Generator[Session, None, None]:
    """A session whose writes are rolled back when the test finishes.

    `join_transaction_mode="create_savepoint"` turns the service layer's
    `commit()` calls into savepoint releases, so production code runs unchanged
    while the outer transaction still rolls everything back.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """A TestClient bound to the same rolled-back transaction as `db`."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---- Reference data ---------------------------------------------------------
def _role(db: Session, name: RoleName) -> Role:
    role = db.query(Role).filter(Role.name == name.value).one_or_none()
    if role is None:  # pragma: no cover - would mean the seed migration failed
        raise AssertionError(f"Role {name} was not seeded by the baseline migration.")
    return role


# ---- User factories ---------------------------------------------------------
def make_user(
    db: Session,
    *,
    email: str,
    role: RoleName,
    password: str = DEFAULT_PASSWORD,
    full_name: str = "Test User",
    phone: str | None = None,
    is_active: bool = True,
) -> User:
    """Insert a user with a real bcrypt digest, as the application would."""
    user = User(
        email=email.lower(),
        full_name=full_name,
        phone=phone,
        hashed_password=hash_password(password),
        role_id=_role(db, role).id,
        is_active=is_active,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def customer(db: Session) -> User:
    return make_user(
        db,
        email="customer@example.com",
        role=RoleName.CUSTOMER,
        full_name="Ravi Kumar",
        phone="9876543210",
    )


@pytest.fixture
def staff(db: Session) -> User:
    return make_user(db, email="staff@example.com", role=RoleName.STAFF, full_name="Staff Member")


@pytest.fixture
def admin(db: Session) -> User:
    return make_user(db, email="admin@example.com", role=RoleName.ADMIN, full_name="Kumaran Admin")


# ---- Auth helpers -----------------------------------------------------------
def login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> str:
    """Log in through the real endpoint and return the access token."""
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["tokens"]["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def customer_headers(client: TestClient, customer: User) -> dict[str, str]:
    return auth_header(login(client, customer.email))


@pytest.fixture
def staff_headers(client: TestClient, staff: User) -> dict[str, str]:
    return auth_header(login(client, staff.email))


@pytest.fixture
def admin_headers(client: TestClient, admin: User) -> dict[str, str]:
    return auth_header(login(client, admin.email))
