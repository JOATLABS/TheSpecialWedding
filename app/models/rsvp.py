from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
import re

class PlusOneInputModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None
    attending: List[str] = Field(default_factory=list)
    dietary: Optional[str] = None

    @field_validator("phone")
    def validate_phone(cls, value):
        if value and not re.match(r"^\+?\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits, optionally prefixed with +")
        return value

    @field_validator("attending")
    def validate_attending(cls, v):
        valid_events = {"traditional", "white_wedding", "reception"}
        if not all(event in valid_events for event in v):
            raise ValueError("Invalid event(s) in attending list")
        return v

class RSVPModel(BaseModel):
    attending: List[str]
    dietary: Optional[str] = Field(default=None, max_length=250)
    phone: Optional[str] = None
    sms_opt_in: Optional[bool] = Field(default=False, description="Opt-in to receive SMS reminders")
    plus_ones: Optional[List[PlusOneInputModel]] = Field(default_factory=list, max_length=10)

    @field_validator("attending")
    def validate_attending(cls, v):
        valid_events = {"traditional", "white_wedding", "reception"}
        # Allow empty list (guest not attending any events) or valid events
        if v and not all(event in valid_events for event in v):
            raise ValueError("Invalid event(s) in attending list")
        return v

    @field_validator("phone")
    def validate_phone(cls, value):
        if value and not re.match(r"^\+?\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits, optionally prefixed with +")
        return value