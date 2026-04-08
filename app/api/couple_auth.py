"""
Couple Authentication API Routes

Handles couple invitation, password setup, login, and password reset.
Couples are invited by planners via magic link email.

Sprint 1: Setup, login, verify, profile
Sprint 3: Forgot password, password reset
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
from app.core.database import mongo
from app.utils.auth_utils import (
    DUMMY_PASSWORD_HASH,
    clear_auth_cookie,
    create_access_token,
    get_password_hash,
    set_auth_cookie,
    verify_password,
)
from app.dependencies.couple_auth import require_couple_auth
from app.services.couple_lifecycle_service import (
    COUPLE_PORTAL_STATE_ARCHIVED,
    COUPLE_PORTAL_STATE_PENDING_SETUP,
    couple_lifecycle_service,
)
from app.utils.planner_ownership import (
    normalize_wedding_query_id,
    resolve_wedding_owner_identity,
)
import secrets
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
COUPLE_ACCESS_TOKEN_MAX_AGE = 24 * 60 * 60


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class CoupleSetupPasswordRequest(BaseModel):
    """Couple sets their password after receiving magic link."""

    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=128)


class CoupleLoginRequest(BaseModel):
    """Couple login."""

    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class CoupleForgotPasswordRequest(BaseModel):
    """Request a password reset link."""

    email: str = Field(..., max_length=254)


class CoupleResetPasswordRequest(BaseModel):
    """Reset password using a token."""

    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=128)


class CoupleOnboardingUpdateRequest(BaseModel):
    """Update persisted onboarding completion for the couple portal."""

    completed: bool = Field(..., description="Whether onboarding has been completed")
    steps_completed: Optional[list[str]] = Field(
        None, description="Completed onboarding step identifiers"
    )


def _serialize_onboarding_fields(couple: dict) -> dict:
    return {
        "onboarding_completed": couple.get("onboarding_completed", False),
        "onboarding_completed_at": (
            couple.get("onboarding_completed_at").isoformat()
            if couple.get("onboarding_completed_at")
            else None
        ),
        "onboarding_steps_completed": couple.get("onboarding_steps_completed", []),
    }


def _serialize_couple_payload(couple: dict) -> dict:
    return {
        "email": couple["email"],
        "partner1_name": couple.get("partner1_name"),
        "partner2_name": couple.get("partner2_name"),
        "wedding_id": couple.get("wedding_id"),
        **_serialize_onboarding_fields(couple),
    }


def _set_couple_session_cookie(response: Response, email: str) -> str:
    token_data = {"sub": email, "role": "couple"}
    access_token = create_access_token(
        data=token_data, expires_delta=timedelta(hours=24)
    )
    set_auth_cookie(
        response,
        "couple_token",
        access_token,
        max_age=COUPLE_ACCESS_TOKEN_MAX_AGE,
    )
    return access_token


async def _load_wedding_for_couple(couple: dict) -> dict | None:
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        return None

    return await mongo.get_weddings_collection().find_one(
        {"_id": normalize_wedding_query_id(wedding_id)},
        {
            "assigned_planner_id": 1,
            "assigned_planner_email": 1,
            "data_access_suspended_reason": 1,
        },
    )


async def _resolve_portal_access(couple: dict) -> tuple[dict | None, dict]:
    wedding = await _load_wedding_for_couple(couple)
    access = await couple_lifecycle_service.resolve_effective_state(
        couple, wedding=wedding
    )
    return wedding, access


# ============================================================================
# PUBLIC ENDPOINTS (No auth required)
# ============================================================================


@router.post("/couple/setup-password", tags=["Couple Auth"])
async def setup_couple_password(data: CoupleSetupPasswordRequest, response: Response):
    """
    Couple sets their password using the invite token from the magic link.
    This completes the couple's account setup.
    """
    # Find the couple by invite token
    couple = await mongo.db["couple_users"].find_one(
        {
            "invite_token": data.token,
            "invite_token_expires": {"$gt": datetime.now(timezone.utc)},
        }
    )

    if not couple:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired invitation link. Please ask your planner to resend the invitation.",
        )

    _, access = await _resolve_portal_access(couple)
    if access.get("blocked"):
        raise HTTPException(status_code=403, detail=access["detail"])
    if access["state"] == COUPLE_PORTAL_STATE_ARCHIVED:
        raise HTTPException(
            status_code=403,
            detail="This wedding has already been archived. New couple portal setup is unavailable.",
        )

    # Hash password and activate account
    password_hash = get_password_hash(data.password)
    update_fields = {
        "password_hash": password_hash,
        **couple_lifecycle_service.build_setup_completed_update(),
    }

    await mongo.db["couple_users"].update_one(
        {"_id": couple["_id"]},
        {"$set": update_fields},
    )

    access_token = _set_couple_session_cookie(response, couple["email"])
    updated_couple = {**couple, **update_fields}

    logger.info(f"Couple account setup completed: {couple['email']}")

    return {
        "message": "Account setup complete! Welcome to your wedding portal.",
        "access_token": access_token,
        "token_type": "bearer",
        "couple": _serialize_couple_payload(updated_couple),
    }


@router.post("/couple/login", tags=["Couple Auth"])
async def couple_login(data: CoupleLoginRequest, response: Response):
    """
    Couple logs into their portal.
    """
    couple = await mongo.db["couple_users"].find_one(
        {"email": data.email.lower().strip()}
    )

    if not couple or not couple.get("password_hash"):
        # Timing attack mitigation: always run a hash comparison even when user not found
        verify_password("dummy_password", DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(data.password, couple["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _, access = await _resolve_portal_access(couple)
    if access["state"] == COUPLE_PORTAL_STATE_PENDING_SETUP:
        raise HTTPException(
            status_code=401,
            detail="Please complete your account setup using the invitation link from your planner.",
        )
    if access.get("blocked"):
        raise HTTPException(status_code=403, detail=access["detail"])
    if access["state"] == COUPLE_PORTAL_STATE_ARCHIVED and not couple.get(
        "setup_completed", False
    ):
        raise HTTPException(
            status_code=403,
            detail="This wedding has been archived. Couple portal login is unavailable for accounts that were never set up.",
        )

    # Update last login
    await mongo.db["couple_users"].update_one(
        {"_id": couple["_id"]}, {"$set": {"last_login": datetime.now(timezone.utc)}}
    )

    access_token = _set_couple_session_cookie(response, couple["email"])

    logger.info(f"Couple logged in: {couple['email']}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "couple": {
            "id": str(couple["_id"]),
            **_serialize_couple_payload(couple),
        },
    }


@router.get("/couple/verify-invite/{token}", tags=["Couple Auth"])
async def verify_invite_token(token: str):
    """
    Verify that an invite token is valid (used by the setup page to check before showing form).
    """
    couple = await mongo.db["couple_users"].find_one(
        {
            "invite_token": token,
            "invite_token_expires": {"$gt": datetime.now(timezone.utc)},
        }
    )

    if not couple:
        raise HTTPException(
            status_code=400, detail="Invalid or expired invitation link."
        )

    _, access = await _resolve_portal_access(couple)
    if access.get("blocked"):
        raise HTTPException(status_code=403, detail=access["detail"])
    if access["state"] == COUPLE_PORTAL_STATE_ARCHIVED:
        raise HTTPException(
            status_code=403,
            detail="This wedding has already been archived. New couple portal setup is unavailable.",
        )

    return {
        "valid": True,
        "email": couple["email"],
        "partner1_name": couple.get("partner1_name"),
        "partner2_name": couple.get("partner2_name"),
    }


@router.get("/couple/profile", tags=["Couple Auth"])
async def get_couple_profile(couple: dict = Depends(require_couple_auth)):
    """
    Get the authenticated couple's profile.
    Requires Bearer token from couple login.
    """
    from bson import ObjectId

    couple_id = (
        str(couple["_id"]) if isinstance(couple["_id"], ObjectId) else couple["_id"]
    )
    wedding = await _load_wedding_for_couple(couple)
    owner_identity = await resolve_wedding_owner_identity(wedding)

    return {
        "id": couple_id,
        "email": couple["email"],
        "partner1_name": couple.get("partner1_name"),
        "partner2_name": couple.get("partner2_name"),
        "phone": couple.get("phone"),
        "wedding_id": couple.get("wedding_id"),
        "planner_id": owner_identity.get("planner_id"),
        "is_active": couple.get("is_active", False),
        "access_state": couple.get("access_state")
        or couple_lifecycle_service.infer_stored_state(couple),
        "portal_access_state": couple.get("_portal_access_state"),
        "portal_access_detail": couple.get("_portal_access_detail"),
        "setup_completed": couple.get("setup_completed", False),
        "last_login": couple.get("last_login", "").isoformat()
        if couple.get("last_login")
        else None,
        "created_at": couple.get("created_at", "").isoformat()
        if couple.get("created_at")
        else None,
        **_serialize_onboarding_fields(couple),
    }


@router.get("/couple/profile/onboarding", tags=["Couple Auth"])
async def get_couple_onboarding_status(couple: dict = Depends(require_couple_auth)):
    """Get the current couple portal onboarding state."""
    return _serialize_onboarding_fields(couple)


@router.put("/couple/profile/onboarding", tags=["Couple Auth"])
async def update_couple_onboarding_status(
    onboarding_data: CoupleOnboardingUpdateRequest,
    couple: dict = Depends(require_couple_auth),
):
    """Persist couple portal onboarding completion and visited steps."""
    update_data = {
        "onboarding_completed": onboarding_data.completed,
        "updated_at": datetime.now(timezone.utc),
    }

    if onboarding_data.completed:
        update_data["onboarding_completed_at"] = datetime.now(timezone.utc)

    if onboarding_data.steps_completed is not None:
        update_data["onboarding_steps_completed"] = onboarding_data.steps_completed

    await mongo.db["couple_users"].update_one(
        {"_id": couple["_id"]}, {"$set": update_data}
    )

    return {
        "message": "Couple onboarding status updated",
        "onboarding_completed": onboarding_data.completed,
        "onboarding_steps_completed": onboarding_data.steps_completed or [],
    }


# ============================================================================
# SPRINT 3: PASSWORD RESET FLOW
# Mirrors planner password reset from user_management_service.py.
# Uses couple_users collection fields: password_reset_token, password_reset_expires.
# ============================================================================


@router.post("/couple/forgot-password", tags=["Couple Auth"])
async def couple_forgot_password(data: CoupleForgotPasswordRequest):
    """
    Request a password reset link. Sends email if account exists.
    Always returns the same message to prevent email enumeration.
    """
    # Consistent response to prevent email enumeration (mirrors planner pattern)
    success_message = {
        "message": "If an account with this email exists, you will receive a password reset link shortly."
    }

    email = data.email.lower().strip()
    couple = await mongo.db["couple_users"].find_one({"email": email})

    if not couple:
        return success_message

    if not couple.get("setup_completed", False):
        # Account not set up yet — shouldn't reset password
        return success_message

    _, access = await _resolve_portal_access(couple)
    if access.get("blocked"):
        return success_message
    if access["state"] == COUPLE_PORTAL_STATE_ARCHIVED and not couple.get(
        "setup_completed", False
    ):
        return success_message

    # Generate reset token (mirrors planner pattern: 32 hex chars, 1-hour expiry)
    reset_token = secrets.token_hex(32)
    reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)

    await mongo.db["couple_users"].update_one(
        {"_id": couple["_id"]},
        {
            "$set": {
                "password_reset_token": reset_token,
                "password_reset_expires": reset_expires,
                "password_reset_requested_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    # Send reset email via email_service (reuses existing Resend service)
    try:
        from app.core.settings import settings
        from app.services.email_service_resend import ResendEmailService

        email_service = ResendEmailService()

        frontend_url = (
            getattr(settings, "frontend_url", None) or "https://thespecialwedding.io"
        )
        normalized_frontend_url = frontend_url.rstrip("/")
        reset_link = f"{normalized_frontend_url}/couple/reset-password/{reset_token}"

        couple_name = couple.get("partner1_name", "")
        if couple.get("partner2_name"):
            couple_name = f"{couple['partner1_name']} & {couple['partner2_name']}"

        html_content = f"""
        <div style="font-family: 'Georgia', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #1e3a5f; font-size: 28px; margin-bottom: 8px;">Reset Your Password</h1>
                <p style="color: #d4af37; font-size: 16px; letter-spacing: 2px;">THE SPECIAL WEDDING</p>
            </div>

            <p style="color: #333; font-size: 16px; line-height: 1.6;">
                Dear {couple_name or "there"},
            </p>

            <p style="color: #333; font-size: 16px; line-height: 1.6;">
                We received a request to reset your wedding portal password.
                Click the button below to set a new password.
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}"
                   style="background-color: #1e3a5f; color: white; padding: 14px 32px;
                          text-decoration: none; border-radius: 6px; font-size: 16px;
                          display: inline-block;">
                    Reset Password
                </a>
            </div>

            <p style="color: #666; font-size: 14px; line-height: 1.6;">
                This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
            </p>

            <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;" />

            <p style="color: #999; font-size: 12px; text-align: center;">
                If you're having trouble with the button, copy and paste this URL into your browser:<br/>
                <span style="color: #1e3a5f;">{reset_link}</span>
            </p>
        </div>
        """

        await email_service.send_email(
            to_email=email,
            subject="Reset Your Wedding Portal Password",
            html_content=html_content,
        )
    except Exception as e:
        logger.error(f"Failed to send couple password reset email: {e}")

    return success_message


@router.get("/couple/reset-password/validate/{token}", tags=["Couple Auth"])
async def validate_couple_reset_token(token: str):
    """
    Validate a password reset token without consuming it.
    Used by the frontend to check if the token is valid before showing the form.
    """
    couple = await mongo.db["couple_users"].find_one(
        {
            "password_reset_token": token,
        }
    )

    if not couple:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    if couple.get("password_reset_expires") and couple[
        "password_reset_expires"
    ] < datetime.now(timezone.utc):
        # Clean up expired token
        await mongo.db["couple_users"].update_one(
            {"_id": couple["_id"]},
            {
                "$unset": {
                    "password_reset_token": "",
                    "password_reset_expires": "",
                    "password_reset_requested_at": "",
                }
            },
        )
        raise HTTPException(
            status_code=400,
            detail="Password reset token has expired. Please request a new one.",
        )

    _, access = await _resolve_portal_access(couple)
    if access.get("blocked"):
        raise HTTPException(status_code=403, detail=access["detail"])
    if access["state"] == COUPLE_PORTAL_STATE_ARCHIVED and not couple.get(
        "setup_completed", False
    ):
        raise HTTPException(
            status_code=403,
            detail="This wedding has been archived. Password reset is unavailable for accounts that were never set up.",
        )

    # Mask email for privacy (mirrors planner pattern)
    email = couple["email"]
    email_parts = email.split("@")
    if len(email_parts[0]) > 2:
        masked_email = email_parts[0][:2] + "***@" + email_parts[1]
    else:
        masked_email = email_parts[0][0] + "***@" + email_parts[1]

    return {
        "valid": True,
        "email": masked_email,
        "partner1_name": couple.get("partner1_name"),
    }


@router.post("/couple/reset-password", tags=["Couple Auth"])
async def couple_reset_password(data: CoupleResetPasswordRequest, response: Response):
    """
    Reset the couple's password using a valid reset token.
    Uses atomic compare-and-swap to consume the token in a single operation,
    preventing reuse and race conditions.
    """
    couple = await mongo.db["couple_users"].find_one(
        {"password_reset_token": data.token}
    )
    if not couple:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token. Please request a new one.",
        )

    if couple.get("password_reset_expires") and couple[
        "password_reset_expires"
    ] < datetime.now(timezone.utc):
        await mongo.db["couple_users"].update_one(
            {"_id": couple["_id"]},
            {
                "$unset": {
                    "password_reset_token": "",
                    "password_reset_expires": "",
                    "password_reset_requested_at": "",
                }
            },
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token. Please request a new one.",
        )

    _, access = await _resolve_portal_access(couple)
    if access.get("blocked"):
        raise HTTPException(status_code=403, detail=access["detail"])
    if access["state"] == COUPLE_PORTAL_STATE_ARCHIVED and not couple.get(
        "setup_completed", False
    ):
        raise HTTPException(
            status_code=403,
            detail="This wedding has been archived. Password reset is unavailable for accounts that were never set up.",
        )

    # Hash new password before the atomic update
    password_hash = get_password_hash(data.password)

    # Atomic: find by token + not expired + consume in one operation
    result = await mongo.db["couple_users"].find_one_and_update(
        {
            "password_reset_token": data.token,
            "password_reset_expires": {"$gt": datetime.now(timezone.utc)},
        },
        {
            "$set": {
                "password_hash": password_hash,
                "updated_at": datetime.now(timezone.utc),
            },
            "$unset": {
                "password_reset_token": True,
                "password_reset_expires": True,
                "password_reset_requested_at": True,
            },
        },
        return_document=False,  # return pre-update doc for couple data
    )

    if not result:
        # Could be invalid token or expired — generic message for security
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token. Please request a new one.",
        )

    couple = result

    access_token = _set_couple_session_cookie(response, couple["email"])

    logger.info(f"Couple password reset completed: {couple['email']}")

    return {
        "message": "Password reset successfully. You are now logged in.",
        "access_token": access_token,
        "token_type": "bearer",
        "couple": _serialize_couple_payload(couple),
    }


@router.post("/couple/logout", tags=["Couple Auth"])
async def couple_logout(response: Response):
    """Clear the authenticated couple session cookie."""
    clear_auth_cookie(response, "couple_token")
    return {"success": True}
