"""
Integration tests for notification API endpoints.
Tests the API endpoints for form response notifications and preferences.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from fastapi import status
from datetime import datetime
import json

from app.main import app


class TestNotificationAPI:
    """Integration tests for notification-related API endpoints."""

    @pytest.fixture(scope="class")
    def client(self):
        """Create test client for API requests."""
        return TestClient(app)

    @pytest.fixture
    async def test_user_token(self, client):
        """Create a test user and return authentication token."""
        # Create test user
        user_data = {
            "email": "testplanner@example.com",
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "Planner",
            "company_name": "Test Wedding Co"
        }

        # Register user
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 200

        # Login to get token
        login_data = {
            "email": user_data["email"],
            "password": user_data["password"]
        }
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200

        return response.json()["access_token"]

    @pytest.fixture
    async def test_form(self, client, test_user_token):
        """Create a test form for notification testing."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        form_data = {
            "name": "Wedding Feedback Form",
            "settings": {
                "title": "How was your wedding experience?",
                "description": "Please share your feedback",
                "submit_button_text": "Submit Feedback",
                "success_message": "Thank you for your feedback!"
            },
            "fields": [
                {
                    "id": "overall_rating",
                    "label": "Overall Rating",
                    "type": "rating",
                    "required": True,
                    "order": 1
                },
                {
                    "id": "feedback_text",
                    "label": "Additional Comments",
                    "type": "textarea",
                    "order": 2
                }
            ]
        }

        response = client.post("/admin/forms", json=form_data, headers=headers)
        assert response.status_code == 200

        return response.json()

    @pytest.fixture
    async def test_form_response(self, client, test_form):
        """Create a test form response."""
        form_id = test_form["id"]

        response_data = {
            "responses": {
                "overall_rating": 5,
                "feedback_text": "Amazing experience! Everything was perfect."
            },
            "submitted_by_email": "happy.bride@example.com",
            "submitted_by_name": "Sarah Johnson"
        }

        response = client.post(f"/public/forms/{form_id}/submit", json=response_data)
        assert response.status_code == 200

        return response.json()

    def test_get_notification_preferences_default(self, client, test_user_token):
        """Test getting default notification preferences for new user."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        response = client.get("/admin/notifications/preferences", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Should return default preferences
        assert data["email_enabled"] is True
        assert data["instant_notifications"] is True
        assert data["digest_frequency"] == "daily"
        assert data["forms"] == []

    def test_update_notification_preferences_success(self, client, test_user_token):
        """Test successful update of notification preferences."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        new_preferences = {
            "email_enabled": False,
            "instant_notifications": False,
            "digest_frequency": "weekly",
            "forms": ["form_123", "form_456"]
        }

        response = client.put(
            "/admin/notifications/preferences",
            json=new_preferences,
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify preferences were saved
        response = client.get("/admin/notifications/preferences", headers=headers)
        assert response.status_code == 200
        data = response.json()

        assert data["email_enabled"] is False
        assert data["instant_notifications"] is False
        assert data["digest_frequency"] == "weekly"
        assert data["forms"] == ["form_123", "form_456"]

    def test_update_notification_preferences_validation(self, client, test_user_token):
        """Test validation of notification preference updates."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        # Invalid digest frequency
        invalid_preferences = {
            "email_enabled": True,
            "instant_notifications": True,
            "digest_frequency": "invalid_frequency",
            "forms": []
        }

        response = client.put(
            "/admin/notifications/preferences",
            json=invalid_preferences,
            headers=headers
        )

        assert response.status_code == 422  # Validation error

    def test_get_unread_response_count_zero(self, client, test_user_token):
        """Test getting unread response count when no responses exist."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        response = client.get("/admin/notifications/unread-count", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    def test_get_unread_response_count_with_responses(self, client, test_user_token, test_form_response):
        """Test getting unread response count with actual responses."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        response = client.get("/admin/notifications/unread-count", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1  # One unread response

    def test_mark_response_reviewed(self, client, test_user_token, test_form, test_form_response):
        """Test marking a response as reviewed."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        form_id = test_form["id"]
        response_id = test_form_response["id"]

        # Mark as reviewed
        update_data = {"is_reviewed": True}

        response = client.patch(
            f"/admin/forms/{form_id}/responses/{response_id}/review",
            json=update_data,
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify unread count decreased
        response = client.get("/admin/notifications/unread-count", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0  # Should be 0 now

    def test_mark_response_unreviewed(self, client, test_user_token, test_form, test_form_response):
        """Test marking a response as unreviewed."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        form_id = test_form["id"]
        response_id = test_form_response["id"]

        # First mark as reviewed
        update_data = {"is_reviewed": True}
        response = client.patch(
            f"/admin/forms/{form_id}/responses/{response_id}/review",
            json=update_data,
            headers=headers
        )
        assert response.status_code == 200

        # Then mark as unreviewed
        update_data = {"is_reviewed": False}
        response = client.patch(
            f"/admin/forms/{form_id}/responses/{response_id}/review",
            json=update_data,
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify unread count increased
        response = client.get("/admin/notifications/unread-count", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1  # Should be 1 again

    def test_mark_response_reviewed_invalid_form(self, client, test_user_token):
        """Test marking response as reviewed with invalid form ID."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        update_data = {"is_reviewed": True}

        response = client.patch(
            "/admin/forms/invalid_form_id/responses/invalid_response_id/review",
            json=update_data,
            headers=headers
        )

        assert response.status_code == 404

    def test_mark_response_reviewed_invalid_response(self, client, test_user_token, test_form):
        """Test marking response as reviewed with invalid response ID."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        form_id = test_form["id"]

        update_data = {"is_reviewed": True}

        response = client.patch(
            f"/admin/forms/{form_id}/responses/invalid_response_id/review",
            json=update_data,
            headers=headers
        )

        assert response.status_code == 404

    def test_unauthorized_access_to_preferences(self, client):
        """Test unauthorized access to notification preferences."""
        # No authorization header
        response = client.get("/admin/notifications/preferences")
        assert response.status_code == 401

        # Invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/admin/notifications/preferences", headers=headers)
        assert response.status_code == 401

    def test_unauthorized_access_to_unread_count(self, client):
        """Test unauthorized access to unread count endpoint."""
        response = client.get("/admin/notifications/unread-count")
        assert response.status_code == 401

    def test_unauthorized_mark_response_reviewed(self, client):
        """Test unauthorized access to mark response as reviewed."""
        update_data = {"is_reviewed": True}

        response = client.patch(
            "/admin/forms/form_123/responses/response_456/review",
            json=update_data
        )
        assert response.status_code == 401

    def test_notification_preferences_persistence(self, client, test_user_token):
        """Test that notification preferences persist across sessions."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        # Set custom preferences
        preferences = {
            "email_enabled": False,
            "instant_notifications": False,
            "digest_frequency": "weekly",
            "forms": ["specific_form_id"]
        }

        response = client.put(
            "/admin/notifications/preferences",
            json=preferences,
            headers=headers
        )
        assert response.status_code == 200

        # Simulate new session by getting preferences again
        response = client.get("/admin/notifications/preferences", headers=headers)
        assert response.status_code == 200
        data = response.json()

        # Should match what we set
        assert data["email_enabled"] is False
        assert data["instant_notifications"] is False
        assert data["digest_frequency"] == "weekly"
        assert data["forms"] == ["specific_form_id"]

    def test_form_specific_notification_preferences(self, client, test_user_token, test_form):
        """Test form-specific notification preferences."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        form_id = test_form["id"]

        # Set preferences to only notify for specific form
        preferences = {
            "email_enabled": True,
            "instant_notifications": True,
            "digest_frequency": "daily",
            "forms": [form_id]
        }

        response = client.put(
            "/admin/notifications/preferences",
            json=preferences,
            headers=headers
        )
        assert response.status_code == 200

        # Verify preferences include our form
        response = client.get("/admin/notifications/preferences", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert form_id in data["forms"]

    def test_notification_preferences_with_multiple_forms(self, client, test_user_token):
        """Test notification preferences with multiple forms."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        # Create multiple forms
        form_ids = []
        for i in range(3):
            form_data = {
                "name": f"Test Form {i}",
                "settings": {
                    "title": f"Test Form {i}",
                    "description": "Test form for notifications"
                },
                "fields": [
                    {
                        "id": "test_field",
                        "label": "Test Field",
                        "type": "text",
                        "order": 1
                    }
                ]
            }

            response = client.post("/admin/forms", json=form_data, headers=headers)
            assert response.status_code == 200
            form_ids.append(response.json()["id"])

        # Set preferences for subset of forms
        preferences = {
            "email_enabled": True,
            "instant_notifications": True,
            "digest_frequency": "daily",
            "forms": form_ids[:2]  # Only first two forms
        }

        response = client.put(
            "/admin/notifications/preferences",
            json=preferences,
            headers=headers
        )
        assert response.status_code == 200

        # Verify preferences
        response = client.get("/admin/notifications/preferences", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["forms"]) == 2
        assert form_ids[0] in data["forms"]
        assert form_ids[1] in data["forms"]
        assert form_ids[2] not in data["forms"]

    def test_response_review_status_in_form_responses(self, client, test_user_token, test_form, test_form_response):
        """Test that response review status is included in form responses API."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        form_id = test_form["id"]

        # Get form responses
        response = client.get(f"/admin/forms/{form_id}/responses", headers=headers)
        assert response.status_code == 200
        responses = response.json()

        assert len(responses) == 1
        response_data = responses[0]

        # Should include review status fields
        assert "is_reviewed" in response_data
        assert "reviewed_at" in response_data
        assert "reviewed_by" in response_data
        assert "notification_sent" in response_data
        assert "notification_sent_at" in response_data

        # Initially should be unreviewed
        assert response_data["is_reviewed"] is False

    def test_concurrent_response_review_updates(self, client, test_user_token, test_form, test_form_response):
        """Test concurrent updates to response review status."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        form_id = test_form["id"]
        response_id = test_form_response["id"]

        # Simulate concurrent updates
        import threading
        import time

        results = []

        def update_review_status(is_reviewed):
            update_data = {"is_reviewed": is_reviewed}
            response = client.patch(
                f"/admin/forms/{form_id}/responses/{response_id}/review",
                json=update_data,
                headers=headers
            )
            results.append(response.status_code)

        # Start concurrent threads
        thread1 = threading.Thread(target=update_review_status, args=(True,))
        thread2 = threading.Thread(target=update_review_status, args=(False,))

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Both requests should succeed (last one wins)
        assert all(status_code == 200 for status_code in results)


if __name__ == '__main__':
    pytest.main([__file__])