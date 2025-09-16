# app/models/email_template.py

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class TemplateType(str, Enum):
    CONTACT_FORM = "contact_form"
    NEW_USER = "new_user"
    PAYMENT = "payment"
    SYSTEM_ALERT = "system_alert"
    GENERAL = "general"

class TemplateStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"

class EmailTemplate(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str = Field(..., min_length=1, max_length=100)
    type: TemplateType
    subject: str = Field(..., min_length=1, max_length=200)
    html_content: str = Field(..., min_length=1)
    plain_text_content: Optional[str] = None
    variables: List[str] = Field(default_factory=list)  # Template variables like {name}, {email}
    status: TemplateStatus = TemplateStatus.DRAFT
    version: int = Field(default=1, ge=1)
    is_default: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @validator('html_content')
    def validate_html_content(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('HTML content must be at least 10 characters')
        return v

    @validator('variables')
    def validate_variables(cls, v):
        # Extract variables from content and validate
        return list(set(v))  # Remove duplicates

    class Config:
        use_enum_values = True
        allow_population_by_field_name = True

class EmailTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: TemplateType
    subject: str = Field(..., min_length=1, max_length=200)
    html_content: str = Field(..., min_length=1)
    plain_text_content: Optional[str] = None
    variables: List[str] = Field(default_factory=list)
    is_default: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    html_content: Optional[str] = Field(None, min_length=1)
    plain_text_content: Optional[str] = None
    variables: Optional[List[str]] = None
    status: Optional[TemplateStatus] = None
    is_default: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None

class EmailTemplatePreview(BaseModel):
    html_content: str
    subject: str
    sample_data: Dict[str, str] = Field(default_factory=dict)  # Sample data for variables

class EmailDeliveryEvent(BaseModel):
    event_id: str
    email_id: str
    event_type: str  # sent, delivered, opened, clicked, bounced, complained
    timestamp: datetime
    recipient: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EmailAnalytics(BaseModel):
    template_id: str
    template_name: str
    sent_count: int = 0
    delivered_count: int = 0
    opened_count: int = 0
    clicked_count: int = 0
    bounced_count: int = 0
    complained_count: int = 0
    delivery_rate: float = 0.0
    open_rate: float = 0.0
    click_rate: float = 0.0
    bounce_rate: float = 0.0
    complaint_rate: float = 0.0
    last_sent: Optional[datetime] = None
    date_range: Dict[str, datetime] = Field(default_factory=dict)