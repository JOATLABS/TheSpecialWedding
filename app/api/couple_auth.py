"""
Couple Authentication API Routes

Handles couple invitation, password setup, login, and password reset.
Couples are invited by planners via magic link email.

Sprint 1: Setup, login, verify, profile
Sprint 3: Forgot password, password reset
"""

import html
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.core.database import mongo
from app.dependencies.couple_auth import require_couple_auth
from app.services.couple_lifecycle_service import (
    COUPLE_PORTAL_STATE_ARCHIVED,
    COUPLE_PORTAL_STATE_PENDING_SETUP,
    couple_lifecycle_service,
)
from app.utils.auth_utils import (
    DUMMY_PASSWORD_HASH,
    clear_auth_cookie,
    create_access_token,
    get_password_hash,
    set_auth_cookie,
    verify_password,
)
from app.utils.couple_identity import get_couple_record_id, normalize_couple_email
from app.utils.planner_ownership import (
    normalize_wedding_query_id,
    resolve_wedding_owner_identity,
)

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
    completed_at = couple.get("onboarding_completed_at")
    return {
        "onboarding_completed": couple.get("onboarding_completed", False),
        "onboarding_completed_at": (completed_at.isoformat() if completed_at else None),
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


def _set_couple_session_cookie(response: Response, couple: dict) -> str:
    token_data = {
        "sub": get_couple_record_id(couple),
        "role": "couple",
        "wedding_id": couple.get("wedding_id"),
    }
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


async def _list_couples_by_email(email: str) -> list[dict]:
    """Load all couple records for a normalized email address."""
    return await mongo.db["couple_users"].find({"email": email}).to_list(length=None)


def _is_archived_without_setup(couple: dict, access: dict) -> bool:
    return access["state"] == COUPLE_PORTAL_STATE_ARCHIVED and not couple.get(
        "setup_completed", False
    )


def _is_couple_portal_sign_in_allowed(couple: dict, access: dict) -> bool:
    if access.get("blocked"):
        return False
    if access["state"] == COUPLE_PORTAL_STATE_PENDING_SETUP:
        return False
    if _is_archived_without_setup(couple, access):
        return False
    return True


def _raise_couple_sign_in_error(couple: dict, access: dict) -> None:
    if access["state"] == COUPLE_PORTAL_STATE_PENDING_SETUP:
        raise HTTPException(
            status_code=401,
            detail="Please complete your account setup using the invitation link from your planner.",
        )
    if access.get("blocked"):
        raise HTTPException(status_code=403, detail=access["detail"])
    if _is_archived_without_setup(couple, access):
        raise HTTPException(
            status_code=403,
            detail="This wedding has been archived. Couple portal login is unavailable for accounts that were never set up.",
        )


async def _select_login_candidate(
    email: str, password: str
) -> tuple[dict, dict | None]:
    """
    Select the couple account to authenticate for a login attempt.

    Couple emails are not globally unique in the current schema, so a single
    email may map to multiple couple records. We accept the login only when the
    password resolves to one account, or when multiple password matches collapse
    to a single portal-eligible account after lifecycle checks.
    """

    couples = await _list_couples_by_email(email)
    if not couples:
        verify_password("dummy_password", DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    password_matches: list[dict] = []
    for couple in couples:
        password_hash = couple.get("password_hash")
        if password_hash and verify_password(password, password_hash):
            password_matches.append(couple)

    if not password_matches:
        verify_password("dummy_password", DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if len(password_matches) == 1:
        return password_matches[0], None

    eligible_matches: list[tuple[dict, dict]] = []
    for couple in password_matches:
        _, access = await _resolve_portal_access(couple)
        if _is_couple_portal_sign_in_allowed(couple, access):
            eligible_matches.append((couple, access))

    if len(eligible_matches) == 1:
        return eligible_matches[0]

    raise HTTPException(
        status_code=409,
        detail="This email is linked to multiple wedding portal accounts. Use the latest invitation link for the correct wedding or contact support.",
    )


async def _select_password_reset_candidate(email: str) -> dict | None:
    """
    Resolve a unique couple account for password reset.

    If multiple eligible couple accounts share the same email, password reset is
    intentionally suppressed rather than sending a reset token to an ambiguous
    account.
    """

    couples = await _list_couples_by_email(email)
    if not couples:
        return None

    eligible: list[dict] = []
    for couple in couples:
        if not couple.get("setup_completed", False):
            continue

        _, access = await _resolve_portal_access(couple)
        if _is_couple_portal_sign_in_allowed(couple, access):
            eligible.append(couple)

    if len(eligible) == 1:
        return eligible[0]

    if len(eligible) > 1:
        logger.warning(
            "Skipped couple password reset for ambiguous email %s across %s eligible accounts",
            email,
            len(eligible),
        )
    return None


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

    # Resolve portal access — but allow pending_setup state through, since this
    # endpoint is what transitions the couple OUT of pending_setup.
    _, access = await _resolve_portal_access(couple)
    if (
        access.get("blocked")
        and access.get("state") != COUPLE_PORTAL_STATE_PENDING_SETUP
    ):
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

    access_token = _set_couple_session_cookie(response, couple)
    updated_couple = {**couple, **update_fields}

    logger.info(f"Couple account setup completed: {couple['email']}")

    # Stage 2 of the two-stage wedding-checklist nudge: now that the
    # couple has accepted the portal invite, surface a toast on the
    # planner UI carrying the seeded couple_intake form_id so they
    # can one-click "Send checklist" without navigating anywhere.
    #
    # Debounce: skip if the planner already manually sent that form to
    # this couple's email (i.e. a form_distributions row already
    # exists). Best-effort — wrapped so any failure here cannot break
    # the couple's account-setup completion.
    try:
        await _dispatch_couple_portal_accepted_notification(updated_couple)
    except Exception as notify_exc:  # pragma: no cover - defensive
        logger.warning(
            "couple_portal_accepted notification failed for %s "
            "(setup still succeeded): %s",
            couple.get("email"),
            notify_exc,
        )

    return {
        "message": "Account setup complete! Welcome to your wedding portal.",
        "access_token": access_token,
        "token_type": "bearer",
        "couple": _serialize_couple_payload(updated_couple),
    }


async def _dispatch_couple_portal_accepted_notification(couple: dict) -> None:
    """Resolve the planner's seeded couple_intake form id, debounce
    against an already-sent distribution, and dispatch the Stage 2
    notification.
    """
    # Notification fan-out queries SSE channels + team_members.owner_email
    # by email, so the recipient identifier MUST be the planner email,
    # not an ObjectId-style planner_id. Prefer planner_email; only fall
    # back to other id fields when no email is on the doc (legacy rows).
    planner_email = (couple.get("planner_email") or "").lower().strip() or None
    planner_id = planner_email or (
        couple.get("planner_id") or couple.get("assigned_planner_id")
    )
    if not planner_id:
        return

    couple_email = (couple.get("email") or "").lower().strip() or None
    couple_names = couple.get("couple_names") or couple.get("display_name")
    wedding_id = couple.get("wedding_id")

    seeded_form_id: Optional[str] = None
    if planner_email:
        seeded_doc = await mongo.db["forms"].find_one(
            {
                "created_by": planner_email,
                "seeded_from_catalog": True,
                "catalog_template_id": "couple_intake",
            },
            {"_id": 1},
        )
        if seeded_doc:
            seeded_form_id = str(seeded_doc["_id"])

            # Debounce: if the planner already manually sent the seeded
            # checklist to this couple's email, skip the toast. The
            # signal is presence of a form_distributions row.
            if couple_email:
                already_sent = await mongo.db["form_distributions"].find_one(
                    {
                        "form_id": seeded_form_id,
                        "recipient_email": couple_email,
                    }
                )
                if already_sent:
                    logger.info(
                        "Suppressing couple_portal_accepted toast for %s — "
                        "checklist already sent",
                        couple_email,
                    )
                    return

    from app.services.planner_notification_service import (
        planner_notification_service,
    )

    await planner_notification_service.notify_couple_portal_accepted(
        planner_id=str(planner_id),
        wedding_id=str(wedding_id) if wedding_id else None,
        couple_email=couple_email or "",
        couple_names=couple_names,
        seeded_form_id=seeded_form_id,
    )


@router.post("/couple/login", tags=["Couple Auth"])
async def couple_login(data: CoupleLoginRequest, response: Response):
    """
    Couple logs into their portal.
    """
    normalized_email = normalize_couple_email(data.email)
    if not normalized_email:
        verify_password("dummy_password", DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    couple, precomputed_access = await _select_login_candidate(
        normalized_email, data.password
    )

    if precomputed_access is None:
        _, precomputed_access = await _resolve_portal_access(couple)

    _raise_couple_sign_in_error(couple, precomputed_access)

    # Update last login
    await mongo.db["couple_users"].update_one(
        {"_id": couple["_id"]}, {"$set": {"last_login": datetime.now(timezone.utc)}}
    )

    access_token = _set_couple_session_cookie(response, couple)

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

    # Resolve portal access — but allow pending_setup state through, since that is
    # the expected state for a couple who hasn't completed setup yet.  Only block
    # on truly terminal states (revoked, owner_cancelled, owner subscription blocked).
    _, access = await _resolve_portal_access(couple)
    if (
        access.get("blocked")
        and access.get("state") != COUPLE_PORTAL_STATE_PENDING_SETUP
    ):
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
        "last_login": (
            couple.get("last_login", "").isoformat()
            if couple.get("last_login")
            else None
        ),
        "created_at": (
            couple.get("created_at", "").isoformat()
            if couple.get("created_at")
            else None
        ),
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

    email = normalize_couple_email(data.email)
    if not email:
        return success_message

    couple = await _select_password_reset_candidate(email)
    if not couple:
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

        safe_couple_name = html.escape(couple_name or "there", quote=True)
        safe_reset_link = html.escape(str(reset_link), quote=True)

        html_content = f"""
        <div style="font-family: 'Georgia', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #1e3a5f; font-size: 28px; margin-bottom: 8px;">Reset Your Password</h1>
                <p style="color: #d4af37; font-size: 16px; letter-spacing: 2px;">THE SPECIAL WEDDING</p>
            </div>

            <p style="color: #333; font-size: 16px; line-height: 1.6;">
                Dear {safe_couple_name},
            </p>

            <p style="color: #333; font-size: 16px; line-height: 1.6;">
                We received a request to reset your wedding portal password.
                Click the button below to set a new password.
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{safe_reset_link}"
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
                <span style="color: #1e3a5f;">{safe_reset_link}</span>
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

    access_token = _set_couple_session_cookie(response, couple)

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
