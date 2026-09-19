"""Authentication business logic.

This module owns every rule about *who may obtain a token*. Routers only
translate its results into HTTP.
"""

from __future__ import annotations

import functools
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.enums import RoleName, TokenType
from app.models.user import User
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.schemas.auth import TokenPair
from app.schemas.user import UserCreate
from app.utils.errors import (
    AuthenticationError,
    ConflictError,
    InactiveAccountError,
    InvalidTokenError,
)
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


@functools.cache
def _dummy_hash() -> str:
    """A throwaway digest used to equalise login timing.

    Without it, a failed lookup returns measurably faster than a wrong
    password, which lets an attacker enumerate registered e-mail addresses.
    """
    return hash_password("timing-equalisation-placeholder-0")


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)

    # ---- Registration -------------------------------------------------------
    def register(self, payload: UserCreate) -> tuple[User, TokenPair]:
        """Create a CUSTOMER account.

        The role is fixed server-side: a client can never register itself as
        ADMIN or STAFF regardless of what it sends.
        """
        if self.users.email_exists(payload.email):
            raise ConflictError("An account with this email address already exists.")
        if payload.phone and self.users.phone_exists(payload.phone):
            raise ConflictError("An account with this phone number already exists.")

        customer_role = self.roles.get_by_name(RoleName.CUSTOMER)
        if customer_role is None:
            # Reference data is seeded by the baseline migration; its absence is
            # a deployment fault, not a client error.
            raise RuntimeError(
                "The CUSTOMER role is missing. Run `alembic upgrade head` to seed roles."
            )

        user = User(
            email=payload.email,
            full_name=payload.full_name,
            phone=payload.phone,
            hashed_password=hash_password(payload.password),
            role_id=customer_role.id,
            is_active=True,
            is_verified=False,
            date_of_birth=payload.date_of_birth,
        )
        self.users.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user, self.issue_tokens(user)

    # ---- Login --------------------------------------------------------------
    def authenticate(self, email: str, password: str) -> User:
        """Verify credentials and return the user, or raise."""
        user = self.users.get_by_email(email)

        if user is None:
            # Spend the same time as a real verification, then fail generically.
            verify_password(password, _dummy_hash())
            raise AuthenticationError()

        if not verify_password(password, user.hashed_password):
            raise AuthenticationError()

        if not user.is_active:
            raise InactiveAccountError()

        return user

    def login(self, email: str, password: str) -> tuple[User, TokenPair]:
        user = self.authenticate(email, password)
        user.last_login_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(user)
        return user, self.issue_tokens(user)

    def login_admin(self, email: str, password: str) -> tuple[User, TokenPair]:
        """Login path for the admin desktop client.

        Customers are rejected here even with valid credentials, so a stolen
        customer password cannot open the back-office application.
        """
        user = self.authenticate(email, password)
        if not user.is_staff:
            raise AuthenticationError("This account is not permitted to sign in here.")
        user.last_login_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(user)
        return user, self.issue_tokens(user)

    # ---- Tokens -------------------------------------------------------------
    def issue_tokens(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(user.id, user.role.name),
            refresh_token=create_refresh_token(user.id, user.role.name),
            expires_in=settings.access_token_expire_minutes * 60,
        )

    def refresh(self, refresh_token: str) -> tuple[User, TokenPair]:
        """Exchange a valid refresh token for a fresh token pair."""
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)

        user = self.users.get(payload.subject)
        if user is None:
            raise InvalidTokenError()
        if not user.is_active:
            raise InactiveAccountError()

        return user, self.issue_tokens(user)
