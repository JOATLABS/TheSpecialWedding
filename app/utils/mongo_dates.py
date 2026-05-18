from datetime import date, datetime, time, timezone
from typing import Any, Optional, Union

MongoDateLike = Optional[Union[date, datetime]]


def to_mongo_datetime(value: MongoDateLike) -> Optional[datetime]:
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
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def to_utc_datetime(value: Any) -> Optional[datetime]:
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
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

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
