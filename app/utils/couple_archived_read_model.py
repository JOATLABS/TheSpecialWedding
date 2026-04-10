from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.database import mongo
from app.utils.id_utils import to_str_id


async def get_archived_wedding_record(wedding_id: str) -> Optional[dict[str, Any]]:
    """Fetch the archived wedding snapshot for a wedding if one exists."""
    if not wedding_id:
        return None
    return await mongo.db["archived_weddings"].find_one(
        {"original_wedding_id": wedding_id}
    )


def get_archived_wedding_snapshot(archive: Optional[dict[str, Any]]) -> dict[str, Any]:
    return (archive or {}).get("wedding") or {}


def get_archived_registries(archive: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(get_archived_wedding_snapshot(archive).get("registries") or [])


def get_archived_faqs(archive: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(get_archived_wedding_snapshot(archive).get("faqs") or [])


def build_archived_guest_stats(archive: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return archived guest statistics using the same shape as the live dashboard."""
    guests = list((archive or {}).get("guests") or [])
    rsvps = list((archive or {}).get("rsvps") or [])
    wedding = get_archived_wedding_snapshot(archive)

    guest_list_total = len(guests)
    planned_total = max(int(wedding.get("guest_count") or 0), guest_list_total)
    invited = sum(1 for guest in guests if guest.get("invite_sent"))

    confirmed = 0
    declined = 0
    responded_guest_ids: set[str] = set()
    event_counts: dict[str, int] = {}

    for rsvp in rsvps:
        guest_id = to_str_id(rsvp.get("guest_id"))
        if guest_id:
            responded_guest_ids.add(guest_id)

        attending_events = _normalize_attending_events(rsvp)
        if attending_events:
            confirmed += 1
            for event_type in attending_events:
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
        else:
            declined += 1

    responded = len(responded_guest_ids)
    pending = sum(
        1
        for guest in guests
        if guest.get("invite_sent") and to_str_id(guest) not in responded_guest_ids
    )
    not_invited = sum(
        1
        for guest in guests
        if not guest.get("invite_sent") and to_str_id(guest) not in responded_guest_ids
    )
    response_rate = (
        min(100.0, round((responded / invited) * 100, 1)) if invited > 0 else 0.0
    )

    configured_events = wedding.get("events") or []
    ordered_event_types: list[str] = []
    event_dates: dict[str, str] = {}
    event_labels: dict[str, str] = {}
    for event in configured_events:
        event_type = event.get("type")
        if event_type and event_type not in ordered_event_types:
            ordered_event_types.append(event_type)
            if event.get("date"):
                event_dates[event_type] = event.get("date")
            if event.get("custom_type_label"):
                event_labels[event_type] = event.get("custom_type_label")

    for event_type in event_counts:
        if event_type not in ordered_event_types:
            ordered_event_types.append(event_type)

    event_breakdown = [
        {
            "event_type": event_type,
            "custom_type_label": event_labels.get(event_type),
            "date": event_dates.get(event_type),
            "attending": event_counts.get(event_type, 0),
        }
        for event_type in ordered_event_types
    ]

    return {
        "planned_total": planned_total,
        "guest_list_total": guest_list_total,
        "invited": invited,
        "responded": responded,
        "confirmed": confirmed,
        "declined": declined,
        "pending": pending,
        "not_invited": not_invited,
        "response_rate": response_rate,
        "event_breakdown": event_breakdown,
    }


def build_archived_non_responders(
    archive: Optional[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reconstruct the couple non-responder list from archived guest and RSVP data."""
    now = datetime.now(timezone.utc)
    guests = list((archive or {}).get("guests") or [])
    rsvps = list((archive or {}).get("rsvps") or [])
    responded_ids = {
        to_str_id(rsvp.get("guest_id"))
        for rsvp in rsvps
        if rsvp.get("guest_id") is not None
    }

    non_responders: list[dict[str, Any]] = []
    for guest in guests:
        if not guest.get("invite_sent"):
            continue

        guest_id = to_str_id(guest)
        if not guest_id or guest_id in responded_ids:
            continue

        invite_date = _coerce_datetime(guest.get("invite_sent_date"))
        days_since = (now - invite_date).days if invite_date else None

        non_responders.append(
            {
                "guest_id": guest_id,
                "name": guest.get("name", ""),
                "email": guest.get("email"),
                "phone": guest.get("phone"),
                "invite_sent_date": _serialize_datetime(invite_date),
                "days_since_invite": days_since,
                "group_id": guest.get("group_id"),
            }
        )

    non_responders.sort(
        key=lambda guest: (
            guest["days_since_invite"] if guest["days_since_invite"] is not None else -1
        ),
        reverse=True,
    )
    return non_responders


def build_archived_budget_breakdown(
    archive: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Return a budget-breakdown-shaped archived payload from stored budget data."""
    budget_doc = (archive or {}).get("budget") or {}
    categories = list(budget_doc.get("categories") or [])

    breakdown: list[dict[str, Any]] = []
    total_budgeted = 0.0
    total_spent = 0.0
    for category in categories:
        budgeted = float(category.get("budgeted_amount", 0) or 0)
        spent = float(category.get("actual_spent", 0) or 0)
        total_budgeted += budgeted
        total_spent += spent
        breakdown.append(
            {
                "category_id": to_str_id(category),
                "name": category.get("name", ""),
                "budgeted": budgeted,
                "spent": spent,
                "remaining": round(budgeted - spent, 2),
                "percent_of_total_budget": 0.0,
                "percent_spent": (
                    round(spent / budgeted * 100, 1) if budgeted > 0 else 0.0
                ),
                "payment_status": category.get("payment_status", "pending"),
                "priority": category.get("priority", 1),
            }
        )

    stored_total_budget = float(budget_doc.get("total_budget", 0) or 0)
    stored_total_spent = float(
        budget_doc.get("total_spent", budget_doc.get("spent_total", 0)) or 0
    )
    if stored_total_budget > total_budgeted:
        total_budgeted = stored_total_budget
    if stored_total_spent > total_spent:
        total_spent = stored_total_spent

    for category in breakdown:
        category["percent_of_total_budget"] = (
            round(category["budgeted"] / total_budgeted * 100, 1)
            if total_budgeted > 0
            else 0.0
        )

    breakdown.sort(key=lambda category: category["budgeted"], reverse=True)
    total_remaining = round(max(total_budgeted - total_spent, 0), 2)
    return {
        "total_budgeted": round(total_budgeted, 2),
        "total_spent": round(total_spent, 2),
        "total_remaining": total_remaining,
        "percent_spent": (
            round(total_spent / total_budgeted * 100, 1) if total_budgeted > 0 else 0.0
        ),
        "categories": breakdown,
        "category_count": len(breakdown),
    }


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    return None


def _serialize_datetime(value: Any) -> Optional[str]:
    dt = _coerce_datetime(value)
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_attending_events(rsvp: dict[str, Any]) -> list[str]:
    attending = rsvp.get("attending")
    if isinstance(attending, list):
        return [event for event in attending if isinstance(event, str) and event]
    if isinstance(attending, dict):
        return [event for event, is_attending in attending.items() if is_attending]
    return []
