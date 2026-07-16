#!/usr/bin/env python3
"""Serve one isolated, source-bound storefront for visible in-app review.

This runner deliberately skips automated browser execution. It owns the same
production Next build, HTTPS FastAPI harness, isolated Mongo database, provider
credential fence, fixtures, and exact cleanup used by the storefront acceptance
driver, then keeps them alive until SIGINT or SIGTERM.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
from threading import Event
from typing import Any

from pymongo import MongoClient
import requests

try:
    import testbed.verify_storefront_frontend_lifecycle as lifecycle
except ModuleNotFoundError:  # Direct ``python testbed/<runner>.py`` execution.
    import verify_storefront_frontend_lifecycle as lifecycle  # type: ignore[no-redef]


VISIBLE_BROWSER_URL = os.getenv(
    "TESTBED_STOREFRONT_VISIBLE_BROWSER_URL", "http://127.0.0.1:3124"
).strip().rstrip("/")


def _build_manifest(
    run_id: str,
    artifact_dir: Path,
    manifest_path: Path,
    fixtures: lifecycle.Fixtures,
    workspace: dict[str, Any],
) -> dict[str, Any]:
    """Create a receipt that cannot be confused with automated/external proof."""

    return {
        "schema_version": 1,
        "driver": "serve_storefront_visible_playback",
        "evidence_scope": "visible_in_app_playback_only",
        "run_id": run_id,
        "started_at": lifecycle._now().isoformat(),
        "completed_at": None,
        "manifest_path": str(manifest_path),
        "artifact_dir": str(artifact_dir),
        "backend_url": lifecycle.BACKEND_URL,
        "frontend_url": lifecycle.FRONTEND_URL,
        "visible_browser_url": VISIBLE_BROWSER_URL,
        "database": lifecycle.MONGO_DB,
        "provider_mode": "deterministic",
        "external_provider_live": False,
        "external_provider_acceptance": "BLOCKED",
        "playwright": "NOT RUN",
        "workspace": workspace,
        "expected_backend_revision": workspace["runtime_revision"],
        "fixtures": fixtures.manifest_dict(),
        "frontend_runtime": None,
        "backend_runtime": None,
        "provider_harness": None,
        "isolated_runtime": None,
        "playback": {
            "status": "STARTING",
            "visible_review_outcome": "NOT RECORDED",
            "external_provider_live": False,
        },
        "cleanup": {"status": "NOT RUN"},
        "artifact_manifest": None,
        "failure": None,
    }


def _ready_payload(
    fixtures: lifecycle.Fixtures, manifest_path: Path
) -> dict[str, Any]:
    """Return local credentials to stdout only; they are never persisted."""

    return {
        "run_id": fixtures.run_id,
        "scope": (
            "Visible local storefront review only; this is not external-provider proof."
        ),
        "external_provider_live": False,
        "manifest": str(manifest_path),
        "root_admin": {
            "email": fixtures.root_admin_email,
            "password": fixtures.root_admin_password,
        },
        "eligible_planner": {
            "email": fixtures.signature_email,
            "password": fixtures.signature_password,
        },
        "restricted_planner": {
            "email": fixtures.solo_email,
            "password": fixtures.solo_password,
        },
        "conflict_owner": {
            "email": fixtures.foreign_email,
            "password": fixtures.foreign_password,
        },
        "urls": {
            "login": f"{VISIBLE_BROWSER_URL}/admin/login",
            "root_pricing": f"{VISIBLE_BROWSER_URL}/admin/saas?tab=plans",
            "packages": f"{VISIBLE_BROWSER_URL}/admin/packages",
            "domain": (
                f"{VISIBLE_BROWSER_URL}/admin/packages?storefront=domain"
            ),
            "preview": (
                f"{VISIBLE_BROWSER_URL}/storefront/{fixtures.slug}?preview=1"
            ),
        },
        "deterministic_hostname": fixtures.custom_domain,
        "stop": "Send Ctrl-C so exact authenticated cleanup runs before shutdown.",
    }


def _provider_headers(run_id: str, control_token: str) -> dict[str, str]:
    return {
        "x-storefront-testbed-run-id": run_id,
        "x-storefront-testbed-control-token": control_token,
    }


def _configure_automatic_provider(
    fixtures: lifecycle.Fixtures, control_token: str
) -> dict[str, Any]:
    response = requests.post(
        f"{lifecycle.BACKEND_URL}{lifecycle.PROVIDER_CONTROL_PREFIX}/configure",
        headers=_provider_headers(fixtures.run_id, control_token),
        json={
            "hostname": fixtures.custom_domain,
            "domain_connect_supported": True,
            "provider_configuration_ready": True,
            "provider_mutations_enabled": True,
        },
        timeout=lifecycle.REQUEST_TIMEOUT,
        allow_redirects=False,
    )
    if response.status_code != 200:
        raise RuntimeError(
            "Deterministic automatic-provider setup failed: "
            f"HTTP {response.status_code}"
        )
    receipt = response.json()
    if (
        receipt.get("run_id") != fixtures.run_id
        or receipt.get("external_provider_live") is not False
        or receipt.get("provider_mode") != "deterministic_testbed"
    ):
        raise RuntimeError("Deterministic provider identity did not match this run")
    advance = requests.post(
        f"{lifecycle.BACKEND_URL}{lifecycle.PROVIDER_CONTROL_PREFIX}/advance",
        headers=_provider_headers(fixtures.run_id, control_token),
        json={
            "hostname": fixtures.custom_domain,
            "provider_status": "active",
            "ssl_status": "active",
            "https_ok": True,
        },
        timeout=lifecycle.REQUEST_TIMEOUT,
        allow_redirects=False,
    )
    if advance.status_code != 200:
        raise RuntimeError(
            "Deterministic provider readiness setup failed: "
            f"HTTP {advance.status_code}"
        )
    return {**receipt, "ready_state": advance.json()}


def _wait_for_stop(stop_event: Event, runtime: lifecycle.IsolatedStorefrontRuntime) -> None:
    while not stop_event.wait(0.25):
        stopped = [
            label
            for label, process, _log_file in runtime.processes
            if process.poll() is not None
        ]
        if stopped:
            raise RuntimeError(
                "Visible playback runtime exited unexpectedly: " + ", ".join(stopped)
            )


def main() -> int:
    lifecycle.assert_safe_target()
    if lifecycle.EXTERNAL_MODE != "deterministic":
        raise RuntimeError(
            "Visible playback is deterministic-only; live provider mode is forbidden"
        )
    if lifecycle.INQUIRY_DELIVERY_MODE != "disabled":
        raise RuntimeError(
            "Visible playback requires disabled inquiry delivery and cannot send email"
        )

    # The parent process is fenced too, so cleanup and diagnostic requests cannot
    # inherit Cloudflare, R2, Resend, or Domain Connect credentials from .env.
    os.environ.update(lifecycle._disabled_provider_child_environment(os.environ))
    lifecycle._assert_provider_fence(os.environ, media_mode="disabled")

    run_id = secrets.token_hex(6)
    control_token = secrets.token_urlsafe(48)
    artifact_dir = lifecycle.ARTIFACT_ROOT / "visible-playback" / "runs" / run_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = artifact_dir / "run-manifest.json"
    fixtures = lifecycle.Fixtures.create(run_id, artifact_dir)
    workspace = lifecycle._workspace_evidence()
    manifest = _build_manifest(
        run_id, artifact_dir, manifest_path, fixtures, workspace
    )
    lifecycle._write_json(manifest_path, manifest)

    runtime: lifecycle.IsolatedStorefrontRuntime | None = None
    client: MongoClient | None = None
    seeded = False
    exit_code = 1
    stop_event = Event()

    def request_stop(_signum: int, _frame: Any) -> None:
        stop_event.set()

    previous_handlers = {
        signum: signal.signal(signum, request_stop)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }

    try:
        runtime = lifecycle.IsolatedStorefrontRuntime(
            run_id=run_id,
            root_admin_email=fixtures.root_admin_email,
            control_token=control_token,
            artifact_dir=artifact_dir,
            runtime_revision=workspace["runtime_revision"],
            browser_origin=VISIBLE_BROWSER_URL,
        )
        manifest["isolated_runtime"] = runtime.start()
        os.environ["REQUESTS_CA_BUNDLE"] = str(runtime.certificate_path)
        manifest["frontend_runtime"] = lifecycle._attest_frontend(
            workspace["frontend_source_sha256"], artifact_dir
        )

        client = MongoClient(lifecycle.MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client[lifecycle.MONGO_DB]
        lifecycle._seed_canonical_plans(db, run_id)
        lifecycle._seed(db, fixtures)
        seeded = True

        signature_token = lifecycle._login(
            fixtures.signature_email, fixtures.signature_password
        )
        manifest["backend_runtime"] = lifecycle._attest_backend(
            signature_token, workspace["runtime_revision"]
        )
        provider_receipt = _configure_automatic_provider(fixtures, control_token)
        manifest["provider_harness"] = {
            "run_id": provider_receipt["run_id"],
            "provider_mode": provider_receipt["provider_mode"],
            "external_provider_live": False,
            "provider_configuration_ready": provider_receipt.get(
                "provider_configuration_ready"
            ),
            "provider_mutations_enabled": provider_receipt.get(
                "provider_mutations_enabled"
            ),
            "domain_connect_supported": True,
            "control_token_sha256": hashlib.sha256(
                control_token.encode()
            ).hexdigest(),
            "certificate_sha256": runtime.certificate_sha256,
        }
        manifest["playback"] = {
            "status": "READY_FOR_USER_SELECTED_BROWSER",
            "visible_review_outcome": "NOT RECORDED",
            "external_provider_live": False,
            "ready_at": lifecycle._now().isoformat(),
            "routes": list(_ready_payload(fixtures, manifest_path)["urls"].values()),
        }
        lifecycle._write_json(manifest_path, manifest)
        print(
            "STOREFRONT_VISIBLE_PLAYBACK_READY="
            + json.dumps(_ready_payload(fixtures, manifest_path), sort_keys=True),
            flush=True,
        )

        _wait_for_stop(stop_event, runtime)
        manifest["playback"]["status"] = "VISIBLE_SESSION_ENDED"
        manifest["playback"]["ended_at"] = lifecycle._now().isoformat()
        exit_code = 0
    except Exception as exc:
        manifest["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        lifecycle.logger.error("Visible storefront playback failed: %s", exc)
    finally:
        lifecycle._write_json(manifest_path, manifest)
        if seeded:
            manifest["cleanup"] = lifecycle._run_cleanup(
                manifest_path, fixtures, artifact_dir
            )
            if manifest["cleanup"]["status"] != "PASSED":
                exit_code = 1
        else:
            manifest["cleanup"] = {
                "status": "PASSED",
                "reason": "No fixtures were seeded before the failure",
            }
        if client is not None:
            client.close()
        if runtime is not None:
            try:
                lifecycle._record_isolated_runtime_shutdown(
                    manifest, runtime.stop()
                )
            except Exception as exc:
                lifecycle._record_isolated_runtime_shutdown(
                    manifest, {"status": "FAILED", "error": str(exc)}
                )
                manifest["failure"] = {
                    "type": type(exc).__name__,
                    "message": f"Visible runtime shutdown failed: {exc}",
                }
                exit_code = 1
        else:
            manifest["isolated_runtime"] = {
                "status": "NOT_STARTED",
                "shutdown": {"status": "NOT_STARTED"},
            }
        manifest["completed_at"] = lifecycle._now().isoformat()
        manifest["artifact_manifest"] = {
            "schema_version": 2,
            "path": "artifact-seal.json",
            "status": "SEALED_AFTER_FINAL_MANIFEST",
        }
        lifecycle._write_json(manifest_path, manifest)
        try:
            lifecycle._write_final_artifact_seal(
                artifact_dir,
                manifest=manifest,
                workspace=workspace,
                frontend_runtime=manifest.get("frontend_runtime") or {},
            )
        except Exception as exc:
            manifest["artifact_manifest"] = {
                "schema_version": 2,
                "path": "artifact-seal.json",
                "status": "FAILED",
                "error": str(exc),
            }
            manifest["failure"] = {
                "type": type(exc).__name__,
                "message": f"Visible playback artifact sealing failed: {exc}",
            }
            lifecycle._write_json(manifest_path, manifest)
            exit_code = 1
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

    lifecycle.logger.info("Visible playback manifest: %s", manifest_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
