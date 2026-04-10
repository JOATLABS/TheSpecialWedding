"""
Couple Authentication Dependency

Shared FastAPI dependency for authenticating couple portal requests.
Used by couple_portal.py and couple_auth.py endpoints.
"""

from fastapi import HTTPException, Request

from app.core.database import mongo
from app.services.couple_lifecycle_service import couple_lifecycle_service
from app.utils.auth_utils import verify_token
from app.utils.couple_identity import build_couple_lookup_query, normalize_couple_email
from app.utils.planner_ownership import normalize_wedding_query_id


async def _load_couple_wedding(couple: dict) -> dict | None:
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

    subject = payload.get("sub")
    role = payload.get("role")

    if role != "couple":
        raise HTTPException(status_code=403, detail="Couple access required")

    if not subject:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    lookup_query = build_couple_lookup_query(subject)
    couple = None
    if lookup_query:
        couple = await mongo.db["couple_users"].find_one(lookup_query)
    if not couple:
        legacy_email = normalize_couple_email(subject)
        if legacy_email:
            legacy_matches = await (
                mongo.db["couple_users"].find({"email": legacy_email}).to_list(length=2)
            )
            if len(legacy_matches) > 1:
                raise HTTPException(
                    status_code=401,
                    detail="This session maps to multiple couple accounts. Please sign in again from the correct wedding portal.",
                )
            if legacy_matches:
                couple = legacy_matches[0]

    if not couple:
        raise HTTPException(status_code=404, detail="Couple account not found")

    wedding = await _load_couple_wedding(couple)
    access = await couple_lifecycle_service.resolve_effective_state(couple, wedding)
    if access.get("blocked"):
        raise HTTPException(status_code=403, detail=access["detail"])

    couple["_portal_access_state"] = access["state"]
    couple["_portal_access_detail"] = access.get("detail")

    return couple
