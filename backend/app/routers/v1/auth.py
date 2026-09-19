"""Authentication endpoints - `/api/v1/auth`."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.dependencies.auth import CurrentUser, DbSession
from app.schemas.auth import AuthResponse, LoginRequest, RefreshRequest
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new customer account",
)
def register(payload: UserCreate, db: DbSession) -> AuthResponse:
    """Create a customer account and return an initial token pair.

    The role is assigned server-side as CUSTOMER; it cannot be influenced by
    the request body.
    """
    user, tokens = AuthService(db).register(payload)
    return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse, summary="Customer login")
def login(payload: LoginRequest, db: DbSession) -> AuthResponse:
    user, tokens = AuthService(db).login(payload.email, payload.password)
    return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.post(
    "/admin/login",
    response_model=AuthResponse,
    summary="Admin / staff login for the desktop client",
)
def admin_login(payload: LoginRequest, db: DbSession) -> AuthResponse:
    """Sign in to the back-office. Customer accounts are rejected here."""
    user, tokens = AuthService(db).login_admin(payload.email, payload.password)
    return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.post("/refresh", response_model=AuthResponse, summary="Exchange a refresh token")
def refresh(payload: RefreshRequest, db: DbSession) -> AuthResponse:
    user, tokens = AuthService(db).refresh(payload.refresh_token)
    return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.get("/me", response_model=UserRead, summary="Current authenticated user")
def read_current_user(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/logout", response_model=MessageResponse, summary="Log out")
def logout(current_user: CurrentUser) -> MessageResponse:
    """Acknowledge a logout.

    Access tokens are stateless and remain cryptographically valid until they
    expire, so the client must discard both tokens from secure storage. The
    endpoint requires authentication and exists as the single place to hook in
    server-side token revocation (a `jti` blocklist) when refresh-token
    rotation is added.
    """
    return MessageResponse(message="Logged out successfully. Please discard your tokens.")
