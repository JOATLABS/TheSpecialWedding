import os
import sys
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.utils.mongo_dates import to_utc_datetime  # noqa: E402


def test_to_utc_datetime_treats_naive_mongo_datetime_as_utc():
    value = datetime(2026, 5, 18, 12, 30, 45)

    assert to_utc_datetime(value) == datetime(
        2026, 5, 18, 12, 30, 45, tzinfo=timezone.utc
    )


def test_to_utc_datetime_normalizes_aware_datetime_to_utc():
    value = datetime(2026, 5, 18, 7, 30, tzinfo=timezone(timedelta(hours=-5)))

    assert to_utc_datetime(value) == datetime(2026, 5, 18, 12, 30, tzinfo=timezone.utc)


def test_to_utc_datetime_parses_iso_strings_and_z_suffix():
    assert to_utc_datetime("2026-05-18T12:30:00Z") == datetime(
        2026, 5, 18, 12, 30, tzinfo=timezone.utc
    )
    assert to_utc_datetime("2026-05-18T07:30:00-05:00") == datetime(
        2026, 5, 18, 12, 30, tzinfo=timezone.utc
    )


def test_to_utc_datetime_returns_none_for_invalid_values():
    assert to_utc_datetime("") is None
    assert to_utc_datetime("not-a-date") is None
    assert to_utc_datetime(object()) is None
