"""Domain exceptions.

Services raise these instead of `fastapi.HTTPException`, keeping the business
layer free of any web-framework import. `app.main` registers a single handler
that renders them as consistent JSON error envelopes.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for every expected, user-facing failure."""

    status_code: int = 400
    error_code: str = "bad_request"
    message: str = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.error_code = error_code or self.error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.error_code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return {"error": payload}


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"
    message = "The resource already exists."


class AuthenticationError(AppError):
    status_code = 401
    error_code = "authentication_failed"
    message = "Incorrect email or password."


class InvalidTokenError(AppError):
    status_code = 401
    error_code = "invalid_token"
    message = "The authentication token is invalid or has expired."


class PermissionDeniedError(AppError):
    status_code = 403
    error_code = "permission_denied"
    message = "You do not have permission to perform this action."


class InactiveAccountError(AppError):
    status_code = 403
    error_code = "inactive_account"
    message = "This account has been deactivated. Please contact support."


class BusinessRuleError(AppError):
    status_code = 422
    error_code = "business_rule_violation"
    message = "This action violates a business rule."
