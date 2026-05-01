"""
Vendor Contract Admin DTOs

Request and response models for planner-to-vendor contract administration.
Shared enums and persisted document models remain in `app.models.vendor`.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.vendor import ContractKind, ContractStatus, VendorCategory


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

    @model_validator(mode="after")
    def _validate_deposit_within_total(self) -> "UpdateVendorContractRequest":
        # DTO-level guard: when both fields are present in the same request,
        # reject deposit > total at the boundary. This catches "set them both
        # in one PUT" cases. Cross-field consistency for partial updates that
        # only touch one side is enforced in vendor_service.update_contract,
        # which folds in the persisted contract's other side.
        if (
            self.deposit_amount is not None
            and self.total_amount is not None
            and self.deposit_amount > self.total_amount
        ):
            raise ValueError("Deposit amount cannot exceed total amount")
        return self


class UpdateVendorContractSectionsRequest(BaseModel):
    """Update section content and adjacent editable contract copy together."""

    sections: List[VendorContractSectionInput]
    terms_and_conditions: Optional[str] = None
    cancellation_policy: Optional[str] = None
    custom_clauses: Optional[str] = None


class VendorContractFormSubmissionSummary(BaseModel):
    """Stable summary of a vendor form submission available to contract tooling.

    Note on the ``_id`` field: Pydantic treats attribute names beginning
    with an underscore as private and excludes them from validation and
    serialization. Declaring ``_id: str`` directly is a no-op — the field
    is silently dropped from the response JSON. To keep the wire shape
    ``{"_id": "..."}`` (which the contract-detail UI reads at
    ``ContractDetailPageClient.tsx:620``), we declare the field as
    ``id`` with an ``_id`` alias and tell FastAPI to serialize via the
    alias on the route (``response_model_by_alias=True``).
    ``populate_by_name=True`` lets the helper dict use either ``_id`` or
    ``id`` as the source key.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
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
