from __future__ import annotations

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.api import planner_metrics as planner_metrics_api
from app.dependencies.auth_extended import ExtendedAuthUser


def test_team_members_without_wedding_directory_permissions_are_blocked() -> None:
    user = ExtendedAuthUser("viewer@example.com", "team_member", {})
    user.team_permissions = {
        "view_analytics": True,
        "manage_wedding_settings": False,
        "manage_couple_portal": False,
    }

    with pytest.raises(HTTPException) as exc_info:
        planner_metrics_api._enforce_weddings_directory_access(user)

    assert exc_info.value.status_code == 403
    assert "weddings" in exc_info.value.detail.lower()


def test_team_members_with_couple_portal_access_can_open_wedding_directory() -> None:
    user = ExtendedAuthUser("portal@example.com", "team_member", {})
    user.team_permissions = {
        "manage_wedding_settings": False,
        "manage_couple_portal": True,
    }

    planner_metrics_api._enforce_weddings_directory_access(user)


def test_owned_weddings_query_uses_team_owner_identity_for_team_members() -> None:
    user = ExtendedAuthUser("team@example.com", "team_member", {})
    user.is_team_member = True
    user.parent_planner_id = "planner_123"
    user.team_owner_email = "planner@example.com"
    user.team_wedding_access = "all"
    user.team_assigned_wedding_ids = []

    (
        query,
        accessible_ids,
        owner_email,
    ) = planner_metrics_api._build_owned_weddings_query(user)

    assert accessible_ids is None
    assert owner_email == "planner@example.com"
    assert query == {
        "$and": [
            {
                "$or": [
                    {"assigned_planner_id": "planner_123"},
                    {"assigned_planner_email": "planner@example.com"},
                ]
            },
            {"status": {"$ne": "cancelled"}},
        ]
    }


def test_owned_weddings_query_preserves_string_assigned_wedding_ids() -> None:
    user = ExtendedAuthUser("team@example.com", "team_member", {})
    user.is_team_member = True
    user.parent_planner_id = "planner_123"
    user.team_owner_email = "planner@example.com"
    user.team_wedding_access = "assigned"
    user.team_assigned_wedding_ids = ["wedding_alpha", "507f1f77bcf86cd799439011"]

    (
        query,
        accessible_ids,
        owner_email,
    ) = planner_metrics_api._build_owned_weddings_query(user)

    assert accessible_ids == ["wedding_alpha", "507f1f77bcf86cd799439011"]
    assert owner_email == "planner@example.com"
    wedding_filter = query["$and"][1]
    assert wedding_filter == {
        "_id": {"$in": ["wedding_alpha", ObjectId("507f1f77bcf86cd799439011")]}
    }


def test_parse_date_safe_normalizes_naive_dates_to_utc() -> None:
    parsed = planner_metrics_api._parse_date_safe("2026-04-01")

    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_parse_date_safe_preserves_aware_datetimes_in_utc() -> None:
    parsed = planner_metrics_api._parse_date_safe("2026-04-01T12:00:00+00:00")

    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_planner_wedding_venue_normalizes_legacy_object_shape() -> None:
    venue = planner_metrics_api._normalize_planner_wedding_venue(
        {"name": "Verification Venue", "location": "123 Verification Lane"}
    )

    assert venue == "Verification Venue - 123 Verification Lane"


def test_planner_wedding_document_mapper_accepts_legacy_venue_shape() -> None:
    wedding = planner_metrics_api._planner_wedding_model_from_document(
        {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "couple_names": "Legacy Venue Couple",
            "date": "2026-10-18",
            "slug": "legacy-venue-couple",
            "venue": {
                "name": "Verification Venue",
                "location": "123 Verification Lane",
            },
        }
    )

    assert wedding.venue == "Verification Venue - 123 Verification Lane"
