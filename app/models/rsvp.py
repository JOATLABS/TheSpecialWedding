import logging
import re
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.wedding_event_types import normalize_event_type_list

logger = logging.getLogger(__name__)


class PlusOneInputModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None
    email: Optional[str] = None
    attending: List[str] = Field(default_factory=list)
    dietary: Optional[str] = Field(default=None, max_length=250)
    sms_opt_in: Optional[bool] = Field(
        default=None, description="Opt-in for SMS reminders"
    )
    email_opt_in: Optional[bool] = Field(
        default=None, description="Opt-in for email updates"
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_types(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Coerce attending: string → [string], bool/None → []
            att = data.get("attending")
            if isinstance(att, str):
                data["attending"] = [att] if att else []
            elif isinstance(att, bool) or att is None:
                data["attending"] = []

            # Strip whitespace from phone
            phone = data.get("phone")
            if isinstance(phone, str):
                phone = phone.strip()
                data["phone"] = phone if phone else None

            # Strip whitespace from email
            email = data.get("email")
            if isinstance(email, str):
                email = email.strip()
                data["email"] = email if email else None

            # Coerce empty-string dietary to None
            dietary = data.get("dietary")
            if isinstance(dietary, str) and not dietary.strip():
                data["dietary"] = None
        return data

    @field_validator("phone")
    def validate_phone(cls, value):
        if value and not re.match(r"^\+?\d{10,15}$", value):
            raise ValueError(
                "Phone number must be 10 to 15 digits, optionally prefixed with +"
            )
        return value

    @field_validator("email")
    def validate_email(cls, v):
        if v is None:
            return v
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @field_validator("attending")
    def validate_attending(cls, v):
        return normalize_event_type_list(v)


class RSVPModel(BaseModel):
    attending: List[str] = Field(default_factory=list)
    dietary: Optional[str] = Field(default=None, max_length=250)
    phone: Optional[str] = None
    sms_opt_in: Optional[bool] = Field(
        default=False, description="Opt-in to receive SMS reminders"
    )
    email_opt_in: Optional[bool] = Field(
        default=False, description="Opt-in to receive email updates"
    )
    plus_ones: Optional[List[PlusOneInputModel]] = Field(
        default_factory=lambda: [], max_length=10
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_and_log(cls, data: Any) -> Any:
        # Log the raw incoming payload so we can debug 422s
        logger.info(f"RSVPModel raw payload: {data}")

        if isinstance(data, dict):
            # Coerce attending: string → [string], bool/None → []
            att = data.get("attending")
            if isinstance(att, str):
                data["attending"] = [att] if att else []
            elif isinstance(att, bool) or att is None:
                data["attending"] = []

            # Strip whitespace from phone, convert empty to None
            phone = data.get("phone")
            if isinstance(phone, str):
                phone = phone.strip()
                data["phone"] = phone if phone else None

            # Coerce empty-string dietary to None
            dietary = data.get("dietary")
            if isinstance(dietary, str) and not dietary.strip():
                data["dietary"] = None

            # Coerce sms_opt_in / email_opt_in to bool
            for opt_field in ("sms_opt_in", "email_opt_in"):
                val = data.get(opt_field)
                if val is not None and not isinstance(val, bool):
                    data[opt_field] = bool(val)
        return data

    @field_validator("attending")
    def validate_attending(cls, v):
        return normalize_event_type_list(v)

    @field_validator("phone")
    def validate_phone(cls, value):
        if value and not re.match(r"^\+?\d{10,15}$", value):
            raise ValueError(
                "Phone number must be 10 to 15 digits, optionally prefixed with +"
            )
        return value
