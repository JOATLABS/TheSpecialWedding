"""
Couple Authentication Dependency

Shared FastAPI dependency for authenticating couple portal requests.
Used by couple_portal.py and couple_auth.py endpoints.
"""
from fastapi import HTTPException, Request
from app.core.database import mongo
from app.utils.auth_utils import verify_token


async def require_couple_auth(request: Request) -> dict:
    """
    FastAPI-compatible dependency that extracts and validates a couple from JWT.

    Returns the couple document from the `couple_users` collection.
    Raises 401/403/404 as appropriate.

    Usage:
        @router.get("/couple/portal/dashboard")
        async def get_dashboard(couple: dict = Depends(require_couple_auth)):
            ...
    """
    auth_header = request.headers.get("Authorization")
    token = None

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.cookies.get("couple_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    email = payload.get("sub")
    role = payload.get("role")

    if role != "couple":
        raise HTTPException(status_code=403, detail="Couple access required")

    couple = await mongo.db["couple_users"].find_one({"email": email, "is_active": True})
    if not couple:
        raise HTTPException(status_code=404, detail="Couple account not found")

    return couple
