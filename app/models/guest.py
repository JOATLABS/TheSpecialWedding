from pydantic import BaseModel, Field, validator
from typing import Optional
from bson import ObjectId
import re

class GuestModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    token: str = Field(..., min_length=6)
    rsvp: Optional[dict] = None
    phone: Optional[str] = None

    @validator("token")
    def validate_token(cls, value):
        if not re.match(r"^[a-zA-Z0-9]+$", value):
            raise ValueError("Token must be alphanumeric")
        return value

    @validator("phone")
    def validate_phone(cls, value):
        if value and not re.match(r"^\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits")
        return value

    class Config:
        schema_extra = {
            "example": {
                "name": "John Doe",
                "token": "abc123xyz",
                "rsvp": None,
                "phone": "1234567890"
            }
        }
