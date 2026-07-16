"""Semantic receipt checks for the storefront browser acceptance driver."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
from types import SimpleNamespace
from typing import Callable

import mongomock
import pytest

import testbed.verify_storefront_frontend_lifecycle as lifecycle_driver
from testbed.verify_storefront_frontend_lifecycle import (
    _PLAYWRIGHT_REQUIRED_RESULTS,
    _assert_domain_connect_flow_receipts,
    _enforce_browser_scenario_truth,
    _parse_playwright_results,
    _record_browser_scenario,
    _required_playwright_results,
    _required_scenario_receipts,
    _write_final_artifact_seal,
)


RUN_ID = "a1b2c3d4e5f6"


def test_domain_connect_receipt_requires_consumed_cancelled_and_authorized_outcomes():
    completed_at = datetime.now(timezone.utc)
    receipt = _assert_domain_connect_flow_receipts(
        [
            {
                "state": "consumed",
                "completion_outcome": "cancelled",
                "consumed_at": completed_at,
                "callback_recorded_at": completed_at,
                "provider_callback_error": "access_denied",
                "last_error": {
                    "code": "domain_connect_authorization_cancelled"
                },
            },
            {
                "state": "consumed",
                "completion_outcome": "authorized",
                "consumed_at": completed_at,
                "callback_recorded_at": completed_at,
                "last_error": None,
            },
        ]
    )

    assert receipt == {
        "flow_count": 2,
        "flow_states": ["consumed"],
        "completion_outcomes": ["authorized", "cancelled"],
    }


@pytest.mark.parametrize(
    ("flows", "missing_outcome"),
    [
        ([{"state": "consumed", "completion_outcome": "authorized"}], "cancelled"),
        ([{"state": "consumed", "completion_outcome": "cancelled"}], "authorized"),
        ([{"state": "cancelled", "completion_outcome": ""}], "cancelled"),
    ],
)
def test_domain_connect_receipt_fails_closed_without_consumed_completion_outcomes(
    flows,
    missing_outcome,
):
    with pytest.raises(
        AssertionError,
        match=rf"consumed Domain Connect {missing_outcome} completion",
    ):
        _assert_domain_connect_flow_receipts(flows)


def test_domain_connect_receipt_rejects_transient_or_incomplete_callback_evidence():
    completed_at = datetime.now(timezone.utc)
    flows = [
        {
            "state": "consumed",
            "completion_outcome": "cancelled",
            "consumed_at": completed_at,
            "callback_recorded_at": completed_at,
            "provider_callback_error": "access_denied",
            "last_error": {"code": "domain_connect_authorization_cancelled"},
        },
        {
            "state": "consumed",
            "completion_outcome": "authorized",
            "consumed_at": completed_at,
            "callback_recorded_at": None,
            "last_error": None,
        },
    ]

    with pytest.raises(
        AssertionError,
        match="authorized completion is missing durable callback metadata",
    ):
        _assert_domain_connect_flow_receipts(flows)


def test_account_fingerprint_ignores_only_expected_login_telemetry():
    db = mongomock.MongoClient()["storefront_receipt_test"]
    fixtures = SimpleNamespace(
        signature_id="signature-owner",
        solo_id="solo-owner",
        foreign_owner_id="foreign-owner",
        signature_subscription_id="signature-subscription",
        solo_subscription_id="solo-subscription",
        foreign_subscription_id="foreign-subscription",
    )
    for owner_id, plan_id in (
        (fixtures.signature_id, "plan_signature"),
        (fixtures.solo_id, "plan_solo"),
        (fixtures.foreign_owner_id, "plan_signature"),
    ):
        db["users"].insert_one(
            {
                "_id": owner_id,
                "email": f"{owner_id}@example.test",
                "plan_id": plan_id,
                "subscription_status": "active",
            }
        )
    for subscription_id, owner_id, plan_id in (
        (
            fixtures.signature_subscription_id,
            fixtures.signature_id,
            "plan_signature",
        ),
        (fixtures.solo_subscription_id, fixtures.solo_id, "plan_solo"),
        (
            fixtures.foreign_subscription_id,
            fixtures.foreign_owner_id,
            "plan_signature",
        ),
    ):
        db["user_subscriptions"].insert_one(
            {
                "_id": subscription_id,
                "user_id": owner_id,
                "plan_id": plan_id,
                "status": "active",
            }
        )

    baseline = lifecycle_driver._account_state_fingerprint(db, fixtures)
    db["users"].update_many({}, {"$set": {"last_login": datetime.now(timezone.utc)}})
    assert lifecycle_driver._account_state_fingerprint(db, fixtures) == baseline

    db["users"].update_one(
        {"_id": fixtures.signature_id}, {"$set": {"plan_id": "plan_solo"}}
    )
    assert lifecycle_driver._account_state_fingerprint(db, fixtures) != baseline


def test_runtime_manifest_state_recovers_when_start_failed_before_returning_receipt():
    manifest = {"isolated_runtime": None}

    lifecycle_driver._record_isolated_runtime_shutdown(manifest, {"status": "STOPPED"})

    assert manifest["isolated_runtime"] == {
        "status": "STOPPED",
        "shutdown": {"status": "STOPPED"},
    }


def test_runtime_manifest_records_failed_shutdown_as_terminal_failure():
    manifest = {"isolated_runtime": {"status": "RUNNING"}}

    lifecycle_driver._record_isolated_runtime_shutdown(
        manifest, {"status": "FAILED", "error": "process did not stop"}
    )

    assert manifest["isolated_runtime"] == {
        "status": "STOP_FAILED",
        "shutdown": {"status": "FAILED", "error": "process did not stop"},
    }


def _attachment(name: str, payload: dict | None = None) -> dict:
    attachment = {"name": name, "contentType": "application/json"}
    if payload is not None:
        attachment["body"] = base64.b64encode(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).decode("ascii")
    return attachment


def _scenario_attachments(title: str, project: str, provider_mode: str) -> list[dict]:
    attachments: list[dict] = []
    for requirement in _required_scenario_receipts(provider_mode):
        if requirement["test_title"] != title or requirement["project"] != project:
            continue
        checkpoint_name = (
            f"checkpoint-{requirement['scenario_id']}-{requirement['component']}"
        )
        receipt = {
            "schema_version": 1,
            "scenario_id": requirement["scenario_id"],
            "component": requirement["component"],
            "run_id": RUN_ID,
            "test_title": title,
            "project": project,
            "captured_at": "2026-07-16T12:00:00+00:00",
            "routes": ["/admin/packages"],
            "checks": {"assertions_completed": True},
            "attachment_names": [checkpoint_name],
        }
        attachments.extend(
            [
                _attachment(checkpoint_name),
                _attachment(
                    f"scenario-receipt-{requirement['scenario_id']}-{requirement['component']}",
                    receipt,
                ),
            ]
        )
    return attachments


def _report(
    *,
    omit: tuple[str, str] | None = None,
    required: dict[tuple[str, str], str] | None = None,
    provider_mode: str = "deterministic",
    mutate_receipt: Callable[[str, str, list[dict]], list[dict]] | None = None,
) -> dict:
    specs = []
    for title, project in required or _PLAYWRIGHT_REQUIRED_RESULTS:
        if (title, project) == omit:
            continue
        attachments = _scenario_attachments(title, project, provider_mode)
        if mutate_receipt is not None:
            attachments = mutate_receipt(title, project, attachments)
        specs.append(
            {
                "title": title,
                "tests": [
                    {
                        "projectName": project,
                        "expectedStatus": "passed",
                        "results": [{"status": "passed", "attachments": attachments}],
                    }
                ],
            }
        )
    return {
        "suites": [{"title": "storefront", "specs": specs}],
        "stats": {
            "expected": len(specs),
            "unexpected": 0,
            "flaky": 0,
            "skipped": 0,
        },
    }


def test_playwright_receipt_requires_every_exact_test_and_project(tmp_path):
    report = tmp_path / "results.json"
    report.write_text(json.dumps(_report()), encoding="utf-8")

    parsed = _parse_playwright_results(report, run_id=RUN_ID)

    assert parsed["status"] == "PASSED"
    assert parsed["required_result_count"] == len(_PLAYWRIGHT_REQUIRED_RESULTS)
    assert parsed["missing_required_results"] == []
    assert parsed["wrong_required_results"] == []
    assert parsed["scenario_receipts"]


def test_playwright_receipt_rejects_an_aggregate_pass_with_missing_scenario(tmp_path):
    missing = next(iter(_PLAYWRIGHT_REQUIRED_RESULTS))
    report = tmp_path / "results.json"
    report.write_text(json.dumps(_report(omit=missing)), encoding="utf-8")

    parsed = _parse_playwright_results(report, run_id=RUN_ID)

    assert parsed["status"] == "FAILED"
    assert parsed["missing_required_results"] == [
        {"title": missing[0], "project": missing[1]}
    ]


def test_playwright_receipt_rejects_unrelated_green_test(tmp_path):
    report = tmp_path / "results.json"
    report.write_text(
        json.dumps(
            {
                "suites": [
                    {
                        "specs": [
                            {
                                "title": "unrelated test",
                                "tests": [
                                    {
                                        "projectName": "chromium-desktop-light",
                                        "expectedStatus": "passed",
                                        "results": [{"status": "passed"}],
                                    }
                                ],
                            }
                        ]
                    }
                ],
                "stats": {
                    "expected": 1,
                    "unexpected": 0,
                    "flaky": 0,
                    "skipped": 0,
                },
            }
        ),
        encoding="utf-8",
    )

    parsed = _parse_playwright_results(report, run_id=RUN_ID)

    assert parsed["status"] == "FAILED"
    assert len(parsed["missing_required_results"]) == len(_PLAYWRIGHT_REQUIRED_RESULTS)


def test_live_receipt_does_not_require_the_deterministic_provider_test(tmp_path):
    live_required = _required_playwright_results("live")
    deterministic_provider_receipt = next(
        receipt
        for receipt in _required_playwright_results("deterministic")
        if "deterministic provider state" in receipt[0]
    )
    assert deterministic_provider_receipt not in live_required
    report = tmp_path / "results.json"
    report.write_text(
        json.dumps(_report(required=live_required, provider_mode="live")),
        encoding="utf-8",
    )

    parsed = _parse_playwright_results(report, provider_mode="live", run_id=RUN_ID)

    assert parsed["status"] == "PASSED"
    assert (
        parsed["provider_receipt_scope"]
        == "configuration_fence_only_not_external_lifecycle"
    )


def test_deterministic_receipt_still_requires_the_provider_lifecycle(tmp_path):
    deterministic_required = _required_playwright_results("deterministic")
    provider_receipt = next(
        receipt
        for receipt in deterministic_required
        if "deterministic provider state" in receipt[0]
    )
    report = tmp_path / "results.json"
    report.write_text(
        json.dumps(_report(required=deterministic_required, omit=provider_receipt)),
        encoding="utf-8",
    )

    parsed = _parse_playwright_results(
        report, provider_mode="deterministic", run_id=RUN_ID
    )

    assert parsed["status"] == "FAILED"
    assert parsed["missing_required_results"] == [
        {"title": provider_receipt[0], "project": provider_receipt[1]}
    ]


def test_required_receipts_cover_internal_gap_closure_without_external_false_positive():
    deterministic = {
        receipt["scenario_id"]
        for receipt in _required_scenario_receipts("deterministic")
    }
    assert {
        "04_design_media_internal_preview",
        "06_inquiry_validation_rate_limit_delivery",
        "08_domain_connect_resume_without_dns",
        "09_manual_and_emailed_instructions",
        "10_dns_expected_vs_observed",
        "15_missing_config_friendly_error",
        "16_existing_site_prevalidation",
        "17_activation_state_immutability",
        "18_disconnect_retry_receipt",
        "19_platform_slug_survives_domain_lifecycle",
    }.issubset(deterministic)
    assert "14_real_custom_url" not in deterministic

    live = {receipt["scenario_id"] for receipt in _required_scenario_receipts("live")}
    assert "14_real_custom_url" not in live
    assert "18_disconnect_retry_receipt" not in live


def test_passing_scenario_removes_its_stale_blocker():
    manifest = {
        "run_id": RUN_ID,
        "browser_scenarios": {"scenario": "NOT RUN"},
        "browser_scenario_blockers": {"scenario": "No receipt yet."},
        "browser_scenario_evidence": {},
    }

    _record_browser_scenario(
        manifest,
        "scenario",
        "PASSED",
        evidence={
            "schema_version": 1,
            "scenario_id": "scenario",
            "run_id": RUN_ID,
            "routes": ["/admin/packages"],
            "receipts": [
                {
                    "scenario_id": "scenario",
                    "run_id": RUN_ID,
                    "sha256": "a" * 64,
                    "routes": ["/admin/packages"],
                    "checks": {"assertions_completed": True},
                }
            ],
        },
    )

    assert manifest["browser_scenarios"]["scenario"] == "PASSED"
    assert "scenario" not in manifest["browser_scenario_blockers"]
    assert _enforce_browser_scenario_truth(manifest) == []


def test_contradictory_scenario_fails_closed_instead_of_remaining_green():
    manifest = {
        "run_id": RUN_ID,
        "browser_scenarios": {"scenario": "PASSED"},
        "browser_scenario_blockers": {"scenario": "Still externally blocked."},
        "browser_scenario_evidence": {},
    }

    contradictions = _enforce_browser_scenario_truth(manifest)

    assert contradictions == ["scenario"]
    assert manifest["browser_scenarios"]["scenario"] == "BLOCKED"
    assert "failed closed" in manifest["browser_scenario_blockers"]["scenario"]


def test_passing_scenario_requires_run_bound_structured_receipts():
    manifest = {
        "run_id": RUN_ID,
        "browser_scenarios": {"scenario": "NOT RUN"},
        "browser_scenario_blockers": {},
        "browser_scenario_evidence": {},
    }

    with pytest.raises(ValueError, match="structured run-bound evidence"):
        _record_browser_scenario(manifest, "scenario", "PASSED")


def test_playwright_receipt_rejects_wrong_run_and_missing_checkpoint_attachment(
    tmp_path,
):
    def corrupt(_title: str, _project: str, attachments: list[dict]) -> list[dict]:
        for attachment in attachments:
            if attachment["name"].startswith("scenario-receipt-"):
                receipt = json.loads(base64.b64decode(attachment["body"]))
                receipt["run_id"] = "ffffffffffff"
                receipt["attachment_names"] = ["not-in-this-test-result"]
                attachment["body"] = base64.b64encode(
                    json.dumps(receipt).encode("utf-8")
                ).decode("ascii")
                break
        return attachments

    report = tmp_path / "results.json"
    report.write_text(json.dumps(_report(mutate_receipt=corrupt)), encoding="utf-8")

    parsed = _parse_playwright_results(report, run_id=RUN_ID)

    assert parsed["status"] == "FAILED"
    assert parsed["invalid_scenario_receipts"]


def test_final_artifact_seal_is_written_after_cleanup_and_shutdown(tmp_path):
    (tmp_path / "playwright").mkdir()
    (tmp_path / "playwright" / "results.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "cleanup-result.json").write_text(
        '{"status":"PASSED"}\n', encoding="utf-8"
    )
    (tmp_path / "runtime-backend.log").write_text("stopped\n", encoding="utf-8")
    mongo_data = tmp_path / "mongo-data"
    mongo_data.mkdir()
    (mongo_data / "WiredTiger").write_text("mutable\n", encoding="utf-8")
    evidence = {
        "schema_version": 1,
        "scenario_id": "01_restricted_upgrade_gate",
        "run_id": RUN_ID,
        "routes": ["/admin/packages"],
        "receipts": [
            {
                "scenario_id": "01_restricted_upgrade_gate",
                "run_id": RUN_ID,
                "sha256": "b" * 64,
                "routes": ["/admin/packages"],
                "checks": {"gate": True},
            }
        ],
    }
    manifest = {
        "run_id": RUN_ID,
        "completed_at": "2026-07-16T12:00:01+00:00",
        "cleanup": {"status": "PASSED"},
        "isolated_runtime": {"shutdown": {"status": "STOPPED"}},
        "browser_scenarios": {"01_restricted_upgrade_gate": "PASSED"},
        "browser_scenario_evidence": {
            "01_restricted_upgrade_gate": evidence,
        },
        "artifact_manifest": {
            "schema_version": 2,
            "path": "artifact-seal.json",
            "status": "SEALED_AFTER_FINAL_MANIFEST",
        },
    }
    manifest_path = tmp_path / "run-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    workspace = {
        "git_head": "1" * 40,
        "tracked_diff_sha256": "2" * 64,
        "frontend_source_sha256": "3" * 64,
        "storefront_evidence_source_sha256": "4" * 64,
        "runtime_revision": "storefront-e2e:" + "5" * 64,
    }

    seal = _write_final_artifact_seal(
        tmp_path,
        manifest=manifest,
        workspace=workspace,
        frontend_runtime={"build_id": "build-123"},
    )

    assert seal["run_id"] == RUN_ID
    assert seal["routes"] == ["/admin/packages"]
    assert seal["scenarios"]["01_restricted_upgrade_gate"]["receipt_sha256"] == [
        "b" * 64
    ]
    assert "run-manifest.json" in {entry["path"] for entry in seal["files"]}
    assert not any(entry["path"].startswith("mongo-data/") for entry in seal["files"])
    assert (tmp_path / "artifact-seal.json").is_file()
