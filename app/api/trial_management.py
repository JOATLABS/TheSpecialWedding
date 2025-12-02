from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.services.trial_expiration_service import TrialExpirationService

router = APIRouter()
trial_service = TrialExpirationService()

@router.post("/trials/check-expired", tags=["ROOT_ADMIN"])
def check_expired_trials(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Check for expired trials and deactivate accounts - ROOT_ADMIN only"""
    return trial_service.check_and_expire_trials()

@router.post("/trials/send-warnings", tags=["ROOT_ADMIN"])
def send_trial_warnings(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Send warning emails for trials expiring soon - ROOT_ADMIN only"""
    return trial_service.send_trial_warning_emails()

@router.post("/trials/run-maintenance", tags=["ROOT_ADMIN"])
def run_trial_maintenance(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Run complete trial maintenance (warnings and expiration) - ROOT_ADMIN only"""
    try:
        # Send warnings first
        warning_result = trial_service.send_trial_warning_emails()

        # Then check for expired trials
        expiration_result = trial_service.check_and_expire_trials()

        return {
            "message": "Trial maintenance completed successfully",
            "warning_results": warning_result,
            "expiration_results": expiration_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running trial maintenance: {str(e)}")

@router.get("/trials/status", tags=["ROOT_ADMIN"])
async def get_trial_status(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get overview of trial statuses - ROOT_ADMIN only"""
    try:
        from app.core.database import mongo
        from datetime import datetime, timedelta

        users_collection = mongo.db["users"]
        now = datetime.utcnow()

        # Count trials by status
        active_trials = await users_collection.count_documents({
            "subscription_status": "trial",
            "is_active": True,
            "email_verified": True
        })

        expired_trials = await users_collection.count_documents({
            "subscription_status": "expired"
        })

        # Trials expiring in next 7 days
        expiring_soon = await users_collection.count_documents({
            "subscription_status": "trial",
            "trial_end_date": {"$lte": now + timedelta(days=7), "$gt": now},
            "is_active": True
        })
        # Trials expiring today
        expiring_today = await users_collection.count_documents({
            "subscription_status": "trial",
            "trial_end_date": {"$lte": now + timedelta(days=1), "$gt": now},
            "is_active": True
        })
        return {
            "active_trials": active_trials,
            "expired_trials": expired_trials,
            "expiring_soon": expiring_soon,
            "expiring_today": expiring_today,
            "checked_at": now.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting trial status: {str(e)}")