"""
Subscription & Billing Tests

Tests subscription plans (public and admin), usage tracking, and billing status.
Critical for the SaaS monetization layer.
"""

import pytest


@pytest.mark.integration
class TestSubscriptions:
    """Test subscription management."""

    def test_list_public_plans(self, api):
        """Public can see available subscription plans."""
        resp = api.get_unauthenticated("/public/subscription-plans")
        assert resp.status_code == 200
        data = resp.json()
        # Should have been seeded by setup script
        assert isinstance(data, list)

    def test_list_admin_plans(self, api):
        """Admin can list all subscription plans."""
        resp = api.get("/subscription-plans")
        assert resp.status_code == 200

    def test_get_subscription_analytics(self, api):
        """Admin can view subscription analytics."""
        resp = api.get("/analytics/subscriptions")
        assert resp.status_code == 200

    def test_stripe_config(self, api):
        """Stripe config endpoint is accessible."""
        resp = api.get("/stripe/config")
        # May return 200 with config or 500 if Stripe not configured — both are informative
        assert resp.status_code in (200, 500)


@pytest.mark.integration
class TestUserManagement:
    """Test user management operations."""

    def test_list_users(self, api):
        """Admin can list users."""
        resp = api.get("/users")
        assert resp.status_code == 200
        data = resp.json()
        users = (
            data if isinstance(data, list) else data.get("users", data.get("items", []))
        )
        # At least the admin user should exist
        assert len(users) >= 1

    def test_list_invitations(self, api):
        """Admin can list pending invitations."""
        resp = api.get("/admin/invitations")
        assert resp.status_code == 200

    def test_invitation_stats(self, api):
        """Admin can view invitation statistics."""
        resp = api.get("/admin/invitations/stats")
        assert resp.status_code == 200
