"""
Platform Operations Tests

Tests platform metrics, activity logging, support tickets, knowledge base,
trial management, and other operational endpoints.
These verify the platform infrastructure is functioning.
"""

import pytest


@pytest.mark.integration
class TestPlatformMetrics:
    """Test platform-level monitoring."""

    def test_platform_health(self, api):
        """Platform health endpoint."""
        resp = api.get("/admin/platform/health")
        assert resp.status_code == 200

    def test_platform_metrics(self, api):
        """Get platform metrics."""
        resp = api.get("/admin/platform/metrics")
        assert resp.status_code == 200

    def test_recent_errors(self, api):
        """Get recent errors."""
        resp = api.get("/admin/platform/errors/recent")
        assert resp.status_code == 200

    def test_planner_metrics(self, api):
        """Get planner metrics."""
        resp = api.get("/admin/planner/metrics")
        assert resp.status_code == 200


@pytest.mark.integration
class TestActivityLog:
    """Test activity logging."""

    def test_get_activity_logs(self, api):
        """Get activity logs."""
        resp = api.get("/admin/activity-log")
        assert resp.status_code == 200

    def test_get_recent_activity(self, api):
        """Get recent activity."""
        resp = api.get("/admin/activity-log/recent")
        assert resp.status_code == 200


@pytest.mark.integration
class TestSupportSystem:
    """Test support ticket system."""

    def test_list_tickets(self, api):
        """List support tickets."""
        resp = api.get("/admin/tickets")
        assert resp.status_code == 200

    def test_create_ticket(self, api):
        """Create a support ticket."""
        resp = api.post(
            "/admin/tickets",
            json={
                "subject": "Integration Test Ticket",
                "description": "This ticket was created by CI integration tests.",
                "priority": "low",
            },
        )
        assert resp.status_code in (200, 201), f"Create ticket failed: {resp.text}"

    def test_get_my_tickets(self, api):
        """Get current user's tickets."""
        resp = api.get("/admin/my-tickets")
        assert resp.status_code == 200

    def test_ticket_categories(self, api):
        """Get ticket categories."""
        resp = api.get("/admin/categories")
        assert resp.status_code == 200


@pytest.mark.integration
class TestKnowledgeBase:
    """Test knowledge base."""

    def test_list_articles(self, api):
        """List KB articles."""
        resp = api.get("/admin/kb/articles")
        assert resp.status_code == 200

    def test_list_categories(self, api):
        """List KB categories."""
        resp = api.get("/admin/kb/categories")
        assert resp.status_code == 200

    def test_search_articles(self, api):
        """Search KB articles."""
        resp = api.get("/admin/kb/search?q=test")
        assert resp.status_code == 200


@pytest.mark.integration
class TestTrialManagement:
    """Test trial lifecycle."""

    def test_trial_status(self, api):
        """Get trial status."""
        resp = api.get("/admin/trials/status")
        assert resp.status_code == 200


@pytest.mark.integration
class TestSaaSConfig:
    """Test SaaS configuration."""

    def test_get_public_config(self, api):
        """Get public SaaS config."""
        resp = api.get_unauthenticated("/saas/config")
        assert resp.status_code == 200

    def test_get_saas_config(self, api):
        """Admin can get full SaaS config."""
        resp = api.get("/saas/saas-config")
        assert resp.status_code == 200

    def test_get_trial_settings(self, api):
        """Get trial settings."""
        resp = api.get("/saas/trial-settings")
        assert resp.status_code == 200


@pytest.mark.integration
class TestScheduler:
    """Test scheduler health."""

    def test_scheduler_health(self, api):
        """Scheduler health check."""
        resp = api.get_unauthenticated("/scheduler/health")
        assert resp.status_code == 200
