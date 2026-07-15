"""Canonical kinds and query scopes for records in ``support_tickets``."""

from typing import Any, Mapping

CONVERSATION_KIND_FIELD = "conversation_kind"
PLATFORM_SUPPORT_KIND = "platform_support"
GUEST_SMS_KIND = "guest_sms"
UNKNOWN_SUPPORT_KIND = "unknown"


def platform_support_ticket_scope(
    query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a query that can only match platform support conversations."""
    return {**(query or {}), CONVERSATION_KIND_FIELD: PLATFORM_SUPPORT_KIND}


def guest_sms_ticket_scope(
    query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a query that requires both canonical and legacy SMS markers."""
    return {
        **(query or {}),
        CONVERSATION_KIND_FIELD: GUEST_SMS_KIND,
        "source": "sms",
    }


def is_platform_support_ticket(ticket: Mapping[str, Any]) -> bool:
    return ticket.get(CONVERSATION_KIND_FIELD) == PLATFORM_SUPPORT_KIND


def support_actor_key(current_user: Any) -> str:
    """Return a stable participant key, falling back to normalized email."""
    user_data = getattr(current_user, "user_data", None) or {}
    user_id = str(user_data.get("_id") or "").strip()
    if user_id:
        return f"user:{user_id}"
    return f"email:{str(getattr(current_user, 'email', '')).strip().lower()}"


def support_ticket_owner_scope(current_user: Any) -> dict[str, Any]:
    """Match a participant by immutable id, with a legacy email fallback."""
    user_data = getattr(current_user, "user_data", None) or {}
    user_id = str(user_data.get("_id") or "").strip()
    email = str(getattr(current_user, "email", "")).strip().lower()
    legacy_scope = {
        "creator_user_id": {"$in": [None, ""]},
        "created_by": email,
    }
    if not user_id:
        return legacy_scope
    return {"$or": [{"creator_user_id": user_id}, legacy_scope]}


def actor_owns_support_ticket(ticket: Mapping[str, Any], current_user: Any) -> bool:
    """Check stable ownership before consulting the legacy email snapshot."""
    creator_user_id = str(ticket.get("creator_user_id") or "").strip()
    actor_user_data = getattr(current_user, "user_data", None) or {}
    actor_user_id = str(actor_user_data.get("_id") or "").strip()
    if creator_user_id:
        return bool(actor_user_id) and creator_user_id == actor_user_id
    return (
        str(ticket.get("created_by") or "").strip().lower()
        == str(getattr(current_user, "email", "")).strip().lower()
    )
