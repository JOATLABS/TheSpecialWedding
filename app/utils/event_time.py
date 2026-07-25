import re

TWELVE_HOUR_TIME_WITH_MINUTES = re.compile(
    r"^(0?[1-9]|1[0-2]):([0-5]\d)\s*([AP]M)$", re.IGNORECASE
)
TWELVE_HOUR_TIME_ON_THE_HOUR = re.compile(
    r"^(0?[1-9]|1[0-2])\s*([AP]M)$", re.IGNORECASE
)
TWENTY_FOUR_HOUR_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

EVENT_TIME_FORMAT_HINT = "Use a time like 3:00 PM, 3 PM, or 15:00."


def _format_normalized_event_time(hours24: int, minutes: int) -> str:
    normalized_hours = hours24 % 12 or 12
    period = "PM" if hours24 >= 12 else "AM"
    return f"{normalized_hours}:{minutes:02d} {period}"


def normalize_optional_event_time(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(EVENT_TIME_FORMAT_HINT)

    trimmed = " ".join(value.strip().split())
    if not trimmed:
        return None

    twelve_hour_with_minutes = TWELVE_HOUR_TIME_WITH_MINUTES.match(trimmed)
    if twelve_hour_with_minutes:
        hours = int(twelve_hour_with_minutes.group(1))
        minutes = int(twelve_hour_with_minutes.group(2))
        period = twelve_hour_with_minutes.group(3).upper()
        if period == "PM" and hours != 12:
            hours += 12
        if period == "AM" and hours == 12:
            hours = 0
        return _format_normalized_event_time(hours, minutes)

    twelve_hour_on_the_hour = TWELVE_HOUR_TIME_ON_THE_HOUR.match(trimmed)
    if twelve_hour_on_the_hour:
        hours = int(twelve_hour_on_the_hour.group(1))
        period = twelve_hour_on_the_hour.group(2).upper()
        if period == "PM" and hours != 12:
            hours += 12
        if period == "AM" and hours == 12:
            hours = 0
        return _format_normalized_event_time(hours, 0)

    twenty_four_hour = TWENTY_FOUR_HOUR_TIME.match(trimmed)
    if twenty_four_hour:
        hours = int(twenty_four_hour.group(1))
        minutes = int(twenty_four_hour.group(2))
        return _format_normalized_event_time(hours, minutes)

    raise ValueError(EVENT_TIME_FORMAT_HINT)
