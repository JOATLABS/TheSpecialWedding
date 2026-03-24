"""
Couple Invitation API (Planner-side)

Endpoints for planners to invite couples to the portal.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
from app.core.database import mongo
from app.dependencies.auth_extended import (
    ExtendedAuthUser, require_team_or_planner, enforce_team_permission, check_wedding_access
)
from bson import ObjectId
import secrets
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


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


@router.post("/couple-portal/invite", tags=["Couple Portal"])
async def invite_couple(
    data: InviteCoupleRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Invite a couple to the wedding portal.
    Creates a couple_users record and sends a magic link email.
    """
    enforce_team_permission(current_user, "manage_contracts")

    # Verify wedding access
    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    # Check if couple already exists for this wedding
    existing = await mongo.db["couple_users"].find_one({
        "email": data.email.lower().strip(),
        "wedding_id": data.wedding_id
    })

    if existing and existing.get("setup_completed"):
        raise HTTPException(status_code=400, detail="This couple already has an active portal account for this wedding.")

    # Get wedding details for the email
    wedding = await mongo.get_weddings_collection().find_one({"_id": data.wedding_id})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    # Get planner info
    planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)
    planner_name = f"{(current_user.user_data or {}).get('first_name', '')} {(current_user.user_data or {}).get('last_name', '')}".strip()
    if not planner_name:
        planner_name = (current_user.user_data or {}).get("company_name", current_user.email)

    # Generate invite token
    invite_token = secrets.token_urlsafe(48)
    invite_expires = datetime.now(timezone.utc) + timedelta(days=7)

    couple_doc = {
        "email": data.email.lower().strip(),
        "partner1_name": data.partner1_name,
        "partner2_name": data.partner2_name,
        "phone": data.phone,
        "wedding_id": data.wedding_id,
        "planner_id": planner_id,
        "planner_email": current_user.email,
        "invite_token": invite_token,
        "invite_token_expires": invite_expires,
        "is_active": False,
        "setup_completed": False,
        "password_hash": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "last_login": None,
    }

    if existing:
        # Update existing record with new invite token
        await mongo.db["couple_users"].update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "invite_token": invite_token,
                "invite_token_expires": invite_expires,
                "partner1_name": data.partner1_name,
                "partner2_name": data.partner2_name,
                "phone": data.phone,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        couple_id = str(existing["_id"])
    else:
        result = await mongo.db["couple_users"].insert_one(couple_doc)
        couple_id = str(result.inserted_id)

    # Also update the wedding to track the couple link
    await mongo.get_weddings_collection().update_one(
        {"_id": data.wedding_id},
        {"$set": {
            "couple_portal_email": data.email.lower().strip(),
            "couple_portal_enabled": True,
            "couple_portal_invited_at": datetime.now(timezone.utc),
            "updated_by": current_user.email
        }}
    )

    # Send invitation email
    from app.core.settings import settings
    frontend_url = getattr(settings, 'frontend_url', None) or "https://thespecialwedding.io"
    setup_link = f"{frontend_url}/couple/setup?token={invite_token}"

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
            Wedding: {wedding.get('couple_names', 'Your Wedding')}<br/>
            Planner: {planner_name} ({current_user.email})
        </p>
    </div>
    """

    try:
        from app.services.email_service import email_service
        await email_service.send_email(
            to=data.email.lower().strip(),
            subject=f"You're Invited to Your Wedding Portal - {wedding.get('couple_names', 'Your Wedding')}",
            html=html_content
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
        "invite_expires": invite_expires.isoformat()
    }


@router.post("/couple-portal/resend-invite", tags=["Couple Portal"])
async def resend_invite(
    data: ResendInviteRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Resend the invitation email to a couple."""
    enforce_team_permission(current_user, "manage_contracts")

    couple = await mongo.db["couple_users"].find_one({"_id": ObjectId(data.couple_id)})
    if not couple:
        raise HTTPException(status_code=404, detail="Couple not found")

    # Verify planner has access to this wedding
    if not await check_wedding_access(current_user, couple["wedding_id"]):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    if couple.get("setup_completed"):
        raise HTTPException(status_code=400, detail="Couple has already set up their account")

    # Generate new token
    invite_token = secrets.token_urlsafe(48)
    invite_expires = datetime.now(timezone.utc) + timedelta(days=7)

    await mongo.db["couple_users"].update_one(
        {"_id": couple["_id"]},
        {"$set": {
            "invite_token": invite_token,
            "invite_token_expires": invite_expires,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    from app.core.settings import settings
    frontend_url = getattr(settings, 'frontend_url', None) or "https://thespecialwedding.io"
    setup_link = f"{frontend_url}/couple/setup?token={invite_token}"

    # Send email (reuse same template logic)
    try:
        from app.services.email_service import email_service
        wedding = await mongo.get_weddings_collection().find_one({"_id": couple["wedding_id"]})
        planner_name = f"{(current_user.user_data or {}).get('first_name', '')} {(current_user.user_data or {}).get('last_name', '')}".strip()
        if not planner_name:
            planner_name = (current_user.user_data or {}).get("company_name", current_user.email)

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

        await email_service.send_email(
            to=couple["email"],
            subject=f"Reminder: Set Up Your Wedding Portal",
            html=html_content
        )
        email_sent = True
    except Exception as e:
        logger.error(f"Failed to resend couple invite: {e}")
        email_sent = False

    return {
        "message": "Invitation resent",
        "email_sent": email_sent,
        "setup_link": setup_link
    }


@router.get("/couple-portal/couples", tags=["Couple Portal"])
async def list_couples(
    wedding_id: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """List all couples for the planner's weddings."""
    planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)

    query = {"planner_id": planner_id}
    if wedding_id:
        query["wedding_id"] = wedding_id

    couples = []
    async for couple in mongo.db["couple_users"].find(query).sort("created_at", -1):
        couple_id = str(couple["_id"]) if isinstance(couple["_id"], ObjectId) else couple["_id"]
        couples.append({
            "id": couple_id,
            "email": couple["email"],
            "partner1_name": couple.get("partner1_name"),
            "partner2_name": couple.get("partner2_name"),
            "wedding_id": couple.get("wedding_id"),
            "is_active": couple.get("is_active", False),
            "setup_completed": couple.get("setup_completed", False),
            "last_login": couple.get("last_login").isoformat() if couple.get("last_login") else None,
            "created_at": couple.get("created_at").isoformat() if couple.get("created_at") else None
        })

    return {"couples": couples, "count": len(couples)}
