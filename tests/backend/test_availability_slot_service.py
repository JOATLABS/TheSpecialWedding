"""Unit tests for the slot-math primitives in availability_slot_service.

The full ``generate_slots`` pipeline integrates the aggregation service and
the planner DB; here we exercise the deterministic helpers (busy merging,
buffered subtraction, slot chunking) that don't touch the database.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("ENVIRONMENT", "test")

from app.services.availability_slot_service import (  # noqa: E402
    DEFAULT_BUFFER_MINUTES,
    AvailabilitySlotService,
)


def _dt(hour: int) -> datetime:
    """Build a fixed UTC datetime on 2026-05-06 at the given hour."""
    return datetime(2026, 5, 6, hour, 0, tzinfo=UTC)


def test_merge_intervals_combines_overlapping_ranges() -> None:
    intervals = [(_dt(9), _dt(10)), (_dt(9), _dt(11)), (_dt(13), _dt(14))]
    merged = AvailabilitySlotService._merge_intervals(intervals)
    assert merged == [(_dt(9), _dt(11)), (_dt(13), _dt(14))]


def test_merge_intervals_keeps_disjoint_ranges() -> None:
    intervals = [(_dt(9), _dt(10)), (_dt(11), _dt(12))]
    merged = AvailabilitySlotService._merge_intervals(intervals)
    assert merged == [(_dt(9), _dt(10)), (_dt(11), _dt(12))]


def test_subtract_busy_with_buffer_removes_blocked_window() -> None:
    service = AvailabilitySlotService.__new__(AvailabilitySlotService)
    free = service._subtract_busy(
        (_dt(9), _dt(18)),
        [(_dt(14), _dt(15))],
        buffer_minutes=DEFAULT_BUFFER_MINUTES,
    )
    # 14:00–15:00 plus 15-min buffer either side = 13:45–15:15 blocked.
    assert free == [(_dt(9), datetime(2026, 5, 6, 13, 45, tzinfo=UTC)),
                    (datetime(2026, 5, 6, 15, 15, tzinfo=UTC), _dt(18))]


def test_chunk_into_slots_yields_full_duration_slots() -> None:
    free = [(_dt(9), _dt(12))]
    slots = AvailabilitySlotService._chunk_into_slots(free, timedelta(minutes=60))
    assert len(slots) == 3
    assert slots[0] == (_dt(9), _dt(10))
    assert slots[2] == (_dt(11), _dt(12))


def test_chunk_into_slots_drops_partial_trailing_window() -> None:
    free = [(_dt(9), datetime(2026, 5, 6, 9, 45, tzinfo=UTC))]
    slots = AvailabilitySlotService._chunk_into_slots(free, timedelta(minutes=60))
    assert slots == []
