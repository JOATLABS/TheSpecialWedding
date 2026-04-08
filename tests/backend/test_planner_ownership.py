from bson import ObjectId

from app.utils.planner_ownership import (
    build_team_owner_query,
    build_wedding_owner_query,
    combine_mongo_filters,
    extract_wedding_owner_identity,
    normalize_planner_email,
    normalize_planner_id,
    normalize_wedding_query_id,
    wedding_belongs_to_owner,
)


def test_normalize_planner_fields_trim_and_lowercase() -> None:
    assert normalize_planner_id(" 507f1f77bcf86cd799439011 ") == "507f1f77bcf86cd799439011"
    assert normalize_planner_email(" Planner@Example.com ") == "planner@example.com"


def test_build_wedding_owner_query_prefers_id_and_email_for_compatibility() -> None:
    query = build_wedding_owner_query(
        planner_id="507f1f77bcf86cd799439011",
        planner_email="planner@example.com",
    )
    assert query == {
        "$or": [
            {"assigned_planner_id": "507f1f77bcf86cd799439011"},
            {"assigned_planner_email": "planner@example.com"},
        ]
    }


def test_build_team_owner_query_handles_single_identifier() -> None:
    assert build_team_owner_query(owner_id="owner-1") == {"owner_id": "owner-1"}
    assert build_team_owner_query(owner_email="planner@example.com") == {
        "owner_email": "planner@example.com"
    }


def test_combine_mongo_filters_preserves_existing_or_clauses() -> None:
    owner_filter = {"$or": [{"assigned_planner_id": "planner-123"}]}
    search_filter = {"$or": [{"name": {"$regex": "smith", "$options": "i"}}]}

    assert combine_mongo_filters(owner_filter, search_filter) == {
        "$and": [owner_filter, search_filter]
    }


def test_extract_wedding_owner_identity_normalizes_values() -> None:
    wedding = {
        "assigned_planner_id": ObjectId("507f1f77bcf86cd799439011"),
        "assigned_planner_email": " Planner@Example.com ",
    }

    assert extract_wedding_owner_identity(wedding) == (
        "507f1f77bcf86cd799439011",
        "planner@example.com",
    )


def test_wedding_belongs_to_owner_matches_id_or_email() -> None:
    wedding = {
        "assigned_planner_id": "507f1f77bcf86cd799439011",
        "assigned_planner_email": "planner@example.com",
    }
    assert wedding_belongs_to_owner(
        wedding,
        planner_id="507f1f77bcf86cd799439011",
        planner_email=None,
    )
    assert wedding_belongs_to_owner(
        wedding,
        planner_id=None,
        planner_email="planner@example.com",
    )


def test_normalize_wedding_query_id_returns_object_id_for_hex() -> None:
    normalized = normalize_wedding_query_id("507f1f77bcf86cd799439011")
    assert isinstance(normalized, ObjectId)
    assert str(normalized) == "507f1f77bcf86cd799439011"
