from __future__ import annotations

import importlib.util
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ssl
from types import SimpleNamespace
from urllib.parse import urlsplit

from bson import ObjectId
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
import httpx
import mongomock
import pytest

import app.api.storefront as storefront_api
from app.api.storefront import public_router as storefront_public_router
from app.api.storefront import router as storefront_router
from app.dependencies.auth_extended import ExtendedAuthUser, get_current_user_extended
from app.services.storefront_entitlement_service import StorefrontEntitlements
from app.utils.storefront_domain_errors import (
    storefront_domain_http_exception_handler,
    storefront_domain_validation_exception_handler,
)
import testbed.storefront_testbed_safety as storefront_safety


def _safe_environment() -> dict[str, str]:
    return {
        "TESTBED_NON_INTERACTIVE": "1",
        "STOREFRONT_PROVIDER_HARNESS_RUN_ID": "run-8f4d2c19a7e1",
        "STOREFRONT_PROVIDER_HARNESS_TOKEN": "testbed-token-" + ("a" * 48),
        "STOREFRONT_PROVIDER_HARNESS_CUSTOMER_ZONE": "customer.test",
        "BACKEND_URL": "http://127.0.0.1:8112",
        "FRONTEND_URL": "https://127.0.0.1:3112",
        "MONGO_URI": "mongodb://127.0.0.1:28117",
        "MONGO_DB": "wedding_storefront_test",
    }


def test_provider_harness_safety_requires_explicit_unattended_loopback_contract():
    validator = getattr(
        storefront_safety, "assert_storefront_provider_harness_environment", None
    )
    assert validator is not None, "provider harness safety validator is missing"

    safe = validator(_safe_environment())

    assert safe.run_id == "run-8f4d2c19a7e1"
    assert safe.customer_zone == "customer.test"
    assert safe.backend_origin == "http://127.0.0.1:8112"
    assert safe.frontend_origin == "https://127.0.0.1:3112"


def test_provider_harness_safety_rejects_missing_mode_weak_token_and_real_zone():
    validator = getattr(
        storefront_safety, "assert_storefront_provider_harness_environment", None
    )
    assert validator is not None, "provider harness safety validator is missing"

    missing_mode = _safe_environment()
    missing_mode.pop("TESTBED_NON_INTERACTIVE")
    weak_token = _safe_environment()
    weak_token["STOREFRONT_PROVIDER_HARNESS_TOKEN"] = "guessable"
    real_zone = _safe_environment()
    real_zone["STOREFRONT_PROVIDER_HARNESS_CUSTOMER_ZONE"] = "customer.com"
    configured_provider = _safe_environment()
    configured_provider["S3_ENDPOINT_URL"] = "https://account.r2.cloudflarestorage.com"

    for candidate in (missing_mode, weak_token, real_zone, configured_provider):
        try:
            validator(candidate)
        except RuntimeError:
            continue
        raise AssertionError("unsafe provider harness environment was accepted")


def test_provider_harness_core_is_a_testbed_only_module():
    assert (
        importlib.util.find_spec("testbed.storefront_provider_harness_core") is not None
    )


def test_provider_harness_normalizes_only_the_explicitly_blank_s3_endpoint():
    normalizer = getattr(
        storefront_safety, "normalize_disabled_provider_settings", None
    )
    assert normalizer is not None, "disabled-provider settings normalizer is missing"
    disabled_settings = SimpleNamespace(s3_endpoint_url="")
    configured_settings = SimpleNamespace(
        s3_endpoint_url="https://account.r2.cloudflarestorage.com"
    )

    assert normalizer(disabled_settings) is disabled_settings
    assert disabled_settings.s3_endpoint_url is None
    assert normalizer(configured_settings) is configured_settings
    assert (
        configured_settings.s3_endpoint_url
        == "https://account.r2.cloudflarestorage.com"
    )


@pytest.mark.asyncio
async def test_signed_edge_probe_replay_distinguishes_active_route_from_disconnect():
    from app.services.storefront_domain_https_probe import (
        PROBE_HEADER,
        build_probe_attestation,
    )
    from testbed.storefront_provider_harness_core import (
        DeterministicProviderState,
        NextRouteStorefrontHttpsVerifier,
    )

    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    state = DeterministicProviderState(environment)
    hostname_state = state.configure(
        "events.customer.test",
        domain_connect_supported=False,
        provider_configuration_ready=True,
        provider_mutations_enabled=True,
    )
    record = {
        "_id": ObjectId("507f1f77bcf86cd799439099"),
        "planner_id": "507f1f77bcf86cd799439011",
        "hostname": "events.customer.test",
        "revision": 7,
        "provider_hostname_id": "tb_cf_edge_probe",
    }
    hostname_state.provider_result = {
        "id": record["provider_hostname_id"],
        "hostname": record["hostname"],
        "status": "active",
        "ssl": {"status": "active"},
    }
    hostname_state.https_ok = True
    route_available = True
    secret_key = "testbed-storefront-edge-probe-secret-" + ("a" * 32)

    def edge(request: httpx.Request) -> httpx.Response:
        assert request.headers["host"] == record["hostname"]
        if not route_available:
            return httpx.Response(404, text="Not Found")
        challenge = request.headers[PROBE_HEADER]
        return httpx.Response(
            200,
            json=build_probe_attestation(record, challenge, secret_key),
            headers={"content-type": "application/json"},
        )

    verifier = NextRouteStorefrontHttpsVerifier(
        state,
        frontend_origin=environment.frontend_origin,
        ca_certificate="",
        secret_key=secret_key,
        ssl_context=ssl.create_default_context(),
        http_transport=httpx.MockTransport(edge),
    )

    active_receipt = await verifier.probe_current(record)
    assert active_receipt == {
        "hostname": record["hostname"],
        "path": "/.well-known/tsw-storefront-verification",
        "status_code": 200,
        "verified": True,
    }

    route_available = False
    hostname_state.provider_result = None
    disconnected_receipt = await verifier.replay_last_verified(record["hostname"])
    assert disconnected_receipt == {
        "hostname": record["hostname"],
        "path": "/.well-known/tsw-storefront-verification",
        "status_code": 404,
        "verified": False,
    }
    status = state.status()
    assert status["explicit_https_probe_count"] == 2
    assert status["latest_explicit_https_probe"] == disconnected_receipt


def test_uvicorn_entrypoint_exists_only_under_testbed_and_production_has_no_controls():
    project_root = Path(__file__).resolve().parents[2]
    entrypoint = project_root / "testbed" / "storefront_provider_harness.py"
    assert entrypoint.is_file()
    production_source = (project_root / "app" / "main.py").read_text(encoding="utf-8")
    api_source = (project_root / "app" / "api" / "storefront.py").read_text(
        encoding="utf-8"
    )
    normalization_call = "normalize_disabled_provider_settings(settings)"
    assert normalization_call in entrypoint.read_text(encoding="utf-8")
    entrypoint_source = entrypoint.read_text(encoding="utf-8")
    assert (
        entrypoint_source.index("environment = assert_storefront")
        < (entrypoint_source.index(normalization_call))
        < entrypoint_source.index("from app.main import")
    )
    assert "/__testbed/storefront-provider" not in production_source
    assert "/__testbed/storefront-provider" not in api_source


class AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, value):
        self._cursor = self._cursor.limit(value)
        return self

    async def to_list(self, length):
        return list(self._cursor)[:length]


class AsyncCollection:
    def __init__(self, collection):
        self._collection = collection

    def find(self, *args, **kwargs):
        return AsyncCursor(self._collection.find(*args, **kwargs))

    async def find_one(self, *args, **kwargs):
        return self._collection.find_one(*args, **kwargs)

    async def find_one_and_update(self, *args, **kwargs):
        return self._collection.find_one_and_update(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._collection.update_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._collection.delete_one(*args, **kwargs)


class AsyncDatabase:
    def __init__(self, raw):
        self.raw = raw
        self._collections: dict[str, AsyncCollection] = {}

    def __getitem__(self, name: str):
        if name not in self._collections:
            self._collections[name] = AsyncCollection(self.raw[name])
        return self._collections[name]


class FakeMongo:
    def __init__(self):
        self.raw = mongomock.MongoClient()["wedding_storefront_test"]
        self.db = AsyncDatabase(self.raw)
        self.raw.storefront_domains.create_index("planner_id", unique=True)
        self.raw.storefront_domains.create_index("hostname", unique=True)
        self.raw.storefront_domain_operations.create_index("operation_id", unique=True)
        self.raw.storefront_domain_tombstones.create_index(
            "deletion_receipt_id", unique=True
        )


class FakeEntitlements:
    async def resolve_for_owner(self, user_data: dict) -> StorefrontEntitlements:
        return self._result(str(user_data.get("_id") or ""))

    async def resolve_for_planner_id(self, planner_id: str) -> StorefrontEntitlements:
        return self._result(planner_id)

    @staticmethod
    def _result(owner_id: str) -> StorefrontEntitlements:
        return StorefrontEntitlements(
            owner_id=owner_id,
            plan_id="plan_signature",
            storefront_enabled=True,
            custom_domain_enabled=True,
        )


OWNER_ID = "507f1f77bcf86cd799439011"
SECOND_OWNER_ID = "507f1f77bcf86cd799439012"
HOSTNAME = "events.customer.test"


def _owner(owner_id: str = OWNER_ID) -> ExtendedAuthUser:
    return ExtendedAuthUser(
        email=f"{owner_id}@example.test",
        role="wedding_planner",
        user_data={"_id": ObjectId(owner_id), "role": "wedding_planner"},
    )


def _production_route_app() -> FastAPI:
    app = FastAPI()
    app.include_router(storefront_router, prefix="/admin")
    app.include_router(storefront_public_router, prefix="/api")
    app.add_exception_handler(
        RequestValidationError, storefront_domain_validation_exception_handler
    )
    from fastapi import HTTPException

    app.add_exception_handler(HTTPException, storefront_domain_http_exception_handler)

    async def current_owner(request: Request):
        return _owner(request.headers.get("x-test-owner", OWNER_ID))

    async def entitled():
        return FakeEntitlements._result(OWNER_ID)

    app.dependency_overrides[get_current_user_extended] = current_owner
    app.dependency_overrides[storefront_api.require_custom_domain] = entitled
    return app


@pytest.mark.asyncio
async def test_harness_control_is_token_bound_and_real_routes_drive_state_machine():
    from testbed.storefront_provider_harness_core import (
        CONTROL_PREFIX,
        create_storefront_provider_harness,
    )

    mongo = FakeMongo()
    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    bundle = create_storefront_provider_harness(
        environment=environment,
        mongo_client=mongo,
        entitlement_service=FakeEntitlements(),
        production_app=_production_route_app(),
    )
    headers = {
        "x-storefront-testbed-run-id": environment.run_id,
        "x-storefront-testbed-control-token": environment.control_token,
    }
    before_subscriptions = deepcopy(list(mongo.raw.user_subscriptions.find({})))
    before_settings = deepcopy(list(mongo.raw.storefront_settings.find({})))

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bundle.app),
            base_url="http://127.0.0.1:8112",
        ) as client:
            denied = await client.post(
                f"{CONTROL_PREFIX}/configure",
                json={"hostname": HOSTNAME},
            )
            assert denied.status_code == 404
            non_callback_page = await client.get(
                "/admin/packages", follow_redirects=False
            )
            assert non_callback_page.status_code == 404

            configured = await client.post(
                f"{CONTROL_PREFIX}/configure",
                headers=headers,
                json={
                    "hostname": HOSTNAME,
                    "domain_connect_supported": False,
                    "provider_mutations_enabled": True,
                },
            )
            assert configured.status_code == 200
            assert configured.json()["provider_mode"] == "deterministic_testbed"
            assert configured.json()["external_provider_live"] is False

            migration_preflight = await client.post(
                "/admin/storefront/custom-domain/preflight",
                json={"domain": HOSTNAME, "intent": "migration"},
            )
            assert migration_preflight.status_code == 200, migration_preflight.text
            assert migration_preflight.json()["recommended_flow"] == (
                "assisted_migration"
            )
            assert migration_preflight.json()["self_service_allowed"] is False
            assert migration_preflight.json()["domain_connect_supported"] is False
            assert {
                row["type"] for row in migration_preflight.json()["expected_records"]
            } == {"TXT"}
            assert any(
                row["code"] == "cloudflare_o2o_migration_requires_assistance"
                for row in migration_preflight.json()["conflicts"]
            )
            before_new_preflight = await client.get(
                f"{CONTROL_PREFIX}/status", headers=headers
            )
            assert before_new_preflight.json()["cloudflare_call_count"] == 0
            assert before_new_preflight.json()["provider_records"] == 0

            preflight = await client.post(
                "/admin/storefront/custom-domain/preflight",
                json={"domain": HOSTNAME, "intent": "new"},
            )
            assert preflight.status_code == 200, preflight.text
            assert preflight.json()["authoritative_dns"]["provider"] == "cloudflare"
            assert preflight.json()["domain_connect_supported"] is False
            harness_status = await client.get(
                f"{CONTROL_PREFIX}/status", headers=headers
            )
            assert harness_status.json()["authoritative_query_count"] >= 4

            claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                json={"domain": HOSTNAME, "intent": "new"},
            )
            assert claim.status_code == 201, claim.text
            attempt_id = claim.json()["attempt_id"]

            instructions = await client.post(
                "/admin/storefront/custom-domain/instructions",
                json={
                    "attempt_id": attempt_id,
                    "email": "dns-owner@example.com",
                    "note": "Please add the exact testbed records.",
                },
            )
            assert instructions.status_code == 200, instructions.text
            assert instructions.json()["status"] == "sent"
            assert instructions.json()["link_id"].startswith("sfil_")
            assert instructions.json()["expires_at"]
            receipt = await client.get(
                f"{CONTROL_PREFIX}/instruction-receipt",
                headers=headers,
                params={"hostname": HOSTNAME},
            )
            assert receipt.status_code == 200, receipt.text
            instruction_url = urlsplit(receipt.json()["instruction_url"])
            assert (
                f"{instruction_url.scheme}://{instruction_url.netloc}"
                == environment.frontend_origin
            )
            assert instruction_url.path.startswith("/domain-instructions/")
            instruction_token = instruction_url.path.rsplit("/", 1)[-1]
            snapshot_path = f"/api/storefront/domain-instructions/{instruction_token}"
            read_only = await client.get(snapshot_path)
            assert read_only.status_code == 200, read_only.text
            assert read_only.json()["hostname"] == HOSTNAME
            assert {record["type"] for record in read_only.json()["records"]} == {
                "TXT",
                "CNAME",
            }

            revoked = await client.delete(
                "/admin/storefront/custom-domain/instructions/"
                + instructions.json()["link_id"]
            )
            assert revoked.status_code == 200
            assert revoked.json() == {"status": "revoked"}
            assert (await client.get(snapshot_path)).status_code == 404

            missing = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert missing.status_code == 200
            assert missing.json()["ownership_status"] == "pending"
            assert missing.json()["provider_hostname_id"] is None

            wrong_dns_control = await client.post(
                f"{CONTROL_PREFIX}/advance",
                headers=headers,
                json={"hostname": HOSTNAME, "dns_mode": "wrong"},
            )
            assert wrong_dns_control.status_code == 200
            wrong_dns = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert wrong_dns.status_code == 200
            assert wrong_dns.json()["ownership_status"] == "pending"
            assert wrong_dns.json()["routing_dns_status"] == "conflict"
            assert wrong_dns.json()["last_error"]["code"] == (
                "dns_ownership_not_verified"
            )

            published = await client.post(
                f"{CONTROL_PREFIX}/publish-claim",
                headers=headers,
                json={"hostname": HOSTNAME},
            )
            assert published.status_code == 200, published.text
            assert published.json()["published"] is True

            verified = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert verified.status_code == 200, verified.text
            assert verified.json()["ownership_status"] == "verified"
            assert verified.json()["provider_hostname_id"].startswith("tb_cf_")
            assert verified.json()["application_status"] == "hostname_validation"

            advanced = await client.post(
                f"{CONTROL_PREFIX}/advance",
                headers=headers,
                json={
                    "hostname": HOSTNAME,
                    "provider_status": "active",
                    "ssl_status": "active",
                    "https_ok": True,
                    "reconcile_passes": 1,
                },
            )
            assert advanced.status_code == 200, advanced.text

            status = await client.get("/admin/storefront/custom-domain/status")
            assert status.status_code == 200
            assert status.json()["application_status"] == "active"
            assert status.json()["status"] == "active"
            assert status.json()["https_status"] == "verified"

            other_owner = await client.get(
                "/admin/storefront/custom-domain/status",
                headers={"x-test-owner": SECOND_OWNER_ID},
            )
            assert other_owner.status_code == 200
            assert other_owner.json() is None

            state = await client.get(f"{CONTROL_PREFIX}/status", headers=headers)
            assert state.status_code == 200
            assert state.json()["run_id"] == environment.run_id
            assert state.json()["hostnames"] == [HOSTNAME]
            assert state.json()["provider_records"] == 1
            assert state.json()["instruction_receipts"] == 1
            assert state.json()["external_provider_live"] is False

            cloudflare_calls_before_conflict = state.json()["cloudflare_call_count"]
            conflict_claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                headers={"x-test-owner": SECOND_OWNER_ID},
                json={"domain": HOSTNAME, "intent": "new"},
            )
            assert conflict_claim.status_code == 201, conflict_claim.text
            conflict_payload = conflict_claim.json()
            assert conflict_payload["conflict_code"] == "hostname_reserved"
            assert conflict_payload["provider_hostname_id"] is None
            assert len(conflict_payload["expected_records"]) == 1
            conflict_txt = conflict_payload["expected_records"][0]
            assert conflict_txt["type"] == "TXT"
            assert conflict_txt["name"] == f"_tsw-storefront.{HOSTNAME}"
            assert conflict_txt["value"].startswith("tsw-conflict-verification=")
            assert conflict_txt["purpose"] == "conflict_ownership_review"
            assert "planner_id" not in conflict_payload
            assert OWNER_ID not in conflict_claim.text

            conflict_dns = await client.post(
                f"{CONTROL_PREFIX}/publish-conflict-claim",
                headers=headers,
                json={"hostname": HOSTNAME},
            )
            assert conflict_dns.status_code == 200, conflict_dns.text
            assert conflict_dns.json()["record_type"] == "TXT"
            assert conflict_dns.json()["routing_changed"] is False

            conflict_verified = await client.post(
                "/admin/storefront/custom-domain/verify",
                headers={"x-test-owner": SECOND_OWNER_ID},
                json={"attempt_id": conflict_payload["attempt_id"]},
            )
            assert conflict_verified.status_code == 200, conflict_verified.text
            assert conflict_verified.json()["application_status"] == "operator_review"
            assert conflict_verified.json()["ownership_status"] == "verified"
            assert conflict_verified.json()["provider_hostname_id"] is None
            assert OWNER_ID not in conflict_verified.text

            conflict_state = await client.get(
                f"{CONTROL_PREFIX}/status", headers=headers
            )
            assert conflict_state.json()["cloudflare_call_count"] == (
                cloudflare_calls_before_conflict
            )
            assert conflict_state.json()["provider_records"] == 1

            conflict_cancelled = await client.delete(
                "/admin/storefront/custom-domain",
                headers={"x-test-owner": SECOND_OWNER_ID},
            )
            assert conflict_cancelled.status_code == 200
            assert conflict_cancelled.json()["application_status"] == "disconnected"
            still_active = await client.get("/admin/storefront/custom-domain/status")
            assert still_active.json()["application_status"] == "active"

            reconfigured = await client.post(
                f"{CONTROL_PREFIX}/configure",
                headers=headers,
                json={
                    "hostname": HOSTNAME,
                    "domain_connect_supported": True,
                    "provider_mutations_enabled": True,
                },
            )
            assert reconfigured.status_code == 200
            assert reconfigured.json()["provider_records"] == 1
            assert (await client.get("/admin/storefront/custom-domain/status")).json()[
                "application_status"
            ] == "active"

        assert list(mongo.raw.user_subscriptions.find({})) == before_subscriptions
        assert list(mongo.raw.storefront_settings.find({})) == before_settings
        stored = mongo.raw.storefront_domains.find_one({"hostname": HOSTNAME})
        assert stored["planner_id"] == OWNER_ID
        assert stored["claim_attempt_id"] == attempt_id
    finally:
        bundle.restore()


@pytest.mark.asyncio
async def test_inquiry_retry_due_control_is_token_owner_run_and_status_bound():
    from testbed.storefront_provider_harness_core import (
        CONTROL_PREFIX,
        create_storefront_provider_harness,
    )

    mongo = FakeMongo()
    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    bundle = create_storefront_provider_harness(
        environment=environment,
        mongo_client=mongo,
        entitlement_service=FakeEntitlements(),
        production_app=_production_route_app(),
    )
    headers = {
        "x-storefront-testbed-run-id": environment.run_id,
        "x-storefront-testbed-control-token": environment.control_token,
    }
    mongo.raw.users.insert_many(
        [
            {
                "_id": ObjectId(OWNER_ID),
                "testbed_run_id": environment.run_id,
            },
            {
                "_id": ObjectId(SECOND_OWNER_ID),
                "testbed_run_id": "run-from-another-proof",
            },
        ]
    )
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    inquiry_ids = {
        "eligible": ObjectId("65f000000000000000000101"),
        "foreign_owner": ObjectId("65f000000000000000000102"),
        "wrong_run": ObjectId("65f000000000000000000103"),
        "wrong_status": ObjectId("65f000000000000000000104"),
    }
    base_inquiry = {
        "planner_id": OWNER_ID,
        "storefront_slug": f"signature-{environment.run_id}",
        "message": f"Inquiry retry proof {environment.run_id}",
        "notification": {
            "status": "retry_pending",
            "attempt_count": 1,
            "delivery_outcome": "not_sent",
            "provider_idempotency_key": "storefront-inquiry/testbed",
            "next_attempt_at": future,
        },
        "updated_at": datetime(2026, 7, 15, tzinfo=timezone.utc),
    }
    mongo.raw.storefront_inquiries.insert_many(
        [
            {**deepcopy(base_inquiry), "_id": inquiry_ids["eligible"]},
            {
                **deepcopy(base_inquiry),
                "_id": inquiry_ids["foreign_owner"],
                "planner_id": SECOND_OWNER_ID,
            },
            {
                **deepcopy(base_inquiry),
                "_id": inquiry_ids["wrong_run"],
                "message": "Inquiry retry proof from a different run",
            },
            {
                **deepcopy(base_inquiry),
                "_id": inquiry_ids["wrong_status"],
                "notification": {
                    **deepcopy(base_inquiry["notification"]),
                    "status": "sent",
                },
            },
        ]
    )

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bundle.app),
            base_url="http://127.0.0.1:8112",
        ) as client:
            endpoint = f"{CONTROL_PREFIX}/inquiry-retry-due"
            denied = await client.post(
                endpoint,
                json={"inquiry_id": str(inquiry_ids["eligible"])},
            )
            assert denied.status_code == 404

            for label in ("foreign_owner", "wrong_run"):
                rejected = await client.post(
                    endpoint,
                    headers=headers,
                    json={"inquiry_id": str(inquiry_ids[label])},
                )
                assert rejected.status_code == 404

            wrong_status = await client.post(
                endpoint,
                headers=headers,
                json={"inquiry_id": str(inquiry_ids["wrong_status"])},
            )
            assert wrong_status.status_code == 409

            before = deepcopy(
                mongo.raw.storefront_inquiries.find_one(
                    {"_id": inquiry_ids["eligible"]}
                )
            )
            accepted = await client.post(
                endpoint,
                headers=headers,
                json={"inquiry_id": str(inquiry_ids["eligible"])},
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json() == {
                "run_id": environment.run_id,
                "inquiry_id": str(inquiry_ids["eligible"]),
                "notification_status": "retry_pending",
                "attempt_count": 1,
                "retry_due": True,
                "next_attempt_at": accepted.json()["next_attempt_at"],
                "external_provider_live": False,
            }

            after = mongo.raw.storefront_inquiries.find_one(
                {"_id": inquiry_ids["eligible"]}
            )
            assert after["notification"]["next_attempt_at"] < datetime.now(
                timezone.utc
            ).replace(tzinfo=None)
            before["notification"].pop("next_attempt_at")
            after["notification"].pop("next_attempt_at")
            assert after == before
    finally:
        bundle.restore()


@pytest.mark.asyncio
async def test_automatic_provider_consent_uses_signed_real_callback_and_dns_proof():
    from testbed.storefront_provider_harness_core import (
        CONTROL_PREFIX,
        create_storefront_provider_harness,
    )

    mongo = FakeMongo()
    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    production_app = _production_route_app()
    bundle = create_storefront_provider_harness(
        environment=environment,
        mongo_client=mongo,
        entitlement_service=FakeEntitlements(),
        production_app=production_app,
    )
    headers = {
        "x-storefront-testbed-run-id": environment.run_id,
        "x-storefront-testbed-control-token": environment.control_token,
    }

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bundle.app),
            base_url="http://127.0.0.1:8112",
            follow_redirects=False,
        ) as client:
            await client.post(
                f"{CONTROL_PREFIX}/configure",
                headers=headers,
                json={
                    "hostname": HOSTNAME,
                    "domain_connect_supported": True,
                },
            )
            claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                json={"domain": HOSTNAME, "intent": "new"},
            )
            attempt_id = claim.json()["attempt_id"]
            authorize = await client.post(
                "/admin/storefront/custom-domain/domain-connect/authorize",
                json={"attempt_id": attempt_id},
            )
            assert authorize.status_code == 200, authorize.text
            provider_url = authorize.json()["authorization_url"]
            assert CONTROL_PREFIX in provider_url

            consent = await client.get(provider_url)
            assert consent.status_code == 200
            assert "Authorize DNS changes" in consent.text
            assert "domains.thespecialwedding.com" in consent.text

            provider_decision = await client.post(
                provider_url,
                content="decision=authorize",
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
            assert provider_decision.status_code == 303
            callback_url = provider_decision.headers["location"]
            assert callback_url.startswith(
                "http://127.0.0.1:8112/admin/storefront/custom-domain/domain-connect/callback"
            )

            callback = await client.get(callback_url)
            assert callback.status_code == 303
            assert callback.headers["location"].endswith(
                f"storefront=domain&attempt={attempt_id}"
            )

            complete = await client.post(
                "/admin/storefront/custom-domain/domain-connect/complete",
                json={"attempt_id": attempt_id},
                headers={"Authorization": "Bearer testbed-owner-token"},
            )
            assert complete.status_code == 200, complete.text
            assert complete.json()["application_status"] == "dns_setup_pending"

            verified = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert verified.status_code == 200, verified.text
            assert verified.json()["ownership_status"] == "verified"

            flow = mongo.raw.storefront_domain_flows.find_one(
                {"attempt_id": attempt_id}
            )
            assert flow["state"] == "consumed"
    finally:
        bundle.restore()


@pytest.mark.asyncio
async def test_provider_callback_without_dns_never_marks_the_hostname_connected():
    from testbed.storefront_provider_harness_core import (
        CONTROL_PREFIX,
        create_storefront_provider_harness,
    )

    mongo = FakeMongo()
    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    bundle = create_storefront_provider_harness(
        environment=environment,
        mongo_client=mongo,
        entitlement_service=FakeEntitlements(),
        production_app=_production_route_app(),
    )
    headers = {
        "x-storefront-testbed-run-id": environment.run_id,
        "x-storefront-testbed-control-token": environment.control_token,
    }

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bundle.app),
            base_url="http://127.0.0.1:8112",
            follow_redirects=False,
        ) as client:
            await client.post(
                f"{CONTROL_PREFIX}/configure",
                headers=headers,
                json={"hostname": HOSTNAME, "domain_connect_supported": True},
            )
            claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                json={"domain": HOSTNAME, "intent": "new"},
            )
            attempt_id = claim.json()["attempt_id"]
            authorize = await client.post(
                "/admin/storefront/custom-domain/domain-connect/authorize",
                json={"attempt_id": attempt_id},
            )
            provider_url = authorize.json()["authorization_url"]
            provider_decision = await client.post(
                provider_url,
                content="decision=authorize_without_dns",
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
            assert provider_decision.status_code == 303

            callback = await client.get(provider_decision.headers["location"])
            assert callback.status_code == 303
            complete = await client.post(
                "/admin/storefront/custom-domain/domain-connect/complete",
                json={"attempt_id": attempt_id},
                headers={"Authorization": "Bearer testbed-owner-token"},
            )
            assert complete.status_code == 200, complete.text
            assert complete.json()["application_status"] == "dns_setup_pending"
            assert complete.json()["ownership_status"] == "pending"
            assert complete.json()["routing_dns_status"] == "pending"
            assert complete.json()["provider_hostname_id"] is None

            flow = mongo.raw.storefront_domain_flows.find_one(
                {"attempt_id": attempt_id}
            )
            assert flow["state"] == "consumed"
    finally:
        bundle.restore()


@pytest.mark.asyncio
async def test_migration_ownership_only_control_preserves_existing_routing():
    from testbed.storefront_provider_harness_core import (
        CONTROL_PREFIX,
        create_storefront_provider_harness,
    )

    mongo = FakeMongo()
    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    bundle = create_storefront_provider_harness(
        environment=environment,
        mongo_client=mongo,
        entitlement_service=FakeEntitlements(),
        production_app=_production_route_app(),
    )
    headers = {
        "x-storefront-testbed-run-id": environment.run_id,
        "x-storefront-testbed-control-token": environment.control_token,
    }

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bundle.app),
            base_url="http://127.0.0.1:8112",
            follow_redirects=False,
        ) as client:
            await client.post(
                f"{CONTROL_PREFIX}/configure",
                headers=headers,
                json={"hostname": HOSTNAME, "domain_connect_supported": False},
            )
            await client.post(
                f"{CONTROL_PREFIX}/advance",
                headers=headers,
                json={"hostname": HOSTNAME, "dns_mode": "wrong"},
            )
            claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                json={"domain": HOSTNAME, "intent": "migration"},
            )
            assert claim.status_code == 201, claim.text

            before = await client.get(
                f"{CONTROL_PREFIX}/routing-snapshot",
                headers=headers,
                params={"hostname": HOSTNAME},
            )
            ownership = await client.post(
                f"{CONTROL_PREFIX}/publish-claim",
                headers=headers,
                json={"hostname": HOSTNAME, "ownership_only": True},
            )
            after = await client.get(
                f"{CONTROL_PREFIX}/routing-snapshot",
                headers=headers,
                params={"hostname": HOSTNAME},
            )

            assert ownership.status_code == 200, ownership.text
            assert ownership.json()["ownership_only"] is True
            assert ownership.json()["routing_changed"] is False
            assert before.json()["CNAME"] == ["wrong-target.customer.test"]
            assert after.json() == before.json()
            assert (
                await client.get(
                    f"{CONTROL_PREFIX}/routing-snapshot",
                    params={"hostname": HOSTNAME},
                )
            ).status_code == 404
    finally:
        bundle.restore()


@pytest.mark.asyncio
async def test_stale_provider_consent_cannot_publish_a_rotated_claim():
    from testbed.storefront_provider_harness_core import (
        CONTROL_PREFIX,
        create_storefront_provider_harness,
    )

    mongo = FakeMongo()
    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    bundle = create_storefront_provider_harness(
        environment=environment,
        mongo_client=mongo,
        entitlement_service=FakeEntitlements(),
        production_app=_production_route_app(),
    )
    headers = {
        "x-storefront-testbed-run-id": environment.run_id,
        "x-storefront-testbed-control-token": environment.control_token,
    }

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bundle.app),
            base_url="http://127.0.0.1:8112",
            follow_redirects=False,
        ) as client:
            await client.post(
                f"{CONTROL_PREFIX}/configure",
                headers=headers,
                json={"hostname": HOSTNAME, "domain_connect_supported": True},
            )
            first_claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                json={"domain": HOSTNAME, "intent": "new"},
            )
            authorization = await client.post(
                "/admin/storefront/custom-domain/domain-connect/authorize",
                json={"attempt_id": first_claim.json()["attempt_id"]},
            )
            stale_provider_url = authorization.json()["authorization_url"]

            mongo.raw.storefront_domains.update_one(
                {"hostname": HOSTNAME},
                {
                    "$set": {
                        "claim_expires_at": datetime.now(timezone.utc)
                        - timedelta(minutes=1)
                    }
                },
            )

            rotated_claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                json={"domain": HOSTNAME, "intent": "new"},
            )
            assert rotated_claim.status_code == 201
            assert (
                rotated_claim.json()["attempt_id"] != first_claim.json()["attempt_id"]
            )

            stale_consent = await client.post(
                stale_provider_url,
                content="decision=authorize",
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
            assert stale_consent.status_code == 409
            verify = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert verify.status_code == 200
            assert verify.json()["ownership_status"] == "pending"
            assert verify.json()["provider_hostname_id"] is None
    finally:
        bundle.restore()


@pytest.mark.asyncio
async def test_provider_configuration_failure_is_distinct_resumable_and_slug_safe():
    from testbed.storefront_provider_harness_core import (
        CONTROL_PREFIX,
        create_storefront_provider_harness,
    )

    mongo = FakeMongo()
    mongo.raw.user_subscriptions.insert_one(
        {"user_id": OWNER_ID, "plan_id": "plan_signature", "status": "active"}
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "slug": "north-star-signature",
            "is_published": True,
        }
    )
    before_subscriptions = deepcopy(list(mongo.raw.user_subscriptions.find({})))
    before_settings = deepcopy(list(mongo.raw.storefront_settings.find({})))
    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    bundle = create_storefront_provider_harness(
        environment=environment,
        mongo_client=mongo,
        entitlement_service=FakeEntitlements(),
        production_app=_production_route_app(),
    )
    headers = {
        "x-storefront-testbed-run-id": environment.run_id,
        "x-storefront-testbed-control-token": environment.control_token,
    }

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bundle.app),
            base_url="http://127.0.0.1:8112",
        ) as client:
            configured = await client.post(
                f"{CONTROL_PREFIX}/configure",
                headers=headers,
                json={
                    "hostname": HOSTNAME,
                    "provider_configuration_ready": False,
                    "provider_mutations_enabled": True,
                },
            )
            assert configured.status_code == 200
            assert configured.json()["provider_configuration_ready"] is False
            assert configured.json()["provider_mutations_enabled"] is True
            assert configured.json()["provider_configuration_missing"] == [
                "CLOUDFLARE_ZONE_ID",
                "STOREFRONT_CNAME_TARGET",
            ]

            claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                json={"domain": HOSTNAME, "intent": "new"},
            )
            assert claim.status_code == 201
            published = await client.post(
                f"{CONTROL_PREFIX}/publish-claim",
                headers=headers,
                json={"hostname": HOSTNAME},
            )
            assert published.status_code == 200

            unavailable = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert unavailable.status_code == 503
            assert unavailable.json() == {
                "error": {
                    "code": "custom_domain_provider_unavailable",
                    "message": (
                        "Custom-domain provider operations are temporarily unavailable."
                    ),
                    "customer_action": (
                        "Keep using the platform storefront URL and retry later."
                    ),
                    "retryable": True,
                    "support_id": unavailable.json()["error"]["support_id"],
                    "field_errors": {},
                }
            }
            assert unavailable.json()["error"]["support_id"]

            blocked_status = await client.get(
                f"{CONTROL_PREFIX}/status", headers=headers
            )
            assert blocked_status.status_code == 200
            assert blocked_status.json()["cloudflare_call_count"] == 0
            assert blocked_status.json()["provider_records"] == 0
            assert list(mongo.raw.user_subscriptions.find({})) == before_subscriptions
            assert list(mongo.raw.storefront_settings.find({})) == before_settings

            restored = await client.post(
                f"{CONTROL_PREFIX}/advance",
                headers=headers,
                json={
                    "hostname": HOSTNAME,
                    "provider_configuration_ready": True,
                },
            )
            assert restored.status_code == 200
            assert restored.json()["provider_configuration_ready"] is True
            assert restored.json()["provider_configuration_missing"] == []

            resumed = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert resumed.status_code == 200
            assert resumed.json()["provider_hostname_id"].startswith("tb_cf_")
            assert list(mongo.raw.user_subscriptions.find({})) == before_subscriptions
            assert list(mongo.raw.storefront_settings.find({})) == before_settings
    finally:
        bundle.restore()


@pytest.mark.asyncio
async def test_provider_disabled_and_disconnect_failure_remain_structured_and_resumable():
    from testbed.storefront_provider_harness_core import (
        CONTROL_PREFIX,
        create_storefront_provider_harness,
    )

    mongo = FakeMongo()
    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    bundle = create_storefront_provider_harness(
        environment=environment,
        mongo_client=mongo,
        entitlement_service=FakeEntitlements(),
        production_app=_production_route_app(),
    )
    headers = {
        "x-storefront-testbed-run-id": environment.run_id,
        "x-storefront-testbed-control-token": environment.control_token,
    }

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bundle.app),
            base_url="http://127.0.0.1:8112",
        ) as client:
            await client.post(
                f"{CONTROL_PREFIX}/configure",
                headers=headers,
                json={"hostname": HOSTNAME, "provider_mutations_enabled": False},
            )
            claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                json={"domain": HOSTNAME, "intent": "new"},
            )
            await client.post(
                f"{CONTROL_PREFIX}/publish-claim",
                headers=headers,
                json={"hostname": HOSTNAME},
            )
            unavailable = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert unavailable.status_code == 503
            assert unavailable.json()["error"]["code"] == (
                "custom_domain_provider_unavailable"
            )
            assert "detail" not in unavailable.json()
            assert claim.status_code == 201

            await client.post(
                f"{CONTROL_PREFIX}/advance",
                headers=headers,
                json={
                    "hostname": HOSTNAME,
                    "provider_mutations_enabled": True,
                    "provider_status": "active",
                    "ssl_status": "active",
                    "https_ok": True,
                },
            )
            verified = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert verified.status_code == 200
            await client.post(
                f"{CONTROL_PREFIX}/advance",
                headers=headers,
                json={
                    "hostname": HOSTNAME,
                    "provider_status": "active",
                    "ssl_status": "active",
                    "https_ok": True,
                    "fail_next_delete": 1,
                    "reconcile_passes": 1,
                },
            )

            failed_delete = await client.delete("/admin/storefront/custom-domain")
            assert failed_delete.status_code == 502
            assert failed_delete.json()["error"]["code"] == (
                "custom_domain_provider_error"
            )
            failed_status = await client.get("/admin/storefront/custom-domain/status")
            assert failed_status.json()["application_status"] == "disconnect_failed"

            retried_delete = await client.delete("/admin/storefront/custom-domain")
            assert retried_delete.status_code == 200
            assert retried_delete.json()["application_status"] == "disconnected"
            disconnected = (
                await client.get("/admin/storefront/custom-domain/status")
            ).json()
            assert disconnected["application_status"] == "disconnected"
            assert disconnected["action"] == "remove_dns_records"
            assert {record["type"] for record in disconnected["cleanup_records"]} == {
                "TXT",
                "CNAME",
            }
            tombstone = mongo.raw.storefront_domain_tombstones.find_one(
                {"hostname": HOSTNAME}
            )
            assert tombstone["provider_hostname_id"].startswith("tb_cf_")
            delete_operations = list(
                mongo.raw.storefront_domain_operations.find(
                    {
                        "planner_id": OWNER_ID,
                        "hostname": HOSTNAME,
                        "kind": "provider_delete",
                    }
                )
            )
            assert len(delete_operations) == 2
            assert {operation["state"] for operation in delete_operations} == {
                "failed",
                "completed",
            }
            completed_delete = next(
                operation
                for operation in delete_operations
                if operation["state"] == "completed"
            )
            assert (
                tombstone["provider_delete_operation_id"]
                == completed_delete["operation_id"]
            )
            assert (
                tombstone["provider_delete_receipt"]
                == completed_delete["provider_receipt"]
            )

            reconnect_claim = await client.post(
                "/admin/storefront/custom-domain/claim",
                json={"domain": HOSTNAME, "intent": "new"},
            )
            assert reconnect_claim.status_code == 201
            await client.post(
                f"{CONTROL_PREFIX}/publish-claim",
                headers=headers,
                json={"hostname": HOSTNAME},
            )
            reconnect = await client.post(
                "/admin/storefront/custom-domain/verify", json={}
            )
            assert reconnect.status_code == 200
            assert (
                reconnect.json()["provider_hostname_id"]
                != tombstone["provider_hostname_id"]
            )
    finally:
        bundle.restore()


@pytest.mark.asyncio
async def test_manual_advance_never_steals_an_unexpired_reconciliation_lease():
    from testbed.storefront_provider_harness_core import (
        CONTROL_PREFIX,
        create_storefront_provider_harness,
    )

    mongo = FakeMongo()
    environment = storefront_safety.assert_storefront_provider_harness_environment(
        _safe_environment()
    )
    bundle = create_storefront_provider_harness(
        environment=environment,
        mongo_client=mongo,
        entitlement_service=FakeEntitlements(),
        production_app=_production_route_app(),
    )
    headers = {
        "x-storefront-testbed-run-id": environment.run_id,
        "x-storefront-testbed-control-token": environment.control_token,
    }
    now = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=bundle.app),
            base_url="http://127.0.0.1:8112",
        ) as client:
            configured = await client.post(
                f"{CONTROL_PREFIX}/configure",
                headers=headers,
                json={"hostname": HOSTNAME},
            )
            assert configured.status_code == 200
            mongo.raw.storefront_domains.insert_one(
                {
                    "_id": ObjectId(),
                    "planner_id": OWNER_ID,
                    "hostname": HOSTNAME,
                    "application_status": "active",
                    "provider_hostname_id": "tb_cf_locked",
                    "revision": 3,
                    "deletion_status": None,
                    "retry_due_at": now - timedelta(minutes=1),
                    "lease_token": "sdl_background_worker",
                    "lease_expires_at": now + timedelta(minutes=2),
                    "reconciliation_started_at": now,
                }
            )

            advanced = await client.post(
                f"{CONTROL_PREFIX}/advance",
                headers=headers,
                json={"hostname": HOSTNAME, "reconcile_passes": 1},
            )

            assert advanced.status_code == 200
            assert advanced.json()["reconciled"] == 0
            stored = mongo.raw.storefront_domains.find_one({"hostname": HOSTNAME})
            assert stored["lease_token"] == "sdl_background_worker"
            assert abs(
                stored["lease_expires_at"].replace(tzinfo=timezone.utc)
                - (now + timedelta(minutes=2))
            ) < timedelta(milliseconds=1)
    finally:
        bundle.restore()
