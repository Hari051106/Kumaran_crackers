"""User endpoints - `/api/v1/users`.

Self-service routes live under `/users/me`; everything else requires ADMIN.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import CurrentUser, DbSession, require_admin
from app.enums import RoleName
from app.models.user import User
from app.schemas.common import MessageResponse, Page
from app.schemas.user import (
    AdminUserCreate,
    PasswordChange,
    UserAdminUpdate,
    UserRead,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


# ---- Self-service -----------------------------------------------------------
@router.get("/me", response_model=UserRead, summary="Get my profile")
def get_my_profile(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead, summary="Update my profile")
def update_my_profile(
    payload: UserUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserRead:
    user = UserService(db).update_profile(current_user, payload)
    return UserRead.model_validate(user)


@router.post(
    "/me/change-password",
    response_model=MessageResponse,
    summary="Change my password",
)
def change_my_password(
    payload: PasswordChange,
    current_user: CurrentUser,
    db: DbSession,
) -> MessageResponse:
    UserService(db).change_password(current_user, payload)
    return MessageResponse(message="Password updated successfully.")


# ---- Administration ---------------------------------------------------------
@router.get(
    "",
    response_model=Page[UserRead],
    dependencies=[Depends(require_admin)],
    summary="List users (admin)",
)
def list_users(
    db: DbSession,
    query: str | None = Query(default=None, description="Match name, email or phone."),
    role: RoleName | None = Query(default=None, description="Filter by role."),
    is_active: bool | None = Query(default=None, description="Filter by account status."),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[UserRead]:
    rows, total = UserService(db).search(
        query=query,
        role_name=role.value if role else None,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return Page[UserRead].build(
        items=[UserRead.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Create a user with an explicit role (admin)",
)
def create_user(payload: AdminUserCreate, db: DbSession) -> UserRead:
    user = UserService(db).create_user(payload)
    return UserRead.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_admin)],
    summary="Get a user by id (admin)",
)
def get_user(user_id: int, db: DbSession) -> UserRead:
    return UserRead.model_validate(UserService(db).get(user_id))


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update a user's role or status (admin)",
)
def admin_update_user(
    user_id: int,
    payload: UserAdminUpdate,
    db: DbSession,
    actor: User = Depends(require_admin),
) -> UserRead:
    user = UserService(db).admin_update(user_id, payload, actor=actor)
    return UserRead.model_validate(user)
