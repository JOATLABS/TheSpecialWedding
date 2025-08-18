from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.auth_utils import verify_token
from typing import Optional, List
import os
from app.core.database import mongo

# Security scheme
security = HTTPBearer(auto_error=True)

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

class ExtendedAuthUser:
    """Extended auth user supporting multiple roles"""
    def __init__(self, email: str, role: str, user_data: dict = None):
        self.email = email
        self.role = role
        self.user_data = user_data or {}
        
        # Role-specific properties
        self.is_root_admin = (role == "ROOT_ADMIN" and email == "thedeveloper@thespecialwedding.com")
        self.is_wedding_planner = (role == "wedding_planner")
        self.is_vendor = (role == "vendor")
        
        # Legacy admin support
        self.is_legacy_admin = (role == "admin")

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
        if email == "thedeveloper@thespecialwedding.com":
            # Check both legacy admin_users and new users collections
            legacy_user = mongo.get_admin_users_collection().find_one({"email": email})
            new_user = mongo.get_users_collection().find_one({"email": email})
            
            if legacy_user or new_user:
                # ROOT_ADMIN always has full access
                role = "ROOT_ADMIN"
                user_data = new_user or legacy_user or {}
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Root admin user not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # For other users, check the new users collection first, then legacy
            user = mongo.get_users_collection().find_one({"email": email})
            
            if not user:
                # Fallback to legacy admin_users collection for backward compatibility
                legacy_user = mongo.get_admin_users_collection().find_one({"email": email})
                if legacy_user:
                    user_data = legacy_user
                    role = "admin"  # Keep legacy role
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            else:
                user_data = user
                role = user.get("role", "wedding_planner")
                
                # Check if account is active
                if not user_data.get("is_active", True):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Account is deactivated",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            
        return ExtendedAuthUser(email=email, role=role, user_data=user_data)
        
    except Exception as e:
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
    """Require admin or wedding planner access (covers legacy admin too)"""
    if not (current_user.is_root_admin or current_user.is_wedding_planner or current_user.is_legacy_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or wedding planner access required"
        )
    return current_user

async def require_any_admin(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> ExtendedAuthUser:
    """Require any admin access (backward compatible with existing admin endpoints)"""
    if not (current_user.is_root_admin or current_user.is_legacy_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def check_wedding_access(user: ExtendedAuthUser, wedding_id: str) -> bool:
    """Check if user has access to a specific wedding"""
    if user.is_root_admin:
        return True  # ROOT_ADMIN has access to all weddings
    
    if user.is_legacy_admin:
        return True  # Legacy admin has access to all weddings for backward compatibility
    
    if user.is_wedding_planner:
        # Check if this wedding is assigned to this planner
        wedding = mongo.get_weddings_collection().find_one({"_id": wedding_id})
        if wedding:
            return wedding.get("assigned_planner_email") == user.email
    
    if user.is_vendor:
        # Check if vendor has access to this wedding
        vendor = mongo.get_vendors_collection().find_one({"email": user.email, "wedding_id": wedding_id})
        return vendor is not None
    
    return False

async def require_wedding_access(wedding_id: str):
    """Factory function to require access to a specific wedding"""
    async def wedding_access_checker(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> ExtendedAuthUser:
        if not check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this wedding denied"
            )
        return current_user
    return wedding_access_checker