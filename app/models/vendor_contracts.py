"""
Vendor Contract Admin DTOs

Request and response models for planner-to-vendor contract administration.
Shared enums and persisted document models remain in `app.models.vendor`.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.vendor import ContractKind, ContractStatus, VendorCategory


class VendorContractSectionInput(BaseModel):
    """Normalized contract section input for create/update flows."""

    id: Optional[str] = None
    title: str
    content: str = ""
    order: int = 0


class CreateVendorContractTemplateRequest(BaseModel):
    """Create a planner-owned vendor contract template.

    `service_category` may be omitted to create a universal template that
    is offered for any vendor type, including custom 'other' categories.
    """

    name: str
    description: Optional[str] = None
    service_category: Optional[VendorCategory] = None
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


class CreateVendorContractRevisionRequest(BaseModel):
    """Create a new draft revision or amendment from a live contract."""

    revision_kind: Literal["revision", "amendment"]
    reason: Optional[str] = None
    copy_sections: bool = True
    copy_terms_and_conditions: bool = True
    copy_cancellation_policy: bool = True
    copy_custom_clauses: bool = True


class DuplicateVendorContractRequest(BaseModel):
    """Clone an existing contract into a brand-new draft root contract.

    Unlike a revision (which creates a new version of the same lineage),
    a duplicate produces an independent root contract with a fresh number,
    no parent, version_number=1, and DRAFT status. Optionally retargets
    to a different wedding or vendor; when retargeted, the new contract's
    denormalized vendor fields are refreshed from the new vendor profile
    and any form-submission linkage is cleared.
    """

    new_contract_title: Optional[str] = Field(None, min_length=1, max_length=300)
    target_wedding_id: Optional[str] = None
    target_vendor_profile_id: Optional[str] = None
    copy_sections: bool = True
    copy_terms_and_conditions: bool = True
    copy_cancellation_policy: bool = True
    copy_custom_clauses: bool = True
    copy_attachments: bool = True


class VendorContractRevisionSummary(BaseModel):
    """Compact lineage summary for vendor contract history surfaces."""

    id: str
    contract_number: Optional[str] = None
    version_number: int
    contract_kind: ContractKind
    status: ContractStatus
    is_current_version: bool
    parent_contract_id: Optional[str] = None
    supersedes_contract_id: Optional[str] = None
    superseded_by_contract_id: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    signed_at: Optional[datetime] = None


class VendorContractRevisionHistoryResponse(BaseModel):
    """Full revision history for a contract lineage."""

    current_contract_id: str
    root_contract_id: str
    versions: List[VendorContractRevisionSummary] = Field(default_factory=list)


class VendorContractActivityType(str, Enum):
    """Normalized activity event types for contract-scoped timelines."""

    CONTRACT_CREATED = "contract_created"
    CONTRACT_UPDATED = "contract_updated"
    FORM_DATA_APPLIED = "form_data_applied"
    CONTRACT_SENT = "contract_sent"
    CONTRACT_VIEWED = "contract_viewed"
    CONTRACT_SIGNED = "contract_signed"
    MILESTONES_CREATED = "milestones_created"
    PAYMENT_RECORDED = "payment_recorded"
    REVISION_CREATED = "revision_created"
    CONTRACT_SUPERSEDED = "contract_superseded"
    CONTRACT_DUPLICATED = "contract_duplicated"


class VendorContractActivityActor(BaseModel):
    """Actor metadata attached to a contract activity entry."""

    type: Literal["planner", "vendor", "system"]
    identifier: Optional[str] = None
    display_name: Optional[str] = None


class VendorContractActivityItem(BaseModel):
    """One contract activity timeline entry."""

    id: str
    contract_id: str
    root_contract_id: str
    activity_type: VendorContractActivityType
    title: str
    description: Optional[str] = None
    actor: VendorContractActivityActor
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class VendorContractActivityResponse(BaseModel):
    """Read-only contract-scoped activity response."""

    contract_id: str
    root_contract_id: str
    items: List[VendorContractActivityItem] = Field(default_factory=list)


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
