"""
Client contract API routes.

This module intentionally separates:
- authenticated planner/admin couple-contract routes
- public couple-contract and portal routes
- internal cron routes

Vendor contract admin routes live in `app.api.vendor_management` under `/admin/contracts`.
"""

import logging
from datetime import timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    enforce_team_permission,
    require_admin_or_planner,
    require_team_or_planner,
)
from app.services.contract_service import contract_service
from app.utils.query_validation import validated_status_filter

logger = logging.getLogger(__name__)
client_contracts_admin_router = APIRouter(prefix="/client-contracts")
client_contracts_public_router = APIRouter(prefix="/public")
client_contracts_cron_router = APIRouter(prefix="/cron/contracts")


def _resolve_couple_display_name(couple: Optional[dict]) -> str:
    couple = couple or {}
    partner1 = (couple.get("partner1_name") or couple.get("name") or "").strip()
    partner2 = (couple.get("partner2_name") or couple.get("partner_name") or "").strip()
    if partner1 and partner2:
        return f"{partner1} & {partner2}"
    return partner1 or partner2 or "A couple"


def _resolve_stripe_reference_id(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        resolved = value.get("id")
        return resolved if isinstance(resolved, str) else None
    resolved = getattr(value, "id", None)
    return resolved if isinstance(resolved, str) else None


def _validate_setup_intent_payment_method(
    stripe_client: Any,
    *,
    customer_id: str,
    contract_token: str,
    payment_method_id: str,
    setup_intent_id: str,
    expected_action: Optional[str],
) -> tuple[str, Optional[str], Optional[str]]:
    """Resolve and validate a payment method captured through Stripe SetupIntent."""

    setup_intent = stripe_client.SetupIntent.retrieve(setup_intent_id)
    if setup_intent.status != "succeeded":
        raise HTTPException(status_code=400, detail="Payment setup is not complete")

    setup_customer_id = _resolve_stripe_reference_id(setup_intent.customer)
    if setup_customer_id != customer_id:
        raise HTTPException(
            status_code=400, detail="Payment setup belongs to a different customer"
        )

    metadata = dict(getattr(setup_intent, "metadata", {}) or {})
    if metadata.get("contract_token") != contract_token:
        raise HTTPException(
            status_code=400, detail="Payment setup does not match this contract"
        )
    if expected_action and metadata.get("action") != expected_action:
        raise HTTPException(status_code=400, detail="Payment setup action is invalid")

    resolved_payment_method_id = _resolve_stripe_reference_id(
        setup_intent.payment_method
    )
    if not resolved_payment_method_id:
        raise HTTPException(
            status_code=400, detail="Payment setup did not produce a payment method"
        )
    if payment_method_id != resolved_payment_method_id:
        raise HTTPException(
            status_code=400,
            detail="Payment method does not match the completed payment setup",
        )

    payment_method = stripe_client.PaymentMethod.retrieve(payment_method_id)
    resolved_customer = _resolve_stripe_reference_id(payment_method.customer)
    if resolved_customer != customer_id:
        raise HTTPException(
            status_code=400, detail="Payment method belongs to a different customer"
        )

    card = payment_method.card if payment_method.type == "card" else None
    resolved_payment_method_id = (
        _resolve_stripe_reference_id(payment_method) or payment_method_id
    )
    if resolved_payment_method_id != payment_method_id:
        raise HTTPException(
            status_code=400,
            detail="Retrieved payment method does not match the requested payment method",
        )

    return (
        resolved_payment_method_id,
        card.last4 if card else None,
        card.brand if card else None,
    )


def _extract_payment_method_card_summary(payment_method: object) -> dict:
    payment_method_type = getattr(payment_method, "type", None)
    card = (
        getattr(payment_method, "card", None) if payment_method_type == "card" else None
    )
    return {
        "brand": getattr(card, "brand", None),
        "last4": getattr(card, "last4", None),
    }


# ============================================================================
# REQUEST MODELS
# ============================================================================


class SignContractRequest(BaseModel):
    """Request to sign a contract."""

    signature_name: str = Field(..., min_length=1, max_length=200)
    stripe_customer_id: Optional[str] = Field(None, min_length=1)
    stripe_payment_method_id: str = Field(..., min_length=1)
    setup_intent_id: str = Field(..., min_length=1)
    payment_method_last4: Optional[str] = Field(None, max_length=4)
    payment_method_brand: Optional[str] = Field(None, max_length=20)
    accept_terms: bool = Field(...)


class UpdateWeddingDateRequest(BaseModel):
    """Request to update wedding date."""

    wedding_date: str = Field(..., description="ISO format date (YYYY-MM-DD)")


class CancelContractRequest(BaseModel):
    """Request to cancel a contract."""

    reason: str = Field(..., min_length=1, max_length=500)


class MarkPaidExternallyRequest(BaseModel):
    """Request to mark a payment as paid externally."""

    payment_method: Optional[str] = Field(
        None,
        max_length=50,
        description="How payment was received: cash, check, wire, etc.",
    )
    note: Optional[str] = Field(
        None, max_length=500, description="Optional note about the payment"
    )


class RefundPaymentRequest(BaseModel):
    """Request to refund a payment."""

    amount: Optional[float] = Field(
        None, gt=0, description="Refund amount (partial). If not provided, full refund."
    )
    reason: Optional[str] = Field(None, max_length=500, description="Reason for refund")


# ============================================================================
# ADMIN ENDPOINTS (Authenticated)
# ============================================================================


@client_contracts_admin_router.get("", tags=["Contracts"])
async def list_contracts(
    status: Optional[str] = Query(None, description="Filter by contract status"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    skip: int = Query(0, ge=0, description="Items to skip"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    List all contracts for the authenticated planner.

    - **status**: Filter by contract status
    """
    try:
        # Validate query parameters
        status = validated_status_filter(
            status,
            ["draft", "sent", "viewed", "signed", "active", "completed", "cancelled"],
        )

        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        contracts = await contract_service.list_contracts(
            planner_id=planner_id, status=status, limit=limit, skip=skip
        )

        return {"contracts": contracts, "count": len(contracts)}

    except Exception as e:
        logger.error(f"Failed to list contracts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contracts")


@client_contracts_admin_router.get("/payments/overview", tags=["Contracts"])
async def get_contract_payments_overview(
    contract_statuses: Optional[str] = Query(
        "signed,active",
        description="Comma-separated list of contract statuses to include",
    ),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get scheduled payments across the planner's contracts in one response.

    Used by the admin money dashboard to avoid per-contract payment fan-out.
    """
    try:
        allowed_statuses = {
            "draft",
            "sent",
            "viewed",
            "signed",
            "active",
            "completed",
            "cancelled",
        }
        parsed_statuses = [
            value.strip()
            for value in (contract_statuses or "").split(",")
            if value.strip()
        ]
        invalid_statuses = sorted(set(parsed_statuses) - allowed_statuses)
        if invalid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid contract status filter: {', '.join(invalid_statuses)}",
            )

        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )
        payments = await contract_service.get_planner_payment_overview(
            planner_id=planner_id,
            contract_statuses=parsed_statuses or None,
        )

        return {
            "payments": payments,
            "count": len(payments),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contract payment overview: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve payment overview"
        )


@client_contracts_admin_router.post("", tags=["Contracts"])
async def create_contract(
    request: Request,
    wedding_id: str = Query(..., description="Wedding ID"),
    vendor_profile_id: str = Query(..., description="Vendor profile ID"),
    total_amount: float = Query(..., gt=0, description="Total contract amount"),
    template_id: Optional[str] = Query(None, description="Template ID"),
    deposit_percentage: float = Query(
        50.0, ge=0, le=100, description="Deposit percentage"
    ),
    service_date: Optional[str] = Query(None, description="Service date (ISO format)"),
    service_location: Optional[str] = Query(None, description="Service location"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Create a new vendor contract (C3).

    Custom sections can be sent as a JSON array in the request body.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        # Parse optional custom sections from body
        custom_sections = None
        try:
            body = await request.json()
            if isinstance(body, list):
                custom_sections = body
        except Exception as e:
            logger.debug(f"No body or invalid JSON in request: {e}")
            pass  # No body or not JSON — that's fine

        contract = await contract_service.create_contract(
            planner_id=planner_id,
            wedding_id=wedding_id,
            vendor_profile_id=vendor_profile_id,
            total_amount=total_amount,
            template_id=template_id,
            deposit_percentage=deposit_percentage,
            service_date=service_date,
            service_location=service_location,
            custom_sections=custom_sections,
        )

        return contract

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create contract")


@client_contracts_admin_router.put("/{contract_id}", tags=["Contracts"])
async def update_contract(
    contract_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Update a contract. Only allowed for draft/pending_review contracts.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )
        body = await request.json()

        contract = await contract_service.update_contract(
            contract_id=contract_id,
            planner_id=planner_id,
            update_data=body,
        )

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        return contract

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update contract")


@client_contracts_admin_router.put("/{contract_id}/sections", tags=["Contracts"])
async def update_contract_sections(
    contract_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Update contract sections (C4).
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )
        body = await request.json()

        contract = await contract_service.update_contract_sections(
            contract_id=contract_id,
            planner_id=planner_id,
            sections=body.get("sections", []),
            terms_and_conditions=body.get("terms_and_conditions"),
            cancellation_policy=body.get("cancellation_policy"),
            custom_clauses=body.get("custom_clauses"),
        )

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        return contract

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update contract sections: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to update contract sections"
        )


@client_contracts_admin_router.post("/{contract_id}/send", tags=["Contracts"])
async def send_contract(
    contract_id: str,
    message: Optional[str] = Query(None, description="Personal message to include"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Send a contract to the vendor for review/signing.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        result = await contract_service.send_contract(
            contract_id=contract_id,
            planner_id=planner_id,
            message=message,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send contract")


@client_contracts_admin_router.post("/{contract_id}/milestones", tags=["Contracts"])
async def create_milestones(
    contract_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Create payment milestones for a contract.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )
        body = await request.json()

        if not isinstance(body, list):
            raise HTTPException(status_code=400, detail="Expected a list of milestones")

        milestones = await contract_service.create_payment_milestones(
            contract_id=contract_id,
            planner_id=planner_id,
            milestones=body,
        )

        return milestones

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create milestones: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create milestones")


@client_contracts_admin_router.get("/{contract_id}/form-data", tags=["Contracts"])
async def get_contract_form_data(
    contract_id: str, current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Get vendor form data submissions for a contract.
    """
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        form_data = await contract_service.get_contract_form_data(
            contract_id=contract_id,
            planner_id=planner_id,
        )

        return form_data

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get contract form data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get form data")


@client_contracts_admin_router.post(
    "/{contract_id}/apply-form-data", tags=["Contracts"]
)
async def apply_form_data_to_contract(
    contract_id: str,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Apply vendor form data to a contract's placeholders.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )
        body = await request.json()

        # Get contract and update sections with form data
        contract = await contract_service.get_contract(contract_id, planner_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        if contract.get("status") not in ("draft", "pending_review"):
            raise HTTPException(
                status_code=400, detail="Cannot modify a non-draft contract"
            )

        # Replace placeholders in sections with form data values
        sections = contract.get("sections", [])
        updated_sections = []
        for section in sections:
            content = section.get("content", "")
            for key, value in body.items():
                placeholder = "{{" + key + "}}"
                content = content.replace(placeholder, str(value) if value else "")
            updated_sections.append({**section, "content": content})

        updated = await contract_service.update_contract_sections(
            contract_id=contract_id,
            planner_id=planner_id,
            sections=updated_sections,
        )

        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply form data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to apply form data")


@client_contracts_admin_router.get("/milestones", tags=["Contracts"])
async def list_milestones(
    contract_id: Optional[str] = Query(None),
    wedding_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    List payment milestones filtered by contract, wedding, or status.
    """
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        milestones = await contract_service.get_milestones(
            planner_id=planner_id,
            contract_id=contract_id,
            wedding_id=wedding_id,
            status=status,
        )

        return milestones

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list milestones: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list milestones")


@client_contracts_admin_router.post(
    "/milestones/{milestone_id}/pay", tags=["Contracts"]
)
async def record_milestone_payment(
    milestone_id: str,
    amount: float = Query(..., gt=0),
    payment_method: str = Query("manual"),
    payment_date: Optional[str] = Query(None),
    notes: Optional[str] = Query(None),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Record a payment against a milestone (C2).
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        milestone = await contract_service.record_milestone_payment(
            milestone_id=milestone_id,
            planner_id=planner_id,
            amount=amount,
            payment_method=payment_method,
            payment_date=payment_date,
            notes=notes,
        )

        if not milestone:
            raise HTTPException(status_code=404, detail="Milestone not found")

        return milestone

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record payment")


@client_contracts_admin_router.get("/stats", tags=["Contracts"])
async def get_contract_stats(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get contract statistics for the planner."""
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )
        stats = await contract_service.get_contract_stats(planner_id)
        return stats

    except Exception as e:
        logger.error(f"Failed to get contract stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


# ============================================================================
# FOLLOW-UP DRAFT ENDPOINTS (Authenticated)
# NOTE: These static paths MUST come before /contracts/{contract_id} to prevent
# FastAPI from matching "followup-drafts" as a contract_id parameter.
# ============================================================================


@client_contracts_admin_router.get("/followup-drafts", tags=["Contracts"])
async def get_followup_drafts(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get all pending follow-up drafts for the planner.

    These are AI-generated email drafts for unsigned contracts.
    """
    try:
        from app.services.contract_followup_service import contract_followup_service

        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )
        drafts = await contract_followup_service.get_pending_drafts(planner_id)

        return {"drafts": drafts, "count": len(drafts)}

    except Exception as e:
        logger.error(f"Failed to get follow-up drafts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve drafts")


class UpdateDraftRequest(BaseModel):
    """Request to update a follow-up draft."""

    subject: Optional[str] = Field(None, max_length=200)
    body: Optional[str] = Field(None, max_length=5000)
    status: Optional[str] = Field(None, pattern="^(pending|dismissed)$")


@client_contracts_admin_router.put("/followup-drafts/{draft_id}", tags=["Contracts"])
async def update_followup_draft(
    draft_id: str,
    update_data: UpdateDraftRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Update a follow-up draft (edit content or dismiss).
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        from app.services.contract_followup_service import contract_followup_service

        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        updates = update_data.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        draft = await contract_followup_service.update_draft(
            draft_id=draft_id, planner_id=planner_id, updates=updates
        )

        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        return {"draft": draft}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update draft: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update draft")


@client_contracts_admin_router.post(
    "/followup-drafts/{draft_id}/send", tags=["Contracts"]
)
async def send_followup_draft(
    draft_id: str, current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Send a follow-up draft as an actual email to the couple.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        from app.services.contract_followup_service import contract_followup_service

        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        success = await contract_followup_service.send_draft(
            draft_id=draft_id, planner_id=planner_id
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to send email")

        return {"message": "Follow-up email sent successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send follow-up: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send email")


# ============================================================================
# PARAMETERIZED CONTRACT ENDPOINTS
# NOTE: All /contracts/{contract_id} routes MUST come after static paths above.
# ============================================================================


@client_contracts_admin_router.get("/{contract_id}", tags=["Contracts"])
async def get_contract(
    contract_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get a specific contract by ID (admin view)."""
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        contract = await contract_service.get_contract(contract_id, planner_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        # Include scheduled payments
        payments = await contract_service.get_contract_payments(contract_id)
        contract["scheduled_payments"] = payments

        # Return contract directly (frontend expects VendorContract, not {contract: ...})
        return contract

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contract")


@client_contracts_admin_router.put("/{contract_id}/wedding-date", tags=["Contracts"])
async def update_wedding_date(
    contract_id: str,
    update_data: UpdateWeddingDateRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Update the wedding date for a contract.

    This will recalculate payment due dates for days_before_wedding triggers.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        from datetime import date

        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        wedding_date = date.fromisoformat(update_data.wedding_date)

        contract = await contract_service.update_wedding_date(
            contract_id=contract_id,
            planner_id=planner_id,
            new_wedding_date=wedding_date,
        )

        return {"message": "Wedding date updated successfully", "contract": contract}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update wedding date: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update wedding date")


@client_contracts_admin_router.post("/{contract_id}/cancel", tags=["Contracts"])
async def cancel_contract(
    contract_id: str,
    cancel_data: CancelContractRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Cancel a contract.

    This will also cancel all pending scheduled payments.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        contract = await contract_service.cancel_contract(
            contract_id=contract_id, planner_id=planner_id, reason=cancel_data.reason
        )

        return {"message": "Contract cancelled successfully", "contract": contract}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel contract")


@client_contracts_admin_router.get("/{contract_id}/payments", tags=["Contracts"])
async def get_contract_payments(
    contract_id: str,
    status: Optional[str] = Query(
        None,
        pattern="^(scheduled|processing|succeeded|failed|cancelled|paid_externally)$",
    ),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get scheduled payments for a contract."""
    try:
        # Verify ownership by getting contract first
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )
        contract = await contract_service.get_contract(contract_id, planner_id)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        payments = await contract_service.get_contract_payments(
            contract_id=contract_id, status=status
        )

        return {"payments": payments, "count": len(payments)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get payments: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payments")


@client_contracts_admin_router.post(
    "/payments/{payment_id}/mark-paid-externally", tags=["Contracts"]
)
async def mark_payment_paid_externally(
    payment_id: str,
    request_data: MarkPaidExternallyRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Mark a scheduled payment as paid externally.

    Use this when a couple pays via cash, check, bank transfer, or other
    method outside of the automated Stripe payment flow.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        payment = await contract_service.mark_payment_paid_externally(
            payment_id=payment_id,
            planner_id=planner_id,
            payment_method=request_data.payment_method,
            note=request_data.note,
        )

        return {"message": "Payment marked as paid externally", "payment": payment}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to mark payment as paid externally: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update payment")


@client_contracts_admin_router.post("/payments/{payment_id}/refund", tags=["Contracts"])
async def refund_payment(
    payment_id: str,
    request_data: RefundPaymentRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Process a refund for a succeeded payment.

    - Full refund: Don't provide amount
    - Partial refund: Provide the amount to refund

    Only succeeded payments can be refunded.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        payment = await contract_service.process_refund(
            payment_id=payment_id,
            planner_id=planner_id,
            amount=request_data.amount,
            reason=request_data.reason,
        )

        refund_type = "partial" if request_data.amount else "full"
        return {
            "message": f"Payment {refund_type} refund processed successfully",
            "payment": payment,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to process refund: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process refund")


@client_contracts_admin_router.post("/payments/{payment_id}/retry", tags=["Contracts"])
async def retry_payment(
    payment_id: str, current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Retry a failed scheduled payment.

    Immediately attempts to process the payment again using the
    saved payment method on the contract.

    Only failed payments can be retried.
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        payment = await contract_service.retry_payment(
            payment_id=payment_id, planner_id=planner_id
        )

        success = payment.get("status") == "succeeded"
        return {
            "message": (
                "Payment retry succeeded"
                if success
                else "Payment retry attempted but failed"
            ),
            "success": success,
            "payment": payment,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to retry payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retry payment")


class CancelPaymentRequest(BaseModel):
    """Request to cancel a scheduled payment."""

    reason: Optional[str] = Field(
        None, max_length=500, description="Optional cancellation reason"
    )


@client_contracts_admin_router.post("/payments/{payment_id}/cancel", tags=["Contracts"])
async def cancel_payment(
    payment_id: str,
    request_data: Optional[CancelPaymentRequest] = None,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Cancel a scheduled payment.

    Only scheduled or failed payments can be cancelled.
    Succeeded payments cannot be cancelled (use refund instead).
    """
    enforce_team_permission(current_user, "manage_contracts")
    try:
        planner_id = str(
            (current_user.user_data or {}).get("_id") or current_user.email
        )

        reason = request_data.reason if request_data else None

        payment = await contract_service.cancel_payment(
            payment_id=payment_id, planner_id=planner_id, reason=reason
        )

        return {"message": "Payment cancelled successfully", "payment": payment}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel payment")


# ============================================================================
# PUBLIC ENDPOINTS (Token-based, no authentication required)
# ============================================================================


@client_contracts_public_router.get("/contracts/{token}", tags=["Public Contracts"])
async def get_public_contract(token: str, request: Request):
    """
    View a contract by token (public, no auth required).

    Used by couples to view their contract before signing.
    Marks the contract as 'viewed' on first access.
    """
    try:
        contract = await contract_service.get_contract_by_token(token)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        # Mark as viewed
        ip_address = request.client.host if request.client else "unknown"
        await contract_service.mark_viewed(token, ip_address)

        # Refresh contract to get updated status (skip expiry check for refresh)
        updated = await contract_service.contracts.find_one({"token": token})
        if updated:
            contract = await contract_service._serialize_contract_response(updated)

        if contract is None:
            raise HTTPException(status_code=404, detail="Contract not found")

        # TODO(payment-status-rendering): The public contract page renders
        # its Payment Schedule from `package_snapshot.payment_schedule`,
        # which is frozen at send-time and has no per-row state. Post-sign
        # the couple sees the same "Due on signing" / "7 days after signing"
        # copy with no Paid/Scheduled badge and no Total/Paid/Remaining
        # summary, even though the backend has correct `scheduled_payments`
        # rows. Fix: also fetch and merge `scheduled_payments` rows by
        # contract_id into the response so the renderer can show live
        # status + actual due dates. Tracked in task #26 (verified via the
        # planner-couple package-flow verifier UI-2 checkpoint, 2026-04-27).
        # Remove sensitive planner data for public view
        public_contract = {
            "id": contract.get("id"),
            "status": contract.get("status"),
            "couple": contract.get("couple"),
            "wedding_date": contract.get("wedding_date"),
            "venue": contract.get("venue"),
            "package_snapshot": contract.get("package_snapshot"),
            "contract_title": contract.get("contract_title"),
            "contract_number": contract.get("contract_number"),
            "vendor_name": contract.get("vendor_name"),
            "total_amount": contract.get("total_amount"),
            "deposit_amount": contract.get("deposit_amount"),
            "sections": contract.get("sections", []),
            "terms_and_conditions": contract.get("terms_and_conditions"),
            "cancellation_policy": contract.get("cancellation_policy"),
            "service_date": contract.get("service_date"),
            "service_location": contract.get("service_location"),
            "sent_at": contract.get("sent_at"),
            "viewed_at": contract.get("viewed_at"),
            "signed_at": contract.get("signed_at"),
            "planner_name": contract.get("planner_name"),
            "planner_email": contract.get("planner_email"),
            "planner_phone": contract.get("planner_phone"),
            "planner_logo": contract.get("planner_logo"),
            "payment_method_last4": contract.get("payment_method_last4"),
            "payment_method_brand": contract.get("payment_method_brand"),
        }

        return {"contract": public_contract}

    except ValueError as e:
        # Token expired (C11)
        raise HTTPException(status_code=410, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get public contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contract")


@client_contracts_public_router.get(
    "/contracts/{token}/status", tags=["Public Contracts"]
)
async def get_public_contract_status(token: str):
    """
    Get contract status by token (public, no auth required).

    Lightweight endpoint to check contract status.
    """
    try:
        contract = await contract_service.get_contract_by_token(token)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        return {
            "status": contract.get("status"),
            "viewed_at": contract.get("viewed_at"),
            "signed_at": contract.get("signed_at"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contract status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve status")


@client_contracts_public_router.post(
    "/contracts/{token}/sign", tags=["Public Contracts"]
)
async def sign_contract(token: str, sign_data: SignContractRequest, request: Request):
    """
    Sign a contract (public, no auth required).

    This captures the signature and payment method, then creates
    the scheduled payments according to the package schedule.
    """
    try:
        if not sign_data.accept_terms:
            raise HTTPException(
                status_code=400, detail="You must accept the terms and conditions"
            )

        contract = await contract_service.get_contract_by_token(token)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        contract_customer_id = contract.get("stripe_customer_id")
        if (
            sign_data.stripe_customer_id
            and contract_customer_id
            and sign_data.stripe_customer_id != contract_customer_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Provided Stripe customer does not match this contract",
            )

        resolved_payment_method_id = sign_data.stripe_payment_method_id
        resolved_payment_method_last4 = sign_data.payment_method_last4
        resolved_payment_method_brand = sign_data.payment_method_brand
        resolved_customer_id = contract_customer_id or sign_data.stripe_customer_id

        if sign_data.stripe_payment_method_id and not resolved_customer_id:
            raise HTTPException(
                status_code=400,
                detail="No Stripe customer is associated with this contract",
            )

        # C7: Validate Stripe payment method if provided
        if sign_data.stripe_payment_method_id and resolved_customer_id:
            try:
                import stripe

                from app.core.settings import settings as app_settings

                stripe.api_key = app_settings.stripe_secret_key

                (
                    resolved_payment_method_id,
                    resolved_payment_method_last4,
                    resolved_payment_method_brand,
                ) = _validate_setup_intent_payment_method(
                    stripe,
                    customer_id=resolved_customer_id,
                    contract_token=token,
                    payment_method_id=sign_data.stripe_payment_method_id,
                    setup_intent_id=sign_data.setup_intent_id,
                    expected_action="contract_sign",
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Could not validate payment method for signing: {str(e)}")
                raise HTTPException(
                    status_code=400, detail="Payment method validation failed"
                )

        # Get IP and user agent
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        contract = await contract_service.sign_contract(
            token=token,
            signature_name=sign_data.signature_name,
            ip_address=ip_address,
            user_agent=user_agent,
            stripe_customer_id=resolved_customer_id,
            stripe_payment_method_id=resolved_payment_method_id,
            payment_method_last4=resolved_payment_method_last4,
            payment_method_brand=resolved_payment_method_brand,
        )

        if contract is None:
            raise HTTPException(status_code=500, detail="Failed to sign contract")

        return {
            "message": "Contract signed successfully",
            "contract": {
                "id": contract.get("id"),
                "status": contract.get("status"),
                "signed_at": contract.get("signed_at"),
                "scheduled_payments": contract.get("scheduled_payments", []),
                "document_url": contract.get(
                    "document_url"
                ),  # C16: Include signed PDF URL
                "deposit_processed": contract.get("deposit_processed", False),
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sign contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to sign contract")


@client_contracts_public_router.get(
    "/contracts/{token}/payments", tags=["Public Contracts"]
)
async def get_public_contract_payments(token: str):
    """
    Get scheduled payments for a contract (public, no auth required).

    Used by couples to view their payment schedule.
    """
    try:
        contract = await contract_service.get_contract_by_token(token)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        contract_id = contract.get("id")
        if contract_id is None:
            raise HTTPException(
                status_code=500, detail="Contract data is missing an id"
            )

        contract_id_str: str = str(contract_id)
        payments = await contract_service.get_contract_payments(
            contract_id=contract_id_str
        )

        # Return simplified payment info for public view
        public_payments = [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "amount": p.get("amount"),
                "currency": p.get("currency"),
                "due_date": p.get("due_date"),
                "status": p.get("status"),
                "paid_at": p.get("paid_at"),
            }
            for p in payments
        ]

        return {"payments": public_payments, "count": len(public_payments)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get public payments: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payments")


@client_contracts_public_router.post(
    "/contracts/{token}/setup-intent", tags=["Public Contracts"]
)
async def create_contract_setup_intent(token: str):
    """
    Create a Stripe SetupIntent for saving payment method.

    This allows couples to save their card for future scheduled payments
    without being charged immediately.
    """
    try:
        import stripe

        from app.core.settings import settings

        if not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe is not configured")

        stripe.api_key = settings.stripe_secret_key

        # Verify contract exists and is in signable state
        contract = await contract_service.get_contract_by_token(token)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        if contract.get("status") in ["signed", "active", "completed", "cancelled"]:
            raise HTTPException(
                status_code=400,
                detail=f"Contract already in status: {contract['status']}",
            )

        # Get or create Stripe customer
        couple_email = contract.get("couple", {}).get("email")
        couple_name = _resolve_couple_display_name(contract.get("couple"))

        contract_id = contract.get("id")
        if not contract_id:
            raise HTTPException(
                status_code=500, detail="Contract data is missing an id"
            )
        contract_id_str = str(contract_id)

        # Check if customer already exists for this contract
        existing_customer_id = contract.get("stripe_customer_id")

        if existing_customer_id:
            customer_id = existing_customer_id
        else:
            # Create a new customer
            customer = stripe.Customer.create(
                email=couple_email,
                name=couple_name,
                metadata={"contract_id": contract_id_str, "contract_token": token},
            )
            customer_id = customer.id

            # Save customer ID to contract
            from app.core.database import mongo

            await mongo.db["contracts"].update_one(
                {"token": token}, {"$set": {"stripe_customer_id": customer_id}}
            )

        # Create SetupIntent
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
            metadata={
                "contract_id": contract_id_str,
                "contract_token": token,
                "action": "contract_sign",
            },
        )

        return {"client_secret": setup_intent.client_secret, "customer_id": customer_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create setup intent: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to initialize payment setup"
        )


# ============================================================================
# COUPLE PORTAL ENDPOINTS (Public, token-based)
# ============================================================================


@client_contracts_public_router.get("/portal/{token}", tags=["Couple Portal"])
async def get_portal_data(token: str):
    """
    Get complete portal data for couples.

    Returns contract info, payment schedule, and payment history.
    """
    try:
        contract = await contract_service.get_contract_by_token(token)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        # Only allow access to signed contracts
        if contract.get("status") not in ["signed", "active", "completed"]:
            raise HTTPException(
                status_code=403,
                detail="Portal access is only available for signed contracts",
            )

        contract_id = contract.get("id")
        if not contract_id:
            raise HTTPException(
                status_code=500, detail="Contract data is missing an id"
            )

        # Get all scheduled payments
        payments = await contract_service.get_contract_payments(str(contract_id))

        # Calculate summary
        total_amount = contract.get("package_snapshot", {}).get("total_amount", 0)
        paid_amount = sum(
            p.get("amount", 0) for p in payments if p.get("status") == "succeeded"
        )
        pending_amount = sum(
            p.get("amount", 0) for p in payments if p.get("status") == "scheduled"
        )
        failed_amount = sum(
            p.get("amount", 0) for p in payments if p.get("status") == "failed"
        )

        # Get next payment
        scheduled_payments = [p for p in payments if p.get("status") == "scheduled"]
        scheduled_payments.sort(key=lambda x: x.get("due_date", ""))
        next_payment = scheduled_payments[0] if scheduled_payments else None

        return {
            "contract": {
                "id": contract.get("id"),
                "status": contract.get("status"),
                "couple": contract.get("couple"),
                "wedding_date": contract.get("wedding_date"),
                "venue": contract.get("venue"),
                "package_name": contract.get("package_snapshot", {}).get("name"),
                "signed_at": contract.get("signed_at"),
                "payment_method_last4": contract.get("payment_method_last4"),
                "payment_method_brand": contract.get("payment_method_brand"),
                "planner_name": contract.get("planner_name"),
                "planner_email": contract.get("planner_email"),
                "planner_phone": contract.get("planner_phone"),
            },
            "payments": [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "amount": p.get("amount"),
                    "currency": p.get("currency", "usd"),
                    "due_date": p.get("due_date"),
                    "status": p.get("status"),
                    "paid_at": p.get("paid_at"),
                    "receipt_url": p.get("receipt_url"),
                    "failure_reason": p.get("failure_reason"),
                }
                for p in payments
            ],
            "summary": {
                "total_amount": total_amount,
                "paid_amount": paid_amount,
                "pending_amount": pending_amount,
                "failed_amount": failed_amount,
                "remaining_amount": total_amount - paid_amount,
                "payment_count": len(payments),
                "completed_count": len(
                    [p for p in payments if p.get("status") == "succeeded"]
                ),
                "next_payment": (
                    {
                        "name": next_payment.get("name"),
                        "amount": next_payment.get("amount"),
                        "due_date": next_payment.get("due_date"),
                    }
                    if next_payment
                    else None
                ),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get portal data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load portal")


@client_contracts_public_router.post(
    "/portal/{token}/update-payment-method", tags=["Couple Portal"]
)
async def update_portal_payment_method(token: str, request: Request):
    """
    Create a SetupIntent for updating the payment method.

    Returns a client_secret for Stripe Elements.
    """
    try:
        import stripe

        from app.core.settings import settings

        if not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe is not configured")

        stripe.api_key = settings.stripe_secret_key

        contract = await contract_service.get_contract_by_token(token)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        if contract.get("status") not in ["signed", "active"]:
            raise HTTPException(
                status_code=400, detail="Cannot update payment method for this contract"
            )

        customer_id = contract.get("stripe_customer_id")
        if not customer_id:
            raise HTTPException(status_code=400, detail="No payment method on file")

        contract_id = contract.get("id")
        if not contract_id:
            raise HTTPException(
                status_code=500, detail="Contract data is missing an id"
            )
        contract_id_str = str(contract_id)

        # Create SetupIntent for updating payment method
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            automatic_payment_methods={"enabled": True},
            metadata={
                "contract_id": contract_id_str,
                "contract_token": token,
                "action": "update_payment_method",
            },
        )

        return {"client_secret": setup_intent.client_secret, "customer_id": customer_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create update intent: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to initialize payment update"
        )


class UpdatePaymentMethodRequest(BaseModel):
    """Request to confirm payment method update."""

    payment_method_id: str = Field(..., min_length=1)
    setup_intent_id: str = Field(..., min_length=1)
    payment_method_last4: Optional[str] = Field(None, max_length=4)
    payment_method_brand: Optional[str] = Field(None, max_length=20)


@client_contracts_public_router.put(
    "/portal/{token}/payment-method", tags=["Couple Portal"]
)
async def confirm_payment_method_update(
    token: str, update_data: UpdatePaymentMethodRequest
):
    """
    Confirm payment method update after Stripe SetupIntent completes.

    Updates the contract with the new payment method and sets it as
    the default for the customer.
    """
    try:
        from datetime import datetime

        import stripe

        from app.core.database import mongo
        from app.core.settings import settings

        if not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe is not configured")

        stripe.api_key = settings.stripe_secret_key

        contract = await contract_service.get_contract_by_token(token)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        customer_id = contract.get("stripe_customer_id")
        if not customer_id:
            raise HTTPException(status_code=400, detail="No customer on file")

        (
            resolved_payment_method_id,
            payment_method_last4,
            payment_method_brand,
        ) = _validate_setup_intent_payment_method(
            stripe,
            customer_id=customer_id,
            contract_token=token,
            payment_method_id=update_data.payment_method_id,
            setup_intent_id=update_data.setup_intent_id,
            expected_action="update_payment_method",
        )

        # Set as default payment method
        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": resolved_payment_method_id},
        )

        # Update contract with new payment method
        await mongo.db["contracts"].update_one(
            {"token": token},
            {
                "$set": {
                    "stripe_payment_method_id": resolved_payment_method_id,
                    "payment_method_last4": payment_method_last4,
                    "payment_method_brand": payment_method_brand,
                    "payment_method_updated_at": datetime.now(timezone.utc),
                }
            },
        )

        # Notify planner about the update
        try:
            import resend

            resend.api_key = settings.resend_api_key

            planner_email = contract.get("planner_email")
            couple_name = _resolve_couple_display_name(contract.get("couple"))

            if planner_email:
                resend.Emails.send(
                    {
                        "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                        "to": [planner_email],
                        "subject": f"Payment Method Updated - {couple_name}",
                        "html": f"""
                    <h2>Payment Method Updated</h2>
                    <p><strong>{couple_name}</strong> has updated their payment method.</p>
                    <p>New card: {payment_method_brand or "Card"} ending in {payment_method_last4 or "****"}</p>
                    """,
                    }
                )
        except Exception as email_err:
            logger.warning(f"Failed to send planner notification: {email_err}")

        return {
            "message": "Payment method updated successfully",
            "payment_method": {
                "last4": payment_method_last4,
                "brand": payment_method_brand,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update payment method: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update payment method")


# ============================================================================
# CRON JOB ENDPOINT (Internal use)
# ============================================================================


@client_contracts_cron_router.post("/process-followups", tags=["Cron"])
async def process_contract_followups(
    request: Request, days_threshold: int = Query(default=3, ge=1, le=14)
):
    """
    Cron job endpoint to process unsigned contracts and generate follow-up drafts.

    Should be called daily by a cron scheduler (e.g., Vercel Cron).
    Protected by checking for Vercel cron header or API key.
    """
    try:
        # Verify this is a legitimate cron request
        # Check for Vercel cron header or internal API key
        auth_header = request.headers.get("Authorization", "")
        cron_header = request.headers.get("x-vercel-cron", "")

        if not cron_header and not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")

        from app.services.contract_followup_service import contract_followup_service

        results = await contract_followup_service.process_stale_contracts(
            days_threshold=days_threshold
        )

        return {"status": "success", "results": results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cron job failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Cron job failed")


__all__ = [
    "client_contracts_admin_router",
    "client_contracts_public_router",
    "client_contracts_cron_router",
]
