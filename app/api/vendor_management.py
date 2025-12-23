"""
Vendor Management API

Comprehensive API for managing vendors, contracts, and payments.
All endpoints are feature-gated by subscription plan.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from typing import List, Optional
from datetime import datetime

from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
from app.dependencies.feature_gates import require_vendor_feature
from app.services.vendor_service import vendor_service
from app.models.vendor import (
    CreateVendorProfileRequest,
    UpdateVendorProfileRequest,
    AssignVendorRequest,
    VendorCategory,
    CreatePaymentLinkRequest,
    UpdateContractSectionsRequest,
    PayerType,
    RecipientType
)

router = APIRouter()


# =============================================================================
# VENDOR DIRECTORY (Master List)
# =============================================================================

@router.get("/directory", tags=["Vendor Directory"])
async def list_vendor_directory(
    category: Optional[str] = Query(None, description="Filter by service category"),
    is_preferred: Optional[bool] = Query(None, description="Filter by preferred status"),
    search: Optional[str] = Query(None, description="Search by name, email, description"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    List all vendors in the planner's directory.
    Supports filtering by category, preferred status, search, and tags.
    """
    tag_list = tags.split(",") if tags else None
    return await vendor_service.get_vendor_profiles(
        created_by=current_user.email,
        category=category,
        is_preferred=is_preferred,
        search=search,
        tags=tag_list,
        skip=skip,
        limit=limit
    )


@router.post("/directory", tags=["Vendor Directory"])
async def create_vendor_in_directory(
    data: CreateVendorProfileRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Add a new vendor to the directory.
    This creates a reusable vendor contact that can be assigned to any wedding.
    """
    return await vendor_service.create_vendor_profile(
        data=data.model_dump(),
        created_by=current_user.email
    )


@router.get("/directory/categories", tags=["Vendor Directory"])
async def get_used_categories(
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get list of service categories used in the planner's directory"""
    categories = await vendor_service.get_vendor_categories_used(current_user.email)
    return {"categories": categories}


@router.get("/directory/all-categories", tags=["Vendor Directory"])
async def get_all_categories(
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get all available vendor categories"""
    return {"categories": [c.value for c in VendorCategory]}


@router.get("/directory/{vendor_id}", tags=["Vendor Directory"])
async def get_vendor_profile(
    vendor_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get a specific vendor from the directory"""
    return await vendor_service.get_vendor_profile(vendor_id, current_user.email)


@router.put("/directory/{vendor_id}", tags=["Vendor Directory"])
async def update_vendor_profile(
    vendor_id: str,
    data: UpdateVendorProfileRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Update a vendor in the directory"""
    return await vendor_service.update_vendor_profile(
        vendor_id=vendor_id,
        data=data.model_dump(exclude_none=True),
        created_by=current_user.email
    )


@router.delete("/directory/{vendor_id}", tags=["Vendor Directory"])
async def delete_vendor_from_directory(
    vendor_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Remove a vendor from the directory (soft delete)"""
    return await vendor_service.delete_vendor_profile(vendor_id, current_user.email)


# =============================================================================
# VENDOR ASSIGNMENTS (Link to Wedding)
# =============================================================================

@router.post("/assign", tags=["Vendor Assignments"])
async def assign_vendor_to_wedding(
    data: AssignVendorRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Assign a vendor from the directory to a wedding.
    Optionally link to a budget category.
    """
    return await vendor_service.assign_vendor_to_wedding(
        vendor_profile_id=data.vendor_profile_id,
        wedding_id=data.wedding_id,
        created_by=current_user.email,
        budget_category_id=data.budget_category_id,
        service_notes=data.service_notes
    )


@router.get("/weddings/{wedding_id}/vendors", tags=["Vendor Assignments"])
async def get_wedding_vendors(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get all vendors assigned to a wedding"""
    return await vendor_service.get_wedding_vendors(wedding_id, current_user.email)


@router.patch("/assignments/{assignment_id}/status", tags=["Vendor Assignments"])
async def update_vendor_assignment_status(
    assignment_id: str,
    status: str = Query(..., description="New status: inquiry, quoted, contracted, confirmed, completed, cancelled"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Update the status of a vendor assignment"""
    return await vendor_service.update_assignment_status(
        assignment_id=assignment_id,
        status=status,
        created_by=current_user.email
    )


# =============================================================================
# CONTRACT TEMPLATES
# =============================================================================

@router.get("/templates", tags=["Contract Templates"])
async def list_contract_templates(
    category: Optional[str] = Query(None, description="Filter by service category"),
    include_system: bool = Query(True, description="Include system templates"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """List available contract templates"""
    return await vendor_service.get_contract_templates(
        created_by=current_user.email,
        category=category,
        include_system=include_system
    )


@router.post("/templates", tags=["Contract Templates"])
async def create_contract_template(
    data: dict,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Create a new contract template"""
    return await vendor_service.create_contract_template(
        data=data,
        created_by=current_user.email
    )


@router.get("/templates/{template_id}", tags=["Contract Templates"])
async def get_contract_template(
    template_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get a specific contract template"""
    return await vendor_service.get_contract_template(template_id)


# =============================================================================
# CONTRACTS
# =============================================================================

@router.post("/contracts", tags=["Contracts"])
async def create_contract(
    wedding_id: str,
    vendor_profile_id: str,
    total_amount: float,
    template_id: Optional[str] = None,
    quote_id: Optional[str] = None,
    deposit_percentage: Optional[float] = None,
    service_date: Optional[datetime] = None,
    service_location: Optional[str] = None,
    custom_sections: Optional[List[dict]] = None,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Create a new vendor contract.
    Can be created from a template or from scratch.
    Placeholders in templates are auto-populated with vendor/wedding data.
    """
    return await vendor_service.create_contract(
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        created_by=current_user.email,
        template_id=template_id,
        quote_id=quote_id,
        total_amount=total_amount,
        custom_sections=custom_sections,
        deposit_percentage=deposit_percentage,
        service_date=service_date,
        service_location=service_location
    )


@router.get("/contracts", tags=["Contracts"])
async def list_contracts(
    wedding_id: Optional[str] = Query(None),
    vendor_profile_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """List contracts with optional filters"""
    return await vendor_service.get_contracts(
        created_by=current_user.email,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        status=status,
        skip=skip,
        limit=limit
    )


@router.get("/contracts/{contract_id}", tags=["Contracts"])
async def get_contract(
    contract_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get a specific contract"""
    return await vendor_service.get_contract(contract_id)


@router.put("/contracts/{contract_id}", tags=["Contracts"])
async def update_contract(
    contract_id: str,
    data: dict,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Update/customize a contract.
    Planners can modify sections, terms, amounts, etc.
    Only works on draft contracts (not yet sent).
    """
    return await vendor_service.update_contract(
        contract_id=contract_id,
        data=data,
        updated_by=current_user.email
    )


@router.put("/contracts/{contract_id}/sections", tags=["Contracts"])
async def update_contract_sections(
    contract_id: str,
    sections: List[dict],
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Update contract sections.
    Each section has: id, title, content, order.
    Planners can add, remove, or modify any section.
    """
    return await vendor_service.update_contract_sections(
        contract_id=contract_id,
        sections=sections,
        updated_by=current_user.email
    )


@router.get("/contracts/{contract_id}/form-data", tags=["Contracts"])
async def get_vendor_form_data_for_contract(
    contract_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Get vendor form submission data that can be used in the contract.
    Returns form responses from this vendor that can populate contract placeholders.
    """
    return await vendor_service.get_form_data_for_contract(contract_id)


@router.post("/contracts/{contract_id}/apply-form-data", tags=["Contracts"])
async def apply_form_data_to_contract(
    contract_id: str,
    form_submission_id: str,
    field_mappings: Optional[dict] = None,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Apply data from a vendor's form submission to the contract.
    Optionally specify which form fields map to which contract placeholders.
    """
    return await vendor_service.apply_form_data_to_contract(
        contract_id=contract_id,
        form_submission_id=form_submission_id,
        field_mappings=field_mappings,
        applied_by=current_user.email
    )


@router.post("/contracts/{contract_id}/send", tags=["Contracts"])
async def send_contract_to_vendor(
    contract_id: str,
    message: Optional[str] = None,
    cc_emails: Optional[List[str]] = None,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Send contract to vendor for review and signing.
    Vendor receives an email with a secure link.
    """
    return await vendor_service.send_contract(
        contract_id=contract_id,
        created_by=current_user.email,
        message=message,
        cc_emails=cc_emails or []
    )


@router.post("/contracts/{contract_id}/upload", tags=["Contracts"])
async def upload_contract_document(
    contract_id: str,
    file: UploadFile = File(...),
    document_type: str = Query("signed", description="Type: draft, signed, attachment"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Upload a contract document (PDF, etc.)"""
    return await vendor_service.upload_contract_document(
        contract_id=contract_id,
        file=file,
        document_type=document_type
    )


# =============================================================================
# PUBLIC CONTRACT ENDPOINTS (For Vendors - No Auth)
# =============================================================================

@router.get("/public/contracts/{contract_id}", tags=["Public Contract Access"])
async def get_contract_for_vendor(
    contract_id: str,
    token: str = Query(..., description="Access token from email")
):
    """
    Get contract for vendor review (no authentication required).
    Vendor accesses this via the link in their email.
    """
    return await vendor_service.get_contract_by_token(contract_id, token)


@router.post("/public/contracts/{contract_id}/sign", tags=["Public Contract Access"])
async def sign_contract_as_vendor(
    contract_id: str,
    token: str = Query(..., description="Access token"),
    signer_name: str = Query(..., description="Name of person signing"),
    signer_email: str = Query(..., description="Email of signer"),
    request: Request = None
):
    """
    Sign a contract as a vendor (no authentication required).
    Records the signature with timestamp and IP address.
    """
    signature_ip = None
    if request:
        signature_ip = request.client.host

    return await vendor_service.sign_contract(
        contract_id=contract_id,
        token=token,
        signer_name=signer_name,
        signer_email=signer_email,
        signature_ip=signature_ip
    )


# =============================================================================
# PAYMENT MILESTONES
# =============================================================================

@router.post("/contracts/{contract_id}/milestones", tags=["Payment Milestones"])
async def create_payment_milestones(
    contract_id: str,
    milestones: List[dict],
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Create payment milestones for a contract.
    Each milestone has a description, amount, and due date.
    """
    return await vendor_service.create_payment_milestones(
        contract_id=contract_id,
        milestones=milestones,
        created_by=current_user.email
    )


@router.get("/milestones", tags=["Payment Milestones"])
async def list_payment_milestones(
    contract_id: Optional[str] = Query(None),
    wedding_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="pending, due, overdue, paid, partial"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """List payment milestones with optional filters"""
    return await vendor_service.get_payment_milestones(
        contract_id=contract_id,
        wedding_id=wedding_id,
        status=status
    )


@router.post("/milestones/{milestone_id}/pay", tags=["Payment Milestones"])
async def record_milestone_payment(
    milestone_id: str,
    amount: float,
    payment_method: str = Query(..., description="cash, check, card, bank_transfer, stripe"),
    payment_date: Optional[datetime] = None,
    notes: Optional[str] = None,
    receipt_url: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Record a payment against a milestone.
    Updates the milestone status and syncs with budget tracking.
    """
    return await vendor_service.record_payment(
        milestone_id=milestone_id,
        amount=amount,
        payment_method=payment_method,
        created_by=current_user.email,
        payment_date=payment_date,
        notes=notes,
        receipt_url=receipt_url
    )


# =============================================================================
# COMMUNICATION HISTORY
# =============================================================================

@router.get("/vendors/{vendor_id}/communications", tags=["Communication"])
async def get_vendor_communication_history(
    vendor_id: str,
    wedding_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get communication history with a vendor"""
    return await vendor_service.get_vendor_communications(
        vendor_profile_id=vendor_id,
        wedding_id=wedding_id,
        limit=limit
    )


# =============================================================================
# DASHBOARD / SUMMARY
# =============================================================================

@router.get("/dashboard", tags=["Vendor Dashboard"])
async def get_vendor_management_dashboard(
    wedding_id: Optional[str] = Query(None, description="Filter by wedding"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Get vendor management dashboard summary.
    Returns counts, pending items, and recent activity.
    """
    # Get vendors count
    vendors = await vendor_service.get_vendor_profiles(
        created_by=current_user.email,
        limit=1000
    )

    # Get contracts
    contracts = await vendor_service.get_contracts(
        created_by=current_user.email,
        wedding_id=wedding_id
    )

    # Get milestones
    milestones = await vendor_service.get_payment_milestones(
        wedding_id=wedding_id
    )

    # Calculate stats
    total_vendors = len(vendors)
    preferred_vendors = len([v for v in vendors if v.get("is_preferred")])

    pending_contracts = len([c for c in contracts if c["status"] in ["draft", "sent", "viewed"]])
    signed_contracts = len([c for c in contracts if c["status"] == "signed"])

    pending_payments = len([m for m in milestones if m["status"] in ["pending", "due"]])
    overdue_payments = len([m for m in milestones if m["status"] == "overdue"])
    total_paid = sum(m.get("paid_amount", 0) for m in milestones)
    total_due = sum(m["amount"] for m in milestones if m["status"] in ["pending", "due", "overdue"])

    return {
        "vendors": {
            "total": total_vendors,
            "preferred": preferred_vendors,
            "by_category": {}  # Could aggregate by category
        },
        "contracts": {
            "total": len(contracts),
            "pending": pending_contracts,
            "signed": signed_contracts,
            "recent": contracts[:5] if contracts else []
        },
        "payments": {
            "pending_count": pending_payments,
            "overdue_count": overdue_payments,
            "total_paid": total_paid,
            "total_due": total_due,
            "upcoming": [m for m in milestones if m["status"] in ["pending", "due"]][:5]
        }
    }


# =============================================================================
# PDF CONTRACT UPLOAD
# =============================================================================

@router.post("/contracts/upload-pdf", tags=["Contracts"])
async def upload_contract_pdf(
    file: UploadFile = File(...),
    wedding_id: str = Query(..., description="Wedding ID"),
    vendor_profile_id: str = Query(..., description="Vendor profile ID"),
    contract_title: str = Query(..., description="Contract title"),
    total_amount: float = Query(..., description="Total contract amount"),
    deposit_amount: Optional[float] = Query(None, description="Deposit amount"),
    service_date: Optional[str] = Query(None, description="Service date (ISO format)"),
    service_location: Optional[str] = Query(None, description="Service location"),
    notes: Optional[str] = Query(None, description="Internal notes"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Upload an existing PDF contract instead of using templates.
    The planner can upload their own attorney-drafted contract.
    """
    service_date_parsed = None
    if service_date:
        try:
            service_date_parsed = datetime.fromisoformat(service_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid service_date format")

    return await vendor_service.upload_contract_pdf(
        file=file,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        contract_title=contract_title,
        total_amount=total_amount,
        created_by=current_user.email,
        deposit_amount=deposit_amount,
        service_date=service_date_parsed,
        service_location=service_location,
        notes=notes
    )


# =============================================================================
# FORM DATA INTEGRATION
# =============================================================================

@router.get("/contracts/{contract_id}/form-data", tags=["Contracts"])
async def get_form_data_for_contract(
    contract_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Get form submissions from the vendor that can be used to populate contract fields.
    Returns available fields from vendor forms and suggestions for mapping.
    """
    # First get the contract to find vendor email and wedding
    contract = await vendor_service.get_contract(contract_id, current_user.email)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    return await vendor_service.get_form_data_for_contract(
        vendor_email=contract["vendor_email"],
        wedding_id=contract["wedding_id"],
        planner_email=current_user.email
    )


@router.post("/contracts/{contract_id}/apply-form-data", tags=["Contracts"])
async def apply_form_data_to_contract(
    contract_id: str,
    form_data_mappings: dict,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Apply form data to a contract's sections.
    Replaces placeholders like {{package_name}} with actual values from forms.
    """
    return await vendor_service.apply_form_data_to_contract(
        contract_id=contract_id,
        form_data_mappings=form_data_mappings,
        planner_email=current_user.email
    )


@router.put("/contracts/{contract_id}/sections", tags=["Contracts"])
async def update_contract_sections(
    contract_id: str,
    request: UpdateContractSectionsRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Update contract sections for customization after creation.
    Allows editing section content, adding custom clauses, etc.
    """
    return await vendor_service.update_contract(
        contract_id=contract_id,
        updates={
            "sections": request.sections,
            "terms_and_conditions": request.terms_and_conditions,
            "cancellation_policy": request.cancellation_policy,
            "custom_clauses": request.custom_clauses
        },
        planner_email=current_user.email
    )


# =============================================================================
# PAYMENT LINKS
# =============================================================================

@router.post("/payment-links", tags=["Payment Links"])
async def create_payment_link(
    request: CreatePaymentLinkRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Create a payment link that can be sent to vendors or couples.

    Payment Scenarios:
    - Couple pays vendor (planner facilitates)
    - Couple pays planner (planning fee)
    - Vendor pays planner (referral commission)
    """
    return await vendor_service.create_payment_link(
        payer_type=request.payer_type.value,
        payer_email=request.payer_email,
        payer_name=request.payer_name,
        payer_phone=request.payer_phone,
        recipient_type=request.recipient_type.value,
        recipient_email=request.recipient_email,
        recipient_name=request.recipient_name,
        amount=request.amount,
        currency=request.currency,
        description=request.description,
        due_date=request.due_date,
        wedding_id=request.wedding_id,
        contract_id=request.contract_id,
        milestone_id=request.milestone_id,
        vendor_profile_id=request.vendor_profile_id,
        email_subject=request.email_subject,
        email_message=request.email_message,
        created_by=current_user.email
    )


@router.post("/payment-links/{payment_link_id}/send", tags=["Payment Links"])
async def send_payment_link(
    payment_link_id: str,
    custom_message: Optional[str] = Query(None, description="Custom message for the email"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Send a payment link to the payer via email.
    """
    return await vendor_service.send_payment_link(
        payment_link_id=payment_link_id,
        planner_email=current_user.email,
        custom_message=custom_message
    )


@router.get("/payment-links", tags=["Payment Links"])
async def list_payment_links(
    wedding_id: Optional[str] = Query(None, description="Filter by wedding"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    List payment links created by the planner.
    """
    return await vendor_service.get_payment_links(
        planner_email=current_user.email,
        wedding_id=wedding_id,
        status=status,
        skip=skip,
        limit=limit
    )


@router.get("/payment-links/{payment_link_id}", tags=["Payment Links"])
async def get_payment_link(
    payment_link_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Get a specific payment link.
    """
    from bson import ObjectId

    link = await vendor_service.payment_links.find_one({
        "_id": ObjectId(payment_link_id),
        "created_by": current_user.email
    })

    if not link:
        raise HTTPException(status_code=404, detail="Payment link not found")

    link["_id"] = str(link["_id"])
    return link
