"""Schemas shared across every API module."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    """The single error envelope every failing endpoint returns."""

    error: ErrorDetail


class MessageResponse(BaseModel):
    """Simple acknowledgement for endpoints with no resource to return."""

    message: str


class PaginationMeta(BaseModel):
    total: int = Field(description="Total rows matching the query, ignoring pagination.")
    page: int = Field(description="Current 1-based page number.")
    page_size: int = Field(description="Rows requested per page.")
    total_pages: int = Field(description="Total number of pages available.")
    has_next: bool
    has_previous: bool


class Page(BaseModel, Generic[T]):
    """Envelope for every paginated list endpoint."""

    items: list[T]
    meta: PaginationMeta

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> Page[T]:
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(
            items=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_previous=page > 1,
            ),
        )
