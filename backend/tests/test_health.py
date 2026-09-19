"""System endpoints and cross-cutting behaviour."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestSystemEndpoints:
    def test_health_check(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_root_carries_the_branding(self, client: TestClient) -> None:
        body = client.get("/").json()
        assert body["name"] == "Kumaran Crackers API"
        assert body["tagline"] == "Celebrate Every Moment with Kumaran Crackers"

    def test_openapi_schema_is_served(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "/api/v1/auth/login" in response.json()["paths"]


class TestErrorEnvelope:
    """Every failure must use the same shape so clients can parse it uniformly."""

    def test_not_found_uses_the_error_envelope(self, client: TestClient) -> None:
        body = client.get("/api/v1/does-not-exist").json()
        assert "error" in body
        assert {"code", "message"} <= body["error"].keys()

    def test_validation_error_reports_offending_fields(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/login", json={"email": "bad"})
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert "email" in error["details"]
        assert "password" in error["details"]

    def test_protected_route_reveals_nothing_to_anonymous_callers(self, client: TestClient) -> None:
        """Auth is checked before path validation, so a bad id still yields 401."""
        response = client.get("/api/v1/users/not-an-integer")
        assert response.status_code == 401

    def test_internal_details_are_never_leaked(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        """An authenticated caller must never see SQL, stack traces or table names."""
        response = client.get("/api/v1/users/not-an-integer", headers=admin_headers)
        assert response.status_code == 422
        assert "Traceback" not in response.text
        assert "sqlalchemy" not in response.text.lower()
        assert "psycopg" not in response.text.lower()
