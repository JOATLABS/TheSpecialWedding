from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.auth_utils import verify_token
import os
from app.core.database import mongo

# Security scheme
security = HTTPBearer(auto_error=True)

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


class AuthUser:
    def __init__(self, email: str, role: str):
        self.email = email
        self.role = role

# We're no longer using token-based auth, so this function is removed


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthUser:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    try:
        payload = verify_token(token)
        email = payload.get("sub")
        role = payload.get("role", "admin")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )       
        # Verify user still exists in database
        user = mongo.db["admin_users"].find_one({"email": email})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthUser(email=email, role=role)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_admin(
    current_user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    """Require admin role for access"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_role(required_role: str):
    """Factory function to create role-based dependencies"""
    async def role_checker(
        current_user: AuthUser = Depends(get_current_user),
    ) -> AuthUser:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{required_role} access required"
            )
        return current_user
    return role_checker


async def get_current_admin(
    current_user: AuthUser = Depends(require_admin),
) -> str:
    return current_user.email
