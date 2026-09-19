"""Pydantic request/response schemas."""

from app.schemas.auth import AuthResponse, LoginRequest, RefreshRequest, TokenPair
from app.schemas.category import (
    CategoryCreate,
    CategoryRead,
    CategorySummary,
    CategoryUpdate,
    CategoryWithCount,
)
from app.schemas.common import ErrorResponse, MessageResponse, Page, PaginationMeta
from app.schemas.product import (
    ProductAdminDetail,
    ProductCreate,
    ProductDetail,
    ProductImageCreate,
    ProductImageRead,
    ProductListItem,
    ProductUpdate,
    StockAdjustment,
)
from app.schemas.user import (
    AdminUserCreate,
    PasswordChange,
    RoleRead,
    UserAdminUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)

__all__ = [
    "AdminUserCreate",
    "AuthResponse",
    "CategoryCreate",
    "CategoryRead",
    "CategorySummary",
    "CategoryUpdate",
    "CategoryWithCount",
    "ErrorResponse",
    "LoginRequest",
    "MessageResponse",
    "Page",
    "PaginationMeta",
    "PasswordChange",
    "ProductAdminDetail",
    "ProductCreate",
    "ProductDetail",
    "ProductImageCreate",
    "ProductImageRead",
    "ProductListItem",
    "ProductUpdate",
    "RefreshRequest",
    "RoleRead",
    "StockAdjustment",
    "TokenPair",
    "UserAdminUpdate",
    "UserCreate",
    "UserRead",
    "UserUpdate",
]
