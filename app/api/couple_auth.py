"""
Couple Authentication API Routes

Handles couple invitation, password setup, and login.
Couples are invited by planners via magic link email.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
from app.core.database import mongo
from app.utils.auth_utils import get_password_hash, verify_password, create_access_token
import secrets
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class InviteCoupleRequest(BaseModel):
    """Planner invites a couple to the portal."""
    email: str = Field(..., max_length=254)
    partner1_name: str = Field(..., min_length=1, max_length=100)
    partner2_name: Optional[str] = Field(None, max_length=100)
    wedding_id: str = Field(..., description="Wedding ID to link the couple to")
    phone: Optional[str] = Field(None, max_length=20)


class CoupleSetupPasswordRequest(BaseModel):
    """Couple sets their password after receiving magic link."""
    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=128)


class CoupleLoginRequest(BaseModel):
    """Couple login."""
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


# ============================================================================
# PUBLIC ENDPOINTS (No auth required)
# ============================================================================

@router.post("/couple/setup-password", tags=["Couple Auth"])
async def setup_couple_password(data: CoupleSetupPasswordRequest):
    """
    Couple sets their password using the invite token from the magic link.
    This completes the couple's account setup.
    """
    # Find the couple by invite token
    couple = await mongo.db["couple_users"].find_one({
        "invite_token": data.token,
        "invite_token_expires": {"$gt": datetime.now(timezone.utc)}
    })

    if not couple:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation link. Please ask your planner to resend the invitation.")

    # Hash password and activate account
    password_hash = get_password_hash(data.password)

    await mongo.db["couple_users"].update_one(
        {"_id": couple["_id"]},
        {"$set": {
            "password_hash": password_hash,
            "is_active": True,
            "setup_completed": True,
            "setup_completed_at": datetime.now(timezone.utc),
            "invite_token": None,  # Invalidate the token
            "invite_token_expires": None,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    # Generate JWT token so they're logged in immediately
    token_data = {"sub": couple["email"], "role": "couple"}
    access_token = create_access_token(data=token_data, expires_delta=timedelta(hours=24))

    logger.info(f"Couple account setup completed: {couple['email']}")

    return {
        "message": "Account setup complete! Welcome to your wedding portal.",
        "access_token": access_token,
        "token_type": "bearer",
        "couple": {
            "email": couple["email"],
            "partner1_name": couple.get("partner1_name"),
            "partner2_name": couple.get("partner2_name"),
            "wedding_id": couple.get("wedding_id")
        }
    }


@router.post("/couple/login", tags=["Couple Auth"])
async def couple_login(data: CoupleLoginRequest):
    """
    Couple logs into their portal.
    """
    couple = await mongo.db["couple_users"].find_one({"email": data.email.lower().strip()})

    if not couple or not couple.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not couple.get("is_active", False):
        raise HTTPException(status_code=401, detail="Account is not active. Please contact your planner.")

    if not couple.get("setup_completed", False):
        raise HTTPException(status_code=401, detail="Please complete your account setup using the invitation link from your planner.")

    if not verify_password(data.password, couple["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last login
    await mongo.db["couple_users"].update_one(
        {"_id": couple["_id"]},
        {"$set": {"last_login": datetime.now(timezone.utc)}}
    )

    token_data = {"sub": couple["email"], "role": "couple"}
    access_token = create_access_token(data=token_data, expires_delta=timedelta(hours=24))

    logger.info(f"Couple logged in: {couple['email']}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "couple": {
            "email": couple["email"],
            "partner1_name": couple.get("partner1_name"),
            "partner2_name": couple.get("partner2_name"),
            "wedding_id": couple.get("wedding_id")
        }
    }


@router.get("/couple/verify-invite/{token}", tags=["Couple Auth"])
async def verify_invite_token(token: str):
    """
    Verify that an invite token is valid (used by the setup page to check before showing form).
    """
    couple = await mongo.db["couple_users"].find_one({
        "invite_token": token,
        "invite_token_expires": {"$gt": datetime.now(timezone.utc)}
    })

    if not couple:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation link.")

    return {
        "valid": True,
        "email": couple["email"],
        "partner1_name": couple.get("partner1_name"),
        "partner2_name": couple.get("partner2_name")
    }


@router.get("/couple/profile", tags=["Couple Auth"])
async def get_couple_profile(request: Request):
    """
    Get the authenticated couple's profile.
    Requires Bearer token from couple login.
    """
    from app.utils.auth_utils import verify_token
    from fastapi.security import HTTPBearer

    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ")[1]
    try:
        payload = verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    email = payload.get("sub")
    role = payload.get("role")

    if role != "couple":
        raise HTTPException(status_code=403, detail="Couple access required")

    couple = await mongo.db["couple_users"].find_one({"email": email})
    if not couple:
        raise HTTPException(status_code=404, detail="Couple account not found")

    from bson import ObjectId
    couple_id = str(couple["_id"]) if isinstance(couple["_id"], ObjectId) else couple["_id"]

    return {
        "id": couple_id,
        "email": couple["email"],
        "partner1_name": couple.get("partner1_name"),
        "partner2_name": couple.get("partner2_name"),
        "phone": couple.get("phone"),
        "wedding_id": couple.get("wedding_id"),
        "planner_id": couple.get("planner_id"),
        "is_active": couple.get("is_active", False),
        "setup_completed": couple.get("setup_completed", False),
        "last_login": couple.get("last_login", "").isoformat() if couple.get("last_login") else None,
        "created_at": couple.get("created_at", "").isoformat() if couple.get("created_at") else None
    }
