from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from bson import ObjectId
import re

class GuestModel(BaseModel):
    wedding_id: str = Field(...)
    name: str = Field(..., min_length=2, max_length=100)
    token: str = Field(..., min_length=6)
    phone: Optional[str] = None
    email: Optional[str] = None
    group_id: Optional[str] = None
    table_id: Optional[str] = Field(default=None, description="Assigned table ID")
    role: Optional[str] = Field("guest")
    plus_one_allowed: Optional[bool] = Field(default=False)
    number_of_plus_ones_allowed: Optional[int] = Field(default=0, ge=0, le=10)
    plus_one_submitted: Optional[bool] = Field(default=False)
    sms_opt_in: Optional[bool] = Field(default=False, description="Guest opted in to receive SMS reminders")
    sms_opt_in_date: Optional[datetime] = Field(None, description="When guest opted in to SMS")
    sms_opt_out_date: Optional[datetime] = Field(None, description="When guest opted out of SMS")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("token")
    def validate_token(cls, value):
        if not re.match(r"^[a-zA-Z0-9]+$", value):
            raise ValueError("Token must be alphanumeric")
        return value

    @field_validator("phone")
    def validate_phone(cls, value):
        if value and not re.match(r"^\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits")
        return value

    class Config:
        schema_extra = {
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
                "plus_one_submitted": False
            }
        }

class UpdateGuestRequest(BaseModel):
    """Request model for updating guest information"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    email: Optional[str] = None
    group_id: Optional[str] = None
    table_id: Optional[str] = None
    role: Optional[str] = None
    plus_one_allowed: Optional[bool] = None
    number_of_plus_ones_allowed: Optional[int] = Field(None, ge=0, le=10)
    sms_opt_in: Optional[bool] = None

    @field_validator("phone")
    def validate_phone(cls, value):
        if value and not re.match(r"^\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits")
        return value

    class Config:
        schema_extra = {
            "example": {
                "name": "Jane Doe",
                "phone": "1234567890",
                "email": "jane@example.com",
                "role": "guest",
                "plus_one_allowed": True,
                "number_of_plus_ones_allowed": 2
            }
        }