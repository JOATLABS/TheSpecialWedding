"""
Support Ticket Models for SMS and Web-based Support System
Provides Pydantic models with validation for multi-tenant support tickets
"""
from pydantic import BaseModel, Field, field_validator, field_serializer
from typing import Optional, List
from datetime import datetime
from app.models.base import MongoModel, WeddingRelatedModel, UserRelatedModel
from app.utils.pydantic_objectid import PyObjectId
import re


class SMSResponseModel(BaseModel):
    """Individual SMS response in a ticket conversation"""
    message: str = Field(..., min_length=1, max_length=1600, description="Response message content (SMS limit)")
    sent_by: str = Field(..., max_length=254, description="Email of person who sent response")
    sent_by_name: str = Field(..., max_length=100, description="Display name of sender")
    sent_at: datetime = Field(..., description="When response was sent (UTC)")
    sms_provider: Optional[str] = Field(None, description="SMS provider used: twilio or telnyx")
    message_id: Optional[str] = Field(None, description="Provider's message ID for tracking")

    @field_validator("sms_provider")
    @classmethod
    def validate_provider(cls, v):
        if v and v not in ["twilio", "telnyx"]:
            raise ValueError("SMS provider must be 'twilio' or 'telnyx'")
        return v

    @field_serializer('sent_at', when_used='json')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat() if dt else None


class SupportTicketModel(MongoModel):
    """
    SMS Support Ticket Model
    Represents a support message received via SMS from a wedding guest

    Multi-tenant: Tickets are scoped to specific wedding planners via assigned_to field
    """

    # Message Details
    phone: str = Field(..., min_length=10, max_length=20, description="Guest's phone number (E.164 format)")
    message: str = Field(..., min_length=1, max_length=5000, description="Original message from guest")
    source: str = Field(default="sms", description="Message source")
    provider: str = Field(..., description="SMS provider: twilio or telnyx")
    message_sid: Optional[str] = Field(None, description="Provider's message ID (Twilio MessageSid)")

    # Guest Context (Optional - may not exist for unknown senders)
    guest_id: Optional[str] = Field(None, description="Guest MongoDB ObjectId string")
    guest_name: Optional[str] = Field(None, max_length=100, description="Guest's name for quick reference")

    # Wedding Context (Optional - required for routing)
    wedding_id: Optional[str] = Field(None, description="Wedding MongoDB ObjectId string")
    wedding_name: Optional[str] = Field(None, max_length=200, description="Wedding couple names")

    # Routing & Assignment (Critical for multi-tenant isolation)
    assigned_to: Optional[str] = Field(None, max_length=254, description="Wedding planner email who should handle this")
    planner_name: Optional[str] = Field(None, max_length=100, description="Wedding planner display name")

    # Ticket Management
    status: str = Field(default="new", description="Ticket status")
    priority: str = Field(default="normal", description="Priority level")
    category: Optional[str] = Field(None, max_length=50, description="Category: ceremony, venue, dietary, etc.")
    is_read: bool = Field(default=False, description="Whether planner has read this ticket")

    # Response History
    responses: List[SMSResponseModel] = Field(default_factory=list, description="All SMS responses sent")

    # Metrics (SLA Tracking - automatically calculated)
    first_response_at: Optional[datetime] = Field(None, description="When first response was sent")
    first_response_time_minutes: Optional[int] = Field(None, ge=0, description="Minutes from creation to first response")
    resolved_at: Optional[datetime] = Field(None, description="When ticket was marked resolved")
    resolution_time_minutes: Optional[int] = Field(None, ge=0, description="Minutes from creation to resolution")

    # Audit Trail
    updated_by: Optional[str] = Field(None, max_length=254, description="Email of who last updated the ticket")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate phone number format (E.164)"""
        if not v:
            return v
        # Remove all non-digit characters except leading +
        cleaned = re.sub(r'[^\d+]', '', v)
        # Basic validation: should start with + and have 10-15 digits
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            raise ValueError("Phone number must be in E.164 format (+1234567890)")
        return cleaned

    @field_validator("source")
    @classmethod
    def validate_source(cls, v):
        """Validate message source"""
        valid_sources = ["sms", "email", "web_form", "chat"]
        if v not in valid_sources:
            raise ValueError(f"Source must be one of: {', '.join(valid_sources)}")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        """Validate SMS provider"""
        if v not in ["twilio", "telnyx"]:
            raise ValueError("Provider must be 'twilio' or 'telnyx'")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        """Validate ticket status"""
        valid_statuses = ["new", "in_progress", "resolved", "closed"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        """Validate priority level"""
        valid_priorities = ["low", "normal", "high", "urgent"]
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(valid_priorities)}")
        return v

    @field_serializer('first_response_at', 'resolved_at', when_used='json')
    def serialize_optional_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """Serialize optional datetime fields"""
        return dt.isoformat() if dt else None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "phone": "+13195296088",
                "message": "What time does the ceremony start?",
                "source": "sms",
                "provider": "twilio",
                "message_sid": "SM1234567890abcdef",
                "guest_id": "507f1f77bcf86cd799439012",
                "guest_name": "Jane Doe",
                "wedding_id": "507f1f77bcf86cd799439013",
                "wedding_name": "Sarah & John",
                "assigned_to": "planner@dreamweddings.com",
                "planner_name": "Dream Weddings LLC",
                "status": "new",
                "priority": "normal",
                "is_read": False,
                "responses": [],
                "created_at": "2025-01-19T10:30:00Z",
                "updated_at": "2025-01-19T10:30:00Z"
            }
        }


class GeneralSupportTicketModel(MongoModel, UserRelatedModel):
    """
    General Support Ticket Model (Web-based)
    For platform support tickets created through web forms
    Extends both MongoModel and UserRelatedModel for automatic user tracking
    """
    subject: str = Field(..., min_length=1, max_length=200, description="Ticket subject/title")
    description: str = Field(..., min_length=1, max_length=5000, description="Detailed description of issue")
    priority: str = Field(default="medium", description="Priority: low, medium, high, urgent")
    category: str = Field(default="general", description="Ticket category")
    status: str = Field(default="open", description="Status: open, in_progress, resolved, closed")

    # Assignment (for ROOT_ADMIN ticket routing)
    assigned_to: Optional[str] = Field(None, max_length=254, description="Email of admin handling this")
    assigned_to_name: Optional[str] = Field(None, max_length=100, description="Name of assigned admin")

    # Context
    wedding_id: Optional[str] = Field(None, description="Related wedding ID if applicable")
    attachments: List[str] = Field(default_factory=list, description="URLs of attached files")

    # Comments/Updates
    comments: List[dict] = Field(default_factory=list, description="Ticket comments and updates")

    # Resolution tracking
    resolved_at: Optional[datetime] = Field(None, description="When ticket was resolved")
    closed_at: Optional[datetime] = Field(None, description="When ticket was closed")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        valid_priorities = ["low", "medium", "high", "urgent"]
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(valid_priorities)}")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        valid_categories = ["technical", "billing", "feature_request", "bug_report", "general"]
        if v not in valid_categories:
            raise ValueError(f"Category must be one of: {', '.join(valid_categories)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["open", "in_progress", "resolved", "closed"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v

    @field_serializer('resolved_at', 'closed_at', when_used='json')
    def serialize_optional_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        return dt.isoformat() if dt else None
