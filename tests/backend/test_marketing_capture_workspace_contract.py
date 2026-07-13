from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testbed.verify_marketing_capture_workspace import (  # noqa: E402
    assert_setup_namespace_available,
)
from testbed import verify_marketing_capture_workspace as marketing_capture_driver  # noqa: E402
from testbed.cleanup_marketing_capture_workspace_state import (  # noqa: E402
    PLANNER_EMAIL,
    SEED_SCOPE,
    SEED_SOURCE,
    _capture_namespace_is_owned,
    _owned_identity_filter,
)
from testbed import testbed as testbed_cli  # noqa: E402


SEEDER = ROOT / "scripts" / "demo-videos" / "seed-demo-video-workspace.py"
DRIVER = ROOT / "testbed" / "verify_marketing_capture_workspace.py"
CLEANUP = ROOT / "testbed" / "cleanup_marketing_capture_workspace_state.py"
TESTBED_CLI = ROOT / "testbed" / "testbed.py"
PACKAGE_MANIFEST = ROOT / "package.json"
SEED_SOURCES = ROOT / "app" / "constants" / "seed_sources.py"
MARKETING_CAPTURE_MEDIA = ROOT / "app" / "constants" / "marketing_capture_media.py"
GALLERY_API = ROOT / "app" / "api" / "gallery_public.py"
GALLERY_ADMIN_API = ROOT / "app" / "api" / "gallery_admin.py"
GUEST_MEDIA_SERVICE = ROOT / "app" / "services" / "guest_media_service.py"


def _required_text(path: Path) -> str:
    assert path.exists(), (
        f"required marketing-capture file is missing: {path.relative_to(ROOT)}"
    )
    return path.read_text()


def _async_function(source: str, name: str) -> ast.AsyncFunctionDef:
    module = ast.parse(source)
    function = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == name
        ),
        None,
    )
    assert function is not None, f"missing async function: {name}"
    return function


def _dict_keys(node: ast.AST) -> set[str]:
    assert isinstance(node, ast.Dict)
    return {
        key.value
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def _load_seeder_module():
    spec = importlib.util.spec_from_file_location(
        "marketing_capture_workspace_seeder_contract", SEEDER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assigned_dicts(function: ast.AsyncFunctionDef) -> dict[str, ast.Dict]:
    assigned: dict[str, ast.Dict] = {}
    for node in ast.walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                assigned[target.id] = value
    return assigned


def test_marketing_capture_driver_and_cleanup_are_paired():
    _required_text(DRIVER)
    _required_text(CLEANUP)


def test_demo_seed_runs_the_dedicated_verified_marketing_workspace_driver():
    testbed_source = _required_text(TESTBED_CLI)
    package_source = _required_text(PACKAGE_MANIFEST)

    assert "testbed/verify_marketing_capture_workspace.py" not in testbed_source
    demo_seed_command = package_source.split('"demo:seed"', 1)[1].split("\n", 1)[0]
    assert "testbed/verify_marketing_capture_workspace.py" in demo_seed_command
    assert "scripts/demo-videos/seed-demo-video-workspace.py" not in demo_seed_command


def test_testbed_service_status_checks_process_and_http_readiness():
    testbed_source = _required_text(TESTBED_CLI)

    assert "pane_process_names" in testbed_source
    assert "service_is_ready" in testbed_source
    assert "/health/readyz" in testbed_source
    assert "failed readiness" in testbed_source


@pytest.mark.parametrize("process_name", ["node", "npm", "next-server"])
def test_testbed_frontend_liveness_accepts_supported_runtime_names(
    monkeypatch, process_name
):
    monkeypatch.setattr(
        testbed_cli,
        "pane_process_names",
        lambda _session, _window: {process_name},
    )

    assert testbed_cli._service_process_is_live(
        "capture-testbed", testbed_cli.FRONTEND_WINDOW
    )


def test_testbed_status_fails_when_a_required_service_window_is_missing(monkeypatch):
    cfg = SimpleNamespace(
        session_name="capture-testbed",
        with_frontend=False,
        enabled_windows=lambda: [
            testbed_cli.BACKEND_WINDOW,
            testbed_cli.STRIPE_WINDOW,
        ],
    )
    monkeypatch.setattr(testbed_cli, "session_exists", lambda _session: True)
    monkeypatch.setattr(
        testbed_cli,
        "list_windows",
        lambda _session: [testbed_cli.BACKEND_WINDOW],
    )
    monkeypatch.setattr(
        testbed_cli,
        "service_is_ready",
        lambda _cfg, window: window == testbed_cli.BACKEND_WINDOW,
    )

    assert testbed_cli.cmd_status(cfg, SimpleNamespace()) == 1


def test_local_media_fallbacks_accept_the_canonical_marketing_capture_seed():
    constants_source = _required_text(SEED_SOURCES)
    media_source = _required_text(MARKETING_CAPTURE_MEDIA)
    gallery_source = _required_text(GALLERY_API)
    gallery_admin_source = _required_text(GALLERY_ADMIN_API)
    guest_media_source = _required_text(GUEST_MEDIA_SERVICE)

    assert (
        'MARKETING_CAPTURE_SEED_SOURCE = "system:marketing_capture_seed"'
        in constants_source
    )
    assert "is_exact_marketing_capture_seed" in media_source
    assert "allow_local_demo_gallery_fallback" in gallery_source
    assert "allow_local_demo_gallery_fallback" in gallery_admin_source
    assert "is_exact_marketing_capture_seed" in guest_media_source
    assert "MARKETING_CAPTURE_SEED_SCOPE" in constants_source
    assert "/demo-gallery/elegant-couple-stairs.svg" in media_source


def test_marketing_gallery_assets_are_repository_owned_and_present():
    source = _required_text(SEEDER)
    asset_names = (
        "elegant-couple-stairs.svg",
        "elegant-ceremony-aisle.svg",
        "elegant-reception-table.svg",
    )

    for name in asset_names:
        assert f"/demo-gallery/{name}" in source
        assert (ROOT / "public" / "demo-gallery" / name).is_file()
    assert "/demo-gallery/elegant-couple-stairs.jpg" not in source


def test_testbed_driver_resets_then_seeds_then_verifies_before_browser_checkpoints():
    source = _required_text(DRIVER)

    reset_index = source.find("cleanup_marketing_capture_workspace_state")
    identity_index = source.find("setup_smoke_accounts.py")
    workspace_index = source.find("seed-demo-video-workspace.py")
    verification_index = source.find("verify_seeded_workspace")
    checkpoint_index = source.find("MARKETING_CAPTURE_E2E_CHECKPOINTS")

    assert -1 not in {
        reset_index,
        identity_index,
        workspace_index,
        verification_index,
        checkpoint_index,
    }
    assert (
        reset_index
        < identity_index
        < workspace_index
        < verification_index
        < checkpoint_index
    )
    assert "TESTBED_NON_INTERACTIVE" in source
    assert "America/Chicago" in source
    assert "MARKETING_CAPTURE_FRONTEND_URL" in source
    assert '"http://127.0.0.1:3100"' in source


def test_marketing_seed_is_isolated_and_does_not_rebrand_an_arbitrary_planner():
    source = _required_text(SEEDER)

    assert "MARKETING_CAPTURE_SEED_SOURCE" in source
    assert "Marigold & Co. Weddings" in source
    assert "Amina" in source and "Cole" in source
    assert "www.thespecialwedding.io" in source
    assert "marketing-capture@" not in source
    assert "MCW-SHOWCASE" not in source
    assert "--anchor-at" in source

    forbidden_visible_fixture_copy = (
        "JoshLoveWeds",
        "Josh Akinwole",
        "CON-DEMO-VIDEO",
        "peace.emmanuel",
        "test_planner",
    )
    for forbidden in forbidden_visible_fixture_copy:
        assert forbidden not in source

    assert "seed_source" in source
    assert "seed_scope" in source
    assert "existing owner" in source.lower()


def test_marketing_vendor_contract_activity_seed_uses_the_api_response_shape():
    source = _required_text(SEEDER)
    activity_seed = source.split(
        'mongo.get_collection("vendor_contract_activities")', 2
    )[-1].split("remaining_amount =", 1)[0]

    assert "VendorContractActivityType" in source
    assert '"root_contract_id": str(contract_object_id)' in activity_seed
    assert '"activity_type": activity_type.value' in activity_seed
    assert '"title": activity_title' in activity_seed
    assert '"type": actor_type' in activity_seed
    assert '"identifier": actor_identifier' in activity_seed
    assert '"display_name": actor_display_name' in activity_seed
    for legacy_key in ('"role":', '"email":', '"name":'):
        assert legacy_key not in activity_seed


def test_marketing_contract_activity_validator_rejects_legacy_seed_shape():
    validator = getattr(
        marketing_capture_driver, "_validate_vendor_contract_activity_api_shape", None
    )
    assert validator is not None

    with pytest.raises(RuntimeError, match="contract activity is not API-compatible"):
        validator(
            {
                "_id": ObjectId("67ce00000000000000000001"),
                "contract_id": "67c100000000000000000001",
                "activity_type": "sent",
                "actor": {
                    "role": "planner",
                    "email": "amina@studio.thespecialwedding.io",
                },
                "created_at": "2026-07-12T10:00:00+00:00",
            }
        )


def test_marketing_contract_activity_validator_accepts_canonical_seed_shape():
    validator = getattr(
        marketing_capture_driver, "_validate_vendor_contract_activity_api_shape", None
    )
    assert validator is not None

    validator(
        {
            "_id": ObjectId("67ce00000000000000000001"),
            "contract_id": "67c100000000000000000001",
            "root_contract_id": "67c100000000000000000001",
            "activity_type": "contract_sent",
            "title": "Contract sent",
            "description": "Sent to Luna & Co. Photography for review.",
            "actor": {
                "type": "planner",
                "identifier": "amina@studio.thespecialwedding.io",
                "display_name": "Amina Cole",
            },
            "metadata": {"contract_number": "MCW-2027-001"},
            "created_at": "2026-07-12T10:00:00+00:00",
        }
    )


def test_seed_reset_filters_do_not_delete_unowned_global_communications():
    source = _required_text(SEEDER)

    assert '"system:setup_smoke_accounts"' not in source
    assert '"phone": "+13195296088"' not in source
    assert '"recipient": "+13195296088"' not in source
    assert '"to": {"$regex": "^(demo|test)' not in source


def test_every_marketing_seed_deletion_requires_exact_source_and_scope():
    source = _required_text(SEEDER)
    module = ast.parse(source)
    checked = 0

    for function in (
        node for node in module.body if isinstance(node, ast.AsyncFunctionDef)
    ):
        assigned_dicts = _assigned_dicts(function)
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            if not (
                isinstance(call.func, ast.Attribute)
                and call.func.attr in {"delete_many", "delete_one"}
                and call.args
            ):
                continue
            filter_node = call.args[0]
            if isinstance(filter_node, ast.Name):
                filter_node = assigned_dicts.get(filter_node.id, filter_node)
            assert isinstance(filter_node, ast.Dict), (
                f"{function.name} must expose an auditable literal deletion filter"
            )
            assert _dict_keys(filter_node) >= {"seed_source", "seed_scope"}, (
                f"{function.name} deletion is not constrained to the exact capture "
                "source and scope"
            )
            filter_source = ast.unparse(filter_node)
            assert "MARKETING_CAPTURE_SEED_SOURCE" in filter_source
            assert "MARKETING_CAPTURE_SEED_SCOPE" in filter_source
            checked += 1

    assert checked >= 10, (
        "expected the contract to inspect the full fixture reset graph"
    )


def test_marketing_seed_replacements_are_exact_scope_or_fixed_legacy_migrations():
    source = _required_text(SEEDER)
    module = ast.parse(source)
    checked = 0

    for function in (
        node for node in module.body if isinstance(node, ast.AsyncFunctionDef)
    ):
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            if not (
                isinstance(call.func, ast.Attribute)
                and call.func.attr in {"replace_one", "update_one", "update_many"}
                and call.args
            ):
                continue
            filter_node = call.args[0]
            assert isinstance(filter_node, ast.Dict), (
                f"{function.name} must expose an auditable literal mutation filter"
            )
            filter_keys = _dict_keys(filter_node)
            filter_source = ast.unparse(filter_node)
            assert filter_keys >= {"_id", "seed_source", "seed_scope"}
            if function.name == "_migrate_legacy_smoke_workspace":
                assert "SMOKE_ACCOUNT_SEED_SOURCE" in filter_source
                assert "LEGACY_SMOKE_SEED_SCOPE" in filter_source
                assert filter_keys & {"email", "slug", "wedding_id"}
            else:
                assert "MARKETING_CAPTURE_SEED_SOURCE" in filter_source
                assert "MARKETING_CAPTURE_SEED_SCOPE" in filter_source
            checked += 1

    assert checked >= 4, "expected canonical updates plus fixed legacy migrations"


@pytest.mark.asyncio
async def test_seeded_document_reset_uses_the_exact_capture_scope():
    seeder = _load_seeder_module()

    class RecordingCollection:
        def __init__(self):
            self.deleted_with = None
            self.inserted = None

        async def delete_many(self, query):
            self.deleted_with = query

        async def insert_many(self, docs):
            self.inserted = docs

    collection = RecordingCollection()
    documents = [
        {
            "_id": "fixture-1",
            "wedding_id": "wedding-1",
            "seed_source": SEED_SOURCE,
            "seed_scope": SEED_SCOPE,
        }
    ]

    await seeder._replace_seeded_docs(collection, ["wedding-1"], documents)

    assert collection.deleted_with == {
        "wedding_id": {"$in": ["wedding-1"]},
        "seed_source": SEED_SOURCE,
        "seed_scope": SEED_SCOPE,
    }
    assert collection.inserted == documents


def test_seeded_identity_validator_accepts_only_reserved_or_controlled_contacts():
    validator = getattr(
        marketing_capture_driver, "_validate_seeded_identity_document", None
    )
    assert validator is not None

    validator(
        {
            "phone": "+1 (312) 555-0100",
            "phone_numbers": ["(405) 555-0199"],
            "email": "planner@studio.thespecialwedding.io",
            "website": "https://vendors.thespecialwedding.io/luna-lane",
            "nested": {
                "email": "host@example.com",
                "url": "https://florist.example/portfolio",
            },
        },
        path="vendor_profiles/example",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("phone", "+1 (312) 555-0200", "reserved fictional"),
        ("phone", "(555) 014-1188", "reserved fictional"),
        ("email", "routes@atlascoach.co", "controlled or reserved"),
        ("website", "https://atlascoach.co", "controlled or reserved"),
    ],
)
def test_seeded_identity_validator_rejects_unsafe_contacts(field, value, message):
    validator = getattr(
        marketing_capture_driver, "_validate_seeded_identity_document", None
    )
    assert validator is not None

    with pytest.raises(RuntimeError, match=message):
        validator({field: value}, path="vendor_profiles/unsafe")


def test_workspace_verifier_scans_every_scoped_document_for_identity_safety():
    source = _required_text(DRIVER)

    assert "_validate_seeded_identity_document" in source
    assert "database.list_collection_names()" in source
    assert '"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE' in source


def test_seating_reset_is_scoped_to_the_marketing_capture_owner():
    source = _required_text(SEEDER)
    seating_source = source.split("async def _seed_seating_fixture", 1)[1].split(
        "async def ", 1
    )[0]

    assert '"seed_source": MARKETING_CAPTURE_SEED_SOURCE' in seating_source
    assert '"seed_scope": MARKETING_CAPTURE_SEED_SCOPE' in seating_source
    assert 'delete_many({"wedding_id": {"$in": wedding_ids}})' not in seating_source


def test_ai_cache_seed_replaces_only_exact_content_addressed_rows():
    source = _required_text(SEEDER)
    function = _async_function(source, "_seed_ai_cache")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    assert not any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "update_many"
        for call in calls
    ), "AI fixture seeding must never retag every cache row for a tenant/feature"
    assert any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "_generate_cache_key"
        for call in calls
    ), "AI fixtures must derive the canonical content-addressed cache _id"
    assert any(
        isinstance(call.func, ast.Name)
        and call.func.id == "_replace_marketing_capture_owned_document"
        for call in calls
    ), "showcase AI cache fixtures must replace only their exact seed-owned _ids"
    assert "dashboard_insights" in ast.unparse(function)
    assert "budget_insights" in ast.unparse(function)


def test_form_artifact_resets_require_scope_wedding_and_exact_form_id():
    source = _required_text(SEEDER)
    function = _async_function(source, "_seed_form_fixture")
    expected_form_ids = {
        "form_responses": "DEMO_PUBLIC_FORM_ID",
        "form_submissions": "DEMO_COUPLE_FORM_ID",
    }
    checked: set[str] = set()

    for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
        if not (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "delete_many"
            and call.args
        ):
            continue
        collection_expr = ast.unparse(call.func.value)
        collection_name = next(
            (name for name in expected_form_ids if name in collection_expr), None
        )
        if collection_name is None:
            continue

        filter_node = call.args[0]
        assert _dict_keys(filter_node) >= {
            "seed_source",
            "seed_scope",
            "wedding_id",
            "form_id",
        }
        assert expected_form_ids[collection_name] in ast.unparse(filter_node)
        checked.add(collection_name)

    assert checked == set(expected_form_ids)


def test_knowledge_base_fixture_is_published_owned_verified_and_cleaned():
    seeder_source = _required_text(SEEDER)
    driver_source = _required_text(DRIVER)
    cleanup_source = _required_text(CLEANUP)

    kb_function = _async_function(seeder_source, "_seed_knowledge_base_fixture")
    assert "_replace_marketing_capture_owned_document" in ast.unparse(kb_function)
    strict_replace = _async_function(
        seeder_source, "_replace_marketing_capture_owned_document"
    )
    strict_replace_source = ast.unparse(strict_replace)
    assert "MARKETING_CAPTURE_SEED_SOURCE" in strict_replace_source
    assert "MARKETING_CAPTURE_SEED_SCOPE" in strict_replace_source
    assert "DEMO_KB_ARTICLE_ID" in seeder_source
    assert "DEMO_KB_ARTICLE_SLUG" in seeder_source
    assert '"status": "published"' in seeder_source
    assert '"kb_articles"' in cleanup_source
    assert '"kb_articles": 1' in driver_source
    assert "DEMO_KB_ARTICLE_SLUG" in driver_source
    assert "kb_count_before + 1" in driver_source


class _CollisionCollection:
    def __init__(self, existing=None):
        self.existing = existing

    def find_one(self, _query, _projection=None):
        return self.existing


class _CollisionDatabase:
    def __init__(self, collision_collection: str | None = None):
        self.collision_collection = collision_collection

    def __getitem__(self, collection_name: str):
        existing = (
            {"_id": "customer-owned"}
            if collection_name == self.collision_collection
            else None
        )
        return _CollisionCollection(existing)


class _IdentityCollection:
    def __init__(self, records):
        self.records = records

    def find(self, _query, _projection=None):
        return iter(self.records)


class _IdentityDatabase:
    def __init__(self, records_by_collection=None):
        self.records_by_collection = records_by_collection or {}

    def __getitem__(self, collection_name: str):
        return _IdentityCollection(self.records_by_collection.get(collection_name, []))


class _AsyncScopedCollection:
    def __init__(self, existing=None, *, insert_error: Exception | None = None):
        self.existing = existing
        self.insert_error = insert_error
        self.inserted = None
        self.replaced = None

    async def find_one(self, _query, _projection=None):
        return self.existing

    async def replace_one(self, query, document, *, upsert):
        self.replaced = (query, document, upsert)
        return SimpleNamespace(matched_count=1)

    async def insert_one(self, document):
        if self.insert_error:
            raise self.insert_error
        self.inserted = document
        return SimpleNamespace(inserted_id=document["_id"])


def test_setup_namespace_preflight_refuses_colliding_local_identity_before_smoke_seed():
    assert_setup_namespace_available(_CollisionDatabase())  # type: ignore[arg-type]

    with pytest.raises(
        RuntimeError, match="refusing to let setup_smoke_accounts overwrite"
    ):
        assert_setup_namespace_available(  # type: ignore[arg-type]
            _CollisionDatabase("users")
        )

    with pytest.raises(
        RuntimeError, match="refusing to let setup_smoke_accounts overwrite"
    ):
        assert_setup_namespace_available(  # type: ignore[arg-type]
            _CollisionDatabase("kb_articles")
        )


def test_runtime_cleanup_requires_seed_owned_identity_evidence():
    assert not _capture_namespace_is_owned(_IdentityDatabase())  # type: ignore[arg-type]
    assert _capture_namespace_is_owned(  # type: ignore[arg-type]
        _IdentityDatabase(
            {"users": [{"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}]}
        )
    )
    assert not _capture_namespace_is_owned(  # type: ignore[arg-type]
        _IdentityDatabase(
            {"users": [{"seed_source": "customer", "seed_scope": SEED_SCOPE}]}
        )
    )
    assert not _capture_namespace_is_owned(  # type: ignore[arg-type]
        _IdentityDatabase(
            {"users": [{"seed_source": SEED_SOURCE, "seed_scope": "another-demo"}]}
        )
    )


def test_identity_cleanup_filter_preserves_same_identity_from_wrong_seed_scope():
    database = mongomock.MongoClient().db
    database.users.insert_many(
        [
            {
                "_id": "owned",
                "email": PLANNER_EMAIL,
                "seed_source": SEED_SOURCE,
                "seed_scope": SEED_SCOPE,
            },
            {
                "_id": "wrong-scope",
                "email": PLANNER_EMAIL,
                "seed_source": SEED_SOURCE,
                "seed_scope": "another-demo",
            },
        ]
    )

    result = database.users.delete_many(
        _owned_identity_filter({"email": PLANNER_EMAIL})
    )

    assert result.deleted_count == 1
    assert database.users.find_one({"_id": "wrong-scope"}) is not None


@pytest.mark.asyncio
async def test_scoped_seed_replacement_never_mutates_an_unrelated_owner():
    from pymongo.errors import DuplicateKeyError

    from testbed._marketing_capture_seed_ownership import replace_scoped_document

    invalid_document_collection = _AsyncScopedCollection()
    with pytest.raises(RuntimeError, match="must carry exact seed ownership"):
        await replace_scoped_document(
            invalid_document_collection,
            {"_id": "cache-key", "seed_source": "customer"},
            seed_source=SEED_SOURCE,
            seed_scope=SEED_SCOPE,
        )
    assert invalid_document_collection.inserted is None

    unrelated = _AsyncScopedCollection(
        {"_id": "cache-key", "seed_source": "customer", "seed_scope": SEED_SCOPE}
    )
    with pytest.raises(RuntimeError, match="not owned"):
        await replace_scoped_document(
            unrelated,
            {
                "_id": "cache-key",
                "seed_source": SEED_SOURCE,
                "seed_scope": SEED_SCOPE,
            },
            seed_source=SEED_SOURCE,
            seed_scope=SEED_SCOPE,
        )

    assert unrelated.replaced is None
    assert unrelated.inserted is None

    owned = _AsyncScopedCollection(
        {"_id": "cache-key", "seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}
    )
    document = {
        "_id": "cache-key",
        "seed_source": SEED_SOURCE,
        "seed_scope": SEED_SCOPE,
    }
    await replace_scoped_document(
        owned,
        document,
        seed_source=SEED_SOURCE,
        seed_scope=SEED_SCOPE,
    )

    assert owned.replaced == (
        {
            "_id": "cache-key",
            "seed_source": SEED_SOURCE,
            "seed_scope": SEED_SCOPE,
        },
        document,
        False,
    )

    new_row = _AsyncScopedCollection()
    await replace_scoped_document(
        new_row,
        document,
        seed_source=SEED_SOURCE,
        seed_scope=SEED_SCOPE,
    )
    assert new_row.inserted == document

    raced = _AsyncScopedCollection(insert_error=DuplicateKeyError("race"))
    with pytest.raises(RuntimeError, match="collided during insertion"):
        await replace_scoped_document(
            raced,
            document,
            seed_source=SEED_SOURCE,
            seed_scope=SEED_SCOPE,
        )
    assert raced.replaced is None


def test_marketing_seed_uses_a_distinct_deterministic_id_namespace():
    source = _required_text(SEEDER)

    assert '"64f' not in source


def test_marketing_guest_tokens_use_the_capture_scope_not_a_wedding_suffix():
    source = _required_text(SEEDER)

    assert 'f"{MARKETING_CAPTURE_SEED_SCOPE}:{wedding_id}:token"' in source


def test_marketing_seed_does_not_reuse_legacy_string_document_ids():
    source = _required_text(SEEDER)

    for forbidden in (
        '"guest_memory_pending_',
        '"guest_memory_kept_',
        '"guest_memory_rejected_',
        '"form_demo_couple_intake"',
    ):
        assert forbidden not in source
    assert '"marketing_capture_memory_' in source


def test_cleanup_targets_the_full_seeded_domain_graph_and_asserts_no_survivors():
    source = _required_text(CLEANUP)
    required_collections = {
        "users",
        "user_subscriptions",
        "team_members",
        "weddings",
        "couple_users",
        "couple_messages",
        "guests",
        "rsvps",
        "plus_ones",
        "tables",
        "seating_layouts",
        "planner_tasks",
        "inbound_emails",
        "email_logs",
        "support_tickets",
        "vendor_profiles",
        "vendor_assignments",
        "vendor_contracts",
        "vendor_contract_activities",
        "vendor_payment_milestones",
        "vendor_quotes",
        "budget_categories",
        "payment_records",
        "contracts",
        "scheduled_payments",
        "packages",
        "forms",
        "form_responses",
        "form_distributions",
        "form_submissions",
        "guest_media_assets",
        "guest_media_exports",
    }

    missing = sorted(name for name in required_collections if name not in source)
    assert missing == [], f"cleanup is missing seeded collections: {missing}"
    assert "assert_no_seeded_survivors" in source
    assert "seed_source" in source and "seed_scope" in source
    assert "fixture_is_owned" in source
