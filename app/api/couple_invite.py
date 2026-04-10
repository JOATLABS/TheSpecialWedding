"""
Couple Invitation API (Planner-side)

Endpoints for planners to invite couples to the portal.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import mongo
from app.core.settings import settings
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    get_accessible_wedding_ids,
    get_owner_identity,
    require_team_or_planner,
)
from app.services.couple_lifecycle_service import (
    COUPLE_PORTAL_STATE_PENDING_SETUP,
    couple_lifecycle_service,
)
from app.utils.couple_identity import normalize_couple_email
from app.utils.planner_ownership import (
    extract_wedding_owner_identity,
    list_wedding_ids_for_owner,
    normalize_query_id,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _enforce_manage_couple_portal(current_user: ExtendedAuthUser) -> None:
    """Require explicit couple-portal management access for team members."""
    enforce_team_permission(current_user, "manage_couple_portal")


class InviteCoupleRequest(BaseModel):
    """Request to invite a couple to the portal."""

    email: str = Field(..., max_length=254)
    partner1_name: str = Field(..., min_length=1, max_length=100)
    partner2_name: Optional[str] = Field(None, max_length=100)
    wedding_id: str = Field(..., description="Wedding ID to link")
    phone: Optional[str] = Field(None, max_length=20)


class ResendInviteRequest(BaseModel):
    """Request to resend invitation to a couple."""

    couple_id: str = Field(...)


async def _ensure_unique_couple_email_for_wedding(email: str, wedding_id: str) -> None:
    """
    Reject reusing a couple email across different weddings.

    Couple auth now uses the couple record as the principal, but the current
    product still presents a single email/password login surface. Until a
    wedding-selection UX exists, allowing one email to back multiple wedding
    portals creates ambiguous login and reset flows.
    """
    conflict = await mongo.db["couple_users"].find_one(
        {
            "email": email,
            "wedding_id": {"$ne": wedding_id},
        },
        {"_id": 1, "wedding_id": 1, "partner1_name": 1, "partner2_name": 1},
    )

    if conflict:
        raise HTTPException(
            status_code=409,
            detail="This email is already linked to another wedding portal. Use a different email address or retire the existing portal before reusing it.",
        )


def _normalize_invite_expiry(value: object) -> Optional[datetime]:
    """Best-effort normalize an invite expiry value into an aware UTC datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return None


def _build_active_setup_link(
    couple: dict, normalized_frontend_url: str
) -> Optional[str]:
    """Return the current setup link only when the invite token is still active."""
    if couple.get("setup_completed") or not couple.get("invite_token"):
        return None

    invite_expires = _normalize_invite_expiry(couple.get("invite_token_expires"))
    if invite_expires is None or invite_expires <= datetime.now(timezone.utc):
        return None

    return f"{normalized_frontend_url}/couple/setup/{couple['invite_token']}"


@router.post("/couple-portal/invite", tags=["Couple Portal"])
async def invite_couple(
    data: InviteCoupleRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Invite a couple to the wedding portal.
    Creates a couple_users record and sends a magic link email.
    """
    _enforce_manage_couple_portal(current_user)

    # Verify wedding access
    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    normalized_email = normalize_couple_email(data.email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="A valid couple email is required")

    # Check if couple already exists for this wedding
    existing = await mongo.db["couple_users"].find_one(
        {"email": normalized_email, "wedding_id": data.wedding_id}
    )

    if existing and existing.get("setup_completed"):
        raise HTTPException(
            status_code=400,
            detail="This couple already has an active portal account for this wedding.",
        )

    await _ensure_unique_couple_email_for_wedding(normalized_email, data.wedding_id)

    # Get wedding details for the email
    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": normalize_query_id(data.wedding_id)}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    # Get planner info
    planner_id, planner_email = extract_wedding_owner_identity(wedding)
    actor_owner_id, actor_owner_email = get_owner_identity(current_user)
    planner_id = planner_id or actor_owner_id or ""
    planner_email = planner_email or actor_owner_email or current_user.email
    planner_name = f"{(current_user.user_data or {}).get('first_name', '')} {(current_user.user_data or {}).get('last_name', '')}".strip()
    if not planner_name:
        planner_name = (current_user.user_data or {}).get(
            "company_name", current_user.email
        )

    # Generate invite token
    invite_token = secrets.token_urlsafe(48)
    invite_expires = datetime.now(timezone.utc) + timedelta(days=7)

    couple_doc = {
        "email": normalized_email,
        "partner1_name": data.partner1_name,
        "partner2_name": data.partner2_name,
        "phone": data.phone,
        "wedding_id": data.wedding_id,
        "planner_id": planner_id,
        "planner_email": planner_email,
        "invite_token": invite_token,
        "invite_token_expires": invite_expires,
        "is_active": False,
        "access_state": COUPLE_PORTAL_STATE_PENDING_SETUP,
        "setup_completed": False,
        "password_hash": None,
        "revoked_at": None,
        "revoked_by": None,
        "owner_cancelled_at": None,
        "owner_cancelled_by_planner_id": None,
        "owner_cancelled_by_planner_email": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "last_login": None,
    }

    if existing:
        # Update existing record with new invite token
        await mongo.db["couple_users"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "invite_token": invite_token,
                    "invite_token_expires": invite_expires,
                    "planner_id": planner_id,
                    "planner_email": planner_email,
                    "partner1_name": data.partner1_name,
                    "partner2_name": data.partner2_name,
                    "phone": data.phone,
                    "is_active": False,
                    "access_state": COUPLE_PORTAL_STATE_PENDING_SETUP,
                    "revoked_at": None,
                    "revoked_by": None,
                    "owner_cancelled_at": None,
                    "owner_cancelled_by_planner_id": None,
                    "owner_cancelled_by_planner_email": None,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        couple_id = str(existing["_id"])
    else:
        result = await mongo.db["couple_users"].insert_one(couple_doc)
        couple_id = str(result.inserted_id)

    # Also update the wedding to track the couple link
    await mongo.get_weddings_collection().update_one(
        {"_id": normalize_query_id(data.wedding_id)},
        {
            "$set": {
                "couple_portal_email": normalized_email,
                "couple_portal_enabled": True,
                "couple_portal_invited_at": datetime.now(timezone.utc),
                "updated_by": current_user.email,
            }
        },
    )

    # Send invitation email
    from app.core.settings import settings

    frontend_url = (
        getattr(settings, "frontend_url", None) or "https://thespecialwedding.io"
    )
    normalized_frontend_url = frontend_url.rstrip("/")
    setup_link = f"{normalized_frontend_url}/couple/setup/{invite_token}"

    couple_name = data.partner1_name
    if data.partner2_name:
        couple_name = f"{data.partner1_name} & {data.partner2_name}"

    html_content = f"""
    <div style="font-family: 'Georgia', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #1e3a5f; font-size: 28px; margin-bottom: 8px;">Your Wedding Portal</h1>
            <p style="color: #d4af37; font-size: 16px; letter-spacing: 2px;">THE SPECIAL WEDDING</p>
        </div>

        <p style="color: #333; font-size: 16px; line-height: 1.6;">
            Dear {couple_name},
        </p>

        <p style="color: #333; font-size: 16px; line-height: 1.6;">
            Your wedding planner <strong>{planner_name}</strong> has invited you to your
            personal wedding portal. Here you can view your wedding details, track payments,
            review contracts, and stay connected with your planner.
        </p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{setup_link}"
               style="background-color: #1e3a5f; color: white; padding: 14px 32px;
                      text-decoration: none; border-radius: 6px; font-size: 16px;
                      display: inline-block;">
                Set Up Your Account
            </a>
        </div>

        <p style="color: #666; font-size: 14px; line-height: 1.6;">
            This link expires in 7 days. If it expires, ask your planner to resend the invitation.
        </p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;" />

        <p style="color: #999; font-size: 12px; text-align: center;">
            Wedding: {wedding.get("couple_names", "Your Wedding")}<br/>
            Planner: {planner_name} ({planner_email or current_user.email})
        </p>
    </div>
    """

    try:
        from app.services.email_service_resend import ResendEmailService

        _email_svc = ResendEmailService()
        await _email_svc.send_email(
            to_email=normalized_email,
            subject=f"You're Invited to Your Wedding Portal - {wedding.get('couple_names', 'Your Wedding')}",
            html_content=html_content,
        )
        email_sent = True
    except Exception as e:
        logger.error(f"Failed to send couple invite email: {e}")
        email_sent = False

    return {
        "message": "Couple invited successfully",
        "couple_id": couple_id,
        "email_sent": email_sent,
        "setup_link": setup_link,  # Return for planner to share manually if email fails
        "invite_expires": invite_expires.isoformat(),
    }


@router.post("/couple-portal/resend-invite", tags=["Couple Portal"])
async def resend_invite(
    data: ResendInviteRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Resend the invitation email to a couple."""
    _enforce_manage_couple_portal(current_user)

    couple = await mongo.db["couple_users"].find_one({"_id": ObjectId(data.couple_id)})
    if not couple:
        raise HTTPException(status_code=404, detail="Couple not found")

    # Verify planner has access to this wedding
    if not await check_wedding_access(current_user, couple["wedding_id"]):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    if couple.get("setup_completed"):
        raise HTTPException(
            status_code=400, detail="Couple has already set up their account"
        )

    # Generate new token
    invite_token = secrets.token_urlsafe(48)
    invite_expires = datetime.now(timezone.utc) + timedelta(days=7)

    await mongo.db["couple_users"].update_one(
        {"_id": couple["_id"]},
        {
            "$set": {
                "invite_token": invite_token,
                "invite_token_expires": invite_expires,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    from app.core.settings import settings

    frontend_url = (
        getattr(settings, "frontend_url", None) or "https://thespecialwedding.io"
    )
    normalized_frontend_url = frontend_url.rstrip("/")
    setup_link = f"{normalized_frontend_url}/couple/setup/{invite_token}"

    # Send email (reuse same template logic)
    try:
        from app.services.email_service_resend import ResendEmailService

        _email_svc = ResendEmailService()
        planner_name = f"{(current_user.user_data or {}).get('first_name', '')} {(current_user.user_data or {}).get('last_name', '')}".strip()
        if not planner_name:
            planner_name = (current_user.user_data or {}).get(
                "company_name", current_user.email
            )

        couple_name = couple.get("partner1_name", "")
        if couple.get("partner2_name"):
            couple_name = f"{couple['partner1_name']} & {couple['partner2_name']}"

        html_content = f"""
        <div style="font-family: 'Georgia', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #1e3a5f; font-size: 28px; margin-bottom: 8px;">Your Wedding Portal</h1>
                <p style="color: #d4af37; font-size: 16px; letter-spacing: 2px;">THE SPECIAL WEDDING</p>
            </div>
            <p style="color: #333; font-size: 16px; line-height: 1.6;">Dear {couple_name},</p>
            <p style="color: #333; font-size: 16px; line-height: 1.6;">
                Here's a new invitation link to set up your wedding portal account.
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{setup_link}"
                   style="background-color: #1e3a5f; color: white; padding: 14px 32px;
                          text-decoration: none; border-radius: 6px; font-size: 16px;
                          display: inline-block;">
                    Set Up Your Account
                </a>
            </div>
            <p style="color: #666; font-size: 14px;">This link expires in 7 days.</p>
        </div>
        """

        await _email_svc.send_email(
            to_email=couple["email"],
            subject="Reminder: Set Up Your Wedding Portal",
            html_content=html_content,
        )
        email_sent = True
    except Exception as e:
        logger.error(f"Failed to resend couple invite: {e}")
        email_sent = False

    return {
        "message": "Invitation resent",
        "email_sent": email_sent,
        "setup_link": setup_link,
    }


@router.get("/couple-portal/couples", tags=["Couple Portal"])
async def list_couples(
    wedding_id: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """List all couples for the planner's weddings."""
    _enforce_manage_couple_portal(current_user)
    frontend_url = (
        getattr(settings, "frontend_url", None) or "https://thespecialwedding.io"
    )
    normalized_frontend_url = frontend_url.rstrip("/")
    if wedding_id:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )
        query = {"wedding_id": wedding_id}
    elif current_user.is_root_admin:
        query = {}
    else:
        planner_id = (
            current_user.parent_planner_id
            if current_user.is_team_member
            else (current_user.user_data or {}).get("_id")
        )
        planner_email = (
            current_user.team_owner_email
            if current_user.is_team_member
            else current_user.email
        )
        wedding_ids = await list_wedding_ids_for_owner(
            planner_id=planner_id,
            planner_email=planner_email,
            accessible_wedding_ids=get_accessible_wedding_ids(current_user),
        )
        if not wedding_ids:
            return {"couples": [], "count": 0}
        query = {"wedding_id": {"$in": wedding_ids}}

    couples = []
    async for couple in mongo.db["couple_users"].find(query).sort("created_at", -1):
        couple_id = (
            str(couple["_id"]) if isinstance(couple["_id"], ObjectId) else couple["_id"]
        )
        couples.append(
            {
                "id": couple_id,
                "email": couple["email"],
                "partner1_name": couple.get("partner1_name"),
                "partner2_name": couple.get("partner2_name"),
                "wedding_id": couple.get("wedding_id"),
                "is_active": couple.get("is_active", False),
                "access_state": couple_lifecycle_service.infer_stored_state(couple),
                "setup_completed": couple.get("setup_completed", False),
                "wedding_archived": couple.get("wedding_archived", False),
                "setup_link": _build_active_setup_link(couple, normalized_frontend_url),
                "setup_link_expires_at": (
                    _normalize_invite_expiry(
                        couple.get("invite_token_expires")
                    ).isoformat()
                    if _normalize_invite_expiry(couple.get("invite_token_expires"))
                    else None
                ),
                "last_login": (
                    couple.get("last_login").isoformat()
                    if couple.get("last_login")
                    else None
                ),
                "created_at": (
                    couple.get("created_at").isoformat()
                    if couple.get("created_at")
                    else None
                ),
            }
        )

    return {"couples": couples, "count": len(couples)}
