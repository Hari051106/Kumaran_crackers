"""Product endpoints - `/api/v1/products`.

Catalogue reads are public. Writes require ADMIN; stock adjustments are open to
STAFF as well, since inventory is day-to-day operations work.

Visibility rule: a product is public only when the product *and* its category
are active. Staff see everything. This is applied in the service layer, so no
route can forget it.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import DbSession, OptionalUser, require_admin, require_staff
from app.enums import ProductSort
from app.schemas.common import MessageResponse, Page
from app.schemas.product import (
    ProductAdminDetail,
    ProductCreate,
    ProductDetail,
    ProductImageCreate,
    ProductListItem,
    ProductUpdate,
    StockAdjustment,
)
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


def _is_staff(user: object | None) -> bool:
    return user is not None and getattr(user, "is_staff", False)


# ---- Public catalogue -------------------------------------------------------
@router.get("", response_model=Page[ProductListItem], summary="Search the catalogue")
def list_products(
    db: DbSession,
    current_user: OptionalUser,
    query: str | None = Query(default=None, description="Match name, SKU or description."),
    category_id: int | None = Query(default=None, gt=0),
    category: str | None = Query(default=None, description="Category slug."),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    in_stock: bool = Query(default=False, description="Only products with stock left."),
    featured: bool = Query(default=False, description="Only featured products."),
    discounted: bool = Query(default=False, description="Only products priced below MRP."),
    include_inactive: bool = Query(default=False, description="Staff only."),
    sort: ProductSort = Query(default=ProductSort.NEWEST),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[ProductListItem]:
    """The catalogue query behind search, category browsing and filtering.

    `include_inactive` is honoured only for staff; anyone else receives the
    active catalogue regardless of what they send.
    """
    show_all = include_inactive and _is_staff(current_user)

    rows, total = ProductService(db).search(
        query=query,
        category_id=category_id,
        category_slug=category,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock,
        featured_only=featured,
        discounted_only=discounted,
        is_active=None if show_all else True,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return Page[ProductListItem].build(
        items=[ProductListItem.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/low-stock",
    response_model=list[ProductAdminDetail],
    dependencies=[Depends(require_staff)],
    summary="Products at or below their low-stock threshold (staff)",
)
def low_stock(
    db: DbSession, limit: int = Query(default=50, ge=1, le=200)
) -> list[ProductAdminDetail]:
    return [ProductAdminDetail.model_validate(p) for p in ProductService(db).low_stock(limit=limit)]


@router.get(
    "/out-of-stock",
    response_model=list[ProductAdminDetail],
    dependencies=[Depends(require_staff)],
    summary="Products with no stock left (staff)",
)
def out_of_stock(
    db: DbSession, limit: int = Query(default=50, ge=1, le=200)
) -> list[ProductAdminDetail]:
    return [
        ProductAdminDetail.model_validate(p) for p in ProductService(db).out_of_stock(limit=limit)
    ]


@router.get("/{slug}", response_model=ProductDetail, summary="Get a product by slug")
def get_product(slug: str, db: DbSession, current_user: OptionalUser) -> ProductDetail:
    """Full product detail. Inactive products are visible to staff only."""
    product = ProductService(db).get_by_slug(slug, active_only=not _is_staff(current_user))
    return ProductDetail.model_validate(product)


# ---- Admin ------------------------------------------------------------------
@router.post(
    "",
    response_model=ProductAdminDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Create a product (admin)",
)
def create_product(payload: ProductCreate, db: DbSession) -> ProductAdminDetail:
    """The SKU is generated when omitted, and the slug is always derived here."""
    return ProductAdminDetail.model_validate(ProductService(db).create(payload))


@router.get(
    "/id/{product_id}",
    response_model=ProductAdminDetail,
    dependencies=[Depends(require_staff)],
    summary="Get a product by id (staff)",
)
def get_product_by_id(product_id: int, db: DbSession) -> ProductAdminDetail:
    return ProductAdminDetail.model_validate(ProductService(db).get(product_id))


@router.patch(
    "/id/{product_id}",
    response_model=ProductAdminDetail,
    dependencies=[Depends(require_admin)],
    summary="Update a product (admin)",
)
def update_product(product_id: int, payload: ProductUpdate, db: DbSession) -> ProductAdminDetail:
    return ProductAdminDetail.model_validate(ProductService(db).update(product_id, payload))


@router.delete(
    "/id/{product_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_admin)],
    summary="Delete a product (admin)",
)
def delete_product(product_id: int, db: DbSession) -> MessageResponse:
    ProductService(db).delete(product_id)
    return MessageResponse(message="Product deleted.")


@router.post(
    "/id/{product_id}/activate",
    response_model=ProductAdminDetail,
    dependencies=[Depends(require_admin)],
    summary="Activate a product (admin)",
)
def activate_product(product_id: int, db: DbSession) -> ProductAdminDetail:
    return ProductAdminDetail.model_validate(
        ProductService(db).set_active(product_id, is_active=True)
    )


@router.post(
    "/id/{product_id}/deactivate",
    response_model=ProductAdminDetail,
    dependencies=[Depends(require_admin)],
    summary="Deactivate a product (admin)",
)
def deactivate_product(product_id: int, db: DbSession) -> ProductAdminDetail:
    """Hides a product from the catalogue without destroying its history."""
    return ProductAdminDetail.model_validate(
        ProductService(db).set_active(product_id, is_active=False)
    )


# ---- Inventory (staff) ------------------------------------------------------
@router.post(
    "/id/{product_id}/stock",
    response_model=ProductAdminDetail,
    dependencies=[Depends(require_staff)],
    summary="Set or adjust stock (staff)",
)
def adjust_stock(product_id: int, payload: StockAdjustment, db: DbSession) -> ProductAdminDetail:
    """A relative `delta` is applied atomically so concurrent edits cannot be lost."""
    return ProductAdminDetail.model_validate(ProductService(db).adjust_stock(product_id, payload))


# ---- Images (admin) ---------------------------------------------------------
@router.post(
    "/id/{product_id}/images",
    response_model=ProductAdminDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Add a product image (admin)",
)
def add_product_image(
    product_id: int, payload: ProductImageCreate, db: DbSession
) -> ProductAdminDetail:
    return ProductAdminDetail.model_validate(ProductService(db).add_image(product_id, payload))


@router.delete(
    "/id/{product_id}/images/{image_id}",
    response_model=ProductAdminDetail,
    dependencies=[Depends(require_admin)],
    summary="Remove a product image (admin)",
)
def delete_product_image(product_id: int, image_id: int, db: DbSession) -> ProductAdminDetail:
    return ProductAdminDetail.model_validate(ProductService(db).delete_image(product_id, image_id))
