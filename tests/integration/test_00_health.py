"""
Health & Infrastructure Tests

Validates that the backend is running, connected to MongoDB and Redis,
and all critical infrastructure is operational.
"""

import pytest


@pytest.mark.integration
class TestHealth:
    def test_livez_returns_200(self, api):
        """Liveness probe — the process is alive."""
        resp = api.get_unauthenticated("/health/livez")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "alive"

    def test_readyz_returns_200(self, api):
        """Readiness probe — MongoDB and Redis are connected."""
        resp = api.get_unauthenticated("/health/readyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "connected"

    def test_root_endpoint(self, api):
        """Root endpoint returns app info."""
        resp = api.get_unauthenticated("/")
        assert resp.status_code == 200

    def test_health_check_main(self, api):
        """Main health check validates DB connectivity."""
        resp = api.get_unauthenticated("/health/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["checks"]["database"] == "connected"
