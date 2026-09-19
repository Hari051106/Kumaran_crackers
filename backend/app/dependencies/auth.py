"""Authentication and authorisation dependencies.

Authorisation is enforced *here*, on the server. The mobile and desktop clients
hide privileged screens for usability only - never for security.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import RoleName, TokenType
from app.models.user import User
from app.repositories.user import UserRepository
from app.utils.errors import InactiveAccountError, InvalidTokenError, PermissionDeniedError
from app.utils.security import decode_token

# auto_error=False lets us raise our own uniform error envelope instead of
# FastAPI's default "Not authenticated" shape.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[Session, Depends(get_db)]
BearerToken = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def get_current_user(credentials: BearerToken, db: DbSession) -> User:
    """Resolve the caller from the `Authorization: Bearer <token>` header."""
    if credentials is None or not credentials.credentials:
        raise InvalidTokenError("Authentication credentials were not provided.")

    payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)

    user = UserRepository(db).get(payload.subject)
    if user is None:
        raise InvalidTokenError()
    if not user.is_active:
        raise InactiveAccountError()

    # The role is re-read from the database rather than trusted from the token,
    # so a revoked privilege takes effect immediately instead of at token expiry.
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: RoleName) -> Callable[[User], User]:
    """Build a dependency that admits only the listed roles."""
    allowed_names = {role.value for role in allowed}

    def _guard(current_user: CurrentUser) -> User:
        if current_user.role.name not in allowed_names:
            raise PermissionDeniedError()
        return current_user

    return _guard


require_admin = require_roles(RoleName.ADMIN)
require_staff = require_roles(RoleName.ADMIN, RoleName.STAFF)
require_customer = require_roles(RoleName.CUSTOMER)

AdminUser = Annotated[User, Depends(require_admin)]
StaffUser = Annotated[User, Depends(require_staff)]
CustomerUser = Annotated[User, Depends(require_customer)]


def get_optional_user(credentials: BearerToken, db: DbSession) -> User | None:
    """Resolve the caller when a token is present, otherwise return None.

    Used by public catalogue endpoints that personalise their response for
    signed-in shoppers but stay readable to anonymous visitors.
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except (InvalidTokenError, InactiveAccountError):
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def client_ip(request: Request) -> str:
    """Best-effort client address for audit logging."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
