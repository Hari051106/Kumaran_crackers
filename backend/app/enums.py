"""Shared domain vocabulary.

Plain enums with no framework dependencies, so models, schemas and services can
all import them without creating a circular or layering dependency.
"""

from __future__ import annotations

from enum import StrEnum


class RoleName(StrEnum):
    """System roles. Seeded into the `roles` table by the baseline migration."""

    ADMIN = "ADMIN"
    STAFF = "STAFF"
    CUSTOMER = "CUSTOMER"


class TokenType(StrEnum):
    """Discriminates JWT purposes so a refresh token cannot be used as an access token."""

    ACCESS = "access"
    REFRESH = "refresh"


class StockStatus(StrEnum):
    """Derived from stock level vs. the product's low-stock threshold.

    Computed, never stored: a stored copy would drift the moment stock changed
    through a path that forgot to update it.
    """

    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class ProductSort(StrEnum):
    """Sort orders the catalogue exposes to clients."""

    NEWEST = "newest"
    PRICE_LOW_TO_HIGH = "price_asc"
    PRICE_HIGH_TO_LOW = "price_desc"
    NAME_A_TO_Z = "name_asc"
    DISCOUNT = "discount"
    POPULARITY = "popularity"
