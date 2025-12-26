"""
Contract API Routes

Includes both admin endpoints (authenticated) and public endpoints (token-based).
Public endpoints allow couples to view and sign contracts without authentication.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import Optional
from pydantic import BaseModel, Field
from app.services.contract_service import contract_service
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    require_admin_or_planner,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# REQUEST MODELS
# ============================================================================

class SignContractRequest(BaseModel):
    """Request to sign a contract."""
    signature_name: str = Field(..., min_length=1, max_length=200)
    stripe_customer_id: str = Field(..., min_length=1)
    stripe_payment_method_id: str = Field(..., min_length=1)
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
    payment_method: Optional[str] = Field(None, max_length=50, description="How payment was received: cash, check, wire, etc.")
    note: Optional[str] = Field(None, max_length=500, description="Optional note about the payment")


class RefundPaymentRequest(BaseModel):
    """Request to refund a payment."""
    amount: Optional[float] = Field(None, gt=0, description="Refund amount (partial). If not provided, full refund.")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for refund")


# ============================================================================
# ADMIN ENDPOINTS (Authenticated)
# ============================================================================

@router.get("/contracts", tags=["Contracts"])
async def list_contracts(
    status: Optional[str] = Query(
        None,
        pattern="^(draft|sent|viewed|signed|active|completed|cancelled)$"
    ),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    List all contracts for the authenticated planner.

    - **status**: Filter by contract status
    """
    try:
        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        contracts = await contract_service.list_contracts(
            planner_id=planner_id,
            status=status,
            limit=limit,
            skip=skip
        )

        return {
            "contracts": contracts,
            "count": len(contracts)
        }

    except Exception as e:
        logger.error(f"Failed to list contracts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contracts")


@router.get("/contracts/stats", tags=["Contracts"])
async def get_contract_stats(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get contract statistics for the planner."""
    try:
        planner_id = str(current_user.user_data.get("_id") or current_user.email)
        stats = await contract_service.get_contract_stats(planner_id)
        return stats

    except Exception as e:
        logger.error(f"Failed to get contract stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/contracts/{contract_id}", tags=["Contracts"])
async def get_contract(
    contract_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get a specific contract by ID (admin view)."""
    try:
        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        contract = await contract_service.get_contract(contract_id, planner_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        # Include scheduled payments
        payments = await contract_service.get_contract_payments(contract_id)
        contract["scheduled_payments"] = payments

        return {"contract": contract}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contract")


@router.put("/contracts/{contract_id}/wedding-date", tags=["Contracts"])
async def update_wedding_date(
    contract_id: str,
    update_data: UpdateWeddingDateRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Update the wedding date for a contract.

    This will recalculate payment due dates for days_before_wedding triggers.
    """
    try:
        from datetime import date
        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        wedding_date = date.fromisoformat(update_data.wedding_date)

        contract = await contract_service.update_wedding_date(
            contract_id=contract_id,
            planner_id=planner_id,
            new_wedding_date=wedding_date
        )

        return {
            "message": "Wedding date updated successfully",
            "contract": contract
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update wedding date: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update wedding date")


@router.post("/contracts/{contract_id}/cancel", tags=["Contracts"])
async def cancel_contract(
    contract_id: str,
    cancel_data: CancelContractRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Cancel a contract.

    This will also cancel all pending scheduled payments.
    """
    try:
        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        contract = await contract_service.cancel_contract(
            contract_id=contract_id,
            planner_id=planner_id,
            reason=cancel_data.reason
        )

        return {
            "message": "Contract cancelled successfully",
            "contract": contract
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel contract")


@router.get("/contracts/{contract_id}/payments", tags=["Contracts"])
async def get_contract_payments(
    contract_id: str,
    status: Optional[str] = Query(
        None,
        pattern="^(scheduled|processing|succeeded|failed|cancelled|paid_externally)$"
    ),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get scheduled payments for a contract."""
    try:
        # Verify ownership by getting contract first
        planner_id = str(current_user.user_data.get("_id") or current_user.email)
        contract = await contract_service.get_contract(contract_id, planner_id)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        payments = await contract_service.get_contract_payments(
            contract_id=contract_id,
            status=status
        )

        return {
            "payments": payments,
            "count": len(payments)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get payments: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payments")


@router.post("/payments/{payment_id}/mark-paid-externally", tags=["Contracts"])
async def mark_payment_paid_externally(
    payment_id: str,
    request_data: MarkPaidExternallyRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Mark a scheduled payment as paid externally.

    Use this when a couple pays via cash, check, bank transfer, or other
    method outside of the automated Stripe payment flow.
    """
    try:
        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        payment = await contract_service.mark_payment_paid_externally(
            payment_id=payment_id,
            planner_id=planner_id,
            payment_method=request_data.payment_method,
            note=request_data.note
        )

        return {
            "message": "Payment marked as paid externally",
            "payment": payment
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to mark payment as paid externally: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update payment")


@router.post("/payments/{payment_id}/refund", tags=["Contracts"])
async def refund_payment(
    payment_id: str,
    request_data: RefundPaymentRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Process a refund for a succeeded payment.

    - Full refund: Don't provide amount
    - Partial refund: Provide the amount to refund

    Only succeeded payments can be refunded.
    """
    try:
        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        payment = await contract_service.process_refund(
            payment_id=payment_id,
            planner_id=planner_id,
            amount=request_data.amount,
            reason=request_data.reason
        )

        refund_type = "partial" if request_data.amount else "full"
        return {
            "message": f"Payment {refund_type} refund processed successfully",
            "payment": payment
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to process refund: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process refund")


@router.post("/payments/{payment_id}/retry", tags=["Contracts"])
async def retry_payment(
    payment_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Retry a failed scheduled payment.

    Immediately attempts to process the payment again using the
    saved payment method on the contract.

    Only failed payments can be retried.
    """
    try:
        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        payment = await contract_service.retry_payment(
            payment_id=payment_id,
            planner_id=planner_id
        )

        success = payment.get("status") == "succeeded"
        return {
            "message": "Payment retry succeeded" if success else "Payment retry attempted but failed",
            "success": success,
            "payment": payment
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to retry payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retry payment")


class CancelPaymentRequest(BaseModel):
    """Request to cancel a scheduled payment."""
    reason: Optional[str] = Field(None, max_length=500, description="Optional cancellation reason")


@router.post("/payments/{payment_id}/cancel", tags=["Contracts"])
async def cancel_payment(
    payment_id: str,
    request_data: CancelPaymentRequest = None,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Cancel a scheduled payment.

    Only scheduled or failed payments can be cancelled.
    Succeeded payments cannot be cancelled (use refund instead).
    """
    try:
        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        reason = request_data.reason if request_data else None

        payment = await contract_service.cancel_payment(
            payment_id=payment_id,
            planner_id=planner_id,
            reason=reason
        )

        return {
            "message": "Payment cancelled successfully",
            "payment": payment
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel payment")


# ============================================================================
# PUBLIC ENDPOINTS (Token-based, no authentication required)
# ============================================================================

@router.get("/public/contracts/{token}", tags=["Public Contracts"])
async def get_public_contract(
    token: str,
    request: Request
):
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

        # Refresh contract to get updated status
        contract = await contract_service.get_contract_by_token(token)

        if contract is None:
            raise HTTPException(status_code=404, detail="Contract not found")

        # Remove sensitive planner data for public view
        public_contract = {
            "id": contract.get("id"),
            "status": contract.get("status"),
            "couple": contract.get("couple"),
            "wedding_date": contract.get("wedding_date"),
            "venue": contract.get("venue"),
            "package_snapshot": contract.get("package_snapshot"),
            "sent_at": contract.get("sent_at"),
            "viewed_at": contract.get("viewed_at"),
            "signed_at": contract.get("signed_at"),
            "payment_method_last4": contract.get("payment_method_last4"),
            "payment_method_brand": contract.get("payment_method_brand")
        }

        return {"contract": public_contract}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get public contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contract")


@router.get("/public/contracts/{token}/status", tags=["Public Contracts"])
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
            "signed_at": contract.get("signed_at")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contract status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve status")


@router.post("/public/contracts/{token}/sign", tags=["Public Contracts"])
async def sign_contract(
    token: str,
    sign_data: SignContractRequest,
    request: Request
):
    """
    Sign a contract (public, no auth required).

    This captures the signature and payment method, then creates
    the scheduled payments according to the package schedule.
    """
    try:
        if not sign_data.accept_terms:
            raise HTTPException(
                status_code=400,
                detail="You must accept the terms and conditions"
            )

        # Get IP and user agent
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        contract = await contract_service.sign_contract(
            token=token,
            signature_name=sign_data.signature_name,
            ip_address=ip_address,
            user_agent=user_agent,
            stripe_customer_id=sign_data.stripe_customer_id,
            stripe_payment_method_id=sign_data.stripe_payment_method_id,
            payment_method_last4=sign_data.payment_method_last4,
            payment_method_brand=sign_data.payment_method_brand
        )

        if contract is None:
            raise HTTPException(status_code=500, detail="Failed to sign contract")

        return {
            "message": "Contract signed successfully",
            "contract": {
                "id": contract.get("id"),
                "status": contract.get("status"),
                "signed_at": contract.get("signed_at"),
                "scheduled_payments": contract.get("scheduled_payments", [])
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sign contract: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to sign contract")


@router.get("/public/contracts/{token}/payments", tags=["Public Contracts"])
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
            raise HTTPException(status_code=500, detail="Contract data is missing an id")

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
                "paid_at": p.get("paid_at")
            }
            for p in payments
        ]

        return {
            "payments": public_payments,
            "count": len(public_payments)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get public payments: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payments")


@router.post("/public/contracts/{token}/setup-intent", tags=["Public Contracts"])
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
                detail=f"Contract already in status: {contract['status']}"
            )

        # Get or create Stripe customer
        couple_email = contract.get("couple", {}).get("email")
        couple_name = contract.get("couple", {}).get("name")

        contract_id = contract.get("id")
        if not contract_id:
            raise HTTPException(status_code=500, detail="Contract data is missing an id")
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
                metadata={
                    "contract_id": contract_id_str,
                    "contract_token": token
                }
            )
            customer_id = customer.id

            # Save customer ID to contract
            from app.core.database import mongo

            await mongo.db["contracts"].update_one(
                {"token": token},
                {"$set": {"stripe_customer_id": customer_id}}
            )

        # Create SetupIntent
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
            metadata={
                "contract_id": contract_id_str,
                "contract_token": token
            }
        )

        return {
            "client_secret": setup_intent.client_secret,
            "customer_id": customer_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create setup intent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize payment setup")


@router.get("/public/payment-method/{payment_method_id}", tags=["Public Contracts"])
async def get_payment_method_details(payment_method_id: str):
    """
    Get payment method details (public endpoint for contract signing).

    Returns card brand and last 4 digits for display.
    """
    try:
        import stripe
        from app.core.settings import settings

        if not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe is not configured")

        stripe.api_key = settings.stripe_secret_key

        pm = stripe.PaymentMethod.retrieve(payment_method_id)

        return {
            "id": pm.id,
            "type": pm.type,
            "card": {
                "brand": pm.card.brand if pm.card else None,
                "last4": pm.card.last4 if pm.card else None,
                "exp_month": pm.card.exp_month if pm.card else None,
                "exp_year": pm.card.exp_year if pm.card else None
            } if pm.type == "card" else None
        }

    except Exception as e:
        logger.error(f"Failed to get payment method: {str(e)}")
        raise HTTPException(status_code=404, detail="Payment method not found")


# ============================================================================
# FOLLOW-UP DRAFT ENDPOINTS (Authenticated)
# ============================================================================

@router.get("/contracts/followup-drafts", tags=["Contracts"])
async def get_followup_drafts(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get all pending follow-up drafts for the planner.

    These are AI-generated email drafts for unsigned contracts.
    """
    try:
        from app.services.contract_followup_service import contract_followup_service

        planner_id = str(current_user.user_data.get("_id") or current_user.email)
        drafts = await contract_followup_service.get_pending_drafts(planner_id)

        return {
            "drafts": drafts,
            "count": len(drafts)
        }

    except Exception as e:
        logger.error(f"Failed to get follow-up drafts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve drafts")


class UpdateDraftRequest(BaseModel):
    """Request to update a follow-up draft."""
    subject: Optional[str] = Field(None, max_length=200)
    body: Optional[str] = Field(None, max_length=5000)
    status: Optional[str] = Field(None, pattern="^(pending|dismissed)$")


@router.put("/contracts/followup-drafts/{draft_id}", tags=["Contracts"])
async def update_followup_draft(
    draft_id: str,
    update_data: UpdateDraftRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Update a follow-up draft (edit content or dismiss).
    """
    try:
        from app.services.contract_followup_service import contract_followup_service

        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        updates = update_data.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        draft = await contract_followup_service.update_draft(
            draft_id=draft_id,
            planner_id=planner_id,
            updates=updates
        )

        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        return {"draft": draft}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update draft: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update draft")


@router.post("/contracts/followup-drafts/{draft_id}/send", tags=["Contracts"])
async def send_followup_draft(
    draft_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Send a follow-up draft as an actual email to the couple.
    """
    try:
        from app.services.contract_followup_service import contract_followup_service

        planner_id = str(current_user.user_data.get("_id") or current_user.email)

        success = await contract_followup_service.send_draft(
            draft_id=draft_id,
            planner_id=planner_id
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
# COUPLE PORTAL ENDPOINTS (Public, token-based)
# ============================================================================

@router.get("/public/portal/{token}", tags=["Couple Portal"])
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
                detail="Portal access is only available for signed contracts"
            )

        contract_id = contract.get("id")
        if not contract_id:
            raise HTTPException(status_code=500, detail="Contract data is missing an id")

        # Get all scheduled payments
        payments = await contract_service.get_contract_payments(str(contract_id))

        # Calculate summary
        total_amount = contract.get("package_snapshot", {}).get("total_amount", 0)
        paid_amount = sum(p.get("amount", 0) for p in payments if p.get("status") == "succeeded")
        pending_amount = sum(p.get("amount", 0) for p in payments if p.get("status") == "scheduled")
        failed_amount = sum(p.get("amount", 0) for p in payments if p.get("status") == "failed")

        # Get next payment
        scheduled_payments = [
            p for p in payments
            if p.get("status") == "scheduled"
        ]
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
                "planner_phone": contract.get("planner_phone")
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
                    "failure_reason": p.get("failure_reason")
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
                "completed_count": len([p for p in payments if p.get("status") == "succeeded"]),
                "next_payment": {
                    "name": next_payment.get("name"),
                    "amount": next_payment.get("amount"),
                    "due_date": next_payment.get("due_date")
                } if next_payment else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get portal data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load portal")


@router.post("/public/portal/{token}/update-payment-method", tags=["Couple Portal"])
async def update_portal_payment_method(
    token: str,
    request: Request
):
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
                status_code=400,
                detail="Cannot update payment method for this contract"
            )

        customer_id = contract.get("stripe_customer_id")
        if not customer_id:
            raise HTTPException(
                status_code=400,
                detail="No payment method on file"
            )

        contract_id = contract.get("id")
        if not contract_id:
            raise HTTPException(status_code=500, detail="Contract data is missing an id")
        contract_id_str = str(contract_id)

        # Create SetupIntent for updating payment method
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
            metadata={
                "contract_id": contract_id_str,
                "action": "update_payment_method"
            }
        )

        return {
            "client_secret": setup_intent.client_secret,
            "customer_id": customer_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create update intent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize payment update")


class UpdatePaymentMethodRequest(BaseModel):
    """Request to confirm payment method update."""
    payment_method_id: str = Field(..., min_length=1)
    payment_method_last4: Optional[str] = Field(None, max_length=4)
    payment_method_brand: Optional[str] = Field(None, max_length=20)


@router.put("/public/portal/{token}/payment-method", tags=["Couple Portal"])
async def confirm_payment_method_update(
    token: str,
    update_data: UpdatePaymentMethodRequest
):
    """
    Confirm payment method update after Stripe SetupIntent completes.

    Updates the contract with the new payment method and sets it as
    the default for the customer.
    """
    try:
        import stripe
        from app.core.settings import settings
        from app.core.database import mongo
        from datetime import datetime

        if not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe is not configured")

        stripe.api_key = settings.stripe_secret_key

        contract = await contract_service.get_contract_by_token(token)

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        customer_id = contract.get("stripe_customer_id")
        if not customer_id:
            raise HTTPException(status_code=400, detail="No customer on file")

        # Attach the new payment method to the customer
        stripe.PaymentMethod.attach(
            update_data.payment_method_id,
            customer=customer_id
        )

        # Set as default payment method
        stripe.Customer.modify(
            customer_id,
            invoice_settings={
                "default_payment_method": update_data.payment_method_id
            }
        )

        # Update contract with new payment method
        await mongo.db["contracts"].update_one(
            {"token": token},
            {
                "$set": {
                    "stripe_payment_method_id": update_data.payment_method_id,
                    "payment_method_last4": update_data.payment_method_last4,
                    "payment_method_brand": update_data.payment_method_brand,
                    "payment_method_updated_at": datetime.utcnow()
                }
            }
        )

        # Notify planner about the update
        try:
            import resend
            resend.api_key = settings.resend_api_key

            planner_email = contract.get("planner_email")
            couple_name = contract.get("couple", {}).get("name", "A couple")

            if planner_email:
                resend.Emails.send({
                    "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                    "to": [planner_email],
                    "subject": f"Payment Method Updated - {couple_name}",
                    "html": f"""
                    <h2>Payment Method Updated</h2>
                    <p><strong>{couple_name}</strong> has updated their payment method.</p>
                    <p>New card: {update_data.payment_method_brand or 'Card'} ending in {update_data.payment_method_last4 or '****'}</p>
                    """
                })
        except Exception as email_err:
            logger.warning(f"Failed to send planner notification: {email_err}")

        return {
            "message": "Payment method updated successfully",
            "payment_method": {
                "last4": update_data.payment_method_last4,
                "brand": update_data.payment_method_brand
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update payment method: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update payment method")


# ============================================================================
# CRON JOB ENDPOINT (Internal use)
# ============================================================================

@router.post("/cron/contracts/process-followups", tags=["Cron"])
async def process_contract_followups(
    request: Request,
    days_threshold: int = Query(default=3, ge=1, le=14)
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

        return {
            "status": "success",
            "results": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cron job failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Cron job failed")
