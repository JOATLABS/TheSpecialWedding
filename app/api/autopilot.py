"""
Autopilot API Endpoints

Provides endpoints for automated payment processing:
- Process due payments
- Send payment reminders
- Retry failed payments
- Recalculate payment schedules
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import os

from app.services.autopilot_service import autopilot_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autopilot", tags=["autopilot"])

# Cron secret for securing internal endpoints
CRON_SECRET = os.getenv("CRON_SECRET", "")


def verify_cron_auth(authorization: Optional[str] = Header(None)):
    """Verify cron job authorization."""
    if not CRON_SECRET:
        # If no secret configured, allow (for development)
        logger.warning("CRON_SECRET not configured - cron endpoints are unprotected")
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")

    # Check Bearer token
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        if token == CRON_SECRET:
            return True

    raise HTTPException(status_code=401, detail="Invalid cron authorization")


# =========================================================================
# CRON JOB ENDPOINTS (WFA-502, WFA-503, WFA-504, WFA-507)
# =========================================================================

@router.post("/process-due-payments")
async def process_due_payments(
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """
    Process all scheduled payments that are due.

    Called daily by Vercel cron at 9:00 AM UTC.
    """
    try:
        logger.info("Starting process-due-payments cron job")
        results = await autopilot_service.process_due_payments()
        logger.info(f"process-due-payments completed: {results}")

        return {
            "status": "success",
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in process-due-payments: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.post("/send-payment-reminders")
async def send_payment_reminders(
    days_ahead: int = 3,
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """
    Send reminders for upcoming payments.

    Called daily by Vercel cron.
    Sends reminders for payments due in `days_ahead` days (default: 3).
    """
    try:
        logger.info(f"Starting send-payment-reminders cron job (days_ahead={days_ahead})")
        results = await autopilot_service.send_payment_reminders(days_ahead)
        logger.info(f"send-payment-reminders completed: {results}")

        return {
            "status": "success",
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in send-payment-reminders: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.post("/retry-failed-payments")
async def retry_failed_payments(
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """
    Retry failed payments that are due for retry.

    Called every 6 hours by Vercel cron.
    Uses exponential backoff: 1d, 2d, 4d, 7d between retries.
    """
    try:
        logger.info("Starting retry-failed-payments cron job")
        results = await autopilot_service.retry_failed_payments()
        logger.info(f"retry-failed-payments completed: {results}")

        return {
            "status": "success",
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in retry-failed-payments: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.post("/recalculate-schedules/{contract_id}")
async def recalculate_payment_schedules(
    contract_id: str,
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """
    Recalculate payment due dates for a contract.

    Called when wedding date changes.
    Updates all scheduled payments with days_before_wedding trigger.
    """
    try:
        logger.info(f"Starting recalculate-schedules for contract {contract_id}")
        results = await autopilot_service.recalculate_payment_schedule(contract_id)
        logger.info(f"recalculate-schedules completed: {results}")

        return {
            "status": "success",
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in recalculate-schedules: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# =========================================================================
# STATUS AND MONITORING
# =========================================================================

@router.get("/status")
async def get_autopilot_status(
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """Get autopilot status and metrics."""
    try:
        # Get counts of payments in various states
        scheduled_count = await autopilot_service.scheduled_payments.count_documents(
            {"status": "scheduled"}
        )
        failed_count = await autopilot_service.scheduled_payments.count_documents(
            {"status": "failed", "max_retries_reached": {"$ne": True}}
        )
        pending_retry_count = await autopilot_service.scheduled_payments.count_documents(
            {"status": "failed", "next_retry_at": {"$exists": True}, "max_retries_reached": {"$ne": True}}
        )
        succeeded_today = await autopilot_service.scheduled_payments.count_documents({
            "status": "succeeded",
            "paid_at": {
                "$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            }
        })

        return {
            "status": "active",
            "metrics": {
                "scheduled_payments": scheduled_count,
                "failed_pending_retry": failed_count,
                "pending_retries": pending_retry_count,
                "succeeded_today": succeeded_today
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting autopilot status: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/due-payments")
async def get_due_payments(
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """Get list of payments due today."""
    try:
        due_payments = await autopilot_service.get_due_payments()
        return {
            "status": "success",
            "count": len(due_payments),
            "payments": due_payments,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting due payments: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/upcoming-reminders")
async def get_upcoming_reminders(
    days_ahead: int = 3,
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """Get list of payments needing reminders."""
    try:
        upcoming = await autopilot_service.get_upcoming_payments(days_ahead)
        return {
            "status": "success",
            "count": len(upcoming),
            "payments": upcoming,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting upcoming reminders: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/failed-payments")
async def get_failed_payments(
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """Get list of failed payments pending retry."""
    try:
        failed = await autopilot_service.get_payments_for_retry()
        return {
            "status": "success",
            "count": len(failed),
            "payments": failed,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting failed payments: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# =========================================================================
# AI FEATURES (WFA-508, WFA-509)
# =========================================================================

@router.get("/ai/retry-timing/{payment_id}")
async def get_optimal_retry_timing(
    payment_id: str,
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """
    Get AI-suggested optimal retry timing for a failed payment.

    Uses AI to analyze:
    - Day of week patterns (payday cycles)
    - Decline reason
    - Previous payment history
    - Time since last attempt
    """
    try:
        from bson import ObjectId

        payment = await autopilot_service.scheduled_payments.find_one(
            {"_id": ObjectId(payment_id)}
        )

        if not payment:
            return {
                "status": "error",
                "error": "Payment not found",
                "timestamp": datetime.utcnow().isoformat()
            }

        result = await autopilot_service.get_optimal_retry_timing(payment)

        return {
            "status": "success",
            "payment_id": payment_id,
            "suggestion": result,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting AI retry timing: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/ai/success-prediction/{payment_id}")
async def predict_payment_success(
    payment_id: str,
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """
    Get AI prediction of payment success likelihood.

    Analyzes:
    - Card age (days since added)
    - Previous payment history
    - Card type
    - Payment amount patterns
    """
    try:
        result = await autopilot_service.get_payment_risk_assessment(payment_id)

        return {
            "status": "success" if result.get("success") else "error",
            **result,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error predicting payment success: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.post("/ai/assess-all-payments")
async def assess_all_scheduled_payments(
    _: bool = Depends(verify_cron_auth)
) -> Dict[str, Any]:
    """
    Run AI risk assessment on all scheduled payments.

    Updates each payment record with risk assessment data
    for display in the Money dashboard.
    """
    try:
        # Get all scheduled payments
        cursor = autopilot_service.scheduled_payments.find({"status": "scheduled"})
        payments = await cursor.to_list(length=100)

        assessed = 0
        errors = 0

        for payment in payments:
            try:
                await autopilot_service.get_payment_risk_assessment(str(payment["_id"]))
                assessed += 1
            except Exception:
                errors += 1

        return {
            "status": "success",
            "assessed": assessed,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error assessing payments: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
