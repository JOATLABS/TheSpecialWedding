"""Contracts for the isolated visible storefront playback runner."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from testbed import storefront_build_evidence
from testbed import serve_storefront_visible_playback as playback


def _fixtures() -> SimpleNamespace:
    return SimpleNamespace(
        run_id="a1b2c3d4e5f6",
        root_admin_email="root@example.test",
        root_admin_password="root-secret",
        signature_email="signature@example.test",
        signature_password="signature-secret",
        solo_email="solo@example.test",
        solo_password="solo-secret",
        foreign_email="foreign@example.test",
        foreign_password="foreign-secret",
        slug="testbed-storefront-a1b2c3d4e5f6",
        custom_domain="events-a1b2c3d4e5f6.customer.test",
        manifest_dict=lambda: {
            "signature_email": "signature@example.test",
            "solo_email": "solo@example.test",
            "foreign_email": "foreign@example.test",
            "slug": "testbed-storefront-a1b2c3d4e5f6",
            "custom_domain": "events-a1b2c3d4e5f6.customer.test",
        },
    )


def test_visible_playback_manifest_is_source_bound_and_never_claims_external_proof(
    tmp_path,
):
    fixtures = _fixtures()
    manifest_path = tmp_path / "run-manifest.json"
    workspace = {
        "git_head": "1" * 40,
        "tracked_diff_sha256": "2" * 64,
        "frontend_source_sha256": "3" * 64,
        "storefront_evidence_source_sha256": "4" * 64,
        "runtime_revision": "storefront-e2e:" + "5" * 64,
    }

    manifest = playback._build_manifest(
        fixtures.run_id,
        tmp_path,
        manifest_path,
        fixtures,
        workspace,
    )

    assert manifest["driver"] == "serve_storefront_visible_playback"
    assert manifest["evidence_scope"] == "visible_in_app_playback_only"
    assert manifest["external_provider_live"] is False
    assert manifest["external_provider_acceptance"] == "BLOCKED"
    assert manifest["playwright"] == "NOT RUN"
    assert manifest["cleanup"]["status"] == "NOT RUN"
    serialized = json.dumps(manifest)
    assert "signature-secret" not in serialized
    assert "solo-secret" not in serialized
    assert "foreign-secret" not in serialized
    assert "root-secret" not in serialized


def test_ready_payload_exposes_only_local_fixture_credentials_and_honest_routes(tmp_path):
    fixtures = _fixtures()
    payload = playback._ready_payload(fixtures, tmp_path / "run-manifest.json")

    assert payload["run_id"] == fixtures.run_id
    assert payload["eligible_planner"] == {
        "email": fixtures.signature_email,
        "password": fixtures.signature_password,
    }
    assert payload["restricted_planner"] == {
        "email": fixtures.solo_email,
        "password": fixtures.solo_password,
    }
    assert payload["urls"]["domain"] == (
        "http://127.0.0.1:3124/admin/packages?storefront=domain"
    )
    assert payload["urls"]["preview"].endswith(
        "/storefront/testbed-storefront-a1b2c3d4e5f6?preview=1"
    )
    assert payload["external_provider_live"] is False
    assert "not external-provider proof" in payload["scope"].lower()


def test_visible_playback_runner_is_receipt_bound_and_does_not_invoke_playwright():
    relative = "testbed/serve_storefront_visible_playback.py"
    assert relative in storefront_build_evidence.STOREFRONT_EVIDENCE_INPUTS
    source = (Path(playback.__file__)).read_text(encoding="utf-8")
    assert "IsolatedStorefrontRuntime" in source
    assert "_run_cleanup" in source
    assert '_assert_provider_fence(os.environ, media_mode="disabled")' in source
    assert "_assert_disabled_provider_fence" not in source
    assert "_run_playwright" not in source
    assert "subprocess" not in source
    assert (Path(playback.__file__).parent / "storefront_browser_facade.mjs").is_file()
    assert "browser_origin=VISIBLE_BROWSER_URL" in source
    assert '"provider_status": "active"' in source
    assert '"ssl_status": "active"' in source
    assert '"https_ok": True' in source
