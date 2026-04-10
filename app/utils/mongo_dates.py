from datetime import date, datetime, time, timezone
from typing import Optional, Union

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
