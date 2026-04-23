from __future__ import annotations

from typing import Any, Optional

from app.utils.id_utils import to_str_id
from app.utils.planner_ownership import normalize_query_id


def normalize_couple_id(value: Any) -> Optional[str]:
    """Normalize a couple record identifier into a stable string form."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def normalize_couple_email(value: Any) -> Optional[str]:
    """Normalize a couple email for consistent comparisons."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def get_couple_record_id(couple: dict) -> str:
    """Extract the canonical couple record id from a document."""
    couple_id = normalize_couple_id(to_str_id(couple))
    if not couple_id:
        raise ValueError("Couple record is missing a stable identifier")
    return couple_id


def build_couple_lookup_query(couple_id: Any) -> dict:
    """Build a Mongo lookup query for a couple record id."""
    normalized = normalize_couple_id(couple_id)
    if not normalized:
        return {}
    return {"_id": normalize_query_id(normalized)}


def build_couple_principal_key(couple_id: Any) -> str:
    """Build a stable namespaced key for couple-scoped realtime/push state."""
    normalized = normalize_couple_id(couple_id)
    if not normalized:
        raise ValueError("Couple id is required for principal key generation")
    return f"couple::{normalized}"


def get_couple_display_name(couple: dict) -> str:
    """Return a displayable name for a couple, falling back to email.

    Produces "Partner1 & Partner2" when both partner names exist, "Partner1"
    or "Partner2" when only one is present, and the couple's email address
    when neither partner name is set. The email fallback matches the
    behavior previously inlined at couple-messaging call sites.
    """
    partner1 = (couple.get("partner1_name") or "").strip()
    partner2 = (couple.get("partner2_name") or "").strip()

    if partner1 and partner2:
        return f"{partner1} & {partner2}"
    if partner1:
        return partner1
    if partner2:
        return partner2
    return str(couple.get("email") or "").strip()


def list_couple_identity_keys(couple: dict) -> list[str]:
    """
    Return current and legacy identity keys for compatibility lookups.

    New realtime/push state is couple-record keyed. The normalized email is kept
    temporarily as a fallback so existing subscriptions are still observable.
    """
    keys: list[str] = []

    try:
        keys.append(build_couple_principal_key(get_couple_record_id(couple)))
    except ValueError:
        pass

    legacy_email = normalize_couple_email(couple.get("email"))
    if legacy_email and legacy_email not in keys:
        keys.append(legacy_email)

    return keys
