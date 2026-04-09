"""
Vendor Contract Admin DTOs

Request and response models for planner-to-vendor contract administration.
Shared enums and persisted document models remain in `app.models.vendor`.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.vendor import VendorCategory


class VendorContractSectionInput(BaseModel):
    """Normalized contract section input for create/update flows."""

    id: Optional[str] = None
    title: str
    content: str = ""
    order: int = 0


class CreateVendorContractTemplateRequest(BaseModel):
    """Create a planner-owned vendor contract template."""

    name: str
    description: Optional[str] = None
    service_category: VendorCategory
    sections: List[VendorContractSectionInput] = Field(default_factory=list)
    terms_and_conditions: Optional[str] = None
    cancellation_policy: Optional[str] = None
    default_deposit_percentage: Optional[float] = Field(None, ge=0, le=100)
    default_payment_schedule: List[Dict[str, Any]] = Field(default_factory=list)
    is_public: bool = False


class CreateVendorContractRequest(BaseModel):
    """Create a vendor contract from a template or custom content."""

    wedding_id: str
    vendor_profile_id: str
    total_amount: float = Field(..., ge=0)
    template_id: Optional[str] = None
    quote_id: Optional[str] = None
    deposit_percentage: Optional[float] = Field(None, ge=0, le=100)
    service_date: Optional[datetime] = None
    service_location: Optional[str] = None
    custom_sections: List[VendorContractSectionInput] = Field(default_factory=list)


class UpdateVendorContractRequest(BaseModel):
    """Partial update request for editable vendor contract fields."""

    contract_title: Optional[str] = Field(None, min_length=1, max_length=300)
    total_amount: Optional[float] = Field(None, ge=0)
    deposit_amount: Optional[float] = Field(None, ge=0)
    deposit_due_date: Optional[datetime] = None
    terms_and_conditions: Optional[str] = None
    cancellation_policy: Optional[str] = None
    custom_clauses: Optional[str] = None
    service_date: Optional[datetime] = None
    service_start_time: Optional[str] = None
    service_end_time: Optional[str] = None
    service_location: Optional[str] = None
    internal_notes: Optional[str] = None
    sections: Optional[List[VendorContractSectionInput]] = None


class UpdateVendorContractSectionsRequest(BaseModel):
    """Update section content and adjacent editable contract copy together."""

    sections: List[VendorContractSectionInput]
    terms_and_conditions: Optional[str] = None
    cancellation_policy: Optional[str] = None
    custom_clauses: Optional[str] = None


class VendorContractFormSubmissionSummary(BaseModel):
    """Stable summary of a vendor form submission available to contract tooling."""

    _id: str
    form_name: str
    submitted_at: Optional[datetime] = None
    source: str
    data: Dict[str, Any] = Field(default_factory=dict)


class VendorContractAvailableField(BaseModel):
    """Field extracted from vendor form data that can populate contract content."""

    value: Any
    source: str
    source_id: str
    original_key: str


class VendorContractSuggestedField(BaseModel):
    """Suggested placeholder mapping for a contract field."""

    value: Any
    source_field: str


class VendorContractFormDataResponse(BaseModel):
    """Normalized vendor form-data payload for contract editing surfaces."""

    vendor_submissions: List[VendorContractFormSubmissionSummary] = Field(
        default_factory=list
    )
    available_fields: Dict[str, VendorContractAvailableField] = Field(
        default_factory=dict
    )
    suggested_contract_fields: Dict[str, VendorContractSuggestedField] = Field(
        default_factory=dict
    )


class ApplyVendorContractFormDataRequest(BaseModel):
    """Apply one vendor submission to a contract with explicit field mappings."""

    form_submission_id: str
    field_mappings: Dict[str, str] = Field(default_factory=dict)


class SendVendorContractRequest(BaseModel):
    """Send a contract to a vendor for review/signing."""

    message: Optional[str] = None
    cc_emails: List[str] = Field(default_factory=list)


class PaymentMilestoneInput(BaseModel):
    """Normalized milestone creation input."""

    description: str
    amount: float = Field(..., gt=0)
    due_date: datetime
    percentage_of_total: Optional[float] = Field(None, ge=0, le=100)
    days_before_event: Optional[int] = None


class CreateVendorPaymentMilestonesRequest(BaseModel):
    """Create one or more milestones for a vendor contract."""

    milestones: List[PaymentMilestoneInput] = Field(default_factory=list)


class RecordVendorMilestonePaymentRequest(BaseModel):
    """Record a payment against one vendor milestone."""

    amount: float = Field(..., gt=0)
    payment_method: str
    payment_date: Optional[datetime] = None
    notes: Optional[str] = None
    receipt_url: Optional[str] = None


class CreateContractFromQuoteRequest(BaseModel):
    """Legacy contract-from-quote request moved out of `vendor.py`."""

    quote_id: str
    template_id: Optional[str] = None
    custom_sections: List[VendorContractSectionInput] = Field(default_factory=list)
    deposit_percentage: Optional[float] = Field(None, ge=0, le=100)
    payment_milestones: List[PaymentMilestoneInput] = Field(default_factory=list)


class UploadContractPdfRequest(BaseModel):
    """Request to create a contract from an uploaded PDF."""

    wedding_id: str
    vendor_profile_id: str
    contract_title: str
    total_amount: float = Field(..., ge=0)
    deposit_amount: Optional[float] = Field(None, ge=0)
    service_date: Optional[datetime] = None
    service_location: Optional[str] = None
    notes: Optional[str] = None


class GetFormDataForContractRequest(BaseModel):
    """Legacy request model for vendor form data lookup."""

    vendor_email: str
    wedding_id: str
