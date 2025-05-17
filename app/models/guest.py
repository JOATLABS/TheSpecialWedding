from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

class GuestModel(BaseModel):
    wedding_id: str = Field(...)
    name: str = Field(..., min_length=2, max_length=100)
    token: str = Field(..., min_length=6)
    phone: Optional[str] = None
    email: Optional[str] = None
    group_id: Optional[str] = None
    role: Optional[str] = Field("guest")
    plus_one_allowed: Optional[bool] = Field(default=False)

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
                "plus_one_allowed": True
            }
        }