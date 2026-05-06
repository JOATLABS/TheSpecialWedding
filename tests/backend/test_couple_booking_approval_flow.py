"""Unit tests for the couple-booking approval workflow scaffolding.

These tests cover the pure data-layer pieces — enums, role presets, aggregation
shapes, model defaults — that gate the approval flow. End-to-end coverage of
the planner API endpoints belongs alongside the existing planner_calendar
integration tests once the test harness for booted FastAPI lives in this repo.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

os.environ.setdefault("ENVIRONMENT", "test")

from app.models.calendar import MeetingLifecycleStatus  # noqa: E402
from app.models.calendar_connection import CalendarConnectionModel  # noqa: E402
from app.models.planner_notification import (  # noqa: E402
    PlannerNotificationTypes,
)
from app.models.team_member import (  # noqa: E402
    ROLE_PRESETS,
    TeamPermissions,
    resolve_team_permissions,
)
from app.services.calendar_aggregation_service import (  # noqa: E402
    calendar_aggregation_service,
)


def test_meeting_lifecycle_status_includes_pending_approval() -> None:
    assert MeetingLifecycleStatus.PENDING_APPROVAL.value == "pending_approval"
    # Order is preserved (PENDING_APPROVAL precedes SCHEDULED).
    statuses = [member.value for member in MeetingLifecycleStatus]
    assert statuses.index("pending_approval") < statuses.index("scheduled")


def test_calendar_connection_couple_booking_auto_confirm_defaults_true() -> None:
    connection = CalendarConnectionModel.model_validate(
        {
            "_id": "abc123",
            "owner_planner_id": "owner",
            "owner_planner_email": "owner@example.com",
            "user_id": "user",
            "user_email": "user@example.com",
            "provider_account_email": "user@example.com",
            "aurinko_account_id": "acc1",
            "aurinko_calendar_id": "cal1",
            "calendar_id": "cal1",
            "calendar_name": "Primary",
        }
    )
    assert connection.couple_booking_auto_confirm is True


def test_role_presets_define_couple_bookable_and_approval_keys() -> None:
    # Defaults across the three presets follow the design: viewer is opted out
    # of both, editor and admin are opted in.
    assert ROLE_PRESETS["admin"]["couple_bookable"] is True
    assert ROLE_PRESETS["admin"]["approve_couple_bookings"] is True
    assert ROLE_PRESETS["editor"]["couple_bookable"] is True
    assert ROLE_PRESETS["editor"]["approve_couple_bookings"] is True
    assert ROLE_PRESETS["viewer"]["couple_bookable"] is False
    assert ROLE_PRESETS["viewer"]["approve_couple_bookings"] is False


def test_resolve_team_permissions_supports_couple_bookable_overrides() -> None:
    # Planner overrides the viewer preset to opt this team member into bookings.
    resolved = resolve_team_permissions(
        "viewer", {"couple_bookable": True, "approve_couple_bookings": True}
    )
    assert resolved["couple_bookable"] is True
    assert resolved["approve_couple_bookings"] is True

    # Planner opts an editor *out* of being bookable while preserving other perms.
    resolved = resolve_team_permissions(
        "editor", {"couple_bookable": False}
    )
    assert resolved["couple_bookable"] is False
    assert resolved["approve_couple_bookings"] is True


def test_team_permissions_pydantic_model_exposes_new_keys() -> None:
    perms = TeamPermissions(couple_bookable=True, approve_couple_bookings=True)
    assert perms.has_permission("couple_bookable") is True
    assert perms.has_permission("approve_couple_bookings") is True

    serialized = perms.to_dict()
    assert "couple_bookable" in serialized
    assert "approve_couple_bookings" in serialized


def test_planner_notification_types_define_meeting_booking_request() -> None:
    assert (
        PlannerNotificationTypes.MEETING_BOOKING_REQUEST == "meeting_booking_request"
    )


def test_aggregation_internal_event_surfaces_external_conflict_snapshot() -> None:
    """The planner UI reads ``details.external_*`` fields to render the
    "modified externally" tray. The aggregation must serialize them."""
    task = {
        "_id": "task1",
        "title": "Tasting",
        "start_date": datetime(2026, 5, 6, 14, 0, tzinfo=UTC),
        "end_date": datetime(2026, 5, 6, 15, 0, tzinfo=UTC),
        "external_conflict_status": "pending_review",
        "external_conflict_source": "webhook",
        "external_conflict_detected_at": datetime(2026, 5, 6, 13, 0, tzinfo=UTC),
        "external_start_date": datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        "external_end_date": datetime(2026, 5, 6, 17, 0, tzinfo=UTC),
        "external_title": "Tasting (moved by chef)",
        "external_description": "Vendor pushed it.",
        "external_location": "Vendor kitchen",
        "external_last_modified_at": datetime(2026, 5, 6, 12, 30, tzinfo=UTC),
        "version": 4,
    }
    normalized = calendar_aggregation_service._normalize_internal(task)
    details = normalized["details"]
    assert details["external_conflict_status"] == "pending_review"
    assert details["external_conflict_source"] == "webhook"
    assert details["external_title"] == "Tasting (moved by chef)"
    assert details["external_description"] == "Vendor pushed it."
    assert details["external_location"] == "Vendor kitchen"
    # Datetimes are serialized as ISO strings so the JSON response from the
    # planner_calendar API is renderable on the client without coercion.
    assert isinstance(details["external_start_date"], str)
    assert details["external_start_date"].startswith("2026-05-06T16:00")
    assert isinstance(details["external_end_date"], str)
    assert isinstance(details["external_last_modified_at"], str)
    assert isinstance(details["external_conflict_detected_at"], str)
    assert details["version"] == 4
