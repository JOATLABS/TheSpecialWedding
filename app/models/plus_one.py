from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any
from bson import ObjectId
import re

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
    attending: List[str] = Field(default_factory=list)
    dietary: Optional[str] = None

    @field_validator("phone")
    def validate_phone(cls, value):
        if value and not re.match(r"^\d{10,15}$", value):
            raise ValueError("Phone number must be 10 to 15 digits")
        return value

    @field_validator("attending")
    def validate_attending(cls, v):
        valid_events = {"traditional", "white_wedding", "reception"}
        if not all(event in valid_events for event in v):
            raise ValueError("Invalid event(s) in attending list")
        return v

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "guest_id": "60c7d3e9e1b1fdbb4f12d9aa",
                "name": "Jane Doe",
                "phone": "1234567890",
                "attending": ["reception"],
                "dietary": "Vegetarian"
            }
        }