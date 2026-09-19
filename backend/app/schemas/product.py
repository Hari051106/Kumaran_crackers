"""Product API schemas.

Money is exchanged as a Decimal, which Pydantic serialises to an exact JSON
string (e.g. "1250.00"). Clients must parse it into a decimal type - parsing
into a float reintroduces the rounding error the Decimal column exists to avoid.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import StockStatus
from app.schemas.category import CategorySummary

# Matches the Numeric(10, 2) columns in the database.
Money = Annotated[Decimal, Field(max_digits=10, decimal_places=2, ge=Decimal("0"))]


def _clean_text(value: str) -> str:
    return " ".join(value.split())


# ---- Images -----------------------------------------------------------------
class ProductImageCreate(BaseModel):
    image_url: str = Field(min_length=1, max_length=500)
    alt_text: str | None = Field(default=None, max_length=200)
    display_order: int = Field(default=0, ge=0)
    is_primary: bool = False


class ProductImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    alt_text: str | None = None
    display_order: int
    is_primary: bool


# ---- Products ---------------------------------------------------------------
class ProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    category_id: int = Field(gt=0)
    mrp: Money
    selling_price: Money
    stock_quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=10, ge=0)
    is_active: bool = True
    is_featured: bool = False

    @field_validator("name")
    @classmethod
    def _tidy_name(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if len(cleaned) < 2:
            raise ValueError("Product name must be at least 2 characters long.")
        return cleaned

    @model_validator(mode="after")
    def _selling_price_within_mrp(self) -> ProductBase:
        # Mirrors the database CHECK constraint so the client gets a readable
        # 422 instead of a 500 from a constraint violation.
        if self.selling_price > self.mrp:
            raise ValueError("Selling price cannot be greater than the MRP.")
        return self


class ProductCreate(ProductBase):
    """Admin product creation.

    `sku` is optional: when omitted the service generates a unique one. The
    slug is always derived server-side.
    """

    sku: str | None = Field(default=None, min_length=2, max_length=64)
    images: list[ProductImageCreate] = Field(default_factory=list)

    @field_validator("sku")
    @classmethod
    def _normalise_sku(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        return cleaned or None


class ProductUpdate(BaseModel):
    """Partial update. Every field is optional."""

    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    category_id: int | None = Field(default=None, gt=0)
    sku: str | None = Field(default=None, min_length=2, max_length=64)
    mrp: Money | None = None
    selling_price: Money | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    is_featured: bool | None = None

    @field_validator("name")
    @classmethod
    def _tidy_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _clean_text(value)
        if len(cleaned) < 2:
            raise ValueError("Product name must be at least 2 characters long.")
        return cleaned

    @field_validator("sku")
    @classmethod
    def _normalise_sku(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @model_validator(mode="after")
    def _selling_price_within_mrp(self) -> ProductUpdate:
        # Only checkable here when both arrive together; the service re-checks
        # against the stored value when only one is supplied.
        both_supplied = self.mrp is not None and self.selling_price is not None
        if both_supplied and self.selling_price > self.mrp:
            raise ValueError("Selling price cannot be greater than the MRP.")
        return self


class StockAdjustment(BaseModel):
    """Set or change stock. Exactly one of `set_to` / `delta` must be given."""

    set_to: int | None = Field(default=None, ge=0, description="Absolute new stock level.")
    delta: int | None = Field(default=None, description="Relative change, may be negative.")
    reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _exactly_one(self) -> StockAdjustment:
        if (self.set_to is None) == (self.delta is None):
            raise ValueError("Provide exactly one of 'set_to' or 'delta'.")
        return self


class ProductListItem(BaseModel):
    """Catalogue card projection - what a product grid needs, nothing more."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    sku: str
    category: CategorySummary
    mrp: Decimal
    selling_price: Decimal
    discount_percentage: Decimal
    discount_amount: Decimal
    stock_status: StockStatus
    in_stock: bool
    primary_image_url: str | None = None
    is_featured: bool
    is_active: bool


class ProductDetail(ProductListItem):
    """Full product view, including images and the exact stock level.

    `stock_quantity` is exposed so the mobile quantity selector can cap itself
    at what is actually available.
    """

    description: str | None = None
    stock_quantity: int
    images: list[ProductImageRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProductAdminDetail(ProductDetail):
    """Adds the operational fields only staff need to see."""

    low_stock_threshold: int
    sold_quantity: int
