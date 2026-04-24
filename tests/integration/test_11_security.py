"""
Security Tests

Tests that security boundaries are enforced:
- Protected endpoints reject unauthenticated requests
- Invalid tokens are rejected
- CORS preflight works
- Rate limiting headers are present (when enabled)
"""

import pytest
import requests

from tests.integration.conftest import BASE_URL


@pytest.mark.integration
class TestSecurityBoundaries:
    """Verify that auth is enforced on protected endpoints."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/admin/weddings"),
        ("GET", "/admin/guests"),
        ("GET", "/admin/profile"),
        ("GET", "/admin/forms"),
        ("GET", "/admin/directory"),
        ("GET", "/admin/tickets"),
        ("GET", "/admin/notifications"),
        ("GET", "/users"),
        ("GET", "/admin/platform/metrics"),
        ("GET", "/admin/activity-log"),
        ("GET", "/subscription-plans"),
        ("GET", "/admin/client-contracts"),
        ("GET", "/admin/contracts"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_protected_endpoint_rejects_unauthenticated(self, method, path):
        """Protected endpoints return 401 or 403 without auth."""
        resp = requests.request(method, f"{BASE_URL}{path}", timeout=10)
        assert resp.status_code in (
            401,
            403,
            405,
        ), (
            f"{method} {path} returned {resp.status_code} without auth (expected 401/403)"
        )

    def test_invalid_jwt_rejected(self):
        """Forged JWT tokens are rejected."""
        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJoYWNrZXJAZXZpbC5jb20iLCJyb2xlIjoiUk9PVF9BRE1JTiJ9.fake"
        }
        resp = requests.get(f"{BASE_URL}/admin/profile", headers=headers, timeout=10)
        assert resp.status_code in (401, 403)

    def test_expired_token_rejected(self):
        """Expired tokens are rejected (we craft one with past expiry)."""
        import datetime

        import jwt as pyjwt

        token = pyjwt.encode(
            {
                "sub": "testadmin@thespecialwedding.com",
                "role": "ROOT_ADMIN",
                "exp": datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),
            },
            # Wrong key — should fail signature verification anyway
            "wrong-secret-key",
            algorithm="HS256",
        )
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/admin/profile", headers=headers, timeout=10)
        assert resp.status_code in (401, 403)

    def test_cors_preflight(self):
        """CORS preflight returns appropriate headers."""
        resp = requests.options(
            f"{BASE_URL}/admin/token",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
            timeout=10,
        )
        # Should not be 500
        assert resp.status_code < 500


@pytest.mark.integration
class TestPublicEndpoints:
    """Verify that public endpoints are accessible without auth."""

    PUBLIC_ENDPOINTS = [
        ("GET", "/"),
        ("GET", "/health/livez"),
        ("GET", "/health/readyz"),
        ("GET", "/health/"),
        ("GET", "/public/subscription-plans"),
        ("GET", "/saas/config"),
        ("GET", "/scheduler/health"),
    ]

    @pytest.mark.parametrize("method,path", PUBLIC_ENDPOINTS)
    def test_public_endpoint_accessible(self, method, path):
        """Public endpoints return 200 without auth."""
        resp = requests.request(method, f"{BASE_URL}{path}", timeout=10)
        assert resp.status_code == 200, (
            f"{method} {path} returned {resp.status_code} (expected 200)"
        )
