from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

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
    type: str = Field(..., description="Validation type: required, min_length, max_length, pattern, min, max")
    value: Union[str, int, bool] = Field(..., description="Validation value")
    message: Optional[str] = Field(None, description="Custom validation error message")

class FormField(BaseModel):
    id: str = Field(..., description="Unique field identifier")
    label: str = Field(..., description="Field label")
    type: FieldType = Field(..., description="Field input type")
    placeholder: Optional[str] = Field(None, description="Field placeholder text")
    required: bool = Field(default=False, description="Whether field is required")
    description: Optional[str] = Field(None, description="Field description/help text")
    options: List[str] = Field(default_factory=list, description="Options for select/radio/checkbox fields")
    validation_rules: List[ValidationRule] = Field(default_factory=list, description="Field validation rules")
    conditional_logic: Optional[Dict[str, Any]] = Field(None, description="Show/hide conditions")
    order: int = Field(default=0, description="Field display order")

class FormSettings(BaseModel):
    title: str = Field(..., description="Form title")
    description: Optional[str] = Field(None, description="Form description")
    submit_button_text: str = Field(default="Submit", description="Submit button text")
    success_message: str = Field(default="Thank you for your submission!", description="Success message")
    redirect_url: Optional[str] = Field(None, description="Redirect URL after submission")
    allow_multiple_submissions: bool = Field(default=False, description="Allow multiple submissions from same user")
    collect_email: bool = Field(default=True, description="Require email from submitters")
    is_public: bool = Field(default=False, description="Whether form is publicly accessible")
    requires_auth: bool = Field(default=False, description="Whether form requires authentication")

class EmailDistributionSettings(BaseModel):
    subject: str = Field(..., description="Email subject line")
    message: str = Field(..., description="Email body message")
    sender_name: str = Field(..., description="Sender name")
    include_form_link: bool = Field(default=True, description="Include direct form link")
    send_reminder: bool = Field(default=False, description="Send reminder emails")
    reminder_days: int = Field(default=7, description="Days until reminder")

class FormModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id", description="Form ID")
    name: str = Field(..., description="Internal form name")
    settings: FormSettings = Field(..., description="Form configuration")
    fields: List[FormField] = Field(..., description="Form fields")
    email_distribution: Optional[EmailDistributionSettings] = Field(None, description="Email settings")
    created_by: str = Field(..., description="Creator email")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    template_type: Optional[str] = Field(None, description="Form template type")
    is_active: bool = Field(default=True, description="Whether form is active")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    submission_count: int = Field(default=0, description="Total submissions received")

    class Config:
        populate_by_name = True
        schema_extra = {
            "example": {
                "name": "Wedding Feedback Form",
                "settings": {
                    "title": "How was your wedding experience?",
                    "description": "We'd love to hear about your special day!",
                    "submit_button_text": "Send Feedback",
                    "success_message": "Thank you for your feedback!"
                },
                "fields": [
                    {
                        "id": "overall_rating",
                        "label": "Overall Experience Rating",
                        "type": "rating",
                        "required": True,
                        "description": "Rate your overall wedding planning experience",
                        "order": 1
                    },
                    {
                        "id": "feedback_text",
                        "label": "Additional Comments",
                        "type": "textarea",
                        "placeholder": "Tell us more about your experience...",
                        "order": 2
                    }
                ],
                "created_by": "planner@example.com",
                "template_type": "wedding_feedback"
            }
        }

class FormResponse(BaseModel):
    id: Optional[str] = Field(None, alias="_id", description="Response ID")
    form_id: str = Field(..., description="Form ID")
    responses: Dict[str, Any] = Field(..., description="Field responses keyed by field ID")
    submitted_by_email: Optional[str] = Field(None, description="Submitter email")
    submitted_by_name: Optional[str] = Field(None, description="Submitter name")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    ip_address: Optional[str] = Field(None, description="Submitter IP address")
    user_agent: Optional[str] = Field(None, description="Submitter user agent")
    submitted_at: datetime = Field(default_factory=datetime.utcnow, description="Submission timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        populate_by_name = True
        schema_extra = {
            "example": {
                "form_id": "form_123",
                "responses": {
                    "overall_rating": 5,
                    "feedback_text": "Amazing experience! Everything was perfect."
                },
                "submitted_by_email": "bride@example.com",
                "submitted_by_name": "Jane Doe",
                "wedding_id": "wedding_456"
            }
        }

class FormDistribution(BaseModel):
    id: Optional[str] = Field(None, alias="_id", description="Distribution ID")
    form_id: str = Field(..., description="Form ID")
    recipient_email: str = Field(..., description="Recipient email address")
    recipient_name: Optional[str] = Field(None, description="Recipient name")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    sent_at: datetime = Field(default_factory=datetime.utcnow, description="Email sent timestamp")
    opened_at: Optional[datetime] = Field(None, description="Email opened timestamp")
    clicked_at: Optional[datetime] = Field(None, description="Form link clicked timestamp")
    submitted_at: Optional[datetime] = Field(None, description="Form submitted timestamp")
    status: str = Field(default="sent", description="Distribution status: sent, opened, clicked, submitted")
    email_id: Optional[str] = Field(None, description="Email service provider ID")

    class Config:
        populate_by_name = True

# Form Builder Request Models
class CreateFormRequest(BaseModel):
    name: str = Field(..., description="Form name")
    settings: FormSettings = Field(..., description="Form settings")
    fields: List[FormField] = Field(..., description="Form fields")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    template_type: Optional[str] = Field(None, description="Template type")

class UpdateFormRequest(BaseModel):
    name: Optional[str] = Field(None, description="Form name")
    settings: Optional[FormSettings] = Field(None, description="Form settings")
    fields: Optional[List[FormField]] = Field(None, description="Form fields")
    is_active: Optional[bool] = Field(None, description="Form active status")

class SendFormRequest(BaseModel):
    recipient_emails: List[str] = Field(..., description="Recipient email addresses")
    email_settings: EmailDistributionSettings = Field(..., description="Email configuration")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")

class SubmitFormRequest(BaseModel):
    responses: Dict[str, Any] = Field(..., description="Form field responses")
    submitted_by_email: Optional[str] = Field(None, description="Submitter email")
    submitted_by_name: Optional[str] = Field(None, description="Submitter name")