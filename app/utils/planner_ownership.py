from __future__ import annotations

from typing import Any, Optional, Sequence

from bson import ObjectId

from app.core.database import mongo


def normalize_planner_id(planner_id: Any) -> Optional[str]:
    """Normalize planner/user identifiers to a comparable string form."""
    if planner_id is None:
        return None
    value = str(planner_id).strip()
    return value or None


def normalize_planner_email(planner_email: Any) -> Optional[str]:
    """Normalize planner email values for consistent comparisons."""
    if planner_email is None:
        return None
    value = str(planner_email).strip().lower()
    return value or None


def normalize_query_id(value: Any) -> Any:
    """Normalize a potentially string Mongo identifier for lookups."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if ObjectId.is_valid(stripped):
            return ObjectId(stripped)
        return stripped
    return value


def normalize_wedding_query_id(value: Any) -> Any:
    """Backward-compatible alias for wedding identifier normalization."""
    return normalize_query_id(value)


def extract_wedding_owner_identity(
    wedding: Optional[dict],
) -> tuple[Optional[str], Optional[str]]:
    """Return the planner owner identity mirrored onto a wedding document."""
    if not wedding:
        return None, None
    return (
        normalize_planner_id(wedding.get("assigned_planner_id")),
        normalize_planner_email(wedding.get("assigned_planner_email")),
    )


def build_wedding_owner_query(
    planner_id: Any = None, planner_email: Any = None
) -> dict:
    """Build a query that matches a wedding by canonical owner id with email fallback."""
    normalized_id = normalize_planner_id(planner_id)
    normalized_email = normalize_planner_email(planner_email)

    clauses: list[dict] = []
    if normalized_id:
        clauses.append({"assigned_planner_id": normalized_id})
    if normalized_email:
        clauses.append({"assigned_planner_email": normalized_email})

    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


def build_team_owner_query(owner_id: Any = None, owner_email: Any = None) -> dict:
    """Build a query that matches team-membership ownership by id with email fallback."""
    normalized_id = normalize_planner_id(owner_id)
    normalized_email = normalize_planner_email(owner_email)

    clauses: list[dict] = []
    if normalized_id:
        clauses.append({"owner_id": normalized_id})
    if normalized_email:
        clauses.append({"owner_email": normalized_email})

    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


def combine_mongo_filters(*filters: Optional[dict]) -> dict:
    """Combine optional Mongo filters without losing existing $or clauses."""
    active_filters = [query for query in filters if query]
    if not active_filters:
        return {}
    if len(active_filters) == 1:
        return active_filters[0]
    return {"$and": active_filters}


def wedding_belongs_to_owner(
    wedding: Optional[dict], planner_id: Any = None, planner_email: Any = None
) -> bool:
    """Check whether a wedding document belongs to the given planner identity."""
    owner_id, owner_email = extract_wedding_owner_identity(wedding)
    normalized_id = normalize_planner_id(planner_id)
    normalized_email = normalize_planner_email(planner_email)

    return bool(
        (normalized_id and owner_id == normalized_id)
        or (normalized_email and owner_email == normalized_email)
    )


async def resolve_planner_email(
    planner_id: Any = None, planner_email: Any = None
) -> Optional[str]:
    """Resolve a planner email, preferring the provided email before a user lookup."""
    normalized_email = normalize_planner_email(planner_email)
    if normalized_email:
        return normalized_email

    normalized_id = normalize_planner_id(planner_id)
    if not normalized_id:
        return None

    user = await mongo.get_users_collection().find_one(
        {"_id": normalize_query_id(normalized_id)},
        {"email": 1},
    )
    return normalize_planner_email(user.get("email")) if user else None


async def resolve_planner_id(
    planner_id: Any = None, planner_email: Any = None
) -> Optional[str]:
    """Resolve a planner id, preferring the provided id before an email lookup."""
    normalized_id = normalize_planner_id(planner_id)
    if normalized_id:
        return normalized_id

    normalized_email = normalize_planner_email(planner_email)
    if not normalized_email:
        return None

    user = await mongo.get_users_collection().find_one(
        {"email": normalized_email},
        {"_id": 1},
    )
    return normalize_planner_id(user.get("_id")) if user else None


async def resolve_planner_identity(
    planner_id: Any = None, planner_email: Any = None
) -> dict:
    """Resolve a full planner identity payload from either canonical field."""
    resolved_id = await resolve_planner_id(planner_id, planner_email)
    resolved_email = await resolve_planner_email(resolved_id, planner_email)
    return {
        "planner_id": resolved_id,
        "planner_email": resolved_email,
    }


async def get_wedding_owner_identity(
    wedding_id: Any, weddings_collection=None
) -> tuple[Optional[str], Optional[str]]:
    """Load the planner owner identity for a wedding."""
    collection = weddings_collection or mongo.get_weddings_collection()
    wedding = await collection.find_one(
        {"_id": normalize_query_id(wedding_id)},
        {"assigned_planner_id": 1, "assigned_planner_email": 1},
    )
    return extract_wedding_owner_identity(wedding)


async def resolve_wedding_owner_identity(wedding: Optional[dict]) -> dict:
    """Resolve a canonical planner identity payload from a wedding document."""
    planner_id, planner_email = extract_wedding_owner_identity(wedding)
    return await resolve_planner_identity(planner_id, planner_email)


async def list_wedding_ids_for_owner(
    planner_id: Any = None,
    planner_email: Any = None,
    accessible_wedding_ids: Optional[Sequence[str]] = None,
    weddings_collection=None,
) -> list[str]:
    """Return wedding ids owned by a planner, optionally narrowed to an access list."""
    collection = weddings_collection or mongo.get_weddings_collection()
    owner_query = build_wedding_owner_query(
        planner_id=planner_id, planner_email=planner_email
    )
    if not owner_query:
        return []

    filters: list[dict] = [owner_query]
    if accessible_wedding_ids is not None:
        normalized_ids = [normalize_query_id(value) for value in accessible_wedding_ids]
        filters.append({"_id": {"$in": normalized_ids}})

    query = combine_mongo_filters(*filters)
    weddings = await collection.find(query, {"_id": 1}).to_list(length=None)
    return [str(wedding["_id"]) for wedding in weddings]
