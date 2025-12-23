"""
Vendor Management Models

This module contains all models for the comprehensive vendor management system:
- VendorProfile: Master vendor directory (reusable across weddings)
- ContractTemplate: Pre-built contract templates with placeholders
- VendorContract: Actual contracts with signing workflow
- VendorPaymentMilestone: Payment tracking with Stripe integration
- VendorAssignment: Links vendors to weddings and budget categories
"""

from pydantic import BaseModel, Field, ConfigDict, field_serializer, EmailStr
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId
from app.utils.pydantic_objectid import PyObjectId, generate_object_id


# =============================================================================
# ENUMS
# =============================================================================

class VendorCategory(str, Enum):
    """Standard vendor service categories"""
    PHOTOGRAPHER = "photographer"
    VIDEOGRAPHER = "videographer"
    FLORIST = "florist"
    CATERER = "caterer"
    VENUE = "venue"
    DJ = "dj"
    BAND = "band"
    OFFICIANT = "officiant"
    PLANNER = "planner"
    DECORATOR = "decorator"
    CAKE = "cake"
    HAIR_MAKEUP = "hair_makeup"
    TRANSPORTATION = "transportation"
    STATIONERY = "stationery"
    RENTALS = "rentals"
    LIGHTING = "lighting"
    PHOTO_BOOTH = "photo_booth"
    JEWELRY = "jewelry"
    ATTIRE = "attire"
    OTHER = "other"


class ContractStatus(str, Enum):
    """Contract lifecycle status"""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    SENT = "sent"
    VIEWED = "viewed"
    SIGNED = "signed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentMilestoneStatus(str, Enum):
    """Payment milestone status"""
    PENDING = "pending"
    DUE = "due"
    OVERDUE = "overdue"
    PAID = "paid"
    PARTIAL = "partial"
    WAIVED = "waived"


class QuoteStatus(str, Enum):
    """Vendor quote status"""
    DRAFT = "draft"
    REQUESTED = "requested"
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONVERTED = "converted"  # Converted to contract


class ContractType(str, Enum):
    """Type of contract - template-based or uploaded PDF"""
    TEMPLATE = "template"
    UPLOADED_PDF = "uploaded_pdf"
    CUSTOM = "custom"


class PaymentLinkStatus(str, Enum):
    """Payment link lifecycle status"""
    DRAFT = "draft"
    SENT = "sent"
    CLICKED = "clicked"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PayerType(str, Enum):
    """Who is paying"""
    COUPLE = "couple"
    VENDOR = "vendor"
    PLANNER = "planner"


class RecipientType(str, Enum):
    """Who receives the payment"""
    VENDOR = "vendor"
    PLANNER = "planner"
    COUPLE = "couple"


# =============================================================================
# VENDOR PROFILE (Master Directory)
# =============================================================================

class VendorProfile(BaseModel):
    """
    Master vendor directory entry.
    Reusable across all weddings managed by a planner.
    """
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")

    # Owner (the planner who added this vendor)
    created_by: str = Field(..., description="Planner email who added this vendor")

    # Basic Info
    business_name: str = Field(..., min_length=1, max_length=200, description="Vendor business name")
    contact_name: Optional[str] = Field(None, max_length=100, description="Primary contact person")
    email: str = Field(..., description="Vendor email address")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    website: Optional[str] = Field(None, max_length=500, description="Website URL")
    address: Optional[str] = Field(None, max_length=500, description="Business address")
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)

    # Categorization
    service_category: VendorCategory = Field(..., description="Primary service category")
    service_subcategories: List[str] = Field(default_factory=list, description="Specific services offered")
    service_description: Optional[str] = Field(None, max_length=2000, description="Description of services")

    # Planner's Notes & Preferences
    internal_notes: Optional[str] = Field(None, max_length=5000, description="Private planner notes")
    internal_rating: Optional[int] = Field(None, ge=1, le=5, description="Planner's rating 1-5")
    is_preferred: bool = Field(False, description="Mark as preferred/go-to vendor")
    tags: List[str] = Field(default_factory=list, description="Custom tags for filtering")

    # Portfolio & Media
    portfolio_urls: List[str] = Field(default_factory=list, description="Portfolio/sample work URLs")
    logo_url: Optional[str] = Field(None, description="Vendor logo URL")

    # Pricing Reference (for quick estimates)
    typical_price_min: Optional[float] = Field(None, ge=0, description="Typical minimum price")
    typical_price_max: Optional[float] = Field(None, ge=0, description="Typical maximum price")
    currency: str = Field("USD", description="Currency code")
    pricing_notes: Optional[str] = Field(None, max_length=1000, description="Pricing notes")

    # Capacity & Availability
    max_events_per_day: Optional[int] = Field(None, ge=1, description="Max events vendor handles per day")
    lead_time_days: Optional[int] = Field(None, ge=0, description="Required booking lead time")
    service_radius_miles: Optional[int] = Field(None, description="Service area radius")
    travel_fee_notes: Optional[str] = Field(None, max_length=500, description="Travel fee policy")

    # Business Details
    business_license: Optional[str] = Field(None, description="License number if applicable")
    insurance_info: Optional[str] = Field(None, max_length=500, description="Insurance details")
    tax_id: Optional[str] = Field(None, description="Tax ID for payments")

    # Usage Stats (auto-updated)
    weddings_count: int = Field(0, description="Number of weddings assigned")
    total_revenue: float = Field(0.0, description="Total paid to this vendor")
    last_used_at: Optional[datetime] = Field(None, description="Last wedding assignment")

    # System
    is_active: bool = Field(True, description="Whether vendor is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )

    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        return str(value) if value else None


# =============================================================================
# CONTRACT TEMPLATE
# =============================================================================

class ContractTemplatePlaceholder(BaseModel):
    """Placeholder definition for contract templates"""
    key: str = Field(..., description="Placeholder key e.g., {{vendor_name}}")
    label: str = Field(..., description="Human-readable label")
    source: str = Field(..., description="Data source: vendor, wedding, planner, custom")
    field_path: Optional[str] = Field(None, description="Path to auto-populate from source")
    default_value: Optional[str] = Field(None, description="Default if source is empty")
    is_required: bool = Field(True, description="Whether this must be filled")


class ContractTemplateSection(BaseModel):
    """Section within a contract template"""
    id: str = Field(default_factory=lambda: str(ObjectId()), description="Section ID")
    title: str = Field(..., min_length=1, max_length=200, description="Section title")
    content: str = Field(..., description="Section content with placeholders")
    order: int = Field(0, description="Display order")
    is_optional: bool = Field(False, description="Can be excluded from final contract")


class ContractTemplate(BaseModel):
    """
    Pre-built contract template with placeholders.
    Placeholders auto-populate vendor, wedding, and planner details.
    """
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")

    # Template Info
    name: str = Field(..., min_length=1, max_length=200, description="Template name")
    description: Optional[str] = Field(None, max_length=1000, description="Template description")
    service_category: VendorCategory = Field(..., description="Which vendor type this is for")

    # Content
    sections: List[ContractTemplateSection] = Field(default_factory=list, description="Contract sections")
    terms_and_conditions: Optional[str] = Field(None, description="Standard terms & conditions")
    cancellation_policy: Optional[str] = Field(None, description="Cancellation policy text")

    # Placeholders
    placeholders: List[ContractTemplatePlaceholder] = Field(
        default_factory=list,
        description="Available placeholders in this template"
    )

    # Default Payment Structure
    default_deposit_percentage: Optional[float] = Field(None, ge=0, le=100, description="Default deposit %")
    default_payment_schedule: List[Dict] = Field(
        default_factory=list,
        description="Default milestones e.g., [{percentage: 50, description: 'Deposit', days_before_event: 90}]"
    )

    # Ownership
    created_by: str = Field(..., description="Planner email who created this")
    is_system_template: bool = Field(False, description="Platform-provided template")
    is_public: bool = Field(False, description="Available to other planners")

    # System
    is_active: bool = Field(True)
    usage_count: int = Field(0, description="How many times used")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )

    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        return str(value) if value else None


# =============================================================================
# VENDOR CONTRACT (Actual Contract Instance)
# =============================================================================

class VendorContract(BaseModel):
    """
    Actual contract between planner/couple and vendor.
    Created from a template or custom, tracks signing workflow.
    """
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")

    # Relationships
    wedding_id: str = Field(..., description="Wedding this contract is for")
    vendor_profile_id: Optional[str] = Field(None, description="Link to VendorProfile if from directory")
    vendor_quote_id: Optional[str] = Field(None, description="Link to VendorQuote if converted from quote")
    budget_category_id: Optional[str] = Field(None, description="Link to BudgetCategory")
    template_id: Optional[str] = Field(None, description="Template this was created from")

    # Vendor Info (denormalized for contract record)
    vendor_name: str = Field(..., description="Vendor business name")
    vendor_email: str = Field(..., description="Vendor email")
    vendor_phone: Optional[str] = Field(None, description="Vendor phone")
    vendor_address: Optional[str] = Field(None, description="Vendor address")
    service_category: VendorCategory = Field(..., description="Service category")

    # Contract Details
    contract_title: str = Field(..., min_length=1, max_length=300, description="Contract title")
    contract_number: Optional[str] = Field(None, description="Contract reference number")
    contract_type: ContractType = Field(ContractType.TEMPLATE, description="template, uploaded_pdf, or custom")

    # Uploaded PDF (when contract_type is uploaded_pdf)
    uploaded_pdf_url: Optional[str] = Field(None, description="URL of uploaded contract PDF")
    uploaded_pdf_name: Optional[str] = Field(None, description="Original filename of uploaded PDF")

    # Form Data Integration
    form_submission_ids: List[str] = Field(default_factory=list, description="Form submissions used to populate contract")
    form_data_mappings: Dict[str, Any] = Field(default_factory=dict, description="Mapping of placeholders to form data")

    # Populated Content (with placeholders filled)
    sections: List[Dict] = Field(default_factory=list, description="Contract sections with content")
    terms_and_conditions: Optional[str] = Field(None)
    cancellation_policy: Optional[str] = Field(None)
    custom_clauses: Optional[str] = Field(None, description="Any custom additions")

    # Financial
    total_amount: float = Field(..., ge=0, description="Total contract value")
    currency: str = Field("USD", description="Currency code")
    deposit_amount: Optional[float] = Field(None, ge=0, description="Required deposit")
    deposit_due_date: Optional[datetime] = Field(None, description="When deposit is due")

    # Status & Workflow
    status: ContractStatus = Field(ContractStatus.DRAFT, description="Current status")
    sent_at: Optional[datetime] = Field(None, description="When sent to vendor")
    viewed_at: Optional[datetime] = Field(None, description="When vendor first viewed")
    signed_at: Optional[datetime] = Field(None, description="When signed")
    signed_by_name: Optional[str] = Field(None, description="Name of signer")
    signed_by_email: Optional[str] = Field(None, description="Email of signer")
    signature_ip: Optional[str] = Field(None, description="IP address of signing")
    completed_at: Optional[datetime] = Field(None, description="When services completed")
    cancelled_at: Optional[datetime] = Field(None, description="When cancelled")
    cancellation_reason: Optional[str] = Field(None, description="Why cancelled")

    # Documents
    draft_document_url: Optional[str] = Field(None, description="Draft PDF URL")
    signed_document_url: Optional[str] = Field(None, description="Signed PDF URL")
    attachments: List[Dict] = Field(
        default_factory=list,
        description="Additional attachments [{name, url, uploaded_at}]"
    )

    # Access Control
    access_token: str = Field(..., description="Secure token for vendor access")
    token_expires_at: Optional[datetime] = Field(None, description="Token expiration")

    # Service Dates
    service_date: Optional[datetime] = Field(None, description="Primary service date")
    service_start_time: Optional[str] = Field(None, description="Start time")
    service_end_time: Optional[str] = Field(None, description="End time")
    service_location: Optional[str] = Field(None, description="Service location")

    # Planner
    created_by: str = Field(..., description="Planner email")

    # Notes & Communication
    internal_notes: Optional[str] = Field(None, description="Planner's private notes")
    vendor_notes: Optional[str] = Field(None, description="Notes from vendor")

    # System
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )

    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        return str(value) if value else None


# =============================================================================
# PAYMENT MILESTONE
# =============================================================================

class VendorPaymentMilestone(BaseModel):
    """
    Individual payment milestone for a vendor contract.
    Supports tracking and Stripe payment integration.
    """
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")

    # Relationships
    contract_id: str = Field(..., description="Parent contract ID")
    wedding_id: str = Field(..., description="Wedding ID")
    vendor_profile_id: Optional[str] = Field(None, description="Vendor profile ID")
    budget_category_id: Optional[str] = Field(None, description="Budget category ID")

    # Milestone Details
    description: str = Field(..., min_length=1, max_length=300, description="Milestone description")
    amount: float = Field(..., gt=0, description="Payment amount")
    currency: str = Field("USD", description="Currency code")
    percentage_of_total: Optional[float] = Field(None, ge=0, le=100, description="% of contract total")

    # Due Date
    due_date: datetime = Field(..., description="When payment is due")
    days_before_event: Optional[int] = Field(None, description="Days before wedding (for auto-calculation)")

    # Status
    status: PaymentMilestoneStatus = Field(PaymentMilestoneStatus.PENDING, description="Payment status")

    # Payment Details
    paid_amount: float = Field(0.0, ge=0, description="Amount paid so far")
    paid_at: Optional[datetime] = Field(None, description="When paid")
    payment_method: Optional[str] = Field(None, description="cash, check, card, bank_transfer, stripe")

    # Stripe Integration
    stripe_payment_intent_id: Optional[str] = Field(None, description="Stripe PaymentIntent ID")
    stripe_charge_id: Optional[str] = Field(None, description="Stripe Charge ID")
    stripe_transfer_id: Optional[str] = Field(None, description="Stripe Transfer ID (to vendor)")

    # Receipt/Invoice
    invoice_number: Optional[str] = Field(None, description="Invoice number")
    invoice_url: Optional[str] = Field(None, description="Invoice document URL")
    receipt_url: Optional[str] = Field(None, description="Receipt URL")

    # Notes
    notes: Optional[str] = Field(None, max_length=1000, description="Payment notes")

    # Reminders
    reminder_sent_at: Optional[datetime] = Field(None, description="Last reminder sent")
    reminder_count: int = Field(0, description="Number of reminders sent")

    # Vendor Info (denormalized)
    vendor_name: str = Field(..., description="Vendor name")
    vendor_email: str = Field(..., description="Vendor email")

    # System
    created_by: str = Field(..., description="Planner email")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )

    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        return str(value) if value else None


# =============================================================================
# VENDOR ASSIGNMENT (Wedding-Vendor Link)
# =============================================================================

class VendorAssignment(BaseModel):
    """
    Links a vendor from directory to a specific wedding.
    Tracks the relationship and status independent of quotes/contracts.
    """
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")

    # Relationships
    wedding_id: str = Field(..., description="Wedding ID")
    vendor_profile_id: str = Field(..., description="Vendor from directory")
    budget_category_id: Optional[str] = Field(None, description="Linked budget category")

    # Status
    status: str = Field("inquiry", description="inquiry, quoted, contracted, confirmed, completed, cancelled")

    # Quick Reference (denormalized)
    vendor_name: str = Field(..., description="Vendor name")
    vendor_email: str = Field(..., description="Vendor email")
    service_category: VendorCategory = Field(..., description="Service type")

    # Linked Records
    quote_ids: List[str] = Field(default_factory=list, description="Associated quote IDs")
    contract_id: Optional[str] = Field(None, description="Associated contract ID")

    # Service Details
    service_date: Optional[datetime] = Field(None, description="Service date")
    service_notes: Optional[str] = Field(None, max_length=2000, description="Service notes")

    # Financial Summary
    quoted_amount: Optional[float] = Field(None, description="Latest quote amount")
    contracted_amount: Optional[float] = Field(None, description="Contract amount")
    paid_amount: float = Field(0.0, description="Total paid")

    # Communication
    last_contacted_at: Optional[datetime] = Field(None, description="Last contact")
    next_followup_at: Optional[datetime] = Field(None, description="Next followup date")

    # System
    created_by: str = Field(..., description="Planner email")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )

    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        return str(value) if value else None


# =============================================================================
# PAYMENT LINK
# =============================================================================

class PaymentLink(BaseModel):
    """
    Payment link for collecting payments from vendors or couples.
    Supports multiple payment scenarios:
    - Couple pays vendor (planner facilitates)
    - Couple pays planner (planner fee)
    - Vendor pays planner (referral commission)
    """
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")

    # Relationships
    wedding_id: Optional[str] = Field(None, description="Wedding ID if applicable")
    contract_id: Optional[str] = Field(None, description="Related contract ID")
    milestone_id: Optional[str] = Field(None, description="Related payment milestone ID")
    vendor_profile_id: Optional[str] = Field(None, description="Related vendor ID")

    # Payer Information
    payer_type: PayerType = Field(..., description="Who is paying: couple, vendor, or planner")
    payer_email: str = Field(..., description="Email of the person paying")
    payer_name: str = Field(..., description="Name of the person paying")
    payer_phone: Optional[str] = Field(None, description="Phone number of payer")

    # Recipient Information
    recipient_type: RecipientType = Field(..., description="Who receives: vendor, planner, or couple")
    recipient_email: str = Field(..., description="Email of recipient")
    recipient_name: str = Field(..., description="Name of recipient")

    # Payment Details
    amount: float = Field(..., gt=0, description="Payment amount")
    currency: str = Field("USD", description="Currency code")
    description: str = Field(..., min_length=1, max_length=500, description="What this payment is for")
    due_date: Optional[datetime] = Field(None, description="When payment is due")

    # Stripe Integration
    stripe_payment_link_id: Optional[str] = Field(None, description="Stripe Payment Link ID")
    stripe_payment_link_url: Optional[str] = Field(None, description="Stripe Payment Link URL")
    stripe_checkout_session_id: Optional[str] = Field(None, description="Stripe Checkout Session ID")
    stripe_payment_intent_id: Optional[str] = Field(None, description="Stripe PaymentIntent ID")

    # Status
    status: PaymentLinkStatus = Field(PaymentLinkStatus.DRAFT, description="Link status")
    sent_at: Optional[datetime] = Field(None, description="When link was sent")
    clicked_at: Optional[datetime] = Field(None, description="When link was first clicked")
    paid_at: Optional[datetime] = Field(None, description="When payment completed")
    expires_at: Optional[datetime] = Field(None, description="When link expires")

    # Communication
    email_subject: Optional[str] = Field(None, description="Custom email subject")
    email_message: Optional[str] = Field(None, description="Custom email message")
    reminder_sent_count: int = Field(0, description="Number of reminders sent")
    last_reminder_at: Optional[datetime] = Field(None, description="When last reminder was sent")

    # Access Control
    access_token: str = Field(..., description="Secure token for payment link access")

    # System
    created_by: str = Field(..., description="Planner email who created this")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )

    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        return str(value) if value else None


# =============================================================================
# VENDOR COMMUNICATION LOG
# =============================================================================

class VendorCommunication(BaseModel):
    """Tracks communication history with vendors"""
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")

    # Relationships
    wedding_id: Optional[str] = Field(None, description="Wedding ID (if specific to a wedding)")
    vendor_profile_id: str = Field(..., description="Vendor profile ID")
    contract_id: Optional[str] = Field(None, description="Related contract ID")
    assignment_id: Optional[str] = Field(None, description="Related assignment ID")

    # Communication Details
    type: str = Field(..., description="email, call, meeting, note, quote_request, contract_sent")
    subject: Optional[str] = Field(None, max_length=300, description="Subject/title")
    content: str = Field(..., description="Communication content")
    direction: str = Field("outgoing", description="outgoing or incoming")

    # Metadata
    sent_to: Optional[str] = Field(None, description="Recipient email if outgoing")
    received_from: Optional[str] = Field(None, description="Sender email if incoming")

    # Attachments
    attachments: List[Dict] = Field(
        default_factory=list,
        description="Attachments [{name, url, type}]"
    )

    # System
    created_by: str = Field(..., description="User who logged this")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )

    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        return str(value) if value else None


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateVendorProfileRequest(BaseModel):
    """Request to create a vendor in directory"""
    business_name: str = Field(..., min_length=1, max_length=200)
    contact_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    service_category: VendorCategory
    service_subcategories: List[str] = []
    service_description: Optional[str] = None
    internal_notes: Optional[str] = None
    internal_rating: Optional[int] = None
    is_preferred: bool = False
    tags: List[str] = []
    portfolio_urls: List[str] = []
    typical_price_min: Optional[float] = None
    typical_price_max: Optional[float] = None
    currency: str = "USD"


class UpdateVendorProfileRequest(BaseModel):
    """Request to update a vendor profile"""
    business_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    service_category: Optional[VendorCategory] = None
    service_subcategories: Optional[List[str]] = None
    service_description: Optional[str] = None
    internal_notes: Optional[str] = None
    internal_rating: Optional[int] = None
    is_preferred: Optional[bool] = None
    tags: Optional[List[str]] = None
    portfolio_urls: Optional[List[str]] = None
    typical_price_min: Optional[float] = None
    typical_price_max: Optional[float] = None
    is_active: Optional[bool] = None


class AssignVendorRequest(BaseModel):
    """Request to assign vendor to a wedding"""
    vendor_profile_id: str
    wedding_id: str
    budget_category_id: Optional[str] = None
    service_notes: Optional[str] = None


class CreateContractFromQuoteRequest(BaseModel):
    """Request to create contract from an accepted quote"""
    quote_id: str
    template_id: Optional[str] = None
    custom_sections: Optional[List[Dict]] = None
    deposit_percentage: Optional[float] = None
    payment_milestones: Optional[List[Dict]] = None


class SendContractRequest(BaseModel):
    """Request to send contract to vendor"""
    contract_id: str
    message: Optional[str] = None
    cc_emails: List[str] = []


class SignContractRequest(BaseModel):
    """Request when vendor signs contract"""
    signer_name: str
    signer_email: str
    signature_data: Optional[str] = None  # Base64 signature image if needed
    agreed_to_terms: bool = True


class RecordPaymentRequest(BaseModel):
    """Request to record a payment"""
    milestone_id: str
    amount: float
    payment_method: str  # cash, check, card, bank_transfer, stripe
    payment_date: Optional[datetime] = None
    notes: Optional[str] = None
    receipt_url: Optional[str] = None


class UploadContractPdfRequest(BaseModel):
    """Request to create contract from uploaded PDF"""
    wedding_id: str
    vendor_profile_id: str
    contract_title: str
    total_amount: float
    deposit_amount: Optional[float] = None
    service_date: Optional[datetime] = None
    service_location: Optional[str] = None
    notes: Optional[str] = None


class UpdateContractSectionsRequest(BaseModel):
    """Request to update contract sections"""
    sections: List[Dict[str, Any]]
    terms_and_conditions: Optional[str] = None
    cancellation_policy: Optional[str] = None
    custom_clauses: Optional[str] = None


class CreatePaymentLinkRequest(BaseModel):
    """Request to create a payment link"""
    # Payer info
    payer_type: PayerType
    payer_email: str
    payer_name: str
    payer_phone: Optional[str] = None

    # Recipient info
    recipient_type: RecipientType
    recipient_email: str
    recipient_name: str

    # Payment details
    amount: float
    currency: str = "USD"
    description: str
    due_date: Optional[datetime] = None

    # Optional relationships
    wedding_id: Optional[str] = None
    contract_id: Optional[str] = None
    milestone_id: Optional[str] = None
    vendor_profile_id: Optional[str] = None

    # Email customization
    email_subject: Optional[str] = None
    email_message: Optional[str] = None


class SendPaymentLinkRequest(BaseModel):
    """Request to send a payment link"""
    payment_link_id: str
    custom_message: Optional[str] = None


class GetFormDataForContractRequest(BaseModel):
    """Request to get form data that can be used in a contract"""
    vendor_email: str
    wedding_id: str
