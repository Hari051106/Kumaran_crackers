"""Category API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_text(value: str) -> str:
    return " ".join(value.split())


class CategoryBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=500)
    display_order: int = Field(default=0, ge=0, description="Lower values appear first.")
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _tidy_name(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if len(cleaned) < 2:
            raise ValueError("Category name must be at least 2 characters long.")
        return cleaned


class CategoryCreate(CategoryBase):
    """The slug is derived from the name server-side, never supplied by a client."""


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=500)
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _tidy_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _clean_text(value)
        if len(cleaned) < 2:
            raise ValueError("Category name must be at least 2 characters long.")
        return cleaned


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    display_order: int
    is_active: bool
    created_at: datetime


class CategorySummary(BaseModel):
    """Minimal projection nested inside a product response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class CategoryWithCount(CategoryRead):
    """Category plus how many active products it holds - used by admin lists."""

    product_count: int = 0
