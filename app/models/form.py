from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union, Literal
from datetime import datetime
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class FieldType(str, Enum):
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    DATE = "date"
    TEXTAREA = "textarea"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    FILE_UPLOAD = "file_upload"
    RATING = "rating"
    SCALE = "scale"


class ValidationRule(BaseModel):
    type: str = Field(
        ...,
        description="Validation type: required, min_length, max_length, pattern, min, max",
    )
    value: Union[str, int, bool] = Field(..., description="Validation value")
    message: Optional[str] = Field(None, description="Custom validation error message")


class FormField(BaseModel):
    id: str = Field(..., description="Unique field identifier")
    label: str = Field(..., description="Field label")
    type: FieldType = Field(..., description="Field input type")
    placeholder: Optional[str] = Field(None, description="Field placeholder text")
    required: bool = Field(default=False, description="Whether field is required")
    description: Optional[str] = Field(None, description="Field description/help text")
    options: List[str] = Field(
        default_factory=list, description="Options for select/radio/checkbox fields"
    )
    validation_rules: List[ValidationRule] = Field(
        default_factory=list, description="Field validation rules"
    )
    conditional_logic: Optional[Dict[str, Any]] = Field(
        None, description="Show/hide conditions"
    )
    order: int = Field(default=0, description="Field display order")

    @field_validator("id")
    @classmethod
    def validate_field_id(cls, v):
        """Validate field ID format for security"""
        if not v or not isinstance(v, str):
            raise ValueError("Field ID is required")

        # Remove dangerous characters and validate format
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Field ID can only contain letters, numbers, underscores, and hyphens"
            )

        if len(v) > 50:
            raise ValueError("Field ID too long (max 50 characters)")

        return v

    @field_validator("label")
    @classmethod
    def validate_label(cls, v):
        """Validate and sanitize field label"""
        if not v or not isinstance(v, str):
            raise ValueError("Field label is required")

        # Basic length validation
        if len(v) > 100:
            raise ValueError("Field label too long (max 100 characters)")

        return v.strip()

    @field_validator("options")
    @classmethod
    def validate_options(cls, v):
        """Validate field options"""
        if not isinstance(v, list):
            return []

        if len(v) > 50:
            raise ValueError("Too many options (max 50)")

        # Validate each option
        validated_options = []
        for option in v:
            if isinstance(option, str) and option.strip():
                if len(option) > 100:
                    raise ValueError("Option too long (max 100 characters)")
                validated_options.append(option.strip())

        return validated_options

    @field_validator("placeholder", "description")
    @classmethod
    def validate_text_fields(cls, v):
        """Validate text fields"""
        if v is None:
            return v

        if not isinstance(v, str):
            return None

        # Basic length validation
        if len(v) > 500:
            raise ValueError("Text field too long (max 500 characters)")

        return v.strip()


class FormSettings(BaseModel):
    title: str = Field(..., description="Form title")
    description: Optional[str] = Field(None, description="Form description")
    submit_button_text: str = Field(default="Submit", description="Submit button text")
    success_message: str = Field(
        default="Thank you for your submission!", description="Success message"
    )
    redirect_url: Optional[str] = Field(
        None, description="Redirect URL after submission"
    )
    allow_multiple_submissions: bool = Field(
        default=False, description="Allow multiple submissions from same user"
    )
    collect_email: bool = Field(
        default=True, description="Require email from submitters"
    )
    is_public: bool = Field(
        default=False, description="Whether form is publicly accessible"
    )
    requires_auth: bool = Field(
        default=False, description="Whether form requires authentication"
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        """Validate form title"""
        if not v or not isinstance(v, str):
            raise ValueError("Form title is required")

        if len(v) > 200:
            raise ValueError("Form title too long (max 200 characters)")

        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        """Validate form description"""
        if v is None:
            return v

        if not isinstance(v, str):
            return None

        if len(v) > 1000:
            raise ValueError("Form description too long (max 1000 characters)")

        return v.strip()

    @field_validator("submit_button_text", "success_message")
    @classmethod
    def validate_text_fields(cls, v):
        """Validate text fields"""
        if not isinstance(v, str):
            raise ValueError("Text field must be a string")

        if len(v) > 100:
            raise ValueError("Text field too long (max 100 characters)")

        return v.strip()

    @field_validator("redirect_url")
    @classmethod
    def validate_redirect_url(cls, v):
        """Validate redirect URL"""
        if v is None:
            return v

        if not isinstance(v, str):
            return None

        # Basic URL validation
        from urllib.parse import urlparse

        try:
            parsed = urlparse(v)
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("Invalid URL scheme (must be http or https)")
            if not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception:
            raise ValueError("Invalid URL format")
        return v


class EmailDistributionSettings(BaseModel):
    subject: str = Field(..., description="Email subject line")
    message: str = Field(..., description="Email body message")
    sender_name: str = Field(..., description="Sender name")
    include_form_link: bool = Field(
        default=True, description="Include direct form link"
    )
    send_reminder: bool = Field(default=False, description="Send reminder emails")
    reminder_days: int = Field(default=7, description="Days until reminder")


class FormType(str, Enum):
    """Polymorphic discriminator for form types.

    Per MongoDB Polymorphic Pattern best practices (Jan 2026), a discriminator
    field enables different-shaped documents to coexist in a single collection
    while maintaining efficient queries via compound indexes.
    Ref: https://oneuptime.com/blog/post/2026-01-30-mongodb-polymorphic-patterns/view
    """

    GENERAL = "general"
    VENDOR_INTAKE = "vendor_intake"
    RSVP_CUSTOM = "rsvp_custom"
    WEDDING_FEEDBACK = "wedding_feedback"
    GUEST_FEEDBACK = "guest_feedback"
    VENDOR_QUESTIONNAIRE = "vendor_questionnaire"
    CONTACT_FORM = "contact_form"
    SURVEY = "survey"
    REGISTRATION = "registration"


class FormModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id", description="Form ID")
    name: str = Field(..., description="Internal form name")
    form_type: FormType = Field(
        default=FormType.GENERAL,
        description="Polymorphic discriminator — identifies the form category for "
        "type-specific queries and indexes. Existing forms without this "
        "field default to 'general'.",
    )
    settings: FormSettings = Field(..., description="Form configuration")
    fields: List[FormField] = Field(..., description="Form fields")
    email_distribution: Optional[EmailDistributionSettings] = Field(
        None, description="Email settings"
    )
    created_by: str = Field(..., description="Creator email")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    template_type: Optional[str] = Field(
        None,
        description="DEPRECATED — use form_type instead. Retained for backward compatibility "
        "with existing documents. Will be removed in a future sprint.",
    )
    is_active: bool = Field(default=True, description="Whether form is active")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
    submission_count: int = Field(default=0, description="Total submissions received")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "name": "Wedding Feedback Form",
                "settings": {
                    "title": "How was your wedding experience?",
                    "description": "We'd love to hear about your special day!",
                    "submit_button_text": "Send Feedback",
                    "success_message": "Thank you for your feedback!",
                },
                "fields": [
                    {
                        "id": "overall_rating",
                        "label": "Overall Experience Rating",
                        "type": "rating",
                        "required": True,
                        "description": "Rate your overall wedding planning experience",
                        "order": 1,
                    },
                    {
                        "id": "feedback_text",
                        "label": "Additional Comments",
                        "type": "textarea",
                        "placeholder": "Tell us more about your experience...",
                        "order": 2,
                    },
                ],
                "created_by": "planner@example.com",
                "template_type": "wedding_feedback",
            }
        }


class FormResponse(BaseModel):
    id: Optional[str] = Field(None, alias="_id", description="Response ID")
    form_id: str = Field(..., description="Form ID")
    responses: Dict[str, Any] = Field(
        ..., description="Field responses keyed by field ID"
    )
    submitted_by_email: Optional[str] = Field(None, description="Submitter email")
    submitted_by_name: Optional[str] = Field(None, description="Submitter name")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    ip_address: Optional[str] = Field(None, description="Submitter IP address")
    user_agent: Optional[str] = Field(None, description="Submitter user agent")
    submitted_at: datetime = Field(
        default_factory=datetime.utcnow, description="Submission timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "form_id": "form_123",
                "responses": {
                    "overall_rating": 5,
                    "feedback_text": "Amazing experience! Everything was perfect.",
                },
                "submitted_by_email": "bride@example.com",
                "submitted_by_name": "Jane Doe",
                "wedding_id": "wedding_456",
            }
        }


class FormDistribution(BaseModel):
    id: Optional[str] = Field(None, alias="_id", description="Distribution ID")
    form_id: str = Field(..., description="Form ID")
    recipient_email: str = Field(..., description="Recipient email address")
    recipient_name: Optional[str] = Field(None, description="Recipient name")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    sent_at: datetime = Field(
        default_factory=datetime.utcnow, description="Email sent timestamp"
    )
    opened_at: Optional[datetime] = Field(None, description="Email opened timestamp")
    clicked_at: Optional[datetime] = Field(
        None, description="Form link clicked timestamp"
    )
    submitted_at: Optional[datetime] = Field(
        None, description="Form submitted timestamp"
    )
    status: str = Field(
        default="sent",
        description="Distribution status: sent, opened, clicked, submitted",
    )
    email_id: Optional[str] = Field(None, description="Email service provider ID")

    class Config:
        populate_by_name = True


# Form Builder Request Models


class CreateFormRequest(BaseModel):
    name: str = Field(..., description="Form name")
    form_type: FormType = Field(
        default=FormType.GENERAL,
        description="Form category discriminator. Defaults to 'general' for backward compatibility.",
    )
    settings: FormSettings = Field(..., description="Form settings")
    fields: List[FormField] = Field(..., description="Form fields")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    template_type: Optional[str] = Field(None, description="Template type")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate form name"""
        if not v or not isinstance(v, str):
            raise ValueError("Form name is required")

        if len(v) > 100:
            raise ValueError("Form name too long (max 100 characters)")

        return v.strip()

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v):
        """Validate form fields"""
        if not isinstance(v, list):
            raise ValueError("Fields must be a list")

        if len(v) > 50:
            raise ValueError("Too many fields (max 50)")

        # Check for duplicate field IDs
        field_ids = [field.id for field in v]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("Field IDs must be unique")

        return v

    @field_validator("template_type")
    @classmethod
    def validate_template_type(cls, v):
        """Validate template type"""
        if v is None:
            return v

        if not isinstance(v, str):
            return None

        # Restrict to known template types
        allowed_templates = [
            "wedding_feedback",
            "guest_feedback",
            "vendor_questionnaire",
            "contact_form",
            "survey",
            "registration",
        ]
        if v not in allowed_templates:
            logger.warning(f"Unknown template type: {v}")

        return v.strip() if len(v) <= 50 else v[:50]


class DuplicateFormRequest(BaseModel):
    new_name: str = Field(..., description="Name for the duplicated form")

    @field_validator("new_name")
    @classmethod
    def validate_new_name(cls, value: str) -> str:
        if not value or not isinstance(value, str):
            raise ValueError("Form name is required")

        trimmed = value.strip()
        if len(trimmed) == 0:
            raise ValueError("Form name is required")
        if len(trimmed) > 100:
            raise ValueError("Form name too long (max 100 characters)")

        return trimmed


class FormViewUpdateRequest(BaseModel):
    scope: Literal["responses", "analytics"] = Field(
        ..., description="Area of the product that was viewed"
    )
    submission_count: Optional[int] = Field(
        None, description="Latest known submission count for the form"
    )

    @field_validator("submission_count")
    @classmethod
    def validate_submission_count(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value

        if not isinstance(value, int):
            raise ValueError("submission_count must be an integer")
        if value < 0:
            raise ValueError("submission_count cannot be negative")

        return value


class UpdateFormRequest(BaseModel):
    name: Optional[str] = Field(None, description="Form name")
    settings: Optional[FormSettings] = Field(None, description="Form settings")
    fields: Optional[List[FormField]] = Field(None, description="Form fields")
    is_active: Optional[bool] = Field(None, description="Form active status")


class SendFormRequest(BaseModel):
    recipient_emails: List[str] = Field(..., description="Recipient email addresses")
    email_settings: EmailDistributionSettings = Field(
        ..., description="Email configuration"
    )
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")


class SubmitFormRequest(BaseModel):
    responses: Dict[str, Any] = Field(..., description="Form field responses")
    submitted_by_email: Optional[str] = Field(None, description="Submitter email")
    submitted_by_name: Optional[str] = Field(None, description="Submitter name")

    @field_validator("responses")
    @classmethod
    def validate_responses(cls, v):
        """Validate form responses"""
        if not isinstance(v, dict):
            raise ValueError("Responses must be a dictionary")

        if len(v) > 100:  # Reasonable limit on response count
            raise ValueError("Too many response fields")

        # Validate field IDs in responses
        for field_id in v.keys():
            if not isinstance(field_id, str):
                raise ValueError("Response field IDs must be strings")

            if not re.match(r"^[a-zA-Z0-9_-]+$", field_id):
                raise ValueError(f"Invalid response field ID: {field_id}")

        return v

    @field_validator("submitted_by_email")
    @classmethod
    def validate_email(cls, v):
        """Validate submitter email"""
        if v is None:
            return v

        if not isinstance(v, str):
            return None

        # Basic email validation
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")

        if len(v) > 254:  # RFC 5321 limit
            raise ValueError("Email address too long")

        return v.lower().strip()

    @field_validator("submitted_by_name")
    @classmethod
    def validate_name(cls, v):
        """Validate submitter name"""
        if v is None:
            return v

        if not isinstance(v, str):
            return None

        if len(v) > 100:
            raise ValueError("Name too long (max 100 characters)")

        return v.strip()
