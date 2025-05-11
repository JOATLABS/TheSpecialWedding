from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class RSVPModel(BaseModel):
    attending: List[str] = Field(..., example=["traditional", "reception"])
    dietary: Optional[str] = Field(None, max_length=250)
    phone: Optional[str] = None

    @field_validator("attending")
    @classmethod
    def validate_attending(cls, v):
        valid_events = {"traditional", "white_wedding", "reception"}
        if not v or not all(event in valid_events for event in v):
            raise ValueError("Invalid event(s) in attending list")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        import re
        if value and not re.match(r"^\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits")
        return value
