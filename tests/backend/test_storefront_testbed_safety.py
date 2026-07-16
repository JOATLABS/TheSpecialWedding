from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image
import mongomock
import pytest

import testbed.cleanup_storefront_frontend_lifecycle_state as cleanup_module
from testbed.verify_storefront_frontend_lifecycle import (
    PROVIDER_DISABLED_ENVIRONMENT_KEYS,
    _assert_disabled_provider_fence,
    _disabled_provider_child_environment,
)
from testbed.storefront_testbed_safety import (
    assert_safe_storefront_target,
    validate_browser_checkpoint_evidence,
)


def test_storefront_target_accepts_only_loopback_services_and_exact_test_labels():
    target = assert_safe_storefront_target(
        backend_url="http://127.0.0.1:8112",
        frontend_url="http://localhost:3112",
        mongo_uri="mongodb://127.0.0.1:28117",
        mongo_db="wedding_storefront_test",
    )

    assert target.mongo_db == "wedding_storefront_test"
    assert target.is_loopback is True


def test_deterministic_child_environment_blanks_every_external_provider_key():
    inherited = {
        name: f"real-{name.lower()}" for name in PROVIDER_DISABLED_ENVIRONMENT_KEYS
    }
    inherited["SAFE_TESTBED_VALUE"] = "retained"

    child = _disabled_provider_child_environment(inherited)

    assert child["SAFE_TESTBED_VALUE"] == "retained"
    assert all(child[name] == "" for name in PROVIDER_DISABLED_ENVIRONMENT_KEYS)
    _assert_disabled_provider_fence(child)
    with pytest.raises(RuntimeError, match="provider credentials/configuration"):
        _assert_disabled_provider_fence(inherited)


@pytest.mark.parametrize(
    "mongo_db",
    ["wedding", "contest", "latest", "production", "wedding_storefrontproduction"],
)
def test_storefront_target_rejects_unlabelled_or_substring_database_names(mongo_db):
    with pytest.raises(RuntimeError, match="isolated loopback target"):
        assert_safe_storefront_target(
            backend_url="http://127.0.0.1:8112",
            frontend_url="http://127.0.0.1:3112",
            mongo_uri="mongodb://127.0.0.1:28117",
            mongo_db=mongo_db,
        )


@pytest.mark.parametrize(
    ("backend_url", "frontend_url", "mongo_uri"),
    [
        (
            "https://api.production-alias.example.com",
            "https://production-alias.example.com",
            "mongodb://production-db.example.com",
        ),
        (
            "http://127.0.0.1:8112",
            "http://127.0.0.1:3112",
            "mongodb://production-db.example.com",
        ),
    ],
)
def test_storefront_target_rejects_remote_services_even_when_database_is_labelled(
    backend_url, frontend_url, mongo_uri
):
    with pytest.raises(RuntimeError, match="isolated loopback target"):
        assert_safe_storefront_target(
            backend_url=backend_url,
            frontend_url=frontend_url,
            mongo_uri=mongo_uri,
            mongo_db="wedding_storefront_test",
        )


def _write_browser_evidence(
    root: Path,
    *,
    marker: str,
    assertions: dict[str, bool],
    captured_at: datetime,
) -> None:
    browser_dir = root / "browser"
    browser_dir.mkdir(parents=True)
    slug = "tier-boundary"
    screenshot_path = browser_dir / f"{slug}.png"
    Image.new("RGB", (40, 40), (20, 40, 60)).save(screenshot_path, format="PNG")
    dom_path = browser_dir / f"{slug}.dom.txt"
    dom_path.write_text(
        'dialog "Unlock Your Planner Storefront"\nbutton "Compare Storefront Plans"\n',
        encoding="utf-8",
    )
    payload = {
        "checkpoint": marker,
        "captured_at": captured_at.isoformat(),
        "result": "passed",
        "urls": [
            "http://127.0.0.1:3112/admin/packages",
            "http://127.0.0.1:3112/admin/planner/billing",
        ],
        "assertions": assertions,
        "console": {"errors": [], "warnings": []},
        "screenshot_sha256": hashlib.sha256(screenshot_path.read_bytes()).hexdigest(),
        "dom_snapshot_sha256": hashlib.sha256(dom_path.read_bytes()).hexdigest(),
    }
    (browser_dir / f"{slug}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_browser_checkpoint_requires_current_hashed_visual_dom_and_console_evidence(
    tmp_path,
):
    marker = "CHECKPOINT TIER_BOUNDARY"
    started_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    required = ("solo_upgrade_dialog", "billing_navigation", "console_clean")
    _write_browser_evidence(
        tmp_path,
        marker=marker,
        assertions={name: True for name in required},
        captured_at=datetime.now(timezone.utc),
    )

    evidence = validate_browser_checkpoint_evidence(
        artifact_dir=tmp_path,
        marker=marker,
        required_assertions=required,
        run_started_at=started_at,
        allowed_origins=("http://127.0.0.1:3112",),
    )

    assert evidence["status"] == "confirmed"
    assert evidence["screenshot"]["sha256"]
    assert evidence["dom_snapshot"]["sha256"]


@pytest.mark.parametrize("failure", ["stale", "false_assertion", "console_error"])
def test_browser_checkpoint_refuses_weak_or_failed_evidence(tmp_path, failure):
    marker = "CHECKPOINT TIER_BOUNDARY"
    started_at = datetime.now(timezone.utc)
    required = ("solo_upgrade_dialog", "billing_navigation", "console_clean")
    captured_at = started_at + timedelta(seconds=1)
    assertions = {name: True for name in required}
    _write_browser_evidence(
        tmp_path,
        marker=marker,
        assertions=assertions,
        captured_at=captured_at,
    )
    evidence_path = tmp_path / "browser" / "tier-boundary.json"
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    if failure == "stale":
        payload["captured_at"] = (started_at - timedelta(minutes=1)).isoformat()
    elif failure == "false_assertion":
        payload["assertions"]["billing_navigation"] = False
    else:
        payload["console"]["errors"] = ["TypeError: failed"]
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises((AssertionError, RuntimeError, ValueError)):
        validate_browser_checkpoint_evidence(
            artifact_dir=tmp_path,
            marker=marker,
            required_assertions=required,
            run_started_at=started_at,
            allowed_origins=("http://127.0.0.1:3112",),
        )


def test_domain_cleanup_requires_exact_hostname_provider_id_and_run_manifest(
    monkeypatch,
):
    hostname = "storefront-test.staging.example.com"
    provider_id = "provider-hostname-123"
    monkeypatch.setenv("TESTBED_STOREFRONT_ALLOWED_CUSTOM_DOMAINS", hostname)
    monkeypatch.setenv("TESTBED_STOREFRONT_ALLOWED_PROVIDER_HOSTNAME_IDS", provider_id)
    manifest = {
        "provider_mode": "live",
        "fixtures": {"custom_domain": hostname},
        "provider_authorization": {
            "provider_hostname_id": provider_id,
        },
    }

    cleanup_module._assert_authorized_domain_cleanup(
        {"hostname": hostname, "provider_hostname_id": provider_id}, manifest
    )

    with pytest.raises(RuntimeError, match="does not exactly match"):
        cleanup_module._assert_authorized_domain_cleanup(
            {"hostname": hostname, "provider_hostname_id": "different-provider"},
            manifest,
        )


def test_cleanup_deletes_and_checks_conflict_metrics_and_reconciliation_alerts():
    db = mongomock.MongoClient()["wedding_storefront_e2e"]
    run_id = "a1b2c3d4e5f6"
    manifest = {
        "run_id": run_id,
        "fixtures": {
            "signature_id": "signature-owner",
            "solo_id": "solo-owner",
            "foreign_owner_id": "foreign-owner",
            "signature_email": "signature@example.com",
            "inquiry_email": "inquiry@example.com",
            "slug": "storefront-a1b2c3d4e5f6",
        },
    }
    db["storefront_domain_conflict_claims"].insert_many(
        [
            {"planner_id": "foreign-owner", "hostname": "claimed.customer.test"},
            {
                "claimant_planner_id": "signature-owner",
                "hostname": "claimed.customer.test",
            },
            {"planner_id": "unrelated-owner", "hostname": "keep.customer.test"},
        ]
    )
    db["storefront_domain_operational_metrics"].insert_many(
        [
            {"name": "storefront.domain.provider_errors", "value": 1},
            {"name": "unrelated.metric", "value": 1},
        ]
    )
    db["notifications"].insert_many(
        [
            {"metadata": {"source": "storefront_domain_reconciliation"}},
            {"metadata": {"source": "unrelated_source"}},
        ]
    )

    survivors = cleanup_module._survivors(db, manifest)
    deleted = cleanup_module._delete_fixture_rows(db, manifest)

    assert survivors["storefront_domain_conflict_claims"] == 2
    assert survivors["storefront_domain_operational_metrics"] == 1
    assert survivors["notifications"] == 1
    assert deleted["storefront_domain_conflict_claims"] == 2
    assert deleted["storefront_domain_operational_metrics"] == 1
    assert deleted["notifications"] == 1
    assert cleanup_module._survivors(db, manifest) == {}
    assert db["storefront_domain_conflict_claims"].count_documents({}) == 1
    assert db["storefront_domain_operational_metrics"].count_documents({}) == 1
    assert db["notifications"].count_documents({}) == 1
