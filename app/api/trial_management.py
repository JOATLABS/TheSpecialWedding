import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.dependencies.auth_extended import ExtendedAuthUser, require_root_admin
from app.services.trial_expiration_service import TrialExpirationService

logger = logging.getLogger(__name__)

router = APIRouter()
trial_service = TrialExpirationService()

# Cron secret for securing internal endpoints (same as used by autopilot)
CRON_SECRET = os.getenv("CRON_SECRET", "")


def verify_cron_auth(authorization: Optional[str] = Header(None)):
    """Verify cron job authorization. Fail-closed: rejects all requests if CRON_SECRET is not set."""
    if not CRON_SECRET:
        # SECURITY: Fail closed — never allow unprotected cron access in production
        logger.error("CRON_SECRET not configured - rejecting cron request for security")
        raise HTTPException(
            status_code=503,
            detail="Cron endpoints unavailable: CRON_SECRET not configured",
        )

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")

    # Check Bearer token
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        if token == CRON_SECRET:
            return True

    raise HTTPException(status_code=401, detail="Invalid cron authorization")


@router.post("/trials/check-expired", tags=["ROOT_ADMIN"])
async def check_expired_trials(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Check for expired trials and deactivate accounts - ROOT_ADMIN only"""
    return await trial_service.check_and_expire_trials()


@router.post("/trials/send-warnings", tags=["ROOT_ADMIN"])
async def send_trial_warnings(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Send warning emails for trials expiring soon - ROOT_ADMIN only"""
    return await trial_service.send_trial_warning_emails()


@router.post("/trials/run-maintenance", tags=["ROOT_ADMIN"])
async def run_trial_maintenance(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Run complete trial maintenance (warnings and expiration) - ROOT_ADMIN only"""
    try:
        # Send warnings first
        warning_result = await trial_service.send_trial_warning_emails()

        # Then check for expired trials
        expiration_result = await trial_service.check_and_expire_trials()

        return {
            "message": "Trial maintenance completed successfully",
            "warning_results": warning_result,
            "expiration_results": expiration_result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error running trial maintenance: {str(e)}"
        )


@router.get("/trials/status", tags=["ROOT_ADMIN"])
async def get_trial_status(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get overview of trial statuses - ROOT_ADMIN only"""
    try:
        from datetime import datetime, timedelta

        from app.core.database import mongo

        users_collection = mongo.db["users"]
        now = datetime.now(timezone.utc)

        # Count trials by status
        active_trials = await users_collection.count_documents(
            {"subscription_status": "trial", "is_active": True, "email_verified": True}
        )

        expired_trials = await users_collection.count_documents(
            {"subscription_status": "expired"}
        )

        # Trials expiring in next 7 days
        expiring_soon = await users_collection.count_documents(
            {
                "subscription_status": "trial",
                "trial_end_date": {"$lte": now + timedelta(days=7), "$gt": now},
                "is_active": True,
            }
        )
        # Trials expiring today
        expiring_today = await users_collection.count_documents(
            {
                "subscription_status": "trial",
                "trial_end_date": {"$lte": now + timedelta(days=1), "$gt": now},
                "is_active": True,
            }
        )
        return {
            "active_trials": active_trials,
            "expired_trials": expired_trials,
            "expiring_soon": expiring_soon,
            "expiring_today": expiring_today,
            "checked_at": now.isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting trial status: {str(e)}"
        )


# =========================================================================
# CRON JOB ENDPOINTS (authenticated via CRON_SECRET)
# These endpoints are called by Cloudflare Workers cron triggers
# =========================================================================


@router.post("/cron/trials/run-maintenance", tags=["CRON"])
async def cron_run_trial_maintenance(_: bool = Depends(verify_cron_auth)):
    """
    Run complete trial maintenance - CRON authenticated.

    Called daily by Cloudflare Workers cron at 8:00 AM UTC.
    Sends warning emails first, then expires trials.
    """
    try:
        logger.info("Starting trial maintenance cron job")

        # Send warnings first
        warning_result = await trial_service.send_trial_warning_emails()
        logger.info(f"Trial warnings sent: {warning_result}")

        # Then check for expired trials
        expiration_result = await trial_service.check_and_expire_trials()
        logger.info(f"Trial expiration check: {expiration_result}")

        return {
            "status": "success",
            "message": "Trial maintenance completed successfully",
            "warning_results": warning_result,
            "expiration_results": expiration_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in trial maintenance cron: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/cron/trials/send-warnings", tags=["CRON"])
async def cron_send_trial_warnings(_: bool = Depends(verify_cron_auth)):
    """
    Send trial warning emails - CRON authenticated.

    Can be called separately if needed.
    """
    try:
        logger.info("Starting trial warnings cron job")
        result = await trial_service.send_trial_warning_emails()
        logger.info(f"Trial warnings result: {result}")

        return {
            "status": "success",
            "results": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in trial warnings cron: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/cron/trials/check-expired", tags=["CRON"])
async def cron_check_expired_trials(_: bool = Depends(verify_cron_auth)):
    """
    Check and expire trials - CRON authenticated.

    Can be called separately if needed.
    """
    try:
        logger.info("Starting trial expiration cron job")
        result = await trial_service.check_and_expire_trials()
        logger.info(f"Trial expiration result: {result}")

        return {
            "status": "success",
            "results": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in trial expiration cron: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
