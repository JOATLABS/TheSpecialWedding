"""
Shared fixtures for integration tests.

These tests run against the REAL backend (docker-compose.test.yml).
No mocks — every request hits the actual FastAPI app, MongoDB, and Redis.

Usage:
    # Start the test stack
    docker compose -f docker-compose.test.yml up -d --wait

    # Run integration tests
    pytest tests/integration/ -v

    # Tear down
    docker compose -f docker-compose.test.yml down -v
"""

import os
import time

import pytest
import requests

# Backend URL — configurable for local dev vs CI
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")

# Admin credentials — must match docker-compose.test.yml
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "testadmin@thespecialwedding.com")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "TestAdmin123!SecurePassword")


def extract_items(data, *keys):
    """Normalize paginated API payloads into a plain list for integration tests."""
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests that require the full stack running"
    )


@pytest.fixture(scope="session")
def api_url():
    """Base URL for the running backend."""
    return BASE_URL


@pytest.fixture(scope="session")
def wait_for_backend(api_url):
    """Wait for the backend to be healthy before running tests."""
    max_attempts = 30
    for i in range(max_attempts):
        try:
            resp = requests.get(f"{api_url}/health/livez", timeout=5)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(2)
    pytest.fail(
        f"Backend at {api_url} did not become healthy after {max_attempts * 2}s"
    )


@pytest.fixture(scope="session")
def admin_token(api_url, wait_for_backend):
    """Authenticate as the root admin and return a valid JWT token."""
    resp = requests.post(
        f"{api_url}/admin/token",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=10,
    )
    assert resp.status_code == 200, (
        f"Admin login failed: {resp.status_code} - {resp.text}"
    )
    data = resp.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    """Auth headers for admin requests."""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def api(api_url, admin_headers):
    """Helper object for making authenticated API calls."""

    class APIClient:
        def __init__(self):
            self.base = api_url
            self.headers = admin_headers

        def get(self, path, **kwargs):
            kwargs.setdefault("headers", self.headers)
            kwargs.setdefault("timeout", 15)
            return requests.get(f"{self.base}{path}", **kwargs)

        def post(self, path, **kwargs):
            kwargs.setdefault("headers", self.headers)
            kwargs.setdefault("timeout", 15)
            return requests.post(f"{self.base}{path}", **kwargs)

        def put(self, path, **kwargs):
            kwargs.setdefault("headers", self.headers)
            kwargs.setdefault("timeout", 15)
            return requests.put(f"{self.base}{path}", **kwargs)

        def patch(self, path, **kwargs):
            kwargs.setdefault("headers", self.headers)
            kwargs.setdefault("timeout", 15)
            return requests.patch(f"{self.base}{path}", **kwargs)

        def delete(self, path, **kwargs):
            kwargs.setdefault("headers", self.headers)
            kwargs.setdefault("timeout", 15)
            return requests.delete(f"{self.base}{path}", **kwargs)

        def get_unauthenticated(self, path, **kwargs):
            kwargs.setdefault("timeout", 15)
            return requests.get(f"{self.base}{path}", **kwargs)

        def post_unauthenticated(self, path, **kwargs):
            kwargs.setdefault("timeout", 15)
            return requests.post(f"{self.base}{path}", **kwargs)

    return APIClient()
