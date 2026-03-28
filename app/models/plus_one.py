from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
import re
from app.utils.contact_sanitizer import sanitize_phone, sanitize_email, validate_email_format
from app.utils.wedding_event_types import normalize_event_type_list


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class PlusOneModel(BaseModel):
    guest_id: str = Field(...)  # Store as string, convert to ObjectId when needed
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None
    email: Optional[str] = None
    attending: List[str] = Field(default_factory=list)
    dietary: Optional[str] = None
    sms_opt_in: Optional[bool] = Field(default=None, description="Opted in for SMS reminders")
    sms_opt_in_date: Optional[datetime] = Field(None, description="When opted in to SMS")
    sms_opt_out_date: Optional[datetime] = Field(None, description="When opted out of SMS")
    email_opt_in: Optional[bool] = Field(default=None, description="Opted in for email reminders")
    email_opt_in_date: Optional[datetime] = Field(None, description="When opted in to email")
    email_opt_out_date: Optional[datetime] = Field(None, description="When opted out of email")

    @field_validator("phone")
    def validate_phone(cls, value):
        if not value:
            return None
        # Sanitize: strip whitespace and delimiters like (), -, .
        value = sanitize_phone(value)
        if not value:
            return None
        if not re.match(r"^\+?\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits, optionally prefixed with +")
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

    @field_validator("attending")
    def validate_attending(cls, v):
        return normalize_event_type_list(v)

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "guest_id": "60c7d3e9e1b1fdbb4f12d9aa",
                "name": "Jane Doe",
                "phone": "1234567890",
                "email": "jane.doe@example.com",
                "attending": ["reception"],
                "dietary": "Vegetarian",
                "sms_opt_in": True,
                "email_opt_in": True
            }
        }
