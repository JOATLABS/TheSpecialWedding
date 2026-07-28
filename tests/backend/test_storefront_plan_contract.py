from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.billing import (  # noqa: E402
    CANONICAL_PUBLIC_PLAN_IDS,
    CANONICAL_PUBLIC_PLAN_IDS_BY_NAME,
)
from app.services.subscription_service import SubscriptionService  # noqa: E402
from app.services.stripe_service import StripeService  # noqa: E402
from app.utils.subscription_plan_seed_policy import (  # noqa: E402
    PLAN_FIELD_SEED_VERSIONS,
    PLAN_SEED_VERSION,
    PUBLIC_PLAN_COPY_SEED_VERSION,
    build_effective_seed_plan,
    legacy_canonical_plan_aliases,
)

BOOT_SEED = PROJECT_ROOT / "scripts" / "seed_subscription_plans.py"
MANUAL_SEED = PROJECT_ROOT / "app" / "api" / "subscription_management.py"


def _module_assignment(path: Path, name: str) -> ast.AST:
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            ):
                return node.value
    raise AssertionError(f"{path}: missing module assignment {name}")


def _function_assignment(path: Path, function_name: str, name: str) -> ast.AST:
    tree = ast.parse(path.read_text())
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ),
        None,
    )
    assert function is not None, f"{path}: missing function {function_name}"
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return node.value
    raise AssertionError(f"{path}: missing {name} inside {function_name}")


def _plan_feature_matrix(value: ast.AST) -> dict[str, dict[str, bool]]:
    assert isinstance(value, ast.List)
    matrix: dict[str, dict[str, bool]] = {}
    for item in value.elts:
        assert isinstance(item, ast.Dict)
        fields = {
            ast.literal_eval(key): field_value
            for key, field_value in zip(item.keys, item.values)
            if key is not None and isinstance(key, ast.Constant)
        }
        plan_name = ast.literal_eval(fields["name"])
        features = ast.literal_eval(fields["features"])
        matrix[plan_name] = features
    return matrix


def _plan_public_copy(value: ast.AST) -> dict[str, dict[str, object]]:
    assert isinstance(value, ast.List)
    catalog: dict[str, dict[str, object]] = {}
    for item in value.elts:
        assert isinstance(item, ast.Dict)
        fields = {
            ast.literal_eval(key): field_value
            for key, field_value in zip(item.keys, item.values)
            if key is not None and isinstance(key, ast.Constant)
        }
        plan_name = ast.literal_eval(fields["name"])
        catalog[plan_name] = {
            "description": ast.literal_eval(fields["description"]),
            "features_list": ast.literal_eval(fields["features_list"]),
        }
    return catalog


@pytest.fixture(scope="module")
def boot_matrix() -> dict[str, dict[str, bool]]:
    return _plan_feature_matrix(_module_assignment(BOOT_SEED, "plans"))


@pytest.fixture(scope="module")
def manual_matrix() -> dict[str, dict[str, bool]]:
    return _plan_feature_matrix(
        _function_assignment(
            MANUAL_SEED,
            "seed_default_subscription_plans",
            "default_plans",
        )
    )


@pytest.fixture(scope="module")
def boot_public_copy() -> dict[str, dict[str, object]]:
    return _plan_public_copy(_module_assignment(BOOT_SEED, "plans"))


@pytest.fixture(scope="module")
def manual_public_copy() -> dict[str, dict[str, object]]:
    return _plan_public_copy(
        _function_assignment(
            MANUAL_SEED,
            "seed_default_subscription_plans",
            "default_plans",
        )
    )


def test_boot_and_manual_seed_feature_dictionaries_have_exact_parity(
    boot_matrix: dict[str, dict[str, bool]],
    manual_matrix: dict[str, dict[str, bool]],
):
    expected_plans = {"Solo Founding", "Solo Standard", "White Glove"}
    assert set(boot_matrix) == expected_plans
    assert set(manual_matrix) == expected_plans
    assert manual_matrix == boot_matrix


def test_boot_and_manual_seed_public_copy_have_exact_parity(
    boot_public_copy: dict[str, dict[str, object]],
    manual_public_copy: dict[str, dict[str, object]],
):
    assert manual_public_copy == boot_public_copy


def test_canonical_plan_highlights_match_the_visible_pricing_contract(
    boot_public_copy: dict[str, dict[str, object]],
):
    expected_features = {
        "Solo Founding": [
            "Unlimited weddings",
            "Unlimited guests",
            "Vendor management",
            "Seating orchestration",
            "Automated reminders",
            "Calendar sync (Google, Outlook)",
            "300 AI credits/month",
            "25GB guest memories storage",
            "Email support",
        ],
        "Solo Standard": [
            "Unlimited weddings",
            "Unlimited guests",
            "Everything in Solo Founding",
            "750 AI credits/month",
            "50GB guest memories storage",
            "Email support",
        ],
        "White Glove": [
            "Unlimited weddings",
            "Unlimited guests",
            "Everything in Solo Standard",
            "Team collaboration (5 staff seats)",
            "Planner storefront on a shareable platform URL",
            "Optional custom domain (app.yourbrand.com)",
            "1,500 AI credits/month",
            "100GB guest memories storage",
            "Priority support (12h response)",
            "Support-assisted onboarding by request",
        ],
    }

    assert {
        plan_name: plan["features_list"] for plan_name, plan in boot_public_copy.items()
    } == expected_features


@pytest.mark.parametrize(
    ("plan_name", "enabled"),
    [
        ("Solo Founding", False),
        ("Solo Standard", False),
        ("White Glove", True),
    ],
)
def test_storefront_features_are_explicit_and_independent_in_both_seed_paths(
    boot_matrix: dict[str, dict[str, bool]],
    manual_matrix: dict[str, dict[str, bool]],
    plan_name: str,
    enabled: bool,
):
    for matrix in (boot_matrix, manual_matrix):
        assert matrix[plan_name]["planner_storefront"] is enabled
        assert matrix[plan_name]["custom_domain"] is enabled


def test_unfinished_vendor_collaboration_is_disabled_in_both_seed_paths(
    boot_matrix: dict[str, dict[str, bool]],
    manual_matrix: dict[str, dict[str, bool]],
):
    for matrix in (boot_matrix, manual_matrix):
        for plan_name in ("Solo Founding", "Solo Standard", "White Glove"):
            assert matrix[plan_name]["vendor_collaboration"] is False


def test_plan_catalog_change_bumps_the_seed_version():
    assert PLAN_SEED_VERSION == "2026-07-28T00:00:00+00:00"
    assert PUBLIC_PLAN_COPY_SEED_VERSION == "2026-07-28T00:00:00+00:00"
    assert PLAN_FIELD_SEED_VERSIONS == {
        "description": PUBLIC_PLAN_COPY_SEED_VERSION,
        "features_list": PUBLIC_PLAN_COPY_SEED_VERSION,
    }


def test_copy_refresh_preserves_newer_commercial_and_hidden_plan_intent():
    seed_plan = {
        "name": "Solo Founding",
        "description": "Current planner-first description",
        "price_monthly": 49,
        "max_weddings": -1,
        "features_list": ["Current public highlight"],
        "is_active": True,
        "display_order": 1,
    }
    existing_plan = {
        **seed_plan,
        "description": "Retired vendor-oriented description",
        "price_monthly": 37,
        "max_weddings": 25,
        "features_list": ["Retired public highlight"],
        "is_active": False,
        "display_order": 9,
        "admin_overrides": {
            # Copy fields edited BEFORE the 2026-07-28 refresh — seed repairs them.
            "description": "2026-07-27T12:00:00+00:00",
            "features_list": "2026-07-27T12:00:00+00:00",
            # Commercial/display intent edited AFTER the refresh — preserved.
            "price_monthly": "2026-07-28T12:00:00+00:00",
            "max_weddings": "2026-07-28T12:00:00+00:00",
            "is_active": "2026-07-28T12:00:00+00:00",
        },
    }

    effective = build_effective_seed_plan(seed_plan, existing_plan)

    assert effective["description"] == seed_plan["description"]
    assert effective["features_list"] == seed_plan["features_list"]
    assert effective["price_monthly"] == 37
    assert effective["max_weddings"] == 25
    assert effective["is_active"] is False
    assert effective["display_order"] == 9


def test_future_copy_override_survives_the_field_scoped_refresh():
    seed_plan = {
        "description": "Canonical description",
        "features_list": ["Canonical highlight"],
    }
    existing_plan = {
        "description": "Operator description",
        "features_list": ["Operator highlight"],
        "admin_overrides": {
            "description": "2026-07-28T16:00:00+00:00",
            "features_list": "2026-07-28T16:00:00+00:00",
        },
    }

    assert build_effective_seed_plan(seed_plan, existing_plan) == {
        "description": "Operator description",
        "features_list": ["Operator highlight"],
    }


def test_all_three_public_plan_ids_are_canonical_for_deduplication():
    assert CANONICAL_PUBLIC_PLAN_IDS == {
        "plan_boutique",
        "plan_solo_standard",
        "plan_signature",
    }
    assert set(CANONICAL_PUBLIC_PLAN_IDS_BY_NAME.values()) == set(
        CANONICAL_PUBLIC_PLAN_IDS
    )


def test_legacy_alias_is_archived_only_after_the_canonical_upsert_succeeds():
    plans = [
        {"_id": "legacy_founding", "name": "Solo Founding", "is_active": True},
        {"_id": "plan_solo_standard", "name": "Solo Standard", "is_active": True},
        {"_id": "plan_signature", "name": "White Glove", "is_active": True},
    ]

    # A failed canonical create must leave the only existing plan selectable.
    assert legacy_canonical_plan_aliases(plans) == []

    plans.append({"_id": "plan_boutique", "name": "Solo Founding", "is_active": True})
    aliases = legacy_canonical_plan_aliases(plans)
    assert aliases == [("legacy_founding", "plan_boutique")]

    for legacy_id, canonical_id in aliases:
        legacy = next(plan for plan in plans if plan["_id"] == legacy_id)
        legacy.update(is_active=False, canonical_plan_id=canonical_id)
    assert {
        plan["_id"] for plan in plans if plan["is_active"]
    } == CANONICAL_PUBLIC_PLAN_IDS
    assert any(
        plan["_id"] == "legacy_founding"
        and plan["canonical_plan_id"] == "plan_boutique"
        for plan in plans
    )


def test_previously_archived_alias_without_override_is_selected_for_backfill():
    plans = [
        {
            "_id": "legacy_founding",
            "name": "Solo Founding",
            "is_active": False,
            "canonical_plan_id": "plan_boutique",
        },
        {"_id": "plan_boutique", "name": "Solo Founding", "is_active": True},
    ]

    assert legacy_canonical_plan_aliases(plans) == [
        ("legacy_founding", "plan_boutique")
    ]

    plans[0]["admin_overrides"] = {
        "is_active": datetime.now(timezone.utc),
    }
    assert legacy_canonical_plan_aliases(plans) == []


@pytest.mark.asyncio
async def test_manual_seed_refreshes_existing_plan_defaults_without_creating_plans(
    monkeypatch,
):
    from app.api import subscription_management

    existing = [
        {"_id": "plan_boutique", "name": "Solo Founding"},
        {"_id": "plan_solo_standard", "name": "Solo Standard"},
        {"_id": "plan_signature", "name": "Operator Agency"},
    ]

    class FakeSubscriptionService:
        def __init__(self):
            self.refresh_calls: list[tuple[str, dict]] = []

        async def list_plans(self, *, include_inactive: bool):
            assert include_inactive is True
            return existing

        async def refresh_seeded_plan_fields(self, plan_id: str, fields: dict):
            self.refresh_calls.append((plan_id, fields))
            return True

        async def archive_legacy_plan_alias(self, *_args, **_kwargs):
            raise AssertionError("canonical plans must not be archived")

        async def create_plan(self, *_args, **_kwargs):
            raise AssertionError("existing canonical plans must not be recreated")

        async def retire_public_plan(self, *_args, **_kwargs):
            raise AssertionError("no retired plan document exists in this scenario")

    fake_service = FakeSubscriptionService()
    monkeypatch.setattr(
        subscription_management,
        "subscription_service",
        fake_service,
    )

    result = await subscription_management.seed_default_subscription_plans(
        SimpleNamespace(email="root@example.com")
    )

    assert result["created_plans"] == 0
    assert result["updated_plans"] == 3
    assert result["skipped_plans"] == 0
    assert result["retired_plans"] == 0
    assert len(fake_service.refresh_calls) == 3
    assert {plan_id for plan_id, _fields in fake_service.refresh_calls} == set(
        CANONICAL_PUBLIC_PLAN_IDS
    )
    for _plan_id, fields in fake_service.refresh_calls:
        assert set(fields) == {"description", "features", "features_list"}


@pytest.mark.asyncio
async def test_manual_seed_retires_off_sale_plans(monkeypatch):
    from app.api import subscription_management

    existing = [
        {"_id": "plan_solo", "name": "Solo", "is_active": True},
        {"_id": "plan_boutique", "name": "Solo Founding"},
        {"_id": "plan_solo_standard", "name": "Solo Standard"},
        {"_id": "plan_signature", "name": "White Glove"},
        {"_id": "plan_enterprise", "name": "Enterprise", "is_active": True},
    ]

    class FakeSubscriptionService:
        def __init__(self):
            self.retired: list[str] = []

        async def list_plans(self, *, include_inactive: bool):
            assert include_inactive is True
            return existing

        async def refresh_seeded_plan_fields(self, *_args, **_kwargs):
            return False

        async def archive_legacy_plan_alias(self, *_args, **_kwargs):
            raise AssertionError("no legacy aliases exist in this scenario")

        async def create_plan(self, *_args, **_kwargs):
            raise AssertionError("existing canonical plans must not be recreated")

        async def retire_public_plan(self, plan_id: str):
            self.retired.append(plan_id)
            return True

    fake_service = FakeSubscriptionService()
    monkeypatch.setattr(
        subscription_management,
        "subscription_service",
        fake_service,
    )

    result = await subscription_management.seed_default_subscription_plans(
        SimpleNamespace(email="root@example.com")
    )

    assert fake_service.retired == ["plan_enterprise", "plan_solo"]
    assert result["retired_plans"] == 2
    assert result["details"]["retired"] == ["plan_enterprise", "plan_solo"]


@pytest.mark.asyncio
async def test_manual_seed_restores_canonical_id_and_archives_legacy_alias(
    monkeypatch,
):
    from app.api import subscription_management

    existing = [
        {"_id": "legacy_founding", "name": " SOLO FOUNDING ", "is_active": True},
        {"_id": "plan_solo_standard", "name": "Solo Standard"},
        {"_id": "plan_signature", "name": "White Glove"},
    ]

    class FakeSubscriptionService:
        def __init__(self):
            self.created: list[str] = []
            self.archived: list[tuple[object, str]] = []

        async def list_plans(self, *, include_inactive: bool):
            assert include_inactive is True
            return existing

        async def refresh_seeded_plan_fields(self, *_args, **_kwargs):
            return False

        async def create_plan(self, plan_data: dict, _creator_email: str):
            self.created.append(plan_data["name"])
            return {"plan_id": "plan_boutique"}

        async def archive_legacy_plan_alias(
            self, legacy_plan_id: object, canonical_plan_id: str
        ):
            self.archived.append((legacy_plan_id, canonical_plan_id))
            return True

        async def retire_public_plan(self, *_args, **_kwargs):
            raise AssertionError("no retired plan document exists in this scenario")

    fake_service = FakeSubscriptionService()
    monkeypatch.setattr(
        subscription_management,
        "subscription_service",
        fake_service,
    )

    result = await subscription_management.seed_default_subscription_plans(
        SimpleNamespace(email="root@example.com")
    )

    assert fake_service.created == ["Solo Founding"]
    assert fake_service.archived == [("legacy_founding", "plan_boutique")]
    assert result["created_plans"] == 1
    assert result["archived_aliases"] == 1


@pytest.mark.asyncio
async def test_manual_seed_field_refresh_bypasses_stripe_and_preserves_newer_copy():
    class FakeCollection:
        def __init__(self):
            self.update: dict | None = None

        async def find_one(self, query):
            assert query == {"_id": "plan_signature"}
            return {
                "_id": "plan_signature",
                "description": "Newer operator description",
                "features": {"vendor_collaboration": True},
                "features_list": ["Retired highlight"],
                "admin_overrides": {
                    "description": "2026-07-28T16:00:00+00:00",
                    "features": "2026-07-28T12:00:00+00:00",
                    "features_list": "2026-07-27T12:00:00+00:00",
                },
            }

        async def update_one(self, query, update):
            assert query == {"_id": "plan_signature"}
            self.update = update

    collection = FakeCollection()
    service = SubscriptionService.__new__(SubscriptionService)
    service.plans_collection = collection

    changed = await service.refresh_seeded_plan_fields(
        "plan_signature",
        {
            "description": "Canonical description",
            "features": {"vendor_collaboration": False},
            "features_list": ["Canonical highlight"],
        },
    )

    assert changed is True
    assert collection.update is not None
    written = collection.update["$set"]
    assert "description" not in written
    assert "features" not in written
    assert written["features_list"] == ["Canonical highlight"]
    assert isinstance(written["updated_at"], datetime)
    assert written["updated_at"].tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_legacy_plan_archive_retains_the_document_for_historical_references():
    class FakeCollection:
        def __init__(self):
            self.update: dict | None = None

        async def find_one(self, query):
            assert query == {"_id": "legacy_founding"}
            return {
                "_id": "legacy_founding",
                "name": "Solo Founding",
                "is_active": True,
            }

        async def update_one(self, query, update):
            assert query == {"_id": "legacy_founding"}
            self.update = update

    collection = FakeCollection()
    service = SubscriptionService.__new__(SubscriptionService)
    service.plans_collection = collection

    archived = await service.archive_legacy_plan_alias(
        "legacy_founding",
        "plan_boutique",
    )

    assert archived is True
    assert collection.update is not None
    written = collection.update["$set"]
    assert written["is_active"] is False
    assert written["canonical_plan_id"] == "plan_boutique"
    assert isinstance(written["admin_overrides.is_active"], datetime)
    assert isinstance(written["archived_as_duplicate_at"], datetime)


@pytest.mark.asyncio
async def test_legacy_plan_archive_backfills_missing_stripe_override():
    class FakeCollection:
        def __init__(self):
            self.update: dict | None = None

        async def find_one(self, query):
            assert query == {"_id": "legacy_founding"}
            return {
                "_id": "legacy_founding",
                "name": "Solo Founding",
                "is_active": False,
                "canonical_plan_id": "plan_boutique",
            }

        async def update_one(self, query, update):
            assert query == {"_id": "legacy_founding"}
            self.update = update

    collection = FakeCollection()
    service = SubscriptionService.__new__(SubscriptionService)
    service.plans_collection = collection

    assert await service.archive_legacy_plan_alias("legacy_founding", "plan_boutique")
    assert collection.update is not None
    assert isinstance(
        collection.update["$set"]["admin_overrides.is_active"],
        datetime,
    )


@pytest.mark.asyncio
async def test_stripe_product_update_cannot_reactivate_archived_legacy_alias():
    class FakeResult:
        modified_count = 1

    class FakeCollection:
        def __init__(self):
            self.update: dict | None = None

        async def find_one(self, query):
            assert query == {
                "_id": "legacy_solo",
                "stripe_product_id": "prod_legacy_solo",
            }
            return {
                "_id": "legacy_solo",
                "stripe_product_id": "prod_legacy_solo",
                "is_active": False,
                "admin_overrides": {
                    "is_active": datetime.now(timezone.utc),
                },
            }

        async def update_one(self, query, update):
            self.update = update
            return FakeResult()

    collection = FakeCollection()
    service = StripeService.__new__(StripeService)
    service.plans_collection = collection

    result = await service._handle_product_updated(
        {
            "id": "prod_legacy_solo",
            "active": True,
            "metadata": {"plan_id": "legacy_solo"},
        }
    )

    assert result["status"] == "success"
    assert collection.update is not None
    assert "is_active" not in collection.update["$set"]
