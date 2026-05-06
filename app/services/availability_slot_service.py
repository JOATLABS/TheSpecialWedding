"""Slot-generation layer for couple-initiated bookings.

The aggregation service returns *events*; couple booking needs *bookable
slots* derived by subtracting busy windows + buffers from working windows.
This service provides that thin layer over
``calendar_aggregation_service.build_shared_view``.

Working-hours / buffer / notice / horizon defaults live here in code.
Per-staff overrides are out of scope for v1 — TODO once a planner-profile
preferences UI exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.core.database import mongo
from app.services.calendar_aggregation_service import calendar_aggregation_service
from app.utils.planner_ownership import (
    extract_wedding_owner_identity,
    normalize_wedding_query_id,
)


# Defaults — Mon-Fri 9am-6pm in the staff's timezone.
DEFAULT_WORKING_HOURS_START = time(9, 0)
DEFAULT_WORKING_HOURS_END = time(18, 0)
DEFAULT_WORKING_DAYS = (0, 1, 2, 3, 4)  # Mon..Fri (Python weekday: Mon=0)
DEFAULT_BUFFER_MINUTES = 15
DEFAULT_MIN_NOTICE_HOURS = 24
DEFAULT_MAX_HORIZON_DAYS = 60
DEFAULT_TIMEZONE = "UTC"


@dataclass(slots=True)
class AvailabilitySlot:
    staff_id: str
    staff_email: Optional[str]
    start: datetime
    end: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "staff_id": self.staff_id,
            "staff_email": self.staff_email,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }


@dataclass(slots=True)
class _CandidateStaff:
    user_id: str
    user_email: Optional[str]
    timezone: str


class AvailabilitySlotService:
    """Generate bookable slots from connected calendars."""

    def __init__(self) -> None:
        self.weddings_collection = mongo.get_weddings_collection()
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.users_collection = mongo.get_users_collection()

    async def _resolve_candidate_staff(
        self,
        *,
        wedding_id: str,
        staff_id: Optional[str],
    ) -> tuple[list[_CandidateStaff], dict[str, Any]]:
        wedding = await self.weddings_collection.find_one(
            {"_id": normalize_wedding_query_id(wedding_id)}
        )
        if not wedding:
            raise ValueError(f"Wedding {wedding_id} not found")

        owner_id, owner_email = extract_wedding_owner_identity(wedding)

        # Owner is always a candidate. Team members are connection-row owners
        # whose `allowed_wedding_ids` includes this wedding (or empty list,
        # meaning "all weddings under this planner").
        candidates: dict[str, _CandidateStaff] = {}
        if owner_id:
            candidates[owner_id] = _CandidateStaff(
                user_id=owner_id,
                user_email=owner_email,
                timezone=DEFAULT_TIMEZONE,
            )

        async for conn in self.connections_collection.find(
            {"owner_planner_id": owner_id, "is_writable": True, "sync_enabled": True}
        ):
            connection_user_id = str(conn.get("user_id") or "")
            if not connection_user_id:
                continue
            allowed = conn.get("allowed_wedding_ids") or []
            if allowed and str(wedding_id) not in {str(v) for v in allowed}:
                continue
            existing = candidates.get(connection_user_id)
            if existing is None:
                candidates[connection_user_id] = _CandidateStaff(
                    user_id=connection_user_id,
                    user_email=conn.get("user_email"),
                    timezone=DEFAULT_TIMEZONE,
                )

        if staff_id is not None:
            if staff_id not in candidates:
                raise PermissionError(
                    f"Staff {staff_id} is not allowed for this wedding"
                )
            return [candidates[staff_id]], wedding

        return list(candidates.values()), wedding

    def _working_window(
        self,
        day: datetime,
        timezone_name: str,
    ) -> Optional[tuple[datetime, datetime]]:
        local = day.astimezone(ZoneInfo(timezone_name))
        if local.weekday() not in DEFAULT_WORKING_DAYS:
            return None
        start_local = local.replace(
            hour=DEFAULT_WORKING_HOURS_START.hour,
            minute=DEFAULT_WORKING_HOURS_START.minute,
            second=0,
            microsecond=0,
        )
        end_local = local.replace(
            hour=DEFAULT_WORKING_HOURS_END.hour,
            minute=DEFAULT_WORKING_HOURS_END.minute,
            second=0,
            microsecond=0,
        )
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    def _busy_intervals_for_staff(
        self,
        events: list[dict[str, Any]],
        staff_id: str,
    ) -> list[tuple[datetime, datetime]]:
        intervals: list[tuple[datetime, datetime]] = []
        for event in events:
            assigned = event.get("assigned_user_ids") or []
            if assigned and staff_id not in [str(v) for v in assigned]:
                continue
            start_value = event.get("start_date")
            end_value = event.get("end_date") or start_value
            start = self._coerce_aware_datetime(start_value)
            end = self._coerce_aware_datetime(end_value)
            if start is None or end is None:
                continue
            if event.get("all_day"):
                intervals.append((start, end + timedelta(days=1)))
            else:
                intervals.append((start, end))
        return self._merge_intervals(intervals)

    @staticmethod
    def _coerce_aware_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        return None

    @staticmethod
    def _merge_intervals(
        intervals: list[tuple[datetime, datetime]],
    ) -> list[tuple[datetime, datetime]]:
        if not intervals:
            return []
        intervals = sorted(intervals)
        merged = [intervals[0]]
        for start, end in intervals[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged

    def _subtract_busy(
        self,
        window: tuple[datetime, datetime],
        busy: list[tuple[datetime, datetime]],
        buffer_minutes: int,
    ) -> list[tuple[datetime, datetime]]:
        """Return free sub-windows after subtracting busy + buffer."""
        free: list[tuple[datetime, datetime]] = [window]
        buffer = timedelta(minutes=buffer_minutes)
        for busy_start, busy_end in busy:
            new_free: list[tuple[datetime, datetime]] = []
            block_start = busy_start - buffer
            block_end = busy_end + buffer
            for free_start, free_end in free:
                if block_end <= free_start or block_start >= free_end:
                    new_free.append((free_start, free_end))
                    continue
                if block_start > free_start:
                    new_free.append((free_start, block_start))
                if block_end < free_end:
                    new_free.append((block_end, free_end))
            free = new_free
        return free

    @staticmethod
    def _chunk_into_slots(
        free_windows: list[tuple[datetime, datetime]],
        duration: timedelta,
    ) -> list[tuple[datetime, datetime]]:
        slots: list[tuple[datetime, datetime]] = []
        for free_start, free_end in free_windows:
            cursor = free_start
            while cursor + duration <= free_end:
                slots.append((cursor, cursor + duration))
                cursor = cursor + duration
        return slots

    async def generate_slots(
        self,
        *,
        wedding_id: str,
        duration_minutes: int,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
        staff_id: Optional[str] = None,
    ) -> list[AvailabilitySlot]:
        """Return bookable slots for the wedding's allowed planner team.

        :raises ValueError: when the wedding doesn't exist.
        :raises PermissionError: when ``staff_id`` is not in the allowed team.
        """
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")

        now = datetime.now(UTC)
        min_start = now + timedelta(hours=DEFAULT_MIN_NOTICE_HOURS)
        max_end = now + timedelta(days=DEFAULT_MAX_HORIZON_DAYS)
        start = max(range_start or min_start, min_start)
        end = min(range_end or max_end, max_end)
        if end <= start:
            return []

        candidates, wedding = await self._resolve_candidate_staff(
            wedding_id=wedding_id, staff_id=staff_id
        )
        if not candidates:
            return []

        owner_id, owner_email = extract_wedding_owner_identity(wedding)
        events = await calendar_aggregation_service.build_shared_view(
            owner_id=owner_id or "",
            owner_email=owner_email,
            current_user_id=owner_id,
            include_all_owner_connections=True,
            can_view_details=False,
            accessible_wedding_ids=None,
            start=start,
            end=end,
            staff_ids=[c.user_id for c in candidates],
        )

        duration = timedelta(minutes=duration_minutes)
        slots: list[AvailabilitySlot] = []
        day_cursor = start
        while day_cursor < end:
            for staff in candidates:
                window = self._working_window(day_cursor, staff.timezone)
                if window is None:
                    continue
                window_start, window_end = window
                window_start = max(window_start, start)
                window_end = min(window_end, end)
                if window_end <= window_start:
                    continue
                busy = self._busy_intervals_for_staff(events, staff.user_id)
                free = self._subtract_busy(
                    (window_start, window_end), busy, DEFAULT_BUFFER_MINUTES
                )
                for slot_start, slot_end in self._chunk_into_slots(free, duration):
                    slots.append(
                        AvailabilitySlot(
                            staff_id=staff.user_id,
                            staff_email=staff.user_email,
                            start=slot_start,
                            end=slot_end,
                        )
                    )
            day_cursor = day_cursor + timedelta(days=1)

        slots.sort(key=lambda s: (s.start, s.staff_id))
        return slots


availability_slot_service = AvailabilitySlotService()
