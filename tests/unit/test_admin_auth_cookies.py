"""Tests for admin auth cookie settings ensuring secure attributes.
"""
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Ensure required env vars before importing app
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only")
os.environ.setdefault("MONGO_URI", "mongodb://test:27017")

from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.mark.parametrize("env,expected_secure", [
    ("development", False),
    ("production", True),
])
@patch("app.api.admin_auth.get_settings")
def test_login_cookie_security(mock_get_settings, client, env, expected_secure):
    class DummySettings:
        def is_production(self):
            return env == "production"
    mock_get_settings.return_value = DummySettings()

    # Mock auth service login
    with patch("app.api.admin_auth.auth_service") as mock_auth_service:
        mock_auth_service.login_and_get_token.return_value = {"access_token": "abc", "token_type": "bearer"}
        payload = {"email": "admin@example.com", "password": "pass"}
        response = client.post("/token", json=payload)

    assert response.status_code == 200
    # Extract set-cookie headers
    set_cookies = response.headers.getlist("set-cookie") if hasattr(response.headers, "getlist") else response.headers.get("set-cookie", "").split(", ")
    # Ensure both cookies are present
    assert any("admin_token=" in c for c in set_cookies)
    assert any("admin_authenticated=" in c for c in set_cookies)
    # Check secure flag on token cookie
    token_cookie = next(c for c in set_cookies if c.startswith("admin_token="))
    if expected_secure:
        assert "Secure" in token_cookie
    else:
        # In dev it should normally not include Secure (case-insensitive check)
        assert "secure" not in token_cookie.lower()
    # HttpOnly must always be present on admin_token
    assert "HttpOnly" in token_cookie
    # SameSite=Strict on token cookie
    assert "SameSite=Strict" in token_cookie

@patch("app.api.admin_auth.get_settings")
@patch("app.api.admin_auth.auth_service")
def test_logout_clears_cookies(mock_auth_service, mock_get_settings, client):
    class DummySettings:
        def is_production(self):
            return False
    mock_get_settings.return_value = DummySettings()
    mock_auth_service.login_and_get_token.return_value = {"access_token": "abc", "token_type": "bearer"}
    client.post("/token", json={"email": "admin@example.com", "password": "pass"})
    resp = client.post("/logout")
    assert resp.status_code == 200
    # Deleted cookies should have Max-Age=0 or empty value
    set_cookie_headers = resp.headers.getlist("set-cookie") if hasattr(resp.headers, "getlist") else [resp.headers.get("set-cookie", "")]
    cleared = [c for c in set_cookie_headers if "admin_token=" in c or "admin_authenticated=" in c]
    assert cleared
