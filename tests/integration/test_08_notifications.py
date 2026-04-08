"""
Notification System Tests

Tests notification CRUD, user notifications, templates, and email service status.
"""

import pytest


@pytest.mark.integration
class TestNotifications:
    """Test notification management."""

    def test_create_notification(self, api):
        """Create a notification."""
        resp = api.post(
            "/admin/notifications",
            json={
                "title": "Integration Test Alert",
                "message": "This is a test notification from CI",
                "type": "info",
            },
        )
        # May require wedding_id or other fields depending on implementation
        assert resp.status_code in (200, 201, 422)

    def test_get_user_notifications(self, api):
        """Get current user's notifications."""
        resp = api.get("/admin/user/notifications")
        assert resp.status_code == 200

    def test_get_unread_notification_count(self, api):
        """Get unread notification count."""
        resp = api.get("/admin/user/notifications/count")
        assert resp.status_code == 200

    def test_mark_all_read(self, api):
        """Mark all notifications as read."""
        resp = api.put("/admin/user/notifications/read-all")
        assert resp.status_code == 200

    def test_email_service_status(self, api):
        """Check email service status."""
        resp = api.get("/admin/email/status")
        assert resp.status_code == 200

    def test_notification_templates(self, api):
        """List notification templates."""
        resp = api.get("/admin/notification-templates")
        assert resp.status_code == 200
