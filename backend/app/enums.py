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
