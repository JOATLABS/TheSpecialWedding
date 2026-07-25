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
from typing import Any
from zoneinfo import ZoneInfo

from bson import ObjectId

from app.core.database import mongo
from app.models.calendar import ScheduleItemType
from app.models.calendar_connection import CalendarConnectionStatus
from app.models.team_member import TeamMemberStatus, resolve_team_permissions
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
    staff_email: str | None
    start: datetime
    end: datetime
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "staff_id": self.staff_id,
            "staff_email": self.staff_email,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "requires_approval": self.requires_approval,
        }


@dataclass(slots=True)
class _CandidateStaff:
    user_id: str
    user_email: str | None
    timezone: str
    requires_approval: bool = False


class AvailabilitySlotService:
    """Generate bookable slots from connected calendars."""

    def __init__(self) -> None:
        self.weddings_collection = mongo.get_weddings_collection()
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.users_collection = mongo.get_users_collection()
        self.team_members_collection = mongo.db["team_members"]

    async def _resolve_user_timezone(self, user_id: str) -> str:
        """Look up a user's preferred timezone, falling back to UTC.

        Without this, every staff member is treated as UTC and their working
        hours are interpreted in UTC — i.e., 9am-6pm UTC instead of 9am-6pm
        local time. The fallback chain is user record → DEFAULT_TIMEZONE.
        """
        if not user_id:
            return DEFAULT_TIMEZONE
        try:
            user_oid: Any = ObjectId(user_id)
        except Exception:
            user_oid = user_id
        doc = await self.users_collection.find_one({"_id": user_oid}, {"timezone": 1})
        if not doc:
            return DEFAULT_TIMEZONE
        tz_value = doc.get("timezone")
        if not isinstance(tz_value, str) or not tz_value.strip():
            return DEFAULT_TIMEZONE
        try:
            ZoneInfo(tz_value.strip())
        except Exception:
            return DEFAULT_TIMEZONE
        return tz_value.strip()

    async def _is_team_member_couple_bookable(
        self, owner_id: str, user_id: str
    ) -> bool:
        """Check the team-permissions ``couple_bookable`` flag.

        Returns True for the owner planner unconditionally — the owner is the
        source of truth and is not represented as a team_members row.
        """
        if not user_id or user_id == owner_id:
            return True
        doc = await self.team_members_collection.find_one(
            {
                "owner_id": owner_id,
                "user_id": user_id,
                "status": TeamMemberStatus.ACTIVE.value,
            }
        )
        if not doc:
            # No team_members row but the user owns a calendar connection in
            # the wedding scope — treat as bookable to preserve back-compat
            # for setups predating the team-management feature.
            return True
        permissions = resolve_team_permissions(
            doc.get("role", "viewer"),
            doc.get("custom_permissions"),
        )
        return bool(permissions.get("couple_bookable", False))

    async def _staff_requires_approval(
        self, owner_id: str, user_id: str, wedding_id: str
    ) -> bool:
        """Return True if any of the staff's writable, wedding-eligible
        connections has ``couple_booking_auto_confirm=False``.

        We err on the side of approval-required: if even one connection
        the booking might land on requires approval, the booking is held
        for the planner to confirm.
        """
        for conn in await self._bookable_connections_for_staff(
            owner_id, user_id, wedding_id
        ):
            if not conn.get("couple_booking_auto_confirm", True):
                return True
        return False

    def _connection_allows_meeting_booking(
        self, connection: dict[str, Any], wedding_id: str
    ) -> bool:
        allowed = {str(value) for value in connection.get("allowed_wedding_ids", [])}
        if allowed and str(wedding_id) not in allowed:
            return False
        allowed_item_types = {
            str(value)
            for value in connection.get("allowed_schedule_item_types", [])
            if value
        }
        if (
            allowed_item_types
            and ScheduleItemType.MEETING.value not in allowed_item_types
        ):
            return False
        return True

    async def _bookable_connections_for_staff(
        self, owner_id: str, user_id: str, wedding_id: str
    ) -> list[dict[str, Any]]:
        rows = await self.connections_collection.find(
            {
                "owner_planner_id": owner_id,
                "user_id": user_id,
                "is_writable": True,
                "sync_enabled": True,
                "connection_status": CalendarConnectionStatus.ACTIVE.value,
            }
        ).to_list(length=100)
        return [
            row
            for row in rows
            if self._connection_allows_meeting_booking(row, wedding_id)
        ]

    async def _resolve_candidate_staff(
        self,
        *,
        wedding_id: str,
        staff_id: str | None,
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
        if owner_id and await self._bookable_connections_for_staff(
            owner_id, owner_id, wedding_id
        ):
            candidates[owner_id] = _CandidateStaff(
                user_id=owner_id,
                user_email=owner_email,
                timezone=await self._resolve_user_timezone(owner_id),
                requires_approval=await self._staff_requires_approval(
                    owner_id, owner_id, wedding_id
                ),
            )

        async for conn in self.connections_collection.find(
            {
                "owner_planner_id": owner_id,
                "is_writable": True,
                "sync_enabled": True,
                "connection_status": CalendarConnectionStatus.ACTIVE.value,
            }
        ):
            connection_user_id = str(conn.get("user_id") or "")
            if not connection_user_id:
                continue
            if not self._connection_allows_meeting_booking(conn, wedding_id):
                continue
            if connection_user_id in candidates:
                continue
            if not await self._is_team_member_couple_bookable(
                owner_id or "", connection_user_id
            ):
                continue
            candidates[connection_user_id] = _CandidateStaff(
                user_id=connection_user_id,
                user_email=conn.get("user_email"),
                timezone=await self._resolve_user_timezone(connection_user_id),
                requires_approval=await self._staff_requires_approval(
                    owner_id or "", connection_user_id, wedding_id
                ),
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
    ) -> tuple[datetime, datetime] | None:
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
    def _coerce_aware_datetime(value: Any) -> datetime | None:
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
        range_start: datetime | None = None,
        range_end: datetime | None = None,
        staff_id: str | None = None,
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
        # Compute busy intervals per staff once, not once per (day × staff).
        busy_by_staff = {
            staff.user_id: self._busy_intervals_for_staff(events, staff.user_id)
            for staff in candidates
        }
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
                free = self._subtract_busy(
                    (window_start, window_end),
                    busy_by_staff[staff.user_id],
                    DEFAULT_BUFFER_MINUTES,
                )
                for slot_start, slot_end in self._chunk_into_slots(free, duration):
                    slots.append(
                        AvailabilitySlot(
                            staff_id=staff.user_id,
                            staff_email=staff.user_email,
                            start=slot_start,
                            end=slot_end,
                            requires_approval=staff.requires_approval,
                        )
                    )
            day_cursor = day_cursor + timedelta(days=1)

        slots.sort(key=lambda s: (s.start, s.staff_id))
        return slots


availability_slot_service = AvailabilitySlotService()
