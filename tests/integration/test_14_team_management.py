"""
Team Management Tests

Tests team member operations — seats, permissions, invitations.
"""

import pytest


@pytest.mark.integration
class TestTeamManagement:
    """Test team management features."""

    def test_get_team_members(self, api):
        """List team members."""
        resp = api.get("/admin/team/members")
        assert resp.status_code == 200

    def test_get_team_seats(self, api):
        """Get team seat count/limits."""
        resp = api.get("/admin/team/seats")
        assert resp.status_code == 200

    def test_get_team_permissions(self, api):
        """Get available permissions."""
        resp = api.get("/admin/team/permissions")
        assert resp.status_code == 200


@pytest.mark.integration
class TestUserProfile:
    """Test user profile operations."""

    def test_get_profile(self, api):
        """Get own profile."""
        resp = api.get("/profile")
        assert resp.status_code == 200

    def test_get_onboarding(self, api):
        """Get onboarding status."""
        resp = api.get("/profile/onboarding")
        assert resp.status_code == 200


@pytest.mark.integration
class TestWebPush:
    """Test web push notification setup."""

    def test_get_vapid_key(self, api):
        """Get VAPID public key for push notifications."""
        resp = api.get("/admin/web-push/vapid-public-key")
        # 200 if configured, 503 if web push is intentionally unavailable in this environment
        assert resp.status_code in (200, 503)
        payload = resp.json()
        if resp.status_code == 200:
            assert payload.get("vapid_public_key")
        else:
            assert "not configured" in str(payload.get("detail", "")).lower()

    def test_push_status(self, api):
        """Get push notification status."""
        resp = api.get("/admin/web-push/status")
        assert resp.status_code == 200
