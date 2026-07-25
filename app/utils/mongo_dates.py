from datetime import UTC, date, datetime, time
from typing import Any

MongoDateLike = date | datetime | None


def to_mongo_datetime(value: MongoDateLike) -> datetime | None:
    """
    Normalize date-like values into Mongo-safe UTC datetimes.

    MongoDB does not accept ``datetime.date`` instances directly. We store
    date-only values at midnight UTC so downstream code can still recover the
    intended calendar date reliably.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    return datetime.combine(value, time.min, tzinfo=UTC)


def to_utc_datetime(value: Any) -> datetime | None:
    """
    Normalize datetime-like values into timezone-aware UTC datetimes.

    PyMongo can return legacy stored datetimes without tzinfo even when newer
    code writes aware UTC values. Treat those naive values as UTC so comparison
    code does not crash on mixed historical data.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return to_utc_datetime(parsed)

    return None
