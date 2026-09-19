"""Password hashing and JSON Web Token helpers.

bcrypt is used directly (rather than through passlib) to avoid the well-known
passlib/bcrypt 4.x backend-detection breakage, and to keep the 72-byte limit
explicit instead of silently truncating long passwords.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings
from app.enums import TokenType
from app.utils.errors import InvalidTokenError

# bcrypt only consumes the first 72 bytes of a password. Silently truncating
# would mean two different long passwords could authenticate each other, so we
# reject anything longer instead.
BCRYPT_MAX_BYTES = 72


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds what bcrypt can meaningfully hash."""


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Validated contents of a decoded JWT."""

    subject: int
    role: str
    token_type: TokenType
    expires_at: datetime
    jti: str


def hash_password(plain_password: str) -> str:
    """Return a salted bcrypt digest of `plain_password`."""
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > BCRYPT_MAX_BYTES:
        raise PasswordTooLongError(
            f"Password must not exceed {BCRYPT_MAX_BYTES} bytes when UTF-8 encoded."
        )
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time check of a candidate password against a stored digest."""
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > BCRYPT_MAX_BYTES:
        # Cannot match any hash we produced - reject without touching bcrypt.
        return False
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed/corrupt digest in the database - never authenticate.
        return False


def _create_token(
    subject: int,
    role: str,
    token_type: TokenType,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "role": role,
        "type": token_type.value,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: int, role: str) -> str:
    """Short-lived token presented on every authenticated request."""
    return _create_token(
        subject,
        role,
        TokenType.ACCESS,
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: int, role: str) -> str:
    """Long-lived token whose only purpose is minting new access tokens."""
    return _create_token(
        subject,
        role,
        TokenType.REFRESH,
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, *, expected_type: TokenType) -> TokenPayload:
    """Decode and validate a JWT.

    `expected_type` is enforced so a refresh token can never be replayed as an
    access token (or vice versa).
    """
    try:
        raw = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("The authentication token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc

    if raw.get("type") != expected_type.value:
        raise InvalidTokenError(f"Expected a {expected_type.value} token.")

    subject = raw.get("sub")
    role = raw.get("role")
    if subject is None or role is None:
        raise InvalidTokenError()

    try:
        subject_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError() from exc

    return TokenPayload(
        subject=subject_id,
        role=role,
        token_type=expected_type,
        expires_at=datetime.fromtimestamp(raw["exp"], tz=UTC),
        jti=raw.get("jti", ""),
    )
