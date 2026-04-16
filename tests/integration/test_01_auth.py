"""
Authentication & Authorization Tests

Tests the complete auth flow: login, token refresh, profile access,
and unauthorized access rejection.
"""

import pytest


def _read_initial_notification_event(response, timeout_lines: int = 25) -> bool:
    saw_notification_event = False

    for line_count, raw_line in enumerate(response.iter_lines(decode_unicode=True), 1):
        if raw_line is None:
            continue

        line = raw_line.strip()
        if line.startswith("event: notification-count"):
            saw_notification_event = True
            continue

        if saw_notification_event and line.startswith("data:"):
            return True

        if line_count >= timeout_lines:
            break

    return False


@pytest.mark.integration
class TestAuthentication:
    def test_login_with_valid_credentials(self, api):
        """Admin can login and receive a JWT token."""
        from tests.integration.conftest import ADMIN_EMAIL, ADMIN_PASSWORD

        resp = api.post_unauthenticated(
            "/admin/token",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_sets_admin_cookie(self, admin_session):
        """Admin login also issues the admin_token cookie used by the frontend."""
        assert admin_session.cookies.get("admin_token")

    def test_login_with_invalid_credentials(self, api):
        """Invalid credentials return 401."""
        resp = api.post_unauthenticated(
            "/admin/token",
            json={"email": "wrong@example.com", "password": "WrongPassword123!"},
        )
        assert resp.status_code == 401

    def test_login_with_wrong_password(self, api):
        """Correct email but wrong password returns 401."""
        from tests.integration.conftest import ADMIN_EMAIL

        resp = api.post_unauthenticated(
            "/admin/token",
            json={"email": ADMIN_EMAIL, "password": "WrongPassword123!"},
        )
        assert resp.status_code == 401

    def test_get_profile_with_valid_token(self, api):
        """Authenticated user can fetch their profile."""
        resp = api.get("/admin/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        assert "role" in data

    def test_get_profile_without_token(self, api):
        """Unauthenticated request to protected endpoint returns 401/403."""
        resp = api.get_unauthenticated("/admin/profile")
        assert resp.status_code in (401, 403)

    def test_get_profile_with_invalid_token(self, api):
        """Invalid JWT returns 401/403."""
        import requests

        from tests.integration.conftest import BASE_URL

        resp = requests.get(
            f"{BASE_URL}/admin/profile",
            headers={"Authorization": "Bearer invalid.token.here"},
            timeout=10,
        )
        assert resp.status_code in (401, 403)

    def test_token_refresh(self, api):
        """Valid token can be refreshed for a new one."""
        resp = api.post("/admin/token/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_token_refresh_with_cookie_auth(self, api_url, admin_session):
        """Silent refresh works with the cookie contract alone."""
        resp = admin_session.post(f"{api_url}/admin/token/refresh", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert admin_session.cookies.get("admin_token")

    def test_notification_stream_with_cookie_auth(self, api_url, admin_session):
        """SSE connects with the admin_token cookie and emits an initial count."""
        response = admin_session.get(
            f"{api_url}/admin/notifications/stream",
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
            },
            timeout=(10, 20),
            stream=True,
        )

        try:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            assert _read_initial_notification_event(response) is True
        finally:
            response.close()
