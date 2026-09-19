"""Category endpoints - `/api/v1/categories`.

Reads are public so the mobile app can render the home screen before sign-in.
Writes require ADMIN.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import DbSession, OptionalUser, require_admin
from app.schemas.category import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    CategoryWithCount,
)
from app.schemas.common import MessageResponse
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])


# ---- Public -----------------------------------------------------------------
@router.get("", response_model=list[CategoryWithCount], summary="List categories")
def list_categories(
    db: DbSession,
    current_user: OptionalUser,
    include_inactive: bool = Query(
        default=False,
        description="Include deactivated categories. Honoured for staff only.",
    ),
) -> list[CategoryWithCount]:
    """Categories for the storefront, each with its live product count.

    Categories are data, not code: the mobile app never hardcodes this list.

    `include_inactive` is honoured only for signed-in staff. A customer or an
    anonymous caller asking for it still receives the active list, so a
    deactivated category cannot be discovered by guessing a query parameter.
    """
    may_see_inactive = current_user is not None and current_user.is_staff
    active_only = not (include_inactive and may_see_inactive)

    pairs = CategoryService(db).list_with_counts(active_only=active_only)
    return [
        CategoryWithCount(**CategoryRead.model_validate(category).model_dump(), product_count=count)
        for category, count in pairs
    ]


@router.get("/{slug}", response_model=CategoryRead, summary="Get a category by slug")
def get_category(slug: str, db: DbSession, current_user: OptionalUser) -> CategoryRead:
    """Staff may fetch a deactivated category; everyone else gets a 404."""
    may_see_inactive = current_user is not None and current_user.is_staff
    category = CategoryService(db).get_by_slug(slug, active_only=not may_see_inactive)
    return CategoryRead.model_validate(category)


# ---- Admin ------------------------------------------------------------------
@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Create a category (admin)",
)
def create_category(payload: CategoryCreate, db: DbSession) -> CategoryRead:
    return CategoryRead.model_validate(CategoryService(db).create(payload))


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    dependencies=[Depends(require_admin)],
    summary="Update a category (admin)",
)
def update_category(category_id: int, payload: CategoryUpdate, db: DbSession) -> CategoryRead:
    return CategoryRead.model_validate(CategoryService(db).update(category_id, payload))


@router.delete(
    "/{category_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_admin)],
    summary="Delete a category (admin)",
)
def delete_category(category_id: int, db: DbSession) -> MessageResponse:
    """Refused if the category still holds products - deactivate it instead."""
    CategoryService(db).delete(category_id)
    return MessageResponse(message="Category deleted.")
