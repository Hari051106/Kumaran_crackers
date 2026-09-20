"""Delivery address schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.user import PHONE_PATTERN

# Six digits, never starting with zero - matches the database CHECK constraint.
PINCODE_PATTERN = re.compile(r"^[1-9][0-9]{5}$")


def _tidy(value: str) -> str:
    return " ".join(value.split())


class AddressBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(max_length=20)
    house_number: str = Field(min_length=1, max_length=100, description="Door or flat number.")
    street: str = Field(min_length=1, max_length=200)
    area: str = Field(min_length=1, max_length=150)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    pincode: str = Field(min_length=6, max_length=6)
    delivery_instructions: str | None = Field(default=None, max_length=500)
    is_default: bool = False

    @field_validator("full_name", "house_number", "street", "area", "city", "state", mode="after")
    @classmethod
    def _collapse_whitespace(cls, value: str) -> str:
        cleaned = _tidy(value)
        if not cleaned:
            raise ValueError("This field cannot be blank.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        candidate = value.strip().replace(" ", "").replace("-", "")
        if not PHONE_PATTERN.match(candidate):
            raise ValueError("Enter a valid 10-digit Indian mobile number.")
        return candidate[-10:]

    @field_validator("pincode")
    @classmethod
    def _check_pincode(cls, value: str) -> str:
        candidate = value.strip()
        if not PINCODE_PATTERN.match(candidate):
            raise ValueError("Enter a valid 6-digit PIN code.")
        return candidate

    @field_validator("delivery_instructions")
    @classmethod
    def _tidy_instructions(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AddressCreate(AddressBase):
    """A new delivery address for the signed-in customer."""


class AddressUpdate(BaseModel):
    """Partial update. Every field is optional."""

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    house_number: str | None = Field(default=None, min_length=1, max_length=100)
    street: str | None = Field(default=None, min_length=1, max_length=200)
    area: str | None = Field(default=None, min_length=1, max_length=150)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    pincode: str | None = Field(default=None, min_length=6, max_length=6)
    delivery_instructions: str | None = Field(default=None, max_length=500)
    is_default: bool | None = None

    @field_validator("full_name", "house_number", "street", "area", "city", "state", mode="after")
    @classmethod
    def _collapse_whitespace(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _tidy(value)
        if not cleaned:
            raise ValueError("This field cannot be blank.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip().replace(" ", "").replace("-", "")
        if not PHONE_PATTERN.match(candidate):
            raise ValueError("Enter a valid 10-digit Indian mobile number.")
        return candidate[-10:]

    @field_validator("pincode")
    @classmethod
    def _check_pincode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        if not PINCODE_PATTERN.match(candidate):
            raise ValueError("Enter a valid 6-digit PIN code.")
        return candidate


class AddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone: str
    house_number: str
    street: str
    area: str
    city: str
    state: str
    pincode: str
    delivery_instructions: str | None = None
    is_default: bool
    created_at: datetime

    #: The whole address on one line, for summaries and receipts.
    single_line: str
