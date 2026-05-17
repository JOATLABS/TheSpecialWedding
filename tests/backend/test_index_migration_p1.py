"""Static checks on the P1 index migration script.

These tests catch authoring mistakes (duplicate names, malformed TTL
specs, partial-filter operator violations) at PR time rather than at
migration runtime against a real Mongo. They explicitly do not run the
migration — that requires a live database and is exercised manually
via ``python scripts/create_indexes_p1_forms_and_ai.py --dry-run`` per
the project README.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_indexes_p1_forms_and_ai.py"


def _load_indexes_module():
    spec = importlib.util.spec_from_file_location("_p1_index_migration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def indexes():
    return _load_indexes_module().INDEXES


def test_index_count_matches_audit_target(indexes):
    """The audit identified 14 indexes (the 5-key reminder compound
    counts as one), plus 3 P1 follow-ups for planner_notifications,
    team_members, and form_distributions per-recipient dedup. Guards
    against accidental drops in future refactors."""
    assert len(indexes) == 17


def test_planner_notifications_unread_recent_index_present(indexes):
    """get_notifications + get_notification_count rely on a compound
    over (planner_id, is_read, created_at desc) — see
    planner_notification_service.py:267-268, 281-283."""
    matches = [
        (collection, spec, kwargs)
        for collection, spec, kwargs in indexes
        if collection == "planner_notifications"
        and spec == [("planner_id", 1), ("is_read", 1), ("created_at", -1)]
    ]
    assert len(matches) == 1, "missing planner_notifications unread-recent index"
    _, _, kwargs = matches[0]
    assert kwargs.get("name") == "idx_planner_unread_recent"
    assert "expireAfterSeconds" not in kwargs, (
        "planner_notifications index must not be TTL"
    )


def test_team_members_owner_status_index_present(indexes):
    """_resolve_team_recipients fan-out scans by (owner_email, status)
    — see planner_notification_service.py:530-537."""
    matches = [
        (collection, spec, kwargs)
        for collection, spec, kwargs in indexes
        if collection == "team_members" and spec == [("owner_email", 1), ("status", 1)]
    ]
    assert len(matches) == 1, "missing team_members owner+status index"
    _, _, kwargs = matches[0]
    assert kwargs.get("name") == "idx_owner_status"
    assert "expireAfterSeconds" not in kwargs, "team_members index must not be TTL"


def test_form_distributions_recipient_dedup_index_present(indexes):
    """send_form's per-recipient dedup loop hits
    form_distributions.find_one({form_id, recipient_email}) — see
    form_service.py:885."""
    matches = [
        (collection, spec, kwargs)
        for collection, spec, kwargs in indexes
        if collection == "form_distributions"
        and spec == [("form_id", 1), ("recipient_email", 1)]
    ]
    assert len(matches) == 1, "missing form_distributions per-recipient index"
    _, _, kwargs = matches[0]
    assert kwargs.get("name") == "idx_form_recipient"
    assert "expireAfterSeconds" not in kwargs, (
        "form_distributions per-recipient index must not be TTL"
    )


def test_every_index_has_a_name(indexes):
    for collection, spec, kwargs in indexes:
        assert "name" in kwargs, f"{collection} {spec} is missing name"
        assert isinstance(kwargs["name"], str)
        assert kwargs["name"]


def test_index_names_are_unique(indexes):
    names = [kwargs["name"] for _, _, kwargs in indexes]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"duplicate index names: {duplicates}"


def test_no_duplicate_collection_key_pairs(indexes):
    seen = set()
    for collection, spec, _ in indexes:
        key = (collection, tuple(spec))
        assert key not in seen, f"duplicate (collection, spec): {key}"
        seen.add(key)


def test_ttl_indexes_carry_expire_after_seconds(indexes):
    """marketing_leads, ai_usage_log, ai_cache.expires_at all need a
    documented expireAfterSeconds value (per
    https://www.mongodb.com/docs/manual/core/index-ttl/)."""
    ttl_specs = [
        (collection, kwargs)
        for collection, _, kwargs in indexes
        if "expireAfterSeconds" in kwargs
    ]
    assert len(ttl_specs) == 3, "expected exactly 3 TTL indexes"
    expected = {
        "marketing_leads": 60 * 60 * 24 * 90,  # 90 days
        "ai_usage_log": 60 * 60 * 24 * 30,  # 30 days
        "ai_cache": 0,  # field-based: delete when datetime passes
    }
    for collection, kwargs in ttl_specs:
        assert kwargs["expireAfterSeconds"] == expected[collection]


def test_marketing_leads_dedup_index_is_unique_sparse(indexes):
    """The Phase C lead-capture idempotence relies on this being the
    DB-layer enforcement. Lose unique=True and you get duplicate-row
    drift across replicas."""
    matches = [
        (collection, spec, kwargs)
        for collection, spec, kwargs in indexes
        if collection == "marketing_leads"
        and spec == [("email", 1), ("template_id", 1)]
    ]
    assert len(matches) == 1, "missing or duplicated dedup index"
    _, _, kwargs = matches[0]
    assert kwargs.get("unique") is True
    assert kwargs.get("sparse") is True


def test_partial_filter_uses_only_permitted_operators(indexes):
    """MongoDB's partial-index allow-list permits only $eq / $exists /
    $gt[e] / $lt[e] / $type / $and / top-level conjunctions. $ne is
    forbidden — P0 fixed this exact bug; we don't want to reintroduce
    it. Walk every partialFilterExpression and assert it's clean."""
    PERMITTED = {"$eq", "$exists", "$gt", "$gte", "$lt", "$lte", "$type", "$and"}

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key.startswith("$"):
                    assert key in PERMITTED, (
                        f"partial filter uses forbidden operator {key}"
                    )
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for _, _, kwargs in indexes:
        pfe = kwargs.get("partialFilterExpression")
        if pfe is not None:
            walk(pfe)


def test_compound_keys_use_correct_sort_direction(indexes):
    """form_responses ordering must descend on submitted_at to match the
    paginated-list query, otherwise Mongo can't satisfy the sort from
    the index alone."""
    matches = [
        (collection, spec)
        for collection, spec, kwargs in indexes
        if collection == "form_responses"
        and spec[0] == ("form_id", 1)
        and any(k == "submitted_at" for k, _ in spec)
    ]
    assert matches
    _, spec = matches[0]
    assert ("submitted_at", -1) in spec, (
        "form_responses paginated index must sort submitted_at descending"
    )


def test_script_module_has_main_and_create_indexes():
    """The script must expose a CLI entry point and an awaitable
    create_indexes(dry_run) so it can be imported by the deploy
    runbook."""
    module = _load_indexes_module()
    assert hasattr(module, "INDEXES")
    assert callable(getattr(module, "create_indexes", None))
    assert callable(getattr(module, "main", None))
