from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from bson import ObjectId
import re

class PlusOneModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None
    rsvp: Optional[dict] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        if value and not re.match(r"^\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits")
        return value

class GuestModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    token: str = Field(..., min_length=6)
    rsvp: Optional[dict] = None
    phone: Optional[str] = None
    allow_plus_ones: bool = Field(False)
    number_of_allowed_plus_ones: int = Field(0, ge=0)
    plus_ones: Optional[List[PlusOneModel]] = []

    @field_validator("token")
    @classmethod
    def validate_token(cls, value):
        if not re.match(r"^[a-zA-Z0-9]+$", value):
            raise ValueError("Token must be alphanumeric")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        if value and not re.match(r"^\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits")
        return value

    @field_validator("number_of_allowed_plus_ones")
    @classmethod
    def validate_number_of_plus_ones(cls, value, values):
        allow_plus_ones = values.data.get("allow_plus_ones", False)
        if not allow_plus_ones and value > 0:
            raise ValueError("Cannot set plus ones when allow_plus_ones is False")
        return value

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "John Doe",
                "token": "abc123xyz",
                "rsvp": None,
                "phone": "1234567890",
                "allow_plus_ones": True,
                "number_of_allowed_plus_ones": 2,
                "plus_ones": []
            }
        }
    }
