"""User and Role API schemas.

ORM objects are never returned directly - every response goes through one of
these models so the password digest can never leak.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.enums import RoleName
from app.utils.security import BCRYPT_MAX_BYTES

# Indian mobile numbers, optionally with a +91 / 0 prefix.
PHONE_PATTERN = re.compile(r"^(?:\+91[-\s]?|0)?[6-9]\d{9}$")

PASSWORD_MIN_LENGTH = 8


def _validate_password_strength(value: str) -> str:
    """Enforce a baseline password policy."""
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must not exceed {BCRYPT_MAX_BYTES} bytes when encoded.")
    if not any(char.isalpha() for char in value):
        raise ValueError("Password must contain at least one letter.")
    if not any(char.isdigit() for char in value):
        raise ValueError("Password must contain at least one digit.")
    return value


def _normalise_phone(value: str | None) -> str | None:
    """Strip formatting and reduce every accepted form to 10 digits."""
    if value is None:
        return None
    candidate = value.strip().replace(" ", "").replace("-", "")
    if not candidate:
        return None
    if not PHONE_PATTERN.match(candidate):
        raise ValueError("Enter a valid 10-digit Indian mobile number.")
    return candidate[-10:]


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, value: str) -> str:
        # Stored lower-cased so the unique index is case-insensitive in practice.
        return value.strip().lower()

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _clean_phone(cls, value: str | None) -> str | None:
        return _normalise_phone(value)


class UserCreate(UserBase):
    """Self-service customer registration payload."""

    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=BCRYPT_MAX_BYTES)
    date_of_birth: date | None = None

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class AdminUserCreate(UserCreate):
    """Admin-initiated account creation - may assign a privileged role."""

    role: RoleName = RoleName.CUSTOMER


class UserUpdate(BaseModel):
    """Partial update of the caller's own profile."""

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _clean_phone(cls, value: str | None) -> str | None:
        return _normalise_phone(value)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=BCRYPT_MAX_BYTES)

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class UserRead(BaseModel):
    """Safe public projection of a user. Note: no password field."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    phone: str | None = None
    role: RoleRead
    is_active: bool
    is_verified: bool
    date_of_birth: date | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class UserAdminUpdate(BaseModel):
    """Fields an administrator may change on someone else's account."""

    is_active: bool | None = None
    is_verified: bool | None = None
    role: RoleName | None = None
