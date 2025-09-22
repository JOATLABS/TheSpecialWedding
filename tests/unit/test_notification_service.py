"""
Unit tests for NotificationService form response functionality.
Tests the notification service methods for form response notifications.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import json

from app.services.notification_service import NotificationService


class TestNotificationService:
    """Test cases for NotificationService form response methods."""

    @pytest.fixture
    def notification_service(self):
        """Create a NotificationService instance for testing."""
        service = NotificationService()
        # Mock the database and email service
        service.db = Mock()
        service.email_service = Mock()
        return service

    @pytest.fixture
    def sample_form_data(self):
        """Sample form data for testing."""
        return {
            'id': 'form_123',
            'name': 'Wedding Feedback Form',
            'settings': {
                'title': 'How was your wedding experience?',
                'description': 'Please share your feedback'
            },
            'created_by': 'planner@example.com',
            'fields': [
                {
                    'id': 'rating',
                    'label': 'Overall Rating',
                    'type': 'rating'
                },
                {
                    'id': 'feedback',
                    'label': 'Additional Comments',
                    'type': 'textarea'
                }
            ]
        }

    @pytest.fixture
    def sample_response_data(self):
        """Sample response data for testing."""
        return {
            'responses': {
                'rating': 5,
                'feedback': 'Amazing experience! Everything was perfect.'
            },
            'submitted_by_email': 'bride@example.com',
            'submitted_by_name': 'Jane Doe',
            'submitted_at': datetime.utcnow().isoformat()
        }

    @pytest.fixture
    def sample_preferences(self):
        """Sample notification preferences for testing."""
        return {
            'email_enabled': True,
            'instant_notifications': True,
            'digest_frequency': 'daily',
            'forms': []
        }

    @pytest.mark.asyncio
    async def test_notify_form_response_success(self, notification_service, sample_form_data, sample_response_data):
        """Test successful form response notification."""
        # Mock database operations
        notification_service.db.form_notifications.find_one = AsyncMock(return_value={
            'user_email': 'planner@example.com',
            'preferences': {
                'email_enabled': True,
                'instant_notifications': True,
                'forms': []
            }
        })
        notification_service.db.notifications.insert_one = AsyncMock()
        notification_service.db.form_responses.update_one = AsyncMock()

        # Mock email service
        notification_service._send_form_response_email = AsyncMock()

        # Execute the method
        result = await notification_service.notify_form_response(
            form_id='form_123',
            response_id='response_456',
            response_data=sample_response_data,
            form_data=sample_form_data
        )

        # Assertions
        assert result['success'] is True
        assert result['notification_id'] is not None
        assert result['email_sent'] is True

        # Verify database calls
        notification_service.db.form_notifications.find_one.assert_called_once()
        notification_service.db.notifications.insert_one.assert_called_once()
        notification_service.db.form_responses.update_one.assert_called_once()

        # Verify email was sent
        notification_service._send_form_response_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_form_response_email_disabled(self, notification_service, sample_form_data, sample_response_data):
        """Test form response notification when email is disabled."""
        # Mock database operations - email disabled
        notification_service.db.form_notifications.find_one = AsyncMock(return_value={
            'user_email': 'planner@example.com',
            'preferences': {
                'email_enabled': False,
                'instant_notifications': True,
                'forms': []
            }
        })
        notification_service.db.notifications.insert_one = AsyncMock()
        notification_service.db.form_responses.update_one = AsyncMock()

        # Mock email service
        notification_service._send_form_response_email = AsyncMock()

        # Execute the method
        result = await notification_service.notify_form_response(
            form_id='form_123',
            response_id='response_456',
            response_data=sample_response_data,
            form_data=sample_form_data
        )

        # Assertions
        assert result['success'] is True
        assert result['email_sent'] is False

        # Verify email was not sent
        notification_service._send_form_response_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_form_response_specific_form_filter(self, notification_service, sample_form_data, sample_response_data):
        """Test form response notification with specific form filtering."""
        # Mock database operations - specific form filtering
        notification_service.db.form_notifications.find_one = AsyncMock(return_value={
            'user_email': 'planner@example.com',
            'preferences': {
                'email_enabled': True,
                'instant_notifications': True,
                'forms': ['other_form_123']  # Different form ID
            }
        })
        notification_service.db.notifications.insert_one = AsyncMock()
        notification_service.db.form_responses.update_one = AsyncMock()

        # Execute the method
        result = await notification_service.notify_form_response(
            form_id='form_123',
            response_id='response_456',
            response_data=sample_response_data,
            form_data=sample_form_data
        )

        # Should still create in-app notification but not send email
        assert result['success'] is True
        assert result['email_sent'] is False

    @pytest.mark.asyncio
    async def test_send_form_response_email(self, notification_service, sample_form_data, sample_response_data):
        """Test email sending for form responses."""
        # Mock email service
        notification_service.email_service.send_email = AsyncMock(return_value=True)

        # Execute the method
        await notification_service._send_form_response_email(
            form_owner_email='planner@example.com',
            form_data=sample_form_data,
            response_data=sample_response_data,
            total_responses=5,
            response_id='response_456'
        )

        # Verify email was sent
        notification_service.email_service.send_email.assert_called_once()

        # Check email content
        call_args = notification_service.email_service.send_email.call_args
        assert call_args[1]['to_email'] == 'planner@example.com'
        assert 'New Response Received' in call_args[1]['subject']
        assert 'Jane Doe' in call_args[1]['body']
        assert 'Amazing experience!' in call_args[1]['body']

    @pytest.mark.asyncio
    async def test_get_notification_preferences_existing(self, notification_service):
        """Test retrieving existing notification preferences."""
        # Mock database response
        notification_service.db.form_notifications.find_one = AsyncMock(return_value={
            'user_email': 'user@example.com',
            'preferences': {
                'email_enabled': True,
                'instant_notifications': False,
                'digest_frequency': 'weekly',
                'forms': ['form_123']
            }
        })

        # Execute the method
        result = await notification_service.get_notification_preferences('user@example.com')

        # Assertions
        assert result['email_enabled'] is True
        assert result['instant_notifications'] is False
        assert result['digest_frequency'] == 'weekly'
        assert result['forms'] == ['form_123']

    @pytest.mark.asyncio
    async def test_get_notification_preferences_default(self, notification_service):
        """Test retrieving default notification preferences for new user."""
        # Mock database response - no existing preferences
        notification_service.db.form_notifications.find_one = AsyncMock(return_value=None)

        # Execute the method
        result = await notification_service.get_notification_preferences('user@example.com')

        # Assertions - should return defaults
        assert result['email_enabled'] is True
        assert result['instant_notifications'] is True
        assert result['digest_frequency'] == 'daily'
        assert result['forms'] == []

    @pytest.mark.asyncio
    async def test_update_notification_preferences(self, notification_service, sample_preferences):
        """Test updating notification preferences."""
        # Mock database operations
        notification_service.db.form_notifications.update_one = AsyncMock()

        # Execute the method
        result = await notification_service.update_notification_preferences(
            'user@example.com',
            sample_preferences
        )

        # Assertions
        assert result['success'] is True

        # Verify database update
        notification_service.db.form_notifications.update_one.assert_called_once()
        call_args = notification_service.db.form_notifications.update_one.call_args
        assert call_args[0][0] == {'user_email': 'user@example.com'}
        assert '$set' in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_unread_form_response_count(self, notification_service):
        """Test getting unread form response count."""
        # Mock database response
        mock_cursor = Mock()
        mock_cursor.to_list = AsyncMock(return_value=[
            {'form_id': 'form_1', 'unread_count': 3},
            {'form_id': 'form_2', 'unread_count': 2}
        ])
        notification_service.db.form_responses.aggregate = Mock(return_value=mock_cursor)

        # Execute the method
        result = await notification_service.get_unread_form_response_count('user@example.com')

        # Assertions
        assert result == 5  # 3 + 2

        # Verify aggregation was called
        notification_service.db.form_responses.aggregate.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_unread_form_response_count_zero(self, notification_service):
        """Test getting unread count when no unread responses."""
        # Mock database response - no unread responses
        mock_cursor = Mock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        notification_service.db.form_responses.aggregate = Mock(return_value=mock_cursor)

        # Execute the method
        result = await notification_service.get_unread_form_response_count('user@example.com')

        # Assertions
        assert result == 0

    @pytest.mark.asyncio
    async def test_email_template_formatting(self, notification_service, sample_form_data, sample_response_data):
        """Test email template formatting and content."""
        # Mock email service to capture the content
        sent_emails = []

        async def mock_send_email(**kwargs):
            sent_emails.append(kwargs)
            return True

        notification_service.email_service.send_email = mock_send_email

        # Execute the method
        await notification_service._send_form_response_email(
            form_owner_email='planner@example.com',
            form_data=sample_form_data,
            response_data=sample_response_data,
            total_responses=10,
            response_id='response_456'
        )

        # Verify email was captured
        assert len(sent_emails) == 1
        email = sent_emails[0]

        # Check email structure
        assert email['to_email'] == 'planner@example.com'
        assert 'Wedding Feedback Form' in email['subject']

        # Check email content includes response data
        body = email['body']
        assert 'Jane Doe' in body
        assert 'bride@example.com' in body
        assert 'Amazing experience!' in body
        assert '10' in body  # total responses
        assert 'Overall Rating: 5' in body

        # Check mobile responsiveness in HTML
        assert 'max-width: 600px' in body  # Mobile-friendly width
        assert 'media screen and (max-width: 600px)' in body  # Mobile media queries

    @pytest.mark.asyncio
    async def test_error_handling_database_failure(self, notification_service, sample_form_data, sample_response_data):
        """Test error handling when database operations fail."""
        # Mock database failure
        notification_service.db.form_notifications.find_one = AsyncMock(side_effect=Exception("Database error"))

        # Execute the method
        result = await notification_service.notify_form_response(
            form_id='form_123',
            response_id='response_456',
            response_data=sample_response_data,
            form_data=sample_form_data
        )

        # Should handle error gracefully
        assert result['success'] is False
        assert 'error' in result
        assert 'Database error' in result['error']

    @pytest.mark.asyncio
    async def test_error_handling_email_failure(self, notification_service, sample_form_data, sample_response_data):
        """Test error handling when email sending fails."""
        # Mock successful database operations
        notification_service.db.form_notifications.find_one = AsyncMock(return_value={
            'user_email': 'planner@example.com',
            'preferences': {
                'email_enabled': True,
                'instant_notifications': True,
                'forms': []
            }
        })
        notification_service.db.notifications.insert_one = AsyncMock()
        notification_service.db.form_responses.update_one = AsyncMock()

        # Mock email failure
        notification_service._send_form_response_email = AsyncMock(side_effect=Exception("Email service error"))

        # Execute the method
        result = await notification_service.notify_form_response(
            form_id='form_123',
            response_id='response_456',
            response_data=sample_response_data,
            form_data=sample_form_data
        )

        # Should create in-app notification but report email failure
        assert result['success'] is True
        assert result['email_sent'] is False
        assert 'email_error' in result


if __name__ == '__main__':
    pytest.main([__file__])