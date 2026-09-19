"""Unit tests for password hashing and JWT handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import settings
from app.enums import TokenType
from app.utils.errors import InvalidTokenError
from app.utils.security import (
    BCRYPT_MAX_BYTES,
    PasswordTooLongError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_the_plain_password(self) -> None:
        digest = hash_password("Test@12345")
        assert digest != "Test@12345"
        assert digest.startswith("$2b$")

    def test_correct_password_verifies(self) -> None:
        assert verify_password("Test@12345", hash_password("Test@12345")) is True

    def test_wrong_password_is_rejected(self) -> None:
        assert verify_password("Wrong@12345", hash_password("Test@12345")) is False

    def test_hashes_are_salted(self) -> None:
        """Two hashes of the same password must differ."""
        assert hash_password("Test@12345") != hash_password("Test@12345")

    def test_oversized_password_is_rejected_not_truncated(self) -> None:
        """Silent truncation would let two different passwords collide."""
        with pytest.raises(PasswordTooLongError):
            hash_password("a" * (BCRYPT_MAX_BYTES + 1))

    def test_verify_against_corrupt_digest_returns_false(self) -> None:
        assert verify_password("Test@12345", "not-a-bcrypt-hash") is False


class TestTokens:
    def test_access_token_round_trip(self) -> None:
        token = create_access_token(subject=42, role="CUSTOMER")
        payload = decode_token(token, expected_type=TokenType.ACCESS)
        assert payload.subject == 42
        assert payload.role == "CUSTOMER"
        assert payload.token_type is TokenType.ACCESS

    def test_refresh_token_round_trip(self) -> None:
        token = create_refresh_token(subject=7, role="ADMIN")
        payload = decode_token(token, expected_type=TokenType.REFRESH)
        assert payload.subject == 7

    def test_refresh_token_cannot_be_used_as_access_token(self) -> None:
        """Token-type confusion would turn a long-lived token into a session key."""
        refresh = create_refresh_token(subject=1, role="CUSTOMER")
        with pytest.raises(InvalidTokenError):
            decode_token(refresh, expected_type=TokenType.ACCESS)

    def test_access_token_cannot_be_used_as_refresh_token(self) -> None:
        access = create_access_token(subject=1, role="CUSTOMER")
        with pytest.raises(InvalidTokenError):
            decode_token(access, expected_type=TokenType.REFRESH)

    def test_token_signed_with_another_key_is_rejected(self) -> None:
        forged = jwt.encode(
            {
                "sub": "1",
                "role": "ADMIN",
                "type": "access",
                "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            },
            "an-attacker-controlled-key",
            algorithm="HS256",
        )
        with pytest.raises(InvalidTokenError):
            decode_token(forged, expected_type=TokenType.ACCESS)

    def test_expired_token_is_rejected(self) -> None:
        expired = jwt.encode(
            {
                "sub": "1",
                "role": "CUSTOMER",
                "type": "access",
                "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
            },
            settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(InvalidTokenError):
            decode_token(expired, expected_type=TokenType.ACCESS)

    def test_garbage_token_is_rejected(self) -> None:
        with pytest.raises(InvalidTokenError):
            decode_token("not.a.jwt", expected_type=TokenType.ACCESS)

    def test_tokens_are_unique_per_issue(self) -> None:
        """A distinct jti per token is what makes future revocation possible."""
        first = decode_token(create_access_token(1, "CUSTOMER"), expected_type=TokenType.ACCESS)
        second = decode_token(create_access_token(1, "CUSTOMER"), expected_type=TokenType.ACCESS)
        assert first.jti != second.jti
