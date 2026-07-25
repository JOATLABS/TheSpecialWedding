from collections.abc import Iterable
from typing import Any

ALL_WEDDING_EVENTS = "all"


def normalize_event_type(event_type: str) -> str:
    if not isinstance(event_type, str):
        raise ValueError("Event type must be a string")

    normalized = event_type.strip()
    if not normalized:
        raise ValueError("Event type cannot be empty")
    if len(normalized) > 100:
        raise ValueError("Event type is too long")

    return normalized


def is_all_wedding_events(event_type: str) -> bool:
    return (
        isinstance(event_type, str) and event_type.strip().lower() == ALL_WEDDING_EVENTS
    )


def normalize_reminder_event_type(event_type: str) -> str:
    normalized = normalize_event_type(event_type)
    return ALL_WEDDING_EVENTS if is_all_wedding_events(normalized) else normalized


def normalize_attending_event_types(attending: Any) -> list[str]:
    if isinstance(attending, str):
        attending_values: Iterable[Any] = [attending]
    elif isinstance(attending, dict):
        attending_values = [
            event_type for event_type, is_attending in attending.items() if is_attending
        ]
    elif isinstance(attending, Iterable):
        attending_values = attending
    else:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for event_type in attending_values:
        if not isinstance(event_type, str):
            continue
        value = event_type.strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def attending_matches_reminder_event(attending: Any, event_type: str) -> bool:
    normalized_event_type = normalize_reminder_event_type(event_type)
    attending_events = normalize_attending_event_types(attending)
    if is_all_wedding_events(normalized_event_type):
        return len(attending_events) > 0
    return normalized_event_type in attending_events


def normalize_event_type_list(event_types: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for event_type in event_types:
        value = normalize_event_type(event_type)
        if value not in seen:
            normalized.append(value)
            seen.add(value)

    return normalized
