from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.utils.auth_utils import verify_password
from app.core.database import mongo
from typing import Optional
import secrets

# Security scheme for Basic Auth
security = HTTPBasic(auto_error=True)

class AuthUser:
    def __init__(self, email: str, role: str):
        self.email = email
        self.role = role

async def get_current_user(credentials: HTTPBasicCredentials = Depends(security)) -> AuthUser:
    """Get current authenticated user from Basic Auth credentials"""
    email = credentials.username
    password = credentials.password
    
    # Verify user exists in database
    user = mongo.db["admin_users"].find_one({"email": email})
    
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return AuthUser(email=email, role=user.get("role", "admin"))

async def require_admin(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Require admin role for access"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def require_role(required_role: str):
    """Factory function to create role-based dependencies"""
    async def role_checker(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{required_role} access required"
            )
        return current_user
    return role_checker