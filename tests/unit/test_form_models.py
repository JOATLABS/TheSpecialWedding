"""
Unit tests for Form models with notification enhancements.
Tests the new review status fields and notification-related models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.form import (
    FormResponse,
    UpdateResponseReviewRequest,
    FieldType,
    FormField,
    ValidationRule
)


class TestFormResponseModel:
    """Test cases for enhanced FormResponse model with review status."""

    def test_form_response_creation_with_defaults(self):
        """Test FormResponse creation with default review status values."""
        response = FormResponse(
            form_id="form_123",
            responses={"rating": 5, "feedback": "Great!"},
            submitted_by_email="user@example.com",
            submitted_by_name="John Doe"
        )

        # Check default values for review fields
        assert response.is_reviewed is False
        assert response.reviewed_at is None
        assert response.reviewed_by is None
        assert response.notification_sent is False
        assert response.notification_sent_at is None

        # Check required fields are set
        assert response.form_id == "form_123"
        assert response.responses == {"rating": 5, "feedback": "Great!"}
        assert response.submitted_by_email == "user@example.com"
        assert response.submitted_by_name == "John Doe"
        assert response.submitted_at is not None

    def test_form_response_with_review_status(self):
        """Test FormResponse with review status fields set."""
        reviewed_time = datetime.utcnow()
        notification_time = datetime.utcnow()

        response = FormResponse(
            form_id="form_123",
            responses={"rating": 5},
            submitted_by_email="user@example.com",
            is_reviewed=True,
            reviewed_at=reviewed_time,
            reviewed_by="admin@example.com",
            notification_sent=True,
            notification_sent_at=notification_time
        )

        assert response.is_reviewed is True
        assert response.reviewed_at == reviewed_time
        assert response.reviewed_by == "admin@example.com"
        assert response.notification_sent is True
        assert response.notification_sent_at == notification_time

    def test_form_response_optional_fields(self):
        """Test FormResponse with optional fields as None."""
        response = FormResponse(
            form_id="form_123",
            responses={"rating": 5},
            submitted_by_email=None,
            submitted_by_name=None,
            wedding_id=None,
            ip_address=None,
            user_agent=None
        )

        assert response.submitted_by_email is None
        assert response.submitted_by_name is None
        assert response.wedding_id is None
        assert response.ip_address is None
        assert response.user_agent is None

    def test_form_response_with_metadata(self):
        """Test FormResponse with custom metadata."""
        metadata = {
            "user_agent": "Mozilla/5.0",
            "referrer": "https://example.com",
            "session_id": "sess_123"
        }

        response = FormResponse(
            form_id="form_123",
            responses={"rating": 5},
            metadata=metadata
        )

        assert response.metadata == metadata

    def test_form_response_serialization(self):
        """Test FormResponse serialization includes all fields."""
        response = FormResponse(
            form_id="form_123",
            responses={"rating": 5, "feedback": "Great!"},
            submitted_by_email="user@example.com",
            is_reviewed=True,
            reviewed_by="admin@example.com",
            notification_sent=True
        )

        response_dict = response.model_dump()

        # Check all review fields are included
        assert "is_reviewed" in response_dict
        assert "reviewed_at" in response_dict
        assert "reviewed_by" in response_dict
        assert "notification_sent" in response_dict
        assert "notification_sent_at" in response_dict

        assert response_dict["is_reviewed"] is True
        assert response_dict["reviewed_by"] == "admin@example.com"
        assert response_dict["notification_sent"] is True

    def test_form_response_validation_errors(self):
        """Test FormResponse validation for required fields."""
        # Missing form_id should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            FormResponse(responses={"rating": 5})

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("form_id",) and error["type"] == "missing" for error in errors)

        # Missing responses should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            FormResponse(form_id="form_123")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("responses",) and error["type"] == "missing" for error in errors)


class TestUpdateResponseReviewRequest:
    """Test cases for UpdateResponseReviewRequest model."""

    def test_valid_review_request_true(self):
        """Test valid UpdateResponseReviewRequest with is_reviewed=True."""
        request = UpdateResponseReviewRequest(is_reviewed=True)
        assert request.is_reviewed is True

    def test_valid_review_request_false(self):
        """Test valid UpdateResponseReviewRequest with is_reviewed=False."""
        request = UpdateResponseReviewRequest(is_reviewed=False)
        assert request.is_reviewed is False

    def test_review_request_serialization(self):
        """Test UpdateResponseReviewRequest serialization."""
        request = UpdateResponseReviewRequest(is_reviewed=True)
        request_dict = request.model_dump()

        assert request_dict == {"is_reviewed": True}

    def test_review_request_validation_missing_field(self):
        """Test UpdateResponseReviewRequest validation for missing required field."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateResponseReviewRequest()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("is_reviewed",) and error["type"] == "missing" for error in errors)

    def test_review_request_validation_wrong_type(self):
        """Test UpdateResponseReviewRequest validation for wrong type."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateResponseReviewRequest(is_reviewed="true")  # String instead of bool

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("is_reviewed",) and "bool" in error["type"] for error in errors)

    def test_review_request_from_json(self):
        """Test UpdateResponseReviewRequest creation from JSON-like dict."""
        data = {"is_reviewed": True}
        request = UpdateResponseReviewRequest(**data)
        assert request.is_reviewed is True

        data = {"is_reviewed": False}
        request = UpdateResponseReviewRequest(**data)
        assert request.is_reviewed is False


class TestFormFieldEnhancements:
    """Test cases for form field types and validation related to notifications."""

    def test_field_type_enum_values(self):
        """Test that all expected field types are available."""
        expected_types = [
            "text", "email", "phone", "number", "date", "textarea",
            "select", "radio", "checkbox", "file_upload", "rating", "scale"
        ]

        for field_type in expected_types:
            # Should not raise an error
            field = FormField(
                id="test_field",
                label="Test Field",
                type=FieldType(field_type)
            )
            assert field.type.value == field_type

    def test_form_field_with_rating_type(self):
        """Test FormField specifically for rating type (common in feedback forms)."""
        field = FormField(
            id="overall_rating",
            label="Overall Experience Rating",
            type=FieldType.RATING,
            required=True,
            description="Rate your overall wedding planning experience",
            order=1
        )

        assert field.type == FieldType.RATING
        assert field.required is True
        assert field.order == 1

    def test_form_field_with_scale_type(self):
        """Test FormField for scale type (useful for detailed feedback)."""
        field = FormField(
            id="satisfaction_scale",
            label="Satisfaction Level",
            type=FieldType.SCALE,
            description="Rate from 1-10",
            validation_rules=[
                ValidationRule(type="min", value=1, message="Minimum value is 1"),
                ValidationRule(type="max", value=10, message="Maximum value is 10")
            ]
        )

        assert field.type == FieldType.SCALE
        assert len(field.validation_rules) == 2
        assert field.validation_rules[0].type == "min"
        assert field.validation_rules[1].type == "max"

    def test_validation_rule_for_notifications(self):
        """Test validation rules that might be used in notification-related forms."""
        # Required field validation
        required_rule = ValidationRule(
            type="required",
            value=True,
            message="This field is required for notifications"
        )

        assert required_rule.type == "required"
        assert required_rule.value is True
        assert "notifications" in required_rule.message

        # Email validation
        email_rule = ValidationRule(
            type="pattern",
            value=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            message="Please enter a valid email address"
        )

        assert email_rule.type == "pattern"
        assert isinstance(email_rule.value, str)

    def test_form_field_id_validation(self):
        """Test FormField ID validation for security."""
        # Valid IDs should work
        valid_ids = ["rating", "overall_rating", "feedback-text", "rating_1", "field123"]

        for valid_id in valid_ids:
            field = FormField(
                id=valid_id,
                label="Test Field",
                type=FieldType.TEXT
            )
            assert field.id == valid_id

        # Invalid IDs should raise validation errors
        invalid_ids = ["rating!", "field with spaces", "field@email", "field#123", ""]

        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError):
                FormField(
                    id=invalid_id,
                    label="Test Field",
                    type=FieldType.TEXT
                )

    def test_form_field_label_validation(self):
        """Test FormField label validation."""
        # Valid labels
        field = FormField(
            id="test_field",
            label="Overall Rating",
            type=FieldType.RATING
        )
        assert field.label == "Overall Rating"

        # Empty label should raise validation error
        with pytest.raises(ValidationError):
            FormField(
                id="test_field",
                label="",
                type=FieldType.TEXT
            )

        # Too long label should raise validation error
        with pytest.raises(ValidationError):
            FormField(
                id="test_field",
                label="x" * 101,  # Longer than 100 characters
                type=FieldType.TEXT
            )

    def test_form_field_options_validation(self):
        """Test FormField options validation for select/radio fields."""
        # Valid options
        field = FormField(
            id="rating_options",
            label="Rating Options",
            type=FieldType.SELECT,
            options=["Excellent", "Good", "Average", "Poor"]
        )
        assert len(field.options) == 4

        # Too many options should raise validation error
        with pytest.raises(ValidationError):
            FormField(
                id="test_field",
                label="Test Field",
                type=FieldType.SELECT,
                options=["Option " + str(i) for i in range(51)]  # More than 50 options
            )

        # Option too long should raise validation error
        with pytest.raises(ValidationError):
            FormField(
                id="test_field",
                label="Test Field",
                type=FieldType.SELECT,
                options=["x" * 101]  # Option longer than 100 characters
            )


class TestFormResponseIntegration:
    """Integration tests for FormResponse with realistic notification scenarios."""

    def test_complete_notification_workflow_data(self):
        """Test complete data structure for notification workflow."""
        # Create a response as it would appear after notification processing
        response = FormResponse(
            id="response_789",
            form_id="wedding_feedback_form",
            responses={
                "overall_rating": 5,
                "service_quality": 4,
                "venue_rating": 5,
                "feedback_text": "Absolutely amazing experience! The planning was flawless.",
                "recommend": True
            },
            submitted_by_email="happy.bride@example.com",
            submitted_by_name="Sarah Johnson",
            wedding_id="wedding_456",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)",
            metadata={
                "referrer": "https://wedding-website.example.com",
                "device_type": "mobile",
                "form_version": "2.1"
            },
            # After notification is processed
            notification_sent=True,
            notification_sent_at=datetime.utcnow(),
            # Initially unreviewed
            is_reviewed=False,
            reviewed_at=None,
            reviewed_by=None
        )

        # Verify the response has all notification-related data
        assert response.notification_sent is True
        assert response.notification_sent_at is not None
        assert response.is_reviewed is False

        # Simulate marking as reviewed
        review_update = UpdateResponseReviewRequest(is_reviewed=True)
        assert review_update.is_reviewed is True

        # Response data should be suitable for email template
        assert response.submitted_by_name == "Sarah Johnson"
        assert response.submitted_by_email == "happy.bride@example.com"
        assert "amazing experience" in response.responses["feedback_text"]

    def test_response_serialization_for_api(self):
        """Test response serialization for API endpoints."""
        response = FormResponse(
            form_id="form_123",
            responses={"rating": 5},
            submitted_by_email="user@example.com",
            is_reviewed=True,
            reviewed_at=datetime(2023, 1, 15, 10, 30, 0),
            reviewed_by="admin@example.com"
        )

        # Serialize with aliases (for MongoDB)
        response_dict = response.model_dump(by_alias=True)

        # Should include _id field mapping
        assert "form_id" in response_dict
        assert response_dict["is_reviewed"] is True
        assert response_dict["reviewed_by"] == "admin@example.com"

        # Should be JSON serializable
        import json
        json_str = json.dumps(response_dict, default=str)
        assert "is_reviewed" in json_str
        assert "admin@example.com" in json_str


if __name__ == '__main__':
    pytest.main([__file__])