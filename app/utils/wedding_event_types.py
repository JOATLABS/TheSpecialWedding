from typing import Iterable, List


def normalize_event_type(event_type: str) -> str:
    if not isinstance(event_type, str):
        raise ValueError("Event type must be a string")

    normalized = event_type.strip()
    if not normalized:
        raise ValueError("Event type cannot be empty")
    if len(normalized) > 100:
        raise ValueError("Event type is too long")

    return normalized


def normalize_event_type_list(event_types: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()

    for event_type in event_types:
        value = normalize_event_type(event_type)
        if value not in seen:
            normalized.append(value)
            seen.add(value)

    return normalized
