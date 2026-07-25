import re
from datetime import datetime

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.utils.contact_sanitizer import (
    sanitize_email,
    sanitize_phone,
    validate_email_format,
)


class GuestModel(BaseModel):
    wedding_id: str = Field(...)
    name: str = Field(..., min_length=2, max_length=100)
    token: str = Field(..., min_length=6)
    phone: str | None = None
    email: str | None = None
    group_id: str | None = None
    table_id: str | None = Field(None, description="ID of assigned seating table")
    role: str | None = Field("guest")
    plus_one_allowed: bool | None = Field(default=False)
    number_of_plus_ones_allowed: int | None = Field(default=0, ge=0, le=10)
    plus_one_submitted: bool | None = Field(default=False)
    sms_opt_in: bool | None = Field(
        default=None,
        description="Guest opted in to receive SMS reminders (None=not yet decided)",
    )
    sms_opt_in_date: datetime | None = Field(
        None, description="When guest opted in to SMS"
    )
    sms_opt_out_date: datetime | None = Field(
        None, description="When guest opted out of SMS"
    )
    phone_status: str | None = Field(
        None,
        description="Phone delivery status: unknown, valid, invalid, landline, unreachable, unsubscribed",
    )
    phone_status_updated_at: datetime | None = Field(
        None, description="When phone_status was last updated"
    )
    email_opt_in: bool | None = Field(
        default=None,
        description="Guest opted in to receive email reminders (None=not yet decided)",
    )
    email_opt_in_date: datetime | None = Field(
        None, description="When guest opted in to email"
    )
    email_opt_out_date: datetime | None = Field(
        None, description="When guest opted out of email"
    )
    invite_sent: bool | None = Field(
        default=False, description="Whether initial invitation was sent"
    )
    invite_sent_date: datetime | None = Field(
        None, description="When initial invitation was sent"
    )
    # Seating optimization fields
    must_sit_with: list[str] | None = Field(
        default_factory=list,
        description="Guest IDs that this guest must sit with (e.g., spouse, partner)",
    )
    must_sit_apart: list[str] | None = Field(
        default_factory=list,
        description="Guest IDs that this guest should NOT sit near (e.g., ex-partners, conflicts)",
    )
    accessibility_needs: str | None = Field(
        None,
        description="Accessibility requirements (e.g., wheelchair, near exit, quiet area)",
    )
    seating_preference: str | None = Field(
        None,
        description="Seating preference (e.g., near_dance_floor, quiet_corner, near_bar)",
    )
    age_group: str | None = Field(
        None, description="Age group for seating (child, young_adult, adult, elder)"
    )
    language_preference: str | None = Field(
        None, description="Primary language for multilingual wedding seating"
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("token")
    def validate_token(cls, value):
        if not re.match(r"^[a-zA-Z0-9]+$", value):
            raise ValueError("Token must be alphanumeric")
        return value

    @field_validator("phone")
    def validate_phone(cls, value):
        if not value:
            return None
        # Sanitize: strip whitespace and delimiters like (), -, .
        value = sanitize_phone(value)
        if not value:
            return None
        if not re.match(r"^\+?\d{10,15}$", value):
            raise ValueError(
                "Phone number must be 10 to 15 digits, optionally prefixed with +"
            )
        return value

    @field_validator("email")
    def validate_email(cls, v):
        if not v:
            return None
        v = sanitize_email(v)
        if not v:
            return None
        if not validate_email_format(v):
            raise ValueError("Invalid email format")
        return v

    @field_serializer(
        "sms_opt_in_date",
        "sms_opt_out_date",
        "phone_status_updated_at",
        "email_opt_in_date",
        "email_opt_out_date",
        "invite_sent_date",
        "created_at",
        "updated_at",
        when_used="json",
    )
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    class Config:
        json_schema_extra = {
            "example": {
                "wedding_id": "wedding_001",
                "name": "John Doe",
                "token": "abc123xyz",
                "phone": "1234567890",
                "email": "john@example.com",
                "group_id": "grp_fam_001",
                "role": "guest",
                "plus_one_allowed": True,
                "number_of_plus_ones_allowed": 2,
                "plus_one_submitted": False,
            }
        }


class UpdateGuestRequest(BaseModel):
    """Request model for updating guest information"""

    name: str | None = Field(None, min_length=2, max_length=100)
    phone: str | None = None
    email: str | None = None
    group_id: str | None = None
    table_id: str | None = Field(None, description="ID of assigned seating table")
    role: str | None = None
    plus_one_allowed: bool | None = None
    number_of_plus_ones_allowed: int | None = Field(None, ge=0, le=10)
    sms_opt_in: bool | None = None
    email_opt_in: bool | None = None
    phone_status: str | None = Field(None, description="Phone delivery status")
    # Seating optimization fields
    must_sit_with: list[str] | None = Field(
        None, description="Guest IDs that this guest must sit with"
    )
    must_sit_apart: list[str] | None = Field(
        None, description="Guest IDs that this guest should NOT sit near"
    )
    accessibility_needs: str | None = Field(
        None, description="Accessibility requirements"
    )
    seating_preference: str | None = Field(None, description="Seating preference")
    age_group: str | None = Field(
        None, description="Age group (child, young_adult, adult, elder)"
    )
    language_preference: str | None = Field(
        None, description="Primary language for seating"
    )

    @field_validator("phone")
    def validate_phone(cls, value):
        if not value:
            return None
        value = sanitize_phone(value)
        if not value:
            return None
        if not re.match(r"^\+?\d{10,15}$", value):
            raise ValueError(
                "Phone number must be 10 to 15 digits, optionally prefixed with +"
            )
        return value

    @field_validator("email")
    def validate_email(cls, v):
        if not v:
            return None
        v = sanitize_email(v)
        if not v:
            return None
        if not validate_email_format(v):
            raise ValueError("Invalid email format")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Jane Doe",
                "phone": "1234567890",
                "email": "jane@example.com",
                "role": "guest",
                "plus_one_allowed": True,
                "number_of_plus_ones_allowed": 2,
                "sms_opt_in": True,
                "email_opt_in": True,
            }
        }


class CreateGuestRequest(BaseModel):
    """Request model for creating a single guest"""

    name: str = Field(..., min_length=2, max_length=100)
    phone: str | None = None
    email: str | None = None
    group_id: str | None = None
    role: str | None = Field("guest")
    plus_one_allowed: bool | None = Field(default=False)
    number_of_plus_ones_allowed: int | None = Field(default=0, ge=0, le=10)

    @field_validator("phone")
    def validate_phone(cls, value):
        if not value:
            return None
        value = sanitize_phone(value)
        if not value:
            return None
        if not re.match(r"^\+?\d{10,15}$", value):
            raise ValueError(
                "Phone number must be 10 to 15 digits, optionally prefixed with +"
            )
        return value

    @field_validator("email")
    def validate_email(cls, v):
        if not v:
            return None
        v = sanitize_email(v)
        if not v:
            return None
        if not validate_email_format(v):
            raise ValueError("Invalid email format")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "phone": "1234567890",
                "email": "john@example.com",
                "role": "guest",
                "group_id": "family_bride",
                "plus_one_allowed": True,
                "number_of_plus_ones_allowed": 1,
            }
        }
