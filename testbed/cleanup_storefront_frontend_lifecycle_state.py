#!/usr/bin/env python3
"""Remove exactly one run-scoped storefront browser fixture set.

Provider-backed objects are reconciled through authenticated application APIs.
Mongo deletion is limited to the unique IDs and ``testbed_run_id`` recorded in
``STOREFRONT_TESTBED_RUN_MANIFEST``. Any survivor fails cleanup.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database
import requests

try:
    from testbed.storefront_testbed_safety import (
        assert_safe_storefront_target,
        parse_exact_hostname_allowlist,
    )
except ModuleNotFoundError:  # Direct ``python testbed/<driver>.py`` execution.
    from storefront_testbed_safety import (  # type: ignore[no-redef]
        assert_safe_storefront_target,
        parse_exact_hostname_allowlist,
    )


REPO_ROOT = Path(__file__).resolve().parent.parent
SHELL_ENVIRONMENT = dict(os.environ)
load_dotenv(REPO_ROOT / ".env", override=False)
testbed_env = REPO_ROOT / "testbed" / ".env"
if testbed_env.exists():
    load_dotenv(testbed_env, override=True)
os.environ.update(SHELL_ENVIRONMENT)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("cleanup_storefront_frontend_lifecycle_state")

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:3000").rstrip("/")
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")
MANIFEST_ENV = "STOREFRONT_TESTBED_RUN_MANIFEST"
SEED_SOURCE = "testbed:storefront_frontend_lifecycle"
REQUEST_TIMEOUT = 30


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unreadable storefront run manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Storefront run manifest must be a JSON object")
    return payload


def _load_manifest() -> tuple[Path, dict[str, Any]]:
    raw_path = os.getenv(MANIFEST_ENV, "").strip()
    if not raw_path:
        raise RuntimeError(f"{MANIFEST_ENV} is required for exact cleanup")
    manifest_path = Path(raw_path).expanduser().resolve()
    manifest = _read_json(manifest_path)
    run_id = manifest.get("run_id")
    fixtures = manifest.get("fixtures")
    artifact_dir = Path(str(manifest.get("artifact_dir") or "")).expanduser().resolve()
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise RuntimeError("Storefront run manifest has an invalid run_id")
    if not isinstance(fixtures, dict):
        raise RuntimeError("Storefront run manifest has no fixture identity map")
    if manifest_path.parent != artifact_dir:
        raise RuntimeError("Run manifest is not inside its exact artifact directory")
    if (
        manifest.get("backend_url") != BACKEND_URL
        or manifest.get("frontend_url") != FRONTEND_URL
        or manifest.get("database") != MONGO_DB
    ):
        raise RuntimeError("Cleanup environment does not match the run manifest target")
    return manifest_path, manifest


def assert_safe_target() -> None:
    assert_safe_storefront_target(
        backend_url=BACKEND_URL,
        frontend_url=FRONTEND_URL,
        mongo_uri=MONGO_URI,
        mongo_db=MONGO_DB,
    )


def _fixture(manifest: dict[str, Any], key: str) -> str:
    fixtures = manifest.get("fixtures")
    value = fixtures.get(key) if isinstance(fixtures, dict) else None
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Run manifest fixture {key!r} is missing")
    return value


def _assert_fixture_ownership(db: Database, manifest: dict[str, Any]) -> None:
    run_id = str(manifest["run_id"])
    for collection in (
        "users",
        "user_subscriptions",
        "subscription_plans",
        "packages",
        "planner_reviews",
    ):
        records = list(db[collection].find({"testbed_run_id": run_id}))
        if any(record.get("seed_source") != SEED_SOURCE for record in records):
            raise RuntimeError(
                f"Refusing to clean a non-testbed row from {collection} for run {run_id}"
            )


def _login(
    manifest: dict[str, Any], *, email_fixture: str, password_environment: str
) -> str:
    password = os.getenv(password_environment, "")
    if not password:
        raise RuntimeError(f"{password_environment} is required for provider cleanup")
    response = requests.post(
        f"{BACKEND_URL}/admin/token",
        json={"email": _fixture(manifest, email_fixture), "password": password},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(
            "Provider cleanup could not authenticate the exact planner fixture: "
            f"{response.status_code} {response.text[:500]}"
        )
    token = response.json().get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Planner fixture login did not return an access token")
    return token


def _api(
    method: str,
    path: str,
    token: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> requests.Response:
    return requests.request(
        method,
        f"{BACKEND_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=json_body,
        timeout=REQUEST_TIMEOUT,
    )


def _assert_authorized_domain_cleanup(
    domain: dict[str, Any], manifest: dict[str, Any] | None = None
) -> None:
    """Bind a live provider deletion to exact manifest and environment fences."""

    if manifest is None:
        _path, manifest = _load_manifest()
    hostname = str(domain.get("hostname") or "").strip().lower()
    provider_hostname_id = str(domain.get("provider_hostname_id") or "").strip()
    expected_hostname = _fixture(manifest, "custom_domain").lower()
    expected_provider_id = str(
        (manifest.get("provider_authorization") or {}).get("provider_hostname_id")
        or os.getenv("TESTBED_STOREFRONT_EXPECTED_PROVIDER_HOSTNAME_ID", "")
    ).strip()
    allowed_hostnames = parse_exact_hostname_allowlist(
        os.getenv("TESTBED_STOREFRONT_ALLOWED_CUSTOM_DOMAINS")
    )
    allowed_provider_ids = {
        value.strip()
        for value in os.getenv(
            "TESTBED_STOREFRONT_ALLOWED_PROVIDER_HOSTNAME_IDS", ""
        ).split(",")
        if value.strip()
    }
    if (
        manifest.get("provider_mode") != "live"
        or hostname != expected_hostname
        or hostname not in allowed_hostnames
        or not provider_hostname_id
        or provider_hostname_id != expected_provider_id
        or provider_hostname_id not in allowed_provider_ids
    ):
        raise RuntimeError(
            "Refusing custom-domain cleanup: hostname/provider ID does not exactly "
            "match this live run's manifest and explicit allowlists"
        )


def _reconcile_external_state(db: Database, manifest: dict[str, Any]) -> None:
    signature_id = _fixture(manifest, "signature_id")
    solo_id = _fixture(manifest, "solo_id")
    foreign_id = _fixture(manifest, "foreign_owner_id")
    impossible_solo = {
        "domains": db["storefront_domains"].count_documents({"planner_id": solo_id}),
        "domain_flows": db["storefront_domain_flows"].count_documents(
            {"planner_id": solo_id}
        ),
        "domain_operations": db["storefront_domain_operations"].count_documents(
            {"planner_id": solo_id}
        ),
        "domain_instruction_links": db[
            "storefront_domain_instruction_links"
        ].count_documents({"planner_id": solo_id}),
        "domain_tombstones": db["storefront_domain_tombstones"].count_documents(
            {"planner_id": solo_id}
        ),
        "domain_conflict_claims": db[
            "storefront_domain_conflict_claims"
        ].count_documents(
            {
                "$or": [
                    {"planner_id": solo_id},
                    {"claimant_planner_id": solo_id},
                ]
            }
        ),
        "assets": db["storefront_assets"].count_documents({"owner_id": solo_id}),
        "asset_cleanup_receipts": db[
            "storefront_asset_cleanup_receipts"
        ].count_documents({"owner_id": solo_id}),
    }
    impossible_solo = {key: value for key, value in impossible_solo.items() if value}
    if impossible_solo:
        raise RuntimeError(
            f"Restricted Solo fixture has provider state; refusing raw deletion: {impossible_solo}"
        )

    domains = list(
        db["storefront_domains"].find(
            {"planner_id": {"$in": [signature_id, foreign_id]}}
        )
    )
    assets = list(db["storefront_assets"].find({"owner_id": signature_id}))
    cleanup_receipts = db["storefront_asset_cleanup_receipts"].count_documents(
        {"owner_id": signature_id}
    )
    if cleanup_receipts:
        raise RuntimeError(
            "Detached asset cleanup receipts survive; provider cleanup must reconcile them first"
        )
    if not domains and not assets:
        return

    signature_token = _login(
        manifest,
        email_fixture="signature_email",
        password_environment="STOREFRONT_TESTBED_SIGNATURE_PASSWORD",
    )
    for domain in domains:
        planner_id = domain.get("planner_id")
        if manifest.get("provider_mode") == "live":
            _assert_authorized_domain_cleanup(domain, manifest)
        elif manifest.get("provider_mode") != "deterministic":
            raise RuntimeError("Unknown storefront provider cleanup mode")
        if planner_id == signature_id:
            token = signature_token
        elif planner_id == foreign_id:
            token = _login(
                manifest,
                email_fixture="foreign_email",
                password_environment="STOREFRONT_TESTBED_FOREIGN_PASSWORD",
            )
        else:
            raise RuntimeError("Refusing cleanup for an owner outside the run manifest")
        response = _api("DELETE", "/admin/storefront/custom-domain", token)
        if response.status_code != 200:
            raise RuntimeError(
                "Custom-domain disconnect failed; Mongo state retained: "
                f"{response.status_code} {response.text[:500]}"
            )
        if response.json().get("application_status") != "disconnected":
            raise RuntimeError("Custom-domain disconnect returned an invalid receipt")
        if db["storefront_domains"].find_one({"planner_id": planner_id}):
            raise RuntimeError("Custom-domain row survived application disconnect")

    if assets:
        response = _api(
            "POST",
            "/admin/storefront/settings",
            signature_token,
            json_body={"hero_asset_id": None, "about_asset_id": None},
        )
        if response.status_code != 200:
            raise RuntimeError(
                "Could not detach storefront images before provider cleanup: "
                f"{response.status_code} {response.text[:500]}"
            )
        for asset in assets:
            response = _api(
                "DELETE",
                f"/admin/storefront/upload?asset_id={asset['_id']}",
                signature_token,
            )
            if response.status_code not in {200, 404}:
                raise RuntimeError(
                    f"Asset {asset['_id']} cleanup failed: {response.status_code} "
                    f"{response.text[:500]}"
                )
        if db["storefront_assets"].count_documents({"owner_id": signature_id}):
            raise RuntimeError("Storefront asset rows survived application cleanup")


def _delete_fixture_rows(db: Database, manifest: dict[str, Any]) -> dict[str, int]:
    run_id = str(manifest["run_id"])
    signature_id = _fixture(manifest, "signature_id")
    solo_id = _fixture(manifest, "solo_id")
    foreign_id = _fixture(manifest, "foreign_owner_id")
    signature_email = _fixture(manifest, "signature_email")
    inquiry_email = _fixture(manifest, "inquiry_email")
    slug = _fixture(manifest, "slug")
    planner_ids = [signature_id, solo_id, foreign_id]
    inquiry_rows = list(
        db["storefront_inquiries"].find(
            {
                "planner_id": signature_id,
                "storefront_slug": slug,
                "email": inquiry_email,
            },
            {"_id": 1},
        )
    )
    inquiry_ids = [str(row["_id"]) for row in inquiry_rows]
    queries: tuple[tuple[str, dict[str, Any]], ...] = (
        (
            "planner_notifications",
            {
                "planner_id": signature_email,
                "metadata.source": "storefront_inquiry",
                "$or": [
                    {"metadata.inquiry_id": {"$in": inquiry_ids}},
                    {"metadata.lead_email": inquiry_email},
                    {"metadata.storefront_slug": slug},
                ],
            },
        ),
        (
            "email_logs",
            {
                "to": signature_email,
                "email_type": "storefront_inquiry",
                "idempotency_key": {"$regex": r"^storefront-inquiry/"},
            },
        ),
        (
            "storefront_inquiries",
            {
                "planner_id": signature_id,
                "storefront_slug": slug,
                "email": inquiry_email,
            },
        ),
        (
            "storefront_domain_flows",
            {"planner_id": {"$in": planner_ids}},
        ),
        (
            "storefront_domain_instruction_links",
            {"planner_id": {"$in": planner_ids}},
        ),
        (
            "storefront_domain_operations",
            {"planner_id": {"$in": planner_ids}},
        ),
        (
            "storefront_domain_tombstones",
            {"planner_id": {"$in": planner_ids}},
        ),
        (
            "storefront_domain_conflict_claims",
            {
                "$or": [
                    {"planner_id": {"$in": planner_ids}},
                    {"claimant_planner_id": {"$in": planner_ids}},
                ]
            },
        ),
        (
            "storefront_domain_operational_metrics",
            {"name": {"$regex": r"^storefront\.domain\."}},
        ),
        (
            "notifications",
            {"metadata.source": "storefront_domain_reconciliation"},
        ),
        ("storefront_settings", {"planner_id": {"$in": planner_ids}}),
        ("planner_reviews", {"testbed_run_id": run_id, "seed_source": SEED_SOURCE}),
        ("packages", {"testbed_run_id": run_id, "seed_source": SEED_SOURCE}),
        (
            "user_subscriptions",
            {"testbed_run_id": run_id, "seed_source": SEED_SOURCE},
        ),
        ("users", {"testbed_run_id": run_id, "seed_source": SEED_SOURCE}),
        (
            "subscription_plans",
            {"testbed_run_id": run_id, "seed_source": SEED_SOURCE},
        ),
    )
    deleted: dict[str, int] = {}
    for collection, query in queries:
        count = db[collection].delete_many(query).deleted_count
        deleted[collection] = count
    return deleted


def _survivors(db: Database, manifest: dict[str, Any]) -> dict[str, int]:
    run_id = str(manifest["run_id"])
    signature_id = _fixture(manifest, "signature_id")
    solo_id = _fixture(manifest, "solo_id")
    foreign_id = _fixture(manifest, "foreign_owner_id")
    signature_email = _fixture(manifest, "signature_email")
    inquiry_email = _fixture(manifest, "inquiry_email")
    slug = _fixture(manifest, "slug")
    planner_ids = [signature_id, solo_id, foreign_id]
    checks: tuple[tuple[str, dict[str, Any]], ...] = (
        (
            "storefront_inquiries",
            {
                "planner_id": signature_id,
                "storefront_slug": slug,
                "email": inquiry_email,
            },
        ),
        ("storefront_domains", {"planner_id": {"$in": planner_ids}}),
        (
            "storefront_domain_flows",
            {"planner_id": {"$in": planner_ids}},
        ),
        (
            "storefront_domain_operations",
            {"planner_id": {"$in": planner_ids}},
        ),
        (
            "storefront_domain_instruction_links",
            {"planner_id": {"$in": planner_ids}},
        ),
        (
            "storefront_domain_tombstones",
            {"planner_id": {"$in": planner_ids}},
        ),
        (
            "storefront_domain_conflict_claims",
            {
                "$or": [
                    {"planner_id": {"$in": planner_ids}},
                    {"claimant_planner_id": {"$in": planner_ids}},
                ]
            },
        ),
        (
            "storefront_domain_operational_metrics",
            {"name": {"$regex": r"^storefront\.domain\."}},
        ),
        (
            "notifications",
            {"metadata.source": "storefront_domain_reconciliation"},
        ),
        ("storefront_settings", {"planner_id": {"$in": planner_ids}}),
        ("storefront_assets", {"owner_id": {"$in": planner_ids}}),
        (
            "storefront_asset_cleanup_receipts",
            {"owner_id": {"$in": planner_ids}},
        ),
        ("planner_reviews", {"testbed_run_id": run_id}),
        ("packages", {"testbed_run_id": run_id}),
        ("user_subscriptions", {"testbed_run_id": run_id}),
        ("users", {"testbed_run_id": run_id}),
        ("subscription_plans", {"testbed_run_id": run_id}),
        (
            "planner_notifications",
            {
                "planner_id": signature_email,
                "metadata.source": "storefront_inquiry",
                "$or": [
                    {"metadata.lead_email": inquiry_email},
                    {"metadata.storefront_slug": slug},
                ],
            },
        ),
        (
            "email_logs",
            {
                "to": signature_email,
                "email_type": "storefront_inquiry",
                "idempotency_key": {"$regex": r"^storefront-inquiry/"},
            },
        ),
    )
    return {
        collection: count
        for collection, query in checks
        if (count := db[collection].count_documents(query))
    }


def main() -> int:
    assert_safe_target()
    manifest_path, manifest = _load_manifest()
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[MONGO_DB]
    result: dict[str, Any] = {
        "run_id": manifest["run_id"],
        "manifest_path": str(manifest_path),
        "status": "FAILED",
        "deleted": {},
        "survivors": {},
    }
    try:
        _assert_fixture_ownership(db, manifest)
        _reconcile_external_state(db, manifest)
        result["deleted"] = _delete_fixture_rows(db, manifest)
        result["survivors"] = _survivors(db, manifest)
        if result["survivors"]:
            raise RuntimeError(
                f"Storefront run cleanup left survivors: {result['survivors']}"
            )
        result["status"] = "PASSED"
        logger.info("PASS storefront run %s fixtures removed", manifest["run_id"])
        return 0
    finally:
        result_path = Path(str(manifest["artifact_dir"])) / "cleanup-result.json"
        result_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        client.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logger.error("Storefront cleanup failed: %s", exc)
        raise SystemExit(1)
