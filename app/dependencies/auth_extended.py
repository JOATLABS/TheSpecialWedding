from typing import Optional, Union
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.auth_utils import verify_token
import os
from datetime import datetime, timezone
from app.core.database import mongo
from bson import ObjectId

# Security scheme
security = HTTPBearer(auto_error=True)

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


class ExtendedAuthUser:
    """Extended auth user supporting multiple roles"""
    def __init__(self, email: str, role: str, user_data: Optional[dict] = None):
        self.email = email
        self.role = role
        self.user_data = user_data or {}
        # Role-specific properties
        root_admin_email = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")
        self.is_root_admin = (role == "ROOT_ADMIN" and email == root_admin_email)
        self.is_wedding_planner = (role == "wedding_planner")
        self.is_vendor = (role == "vendor")


async def get_current_user_extended(credentials: HTTPAuthorizationCredentials = Depends(security)) -> ExtendedAuthUser:
    """Get current authenticated user supporting both legacy and new auth systems"""
    token = credentials.credentials
    try:
        payload = verify_token(token)
        email = payload.get("sub")
        role = payload.get("role", "admin")  # Default to admin for backward compatibility
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_data = {}

        # Check if this is the ROOT_ADMIN
        root_admin_email = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")
        if email == root_admin_email:
            # ROOT_ADMIN must exist in the users collection
            user = await mongo.get_users_collection().find_one({"email": email})
            if user:
                # ROOT_ADMIN always has full access
                role = "ROOT_ADMIN"
                user_data = user.copy()
                # Convert ObjectId to string for consistent data types
                if "_id" in user_data and isinstance(user_data["_id"], ObjectId):
                    user_data["_id"] = str(user_data["_id"])
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Root admin user not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # For other users, check the new users collection first, then legacy
            user = await mongo.get_users_collection().find_one({"email": email})
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user_data = user.copy()  # Make a copy to avoid modifying the original
            # Convert ObjectId to string for consistent data types
            if "_id" in user_data and isinstance(user_data["_id"], ObjectId):
                user_data["_id"] = str(user_data["_id"])
            role = user.get("role", "wedding_planner")
            # Check if account is active
            if not user_data.get("is_active", True):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is deactivated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # Check email verification for new accounts
            if user_data.get("email_verified") is False:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Email address not verified. Please check your email and verify your account.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # Check trial expiration for wedding planners
            if role == "wedding_planner" and user_data.get("subscription_status") == "trial":
                trial_end_date = user_data.get("trial_end_date")
                if trial_end_date:
                    # Handle both datetime objects and ISO strings
                    if isinstance(trial_end_date, str):
                        try:
                            trial_end_date = datetime.fromisoformat(trial_end_date.replace('Z', '+00:00'))
                        except ValueError:
                            trial_end_date = datetime.fromisoformat(trial_end_date)
                    if datetime.now(timezone.utc) > trial_end_date:
                        # Auto-expire the trial
                        await mongo.get_users_collection().update_one(
                            {"email": email},
                            {"$set": {
                                "subscription_status": "expired",
                                "is_active": False,
                                "trial_expired_at": datetime.now(timezone.utc)
                            }}
                        )
                        raise HTTPException(
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail="Free trial has expired. Please upgrade your subscription to continue using the platform.",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

        return ExtendedAuthUser(email=email, role=role, user_data=user_data)

    except HTTPException:
        # Re-raise HTTP exceptions (including trial expiration 402) as-is
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Role-based dependency factories
async def require_root_admin(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> ExtendedAuthUser:
    """Require ROOT_ADMIN access (only thedeveloper@thespecialwedding.com)"""
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Root admin access required"
        )
    return current_user


async def require_wedding_planner(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> ExtendedAuthUser:
    """Require wedding planner access"""
    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wedding planner access required"
        )
    return current_user


async def require_vendor(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> ExtendedAuthUser:
    """Require vendor access"""
    if not (current_user.is_vendor or current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vendor access required"
        )
    return current_user


async def require_admin_or_planner(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> ExtendedAuthUser:
    """Require root admin or wedding planner access"""
    if not (current_user.is_root_admin or current_user.is_wedding_planner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or wedding planner access required"
        )
    return current_user


async def require_any_admin(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> ExtendedAuthUser:
    """Require root admin access"""
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_wedding_planner_only(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> ExtendedAuthUser:
    """Require wedding planner access only (excludes root admin)"""
    if not current_user.is_wedding_planner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wedding planner access required"
        )
    return current_user


async def check_wedding_access(user: ExtendedAuthUser, wedding_id: str) -> bool:
    """Check if user has access to a specific wedding"""
    # ROOT_ADMIN has full access to all weddings for platform management
    if user.is_root_admin:
        return True

    if user.is_wedding_planner:
        # Check if this wedding is assigned to this planner
        from bson import ObjectId
        import re

        # Validate and sanitize wedding_id
        if not wedding_id or not isinstance(wedding_id, str):
            return False

        # Prevent NoSQL injection by validating input
        if len(wedding_id) > 100:  # Reasonable limit
            return False

        try:
            query_id: Union[str, ObjectId]
            # Handle both string and ObjectId formats
            if isinstance(wedding_id, str):
                # Check if it looks like a valid ObjectId (24 hex characters)
                if re.match(r'^[0-9a-fA-F]{24}$', wedding_id):
                    query_id = ObjectId(wedding_id)
                else:
                    # Use as string for slug-based lookups, but sanitize
                    query_id = wedding_id.strip()
            else:
                query_id = wedding_id

            # Use await for find_one since db is async
            wedding = await mongo.get_weddings_collection().find_one({"_id": query_id})

            if wedding:
                return wedding.get("assigned_planner_email") == user.email
        except Exception:
            return False
    if user.is_vendor:
        # Check if vendor has access to this wedding
        vendor = await mongo.get_vendors_collection().find_one({"email": user.email, "wedding_id": wedding_id})
        return vendor is not None
    return False


async def require_wedding_access(wedding_id: str):
    """Factory function to require access to a specific wedding"""
    async def wedding_access_checker(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> ExtendedAuthUser:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this wedding denied"
            )
        return current_user
    return wedding_access_checker
