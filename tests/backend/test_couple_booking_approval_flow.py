"""Unit tests for the couple-booking approval workflow scaffolding.

These tests cover the pure data-layer pieces — enums, role presets, aggregation
shapes, model defaults — that gate the approval flow, plus regression tests
for the round-2 audit defects (silent toggle drop in the connection update
service-layer allow-list, missing optimistic-concurrency check on the
accept/reject/approve/decline endpoints).
"""

from __future__ import annotations

import inspect
import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault("AURINKO_CLIENT_ID", "test-client-id")
os.environ.setdefault("AURINKO_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("AURINKO_OAUTH_STATE_SIGNING_KEY", "test-state-signing-key")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key")
os.environ.setdefault("ENVIRONMENT", "test")

from app.api import planner_calendar  # noqa: E402
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
from app.services import calendar_provider_service as provider_module  # noqa: E402
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


# ─── Regression tests for round-2 audit defects ───────────────────────────────


@pytest.mark.asyncio
async def test_update_connection_persists_couple_booking_auto_confirm(monkeypatch):
    """Regression for Q19: the service-layer ``update_connection`` allow-list
    used to drop ``couple_booking_auto_confirm`` silently because the
    Pydantic update-request model accepted it but the persistence layer's
    hardcoded set didn't include it. Toggling the field in the planner UI
    appeared to succeed but the field never reached MongoDB.
    """
    from bson import ObjectId

    from app.services.calendar_provider_service import calendar_provider_service

    connection_id = str(ObjectId())
    seeded_doc: dict = {
        "_id": ObjectId(connection_id),
        "owner_planner_id": "owner-1",
        "owner_planner_email": "owner@example.com",
        "user_id": "owner-1",
        "user_email": "owner@example.com",
        "calendar_name": "Primary",
        "is_writable": True,
        "couple_booking_auto_confirm": True,
    }

    captured_set: dict = {}

    class _FakeCollection:
        async def update_one(self, filter_doc, update_doc):
            captured_set.update(update_doc.get("$set", {}))
            seeded_doc.update(update_doc.get("$set", {}))

            class _Result:
                modified_count = 1

            return _Result()

        async def find_one(self, *args, **kwargs):
            return seeded_doc

    fake = _FakeCollection()
    monkeypatch.setattr(calendar_provider_service, "connections_collection", fake)
    monkeypatch.setattr(
        calendar_provider_service,
        "_serialize_connection",
        lambda doc: doc,
    )

    await calendar_provider_service.update_connection(
        connection_id,
        {"couple_booking_auto_confirm": False},
        actor_email="owner@example.com",
        actor_role="planner",
    )
    assert captured_set.get("couple_booking_auto_confirm") is False, (
        "couple_booking_auto_confirm must reach the $set doc — the planner "
        "toggle is otherwise silently dropped at the service layer."
    )


@pytest.mark.parametrize(
    "endpoint_name",
    [
        "accept_meeting_external_change",
        "reject_meeting_external_change",
        "approve_couple_booking",
        "decline_couple_booking",
    ],
)
def test_meeting_resolution_endpoints_require_expected_version(
    endpoint_name: str,
) -> None:
    """Regression for Q14: accept / reject / approve / decline must each take
    a required ``expected_version`` so a stale UI cannot clobber concurrent
    webhook updates. Other meeting mutation endpoints in the same file (e.g.
    update_meeting) already enforce this — these four originally did not."""
    endpoint = getattr(planner_calendar, endpoint_name)
    sig = inspect.signature(endpoint)
    assert "expected_version" in sig.parameters, (
        f"{endpoint_name} must accept an expected_version parameter for "
        "optimistic concurrency. Without it, a stale UI click can race a "
        "concurrent webhook write and lose data."
    )
    param = sig.parameters["expected_version"]
    # The endpoint module uses ``from __future__ import annotations`` so the
    # annotation is the string "int" rather than the type object. Accept both.
    assert param.annotation in (int, "int"), (
        f"{endpoint_name} expected_version must be typed int."
    )
    # FastAPI Query(...) defaults marshal to a Query object; the parameter
    # default should not be Parameter.empty (which would mean no Query()
    # binding) and should not be a literal None (which would mean optional).
    assert param.default is not inspect.Parameter.empty, (
        f"{endpoint_name} expected_version must declare a Query(...) default."
    )
    assert param.default is not None, (
        f"{endpoint_name} expected_version must be required, not optional."
    )
