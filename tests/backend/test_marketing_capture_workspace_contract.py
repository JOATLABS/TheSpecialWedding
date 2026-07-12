from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SEEDER = ROOT / "scripts" / "demo-videos" / "seed-demo-video-workspace.py"
DRIVER = ROOT / "testbed" / "verify_marketing_capture_workspace.py"
CLEANUP = ROOT / "testbed" / "cleanup_marketing_capture_workspace_state.py"


def _required_text(path: Path) -> str:
    assert path.exists(), (
        f"required marketing-capture file is missing: {path.relative_to(ROOT)}"
    )
    return path.read_text()


def test_marketing_capture_driver_and_cleanup_are_paired():
    _required_text(DRIVER)
    _required_text(CLEANUP)


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


def test_marketing_seed_is_isolated_and_does_not_rebrand_an_arbitrary_planner():
    source = _required_text(SEEDER)

    assert "system:marketing_capture_seed" in source
    assert "Marigold & Co. Weddings" in source
    assert "Amina" in source and "Cole" in source
    assert "showcase.thespecialwedding.io" in source
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
