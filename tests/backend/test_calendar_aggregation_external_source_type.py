"""Tests for the aggregation service's external-event normalization.

Verifies that external events emit the canonical ``source_type='external'``
plus an ``external_provider`` sub-field, replacing the old
``source_type='external_google'`` shape.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

from app.services.calendar_aggregation_service import (  # noqa: E402
    calendar_aggregation_service,
)


def test_normalize_external_emits_provider_neutral_source_type() -> None:
    event = {
        "id": "evt-1",
        "summary": "Standup",
        "start": {"dateTime": "2026-05-06T15:00:00+00:00"},
        "end": {"dateTime": "2026-05-06T16:00:00+00:00"},
        "_connection": {
            "id": "conn-1",
            "provider": "office365",
            "details_visibility": "details",
            "calendar_name": "Work",
            "provider_account_email": "u@example.com",
            "user_id": "u1",
            "user_email": "u@example.com",
            "owner_planner_email": "owner@example.com",
        },
    }

    normalized = calendar_aggregation_service._normalize_external(event, can_view_details=True)

    assert normalized["source_type"] == "external"
    assert normalized["external_provider"] == "office365"
    assert normalized["title"] == "Standup"
    assert normalized["start_date"] == "2026-05-06T15:00:00+00:00"


def test_normalize_external_hides_details_when_busy_only() -> None:
    event = {
        "id": "evt-2",
        "summary": "Sensitive",
        "description": "Hidden notes",
        "start": {"dateTime": "2026-05-06T15:00:00+00:00"},
        "end": {"dateTime": "2026-05-06T16:00:00+00:00"},
        "_connection": {
            "id": "conn-2",
            "provider": "google",
            "details_visibility": "busy_only",
            "calendar_name": "Personal",
            "provider_account_email": "u@example.com",
            "user_id": "u2",
            "user_email": "u@example.com",
            "owner_planner_email": "owner@example.com",
        },
    }

    normalized = calendar_aggregation_service._normalize_external(event, can_view_details=True)

    assert normalized["title"] == "Busy"
    assert normalized["details"]["description"] is None


def test_wants_external_filter_accepts_canonical_label_only() -> None:
    assert calendar_aggregation_service._wants_external(None) is True
    assert calendar_aggregation_service._wants_external([]) is True
    assert calendar_aggregation_service._wants_external(["external"]) is True
    assert calendar_aggregation_service._wants_external(["internal_task"]) is False
    # Greenfield: no users on the legacy label, so it is not honored.
    assert calendar_aggregation_service._wants_external(["external_google"]) is False
