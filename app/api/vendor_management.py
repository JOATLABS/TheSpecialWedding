"""
Vendor Management API

Comprehensive API for managing vendors, contracts, and payments.
All endpoints are feature-gated by subscription plan.

This router owns planner-to-vendor contract administration under `/admin/contracts`.
Couple/planner client contracts are handled separately under `/admin/client-contracts`.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.dependencies.auth_extended import ExtendedAuthUser, enforce_team_permission
from app.dependencies.feature_gates import require_vendor_feature
from app.models.vendor import (
    AssignVendorRequest,
    CreatePaymentLinkRequest,
    CreateVendorProfileRequest,
    UpdateVendorProfileRequest,
    VendorCategory,
)
from app.models.vendor_contracts import (
    ApplyVendorContractFormDataRequest,
    CreateVendorContractRequest,
    CreateVendorContractRevisionRequest,
    CreateVendorContractTemplateRequest,
    CreateVendorPaymentMilestonesRequest,
    DuplicateVendorContractRequest,
    RecordVendorMilestonePaymentRequest,
    SendVendorContractRequest,
    UpdateVendorContractRequest,
    UpdateVendorContractSectionsRequest,
    VendorContractActivityResponse,
    VendorContractFormDataResponse,
    VendorContractRevisionHistoryResponse,
)
from app.services.vendor_service import vendor_service

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# VENDOR DIRECTORY (Master List)
# =============================================================================


@router.get("/directory", tags=["Vendor Directory"])
async def list_vendor_directory(
    category: Optional[str] = Query(None, description="Filter by service category"),
    is_preferred: Optional[bool] = Query(
        None, description="Filter by preferred status"
    ),
    search: Optional[str] = Query(
        None, description="Search by name, email, description"
    ),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    List all vendors in the planner's directory.
    Root admins see ALL vendors; planners see only their own.
    Supports filtering by category, preferred status, search, and tags.
    """
    tag_list = tags.split(",") if tags else None
    # Root admin sees every vendor regardless of created_by
    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.get_vendor_profiles(
        created_by=owner_email,
        category=category,
        is_preferred=is_preferred,
        search=search,
        tags=tag_list,
        skip=skip,
        limit=limit,
    )


@router.post("/directory", tags=["Vendor Directory"])
async def create_vendor_in_directory(
    data: CreateVendorProfileRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Add a new vendor to the directory.
    This creates a reusable vendor contact that can be assigned to any wedding.
    """
    enforce_team_permission(current_user, "manage_vendors")
    return await vendor_service.create_vendor_profile(
        data=data.model_dump(), created_by=current_user.email
    )


@router.get("/directory/categories", tags=["Vendor Directory"])
async def get_used_categories(
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Get list of service categories used in the planner's directory"""
    categories = await vendor_service.get_vendor_categories_used(current_user.email)
    return {"categories": categories}


@router.get("/directory/all-categories", tags=["Vendor Directory"])
async def get_all_categories(
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Get all available vendor categories"""
    return {"categories": [c.value for c in VendorCategory]}


@router.get("/directory/{vendor_id}", tags=["Vendor Directory"])
async def get_vendor_profile(
    vendor_id: str, current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get a specific vendor from the directory"""
    return await vendor_service.get_vendor_profile(vendor_id, current_user.email)


@router.put("/directory/{vendor_id}", tags=["Vendor Directory"])
async def update_vendor_profile(
    vendor_id: str,
    data: UpdateVendorProfileRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Update a vendor in the directory. Root admins can update any vendor."""
    enforce_team_permission(current_user, "manage_vendors")
    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.update_vendor_profile(
        vendor_id=vendor_id,
        data=data.model_dump(exclude_none=True),
        created_by=owner_email,
    )


@router.delete("/directory/{vendor_id}", tags=["Vendor Directory"])
async def delete_vendor_from_directory(
    vendor_id: str, current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Remove a vendor from the directory (soft delete)"""
    enforce_team_permission(current_user, "manage_vendors")
    # Root admin can delete any vendor; planners can only delete their own
    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.delete_vendor_profile(vendor_id, owner_email)


# =============================================================================
# VENDOR ASSIGNMENTS (Link to Wedding)
# =============================================================================


@router.post("/assign", tags=["Vendor Assignments"])
async def assign_vendor_to_wedding(
    data: AssignVendorRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Assign a vendor from the directory to a wedding.
    Optionally link to a budget category.
    Root admins bypass the planner-ownership filter (pass ``None``).
    """
    enforce_team_permission(current_user, "manage_vendors")
    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.assign_vendor_to_wedding(
        vendor_profile_id=data.vendor_profile_id,
        wedding_id=data.wedding_id,
        created_by=owner_email,
        budget_category_id=data.budget_category_id,
        service_notes=data.service_notes,
    )


@router.get("/weddings/{wedding_id}/vendors", tags=["Vendor Assignments"])
async def get_wedding_vendors(
    wedding_id: str, current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get all vendors assigned to a wedding"""
    return await vendor_service.get_wedding_vendors(wedding_id, current_user.email)


@router.patch("/assignments/{assignment_id}/status", tags=["Vendor Assignments"])
async def update_vendor_assignment_status(
    assignment_id: str,
    status: str = Query(
        ...,
        description="New status: inquiry, quoted, contracted, confirmed, completed, cancelled",
        pattern="^(inquiry|quoted|contracted|confirmed|completed|cancelled)$",
    ),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Update the status of a vendor assignment.

    Root admins bypass the planner-ownership filter (pass ``None``).
    """
    enforce_team_permission(current_user, "manage_vendors")
    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.update_assignment_status(
        assignment_id=assignment_id, status=status, created_by=owner_email
    )


# =============================================================================
# CONTRACT TEMPLATES
# =============================================================================


@router.get("/templates", tags=["Contract Templates"])
async def list_contract_templates(
    category: Optional[str] = Query(None, description="Filter by service category"),
    include_system: bool = Query(True, description="Include system templates"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """List available contract templates"""
    return await vendor_service.get_contract_templates(
        created_by=current_user.email, category=category, include_system=include_system
    )


@router.post("/templates", tags=["Contract Templates"])
async def create_contract_template(
    data: CreateVendorContractTemplateRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Create a new contract template"""
    enforce_team_permission(current_user, "manage_vendors")
    return await vendor_service.create_contract_template(
        data=data.model_dump(exclude_none=True), created_by=current_user.email
    )


@router.get("/templates/{template_id}", tags=["Contract Templates"])
async def get_contract_template(
    template_id: str, current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get a specific contract template"""
    return await vendor_service.get_contract_template(template_id)


# =============================================================================
# CONTRACTS
# =============================================================================


@router.post("/contracts", tags=["Contracts"])
async def create_contract(
    data: CreateVendorContractRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Create a new vendor contract.
    Can be created from a template or from scratch.
    Placeholders in templates are auto-populated with vendor/wedding data.
    Root admins bypass the planner-ownership filter (pass ``None``).
    """
    enforce_team_permission(current_user, "manage_vendors")
    payload = data.model_dump(exclude_none=True)
    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.create_contract(
        created_by=owner_email,
        **payload,
    )


@router.get("/contracts", tags=["Contracts"])
async def list_contracts(
    wedding_id: Optional[str] = Query(None),
    vendor_profile_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """List contracts with optional filters"""
    return await vendor_service.get_contracts(
        created_by=current_user.email,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.get("/contracts/{contract_id}", tags=["Contracts"])
async def get_contract(
    contract_id: str, current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """Get a specific contract (only contracts created by the current user)"""
    return await vendor_service.get_contract(
        contract_id,
        created_by=current_user.email,
        include_couple_contact=True,
    )


@router.post("/contracts/{contract_id}/revisions", tags=["Contracts"])
async def create_contract_revision(
    contract_id: str,
    data: CreateVendorContractRevisionRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Create a new draft revision or amendment from a live vendor contract."""
    enforce_team_permission(current_user, "manage_vendors")
    return await vendor_service.create_contract_revision(
        contract_id=contract_id,
        created_by=current_user.email,
        revision_kind=data.revision_kind,
        reason=data.reason,
        copy_sections=data.copy_sections,
        copy_terms_and_conditions=data.copy_terms_and_conditions,
        copy_cancellation_policy=data.copy_cancellation_policy,
        copy_custom_clauses=data.copy_custom_clauses,
    )


@router.post("/contracts/{contract_id}/duplicate", tags=["Contracts"])
async def duplicate_contract(
    contract_id: str,
    data: DuplicateVendorContractRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Clone a contract into a new draft root contract (independent lineage).

    Optionally retargets the duplicate to a different wedding or vendor;
    when retargeted, denormalized vendor fields are refreshed and form
    submission linkage is dropped.
    """
    enforce_team_permission(current_user, "manage_vendors")
    return await vendor_service.duplicate_contract(
        contract_id=contract_id,
        created_by=current_user.email,
        new_contract_title=data.new_contract_title,
        target_wedding_id=data.target_wedding_id,
        target_vendor_profile_id=data.target_vendor_profile_id,
        copy_sections=data.copy_sections,
        copy_terms_and_conditions=data.copy_terms_and_conditions,
        copy_cancellation_policy=data.copy_cancellation_policy,
        copy_custom_clauses=data.copy_custom_clauses,
        copy_attachments=data.copy_attachments,
    )


@router.get(
    "/contracts/{contract_id}/revisions",
    tags=["Contracts"],
    response_model=VendorContractRevisionHistoryResponse,
)
async def list_contract_revisions(
    contract_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """List the full lineage for the contract chain containing this contract."""
    return await vendor_service.get_contract_revision_history(
        contract_id=contract_id,
        created_by=current_user.email,
    )


@router.put("/contracts/{contract_id}", tags=["Contracts"])
async def update_contract(
    contract_id: str,
    data: UpdateVendorContractRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Update/customize a contract.
    Planners can modify sections, terms, amounts, etc.
    Only works on draft contracts (not yet sent).
    """
    enforce_team_permission(current_user, "manage_vendors")
    return await vendor_service.update_contract(
        contract_id=contract_id,
        data=data.model_dump(exclude_none=True),
        updated_by=current_user.email,
    )


@router.put("/contracts/{contract_id}/sections", tags=["Contracts"])
async def update_contract_sections(
    contract_id: str,
    data: UpdateVendorContractSectionsRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Update contract sections.
    Each section has: id, title, content, order.
    Planners can add, remove, or modify any section.
    """
    enforce_team_permission(current_user, "manage_vendors")
    payload = data.model_dump(exclude_none=True)
    return await vendor_service.update_contract_sections(
        contract_id=contract_id,
        sections=payload["sections"],
        terms_and_conditions=payload.get("terms_and_conditions"),
        cancellation_policy=payload.get("cancellation_policy"),
        custom_clauses=payload.get("custom_clauses"),
        updated_by=current_user.email,
    )


@router.get(
    "/contracts/{contract_id}/form-data",
    tags=["Contracts"],
    response_model=VendorContractFormDataResponse,
    # Each VendorContractFormSubmissionSummary uses Field(alias="_id"). Without
    # response_model_by_alias=True, FastAPI serializes the field as `id` and
    # the contract-detail UI (which reads `selectedSubmission._id`) gets
    # undefined → 422 from the apply endpoint.
    response_model_by_alias=True,
)
async def get_vendor_form_data_for_contract(
    contract_id: str, current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Get vendor form submission data that can be used in the contract.
    Returns form responses from this vendor that can populate contract placeholders.
    """
    return await vendor_service.get_form_data_for_contract(
        contract_id, created_by=current_user.email
    )


@router.post("/contracts/{contract_id}/apply-form-data", tags=["Contracts"])
async def apply_form_data_to_contract(
    contract_id: str,
    data: ApplyVendorContractFormDataRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Apply data from a vendor's form submission to the contract.
    Optionally specify which form fields map to which contract placeholders.

    Scoped to the actor planner unless they are root-admin (root admins
    pass ``None`` to skip the planner-ownership filter on both the
    contract and the source form submission).
    """
    enforce_team_permission(current_user, "manage_vendors")
    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.apply_form_data_to_contract(
        contract_id=contract_id,
        form_submission_id=data.form_submission_id,
        field_mappings=data.field_mappings,
        applied_by=owner_email,
    )


@router.post("/contracts/{contract_id}/send", tags=["Contracts"])
async def send_contract_to_vendor(
    contract_id: str,
    data: SendVendorContractRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Send contract to vendor for review and signing.
    Vendor receives an email with a secure link.
    """
    enforce_team_permission(current_user, "manage_vendors")
    return await vendor_service.send_contract(
        contract_id=contract_id,
        created_by=current_user.email,
        message=data.message,
        cc_emails=data.cc_emails,
    )


@router.post("/contracts/{contract_id}/upload", tags=["Contracts"])
async def upload_contract_document(
    contract_id: str,
    file: UploadFile = File(...),
    document_type: str = Query("signed", description="Type: draft, signed, attachment"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Upload a contract document (PDF, etc.).

    Scoped to the actor planner unless they are root-admin (root admins pass
    ``None`` to skip the ownership filter). Mirrors the pattern used by
    /admin/directory and other planner-scoped routes in this module.
    """
    enforce_team_permission(current_user, "manage_vendors")
    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.upload_contract_document(
        contract_id=contract_id,
        file=file,
        document_type=document_type,
        created_by=owner_email,
    )


# =============================================================================
# PAYMENT MILESTONES
# =============================================================================


@router.post("/contracts/{contract_id}/milestones", tags=["Payment Milestones"])
async def create_payment_milestones(
    contract_id: str,
    data: CreateVendorPaymentMilestonesRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Create payment milestones for a contract.
    Each milestone has a description, amount, and due date.
    """
    enforce_team_permission(current_user, "manage_vendors")
    payload = data.model_dump(exclude_none=True)
    return await vendor_service.create_payment_milestones(
        contract_id=contract_id,
        milestones=payload["milestones"],
        created_by=current_user.email,
    )


@router.get("/milestones", tags=["Payment Milestones"])
async def list_payment_milestones(
    contract_id: Optional[str] = Query(None),
    wedding_id: Optional[str] = Query(None),
    status: Optional[str] = Query(
        None, description="pending, due, overdue, paid, partial"
    ),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """List payment milestones with optional filters.

    Root admins bypass the planner-ownership filter (pass ``None``);
    every other caller is scoped to milestones they own.
    """
    enforce_team_permission(current_user, "manage_vendors")
    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.get_payment_milestones(
        contract_id=contract_id,
        wedding_id=wedding_id,
        status=status,
        created_by=owner_email,
    )


@router.post("/milestones/{milestone_id}/pay", tags=["Payment Milestones"])
async def record_milestone_payment(
    milestone_id: str,
    data: RecordVendorMilestonePaymentRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Record a payment against a milestone.
    Updates the milestone status and syncs with budget tracking.
    """
    enforce_team_permission(current_user, "manage_vendors")
    return await vendor_service.record_payment(
        milestone_id=milestone_id,
        amount=data.amount,
        payment_method=data.payment_method,
        created_by=current_user.email,
        payment_date=data.payment_date,
        notes=data.notes,
        receipt_url=data.receipt_url,
    )


@router.get(
    "/contracts/{contract_id}/activity",
    response_model=VendorContractActivityResponse,
    tags=["Contracts"],
)
async def get_contract_activity(
    contract_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Return chronological activity for one vendor contract."""
    enforce_team_permission(current_user, "manage_vendors")
    return await vendor_service.get_contract_activity(
        contract_id=contract_id,
        created_by=current_user.email,
    )


# =============================================================================
# COMMUNICATION HISTORY
# =============================================================================


@router.get("/vendors/{vendor_id}/communications", tags=["Communication"])
async def get_vendor_communication_history(
    vendor_id: str,
    wedding_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """Get communication history with a vendor"""
    return await vendor_service.get_vendor_communications(
        vendor_profile_id=vendor_id, wedding_id=wedding_id, limit=limit
    )


# =============================================================================
# DASHBOARD / SUMMARY
# =============================================================================


@router.get("/dashboard", tags=["Vendor Dashboard"])
async def get_vendor_management_dashboard(
    wedding_id: Optional[str] = Query(None, description="Filter by wedding"),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Get vendor management dashboard summary.
    Returns counts, pending items, and recent activity.
    Uses efficient count queries instead of loading all documents.

    Root admins bypass the planner-ownership filter (pass ``None`` so
    the aggregation spans every planner); planners see only their own
    counts. Pre-fix the milestone aggregation skipped this scope and
    summed across every other planner's milestones.
    """
    # Root admin sees every planner's counts; planners see only their own.
    owner_email = None if current_user.is_root_admin else current_user.email

    # Get counts efficiently using aggregation
    counts = await vendor_service.get_dashboard_counts(
        created_by=owner_email, wedding_id=wedding_id
    )

    # Only fetch limited recent items for display. ``get_contracts``
    # still requires a concrete email (root-admin bypass on that
    # service method is a separate Ticket #1-shape change, out of
    # scope here), so root admins get their own (typically empty)
    # recent-contracts list — the leak we're fixing here is the
    # aggregation totals, not the recent list.
    recent_contracts = await vendor_service.get_contracts(
        created_by=current_user.email, wedding_id=wedding_id, limit=5
    )

    upcoming_milestones = await vendor_service.get_payment_milestones(
        wedding_id=wedding_id,
        status="pending",
        created_by=owner_email,
    )

    return {
        "vendors": {
            **counts["vendors"],
            "by_category": {},  # Could aggregate by category if needed
        },
        "contracts": {**counts["contracts"], "recent": recent_contracts[:5]},
        "payments": {**counts["payments"], "upcoming": upcoming_milestones[:5]},
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
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Upload an existing PDF contract instead of using templates.
    The planner can upload their own attorney-drafted contract.
    Root admins bypass the planner-ownership filter (pass ``None``).
    """
    enforce_team_permission(current_user, "manage_vendors")
    service_date_parsed = None
    if service_date:
        try:
            service_date_parsed = datetime.fromisoformat(
                service_date.replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid service_date format")

    owner_email = None if current_user.is_root_admin else current_user.email
    return await vendor_service.upload_contract_pdf(
        file=file,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        contract_title=contract_title,
        total_amount=total_amount,
        created_by=owner_email,
        deposit_amount=deposit_amount,
        service_date=service_date_parsed,
        service_location=service_location,
        notes=notes,
    )


# =============================================================================
# PAYMENT LINKS
# =============================================================================


@router.post("/payment-links", tags=["Payment Links"])
async def create_payment_link(
    request: CreatePaymentLinkRequest,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Create a payment link that can be sent to vendors or couples.

    Payment Scenarios:
    - Couple pays vendor (planner facilitates)
    - Couple pays planner (planning fee)
    - Vendor pays planner (referral commission)
    """
    enforce_team_permission(current_user, "manage_vendors")
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
        created_by=current_user.email,
    )


@router.post("/payment-links/{payment_link_id}/send", tags=["Payment Links"])
async def send_payment_link(
    payment_link_id: str,
    custom_message: Optional[str] = Query(
        None, description="Custom message for the email"
    ),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Send a payment link to the payer via email.
    """
    enforce_team_permission(current_user, "manage_vendors")
    return await vendor_service.send_payment_link(
        payment_link_id=payment_link_id,
        planner_email=current_user.email,
        custom_message=custom_message,
    )


@router.get("/payment-links", tags=["Payment Links"])
async def list_payment_links(
    wedding_id: Optional[str] = Query(None, description="Filter by wedding"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    List payment links created by the planner.
    """
    return await vendor_service.get_payment_links(
        planner_email=current_user.email,
        wedding_id=wedding_id,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.get("/payment-links/{payment_link_id}", tags=["Payment Links"])
async def get_payment_link(
    payment_link_id: str,
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Get a specific payment link.
    """
    from bson import ObjectId

    link = await vendor_service.payment_links.find_one(
        {"_id": ObjectId(payment_link_id), "created_by": current_user.email}
    )

    if not link:
        raise HTTPException(status_code=404, detail="Payment link not found")

    link["_id"] = str(link["_id"])
    return link


# =============================================================================
# PLANNER CONTRACT SETTINGS
# =============================================================================


@router.get("/settings/contract", tags=["Settings"])
async def get_contract_settings(
    current_user: ExtendedAuthUser = Depends(require_vendor_feature),
):
    """
    Get the planner's contract settings.

    These settings control default behaviors for contract creation:
    - token_expiry_days: How long contract links remain valid
    - deposit_due_days: Default days after signing for deposit payment
    - payment_reminder_days: When to send payment reminders
    - auto_followup_days: When to auto-generate follow-up for unsigned contracts
    """
    settings = await vendor_service._get_planner_contract_settings(current_user.email)
    return {
        "settings": settings,
        "defaults": {
            "token_expiry_days": 30,
            "deposit_due_days": 7,
            "payment_reminder_days": [7, 3, 1],
            "auto_followup_days": 3,
            "default_currency": "USD",
        },
    }


@router.put("/settings/contract", tags=["Settings"])
async def update_contract_settings(
    settings: dict, current_user: ExtendedAuthUser = Depends(require_vendor_feature)
):
    """
    Update the planner's contract settings.

    Allowed fields:
    - token_expiry_days (7-90): How long contract links remain valid
    - deposit_due_days (1-60): Default days after signing for deposit payment
    - payment_reminder_days: Array of days before due date to send reminders
    - auto_followup_days (1-14): Days to wait before auto-generating follow-up
    - default_currency: Default currency for contracts (e.g., "USD")
    """
    enforce_team_permission(current_user, "manage_vendors")
    # Validate settings
    allowed_fields = {
        "token_expiry_days",
        "deposit_due_days",
        "payment_reminder_days",
        "auto_followup_days",
        "default_currency",
    }

    # Filter to only allowed fields
    validated_settings = {}
    for key, value in settings.items():
        if key not in allowed_fields:
            continue

        # Validate ranges
        if key == "token_expiry_days":
            if not isinstance(value, int) or value < 7 or value > 90:
                raise HTTPException(
                    status_code=400, detail="token_expiry_days must be between 7 and 90"
                )
        elif key == "deposit_due_days":
            if not isinstance(value, int) or value < 1 or value > 60:
                raise HTTPException(
                    status_code=400, detail="deposit_due_days must be between 1 and 60"
                )
        elif key == "auto_followup_days":
            if not isinstance(value, int) or value < 1 or value > 14:
                raise HTTPException(
                    status_code=400,
                    detail="auto_followup_days must be between 1 and 14",
                )
        elif key == "payment_reminder_days":
            if not isinstance(value, list) or not all(
                isinstance(d, int) and d > 0 for d in value
            ):
                raise HTTPException(
                    status_code=400,
                    detail="payment_reminder_days must be an array of positive integers",
                )
        elif key == "default_currency":
            if not isinstance(value, str) or len(value) != 3:
                raise HTTPException(
                    status_code=400,
                    detail="default_currency must be a 3-letter currency code",
                )

        validated_settings[key] = value

    if not validated_settings:
        raise HTTPException(status_code=400, detail="No valid settings provided")

    # Update user document
    from app.core.database import mongo

    result = await mongo.get_users_collection().update_one(
        {"email": current_user.email},
        {"$set": {"contract_settings": validated_settings}},
    )

    if result.modified_count == 0 and result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Contract settings updated", "settings": validated_settings}
