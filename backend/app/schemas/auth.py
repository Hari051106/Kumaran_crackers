"""Authentication API schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenPair(BaseModel):
    """OAuth2-style bearer token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds.")


class AuthResponse(BaseModel):
    """Returned by register / login / refresh - tokens plus the current user."""

    user: UserRead
    tokens: TokenPair


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
