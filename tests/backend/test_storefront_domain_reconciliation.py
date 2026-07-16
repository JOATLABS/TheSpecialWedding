from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import ast
from pathlib import Path

from bson import ObjectId
import mongomock
import pytest

from app.services.cloudflare_service import CloudflareServiceError
from app.constants.storefront_domain import STOREFRONT_DOMAIN_APPLICATION_STATUSES
from app.services.storefront_domain_reconciliation_service import (
    StorefrontDomainReconciliationService,
)


OWNER_ID = "507f1f77bcf86cd799439011"
HOSTNAME = "events.customer.example"
ZONE = "customer.example"
CNAME_TARGET = "domains.thespecialwedding.com"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_persisted_application_status_literals_are_from_the_approved_enum():
    assert STOREFRONT_DOMAIN_APPLICATION_STATUSES == {
        "claim_pending",
        "authorization_pending",
        "authorization_cancelled",
        "dns_setup_pending",
        "migration_prevalidation",
        "cutover_ready",
        "provider_provisioning",
        "hostname_validation",
        "certificate_validation",
        "deploying",
        "active",
        "action_required",
        "operator_review",
        "disconnecting",
        "disconnect_failed",
        "disconnected",
        "expired",
    }
    observed: set[str] = set()
    for relative in (
        "app/services/storefront_domain_service.py",
        "app/services/storefront_domain_connect_service.py",
        "app/services/storefront_domain_reconciliation_service.py",
    ):
        tree = ast.parse((PROJECT_ROOT / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "application_status"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    observed.add(value.value)

    assert observed <= STOREFRONT_DOMAIN_APPLICATION_STATUSES


class AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, value):
        self._cursor = self._cursor.limit(value)
        return self

    async def to_list(self, length=None):
        rows = list(self._cursor)
        return rows if length is None else rows[:length]


class AsyncCollection:
    def __init__(self, collection):
        self._collection = collection

    async def find_one(self, *args, **kwargs):
        return self._collection.find_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return AsyncCursor(self._collection.find(*args, **kwargs))

    async def find_one_and_update(self, query, update, **kwargs):
        return self._collection.find_one_and_update(query, update, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._collection.update_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._collection.insert_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._collection.delete_one(*args, **kwargs)


class AsyncDatabase:
    def __init__(self, raw):
        self.raw = raw
        self._collections = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = AsyncCollection(self.raw[name])
        return self._collections[name]


class FakeMongo:
    def __init__(self):
        self.raw = mongomock.MongoClient()["domain_reconciliation_test"]
        self.db = AsyncDatabase(self.raw)


class FakeCloudflare:
    def __init__(self):
        self.read: list[str] = []
        self.deleted: list[str] = []
        self.listed: list[str] = []
        self.error: CloudflareServiceError | None = None
        self.result = {
            "id": "cf-hostname-1",
            "hostname": HOSTNAME,
            "created_at": "2026-07-15T21:00:00Z",
            "status": "active",
            "ssl": {"status": "active", "validation_records": []},
        }

    async def get_custom_hostname(self, hostname_id: str) -> dict:
        self.read.append(hostname_id)
        if self.error:
            raise self.error
        return deepcopy(self.result)

    async def list_custom_hostnames(self, hostname: str) -> list[dict]:
        self.listed.append(hostname)
        if self.error:
            raise self.error
        return [deepcopy(self.result)]

    async def delete_custom_hostname(self, hostname_id: str) -> dict:
        self.deleted.append(hostname_id)
        return {"id": hostname_id}


class FakeDns:
    def __init__(self):
        self.cname_values = [CNAME_TARGET]
        self.nameserver_values = [
            "ada.ns.cloudflare.com",
            "bob.ns.cloudflare.com",
        ]
        self.calls: list[tuple[str, str]] = []

    async def query(self, name: str, record_type: str) -> list[str]:
        self.calls.append((name, record_type))
        if name == ZONE and record_type == "NS":
            return list(self.nameserver_values)
        if name == HOSTNAME and record_type == "CNAME":
            return list(self.cname_values)
        return []

    async def query_authoritative(
        self, name: str, record_type: str, nameservers: list[str]
    ) -> list[str]:
        self.calls.append(
            (name, f"authoritative:{record_type}:{','.join(nameservers)}")
        )
        if name == HOSTNAME and record_type == "CNAME":
            return list(self.cname_values)
        return []


class FakeHttps:
    def __init__(self, verified: bool = True):
        self.verified = verified
        self.calls: list[tuple[str, int, str]] = []

    async def verify(self, record: dict) -> bool:
        self.calls.append(
            (record["hostname"], record["revision"], str(record["planner_id"]))
        )
        return self.verified


class FakeDomainLifecycle:
    def __init__(self):
        self.verify_calls: list[str] = []
        self.observe_pending_calls: list[str] = []
        self.disconnect_calls: list[str] = []

    async def verify(self, owner: dict) -> dict:
        self.verify_calls.append(str(owner["_id"]))
        return {}

    async def observe_pending_for_owner_id(self, owner_id: str) -> dict:
        self.observe_pending_calls.append(owner_id)
        return {}

    async def _disconnect_claim_record(self, _collection, _record, owner_id: str):
        self.disconnect_calls.append(owner_id)


@pytest.mark.asyncio
async def test_worker_observes_pending_dns_without_calling_activation_verify(
    setup_worker,
):
    worker, mongo, cloudflare, _, _, lifecycle, now = setup_worker
    domain = _record(
        now,
        application_status="dns_setup_pending",
        provider_hostname_id=None,
        provider_status="not_created",
        provider_hostname_status="not_created",
        ssl_status="not_started",
    )
    mongo.raw.storefront_domains.insert_one(domain)

    await worker.sweep_due(batch_size=1)

    assert lifecycle.observe_pending_calls == [OWNER_ID]
    assert lifecycle.verify_calls == []
    assert cloudflare.read == []
    assert cloudflare.listed == []


def _record(now: datetime, **overrides) -> dict:
    value = {
        "_id": ObjectId(),
        "planner_id": OWNER_ID,
        "hostname": HOSTNAME,
        "claim_attempt_id": "attempt-1",
        "revision": 1,
        "application_status": "certificate_validation",
        "status": "pending",
        "ownership_status": "verified",
        "routing_dns_status": "verified",
        "provider_hostname_status": "active",
        "provider_status": "active",
        "provider_hostname_id": "cf-hostname-1",
        "provider_ssl_method": "txt",
        "provider_ssl_type": "dv",
        "ssl_status": "active",
        "https_status": "pending",
        "custom_route_enabled": False,
        "action": "processing",
        "retry_due_at": now,
        "lease_expires_at": None,
        "deletion_status": None,
        "authoritative_dns": {
            "zone": "customer.example",
            "provider": "cloudflare",
            "nameservers": ["ada.ns.cloudflare.com", "bob.ns.cloudflare.com"],
        },
        "updated_at": now,
    }
    value.update(overrides)
    return value


@pytest.fixture
def setup_worker():
    now = datetime(2026, 7, 15, 21, 0, tzinfo=timezone.utc)
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    dns = FakeDns()
    https = FakeHttps()
    lifecycle = FakeDomainLifecycle()
    worker = StorefrontDomainReconciliationService(
        mongo_client=mongo,
        cloudflare_service=cloudflare,
        dns_resolver=dns,
        https_verifier=https,
        domain_service=lifecycle,
        cname_target=CNAME_TARGET,
        now=lambda: now,
        jitter=lambda _low, _high: 0.0,
    )
    return worker, mongo, cloudflare, dns, https, lifecycle, now


@pytest.mark.asyncio
async def test_worker_lease_and_all_five_proofs_are_required_for_activation(
    setup_worker,
):
    worker, mongo, cloudflare, _, https, _, now = setup_worker
    domain = _record(now)
    mongo.raw.storefront_domains.insert_one(domain)

    processed = await worker.sweep_due(batch_size=1)

    assert processed == 1
    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == "active"
    assert saved["custom_route_enabled"] is True
    assert saved["ownership_status"] == "verified"
    assert saved["routing_dns_status"] == "verified"
    assert saved["provider_hostname_status"] == "active"
    assert saved["ssl_status"] == "active"
    assert saved["https_status"] == "verified"
    assert "lease_token" not in saved
    assert "lease_expires_at" not in saved
    assert cloudflare.read == ["cf-hostname-1"]
    assert https.calls == [(HOSTNAME, 1, OWNER_ID)]
    assert (
        HOSTNAME,
        "authoritative:CNAME:ada.ns.cloudflare.com,bob.ns.cloudflare.com",
    ) in setup_worker[3].calls

    https.verified = False
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]}, {"$set": {"retry_due_at": now}}
    )
    await worker.sweep_due(batch_size=1)
    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == "action_required"
    assert saved["action"] == "action_required"
    assert saved["https_status"] == "failed"
    assert saved["custom_route_enabled"] is False
    assert saved["last_error"]["code"] == "custom_domain_https_unreachable"
    assert saved["last_error"]["customer_action"]
    assert saved["last_error"]["retryable"] is True
    operational_alert = mongo.raw.notifications.find_one(
        {"type": "storefront_domain_operations"}
    )
    assert operational_alert["target_audience"] == "root_admin"
    assert operational_alert["metadata"]["category"] == "action_required"
    assert (
        mongo.raw.storefront_domain_operational_metrics.find_one(
            {"name": "storefront.domain.operational_alert"}
        )["value"]
        == 1
    )


@pytest.mark.asyncio
async def test_worker_redelegation_revokes_route_before_stale_routing_proof(
    setup_worker,
):
    worker, mongo, cloudflare, dns, https, _, now = setup_worker
    domain = _record(
        now,
        application_status="active",
        status="active",
        https_status="verified",
        custom_route_enabled=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    dns.nameserver_values = [
        "ns1.redelegated.example.net",
        "ns2.redelegated.example.net",
    ]

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == "action_required"
    assert saved["ownership_status"] == "expired"
    assert saved["routing_dns_status"] == "mismatch"
    assert saved["custom_route_enabled"] is False
    assert saved["last_error"]["code"] == "authoritative_dns_delegation_changed"
    assert cloudflare.read == []
    assert https.calls == []
    assert not any("authoritative:CNAME" in record_type for _, record_type in dns.calls)


@pytest.mark.asyncio
async def test_worker_adopts_legacy_due_row_without_retry_timestamp(setup_worker):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(now, application_status="active", status="active")
    domain.pop("retry_due_at")
    mongo.raw.storefront_domains.insert_one(domain)

    assert await worker.sweep_due(batch_size=1) == 1

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == "active"
    assert saved["retry_due_at"].replace(tzinfo=timezone.utc) > now
    assert cloudflare.read == ["cf-hostname-1"]


@pytest.mark.asyncio
async def test_disconnect_or_revision_change_during_https_probe_cannot_reenable_route(
    setup_worker,
):
    worker, mongo, _, _, _, _, now = setup_worker
    domain = _record(now)
    mongo.raw.storefront_domains.insert_one(domain)

    class DisconnectDuringProbe:
        async def verify(self, leased: dict) -> bool:
            mongo.raw.storefront_domains.update_one(
                {"_id": leased["_id"]},
                {
                    "$set": {
                        "revision": leased["revision"] + 1,
                        "application_status": "disconnecting",
                        "status": "deleting",
                        "deletion_status": "provider_delete_pending",
                        "custom_route_enabled": False,
                    },
                    "$unset": {
                        "lease_token": "",
                        "lease_expires_at": "",
                        "reconciliation_started_at": "",
                    },
                },
            )
            return True

    worker._https = DisconnectDuringProbe()

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["revision"] == 2
    assert saved["application_status"] == "disconnecting"
    assert saved["status"] == "deleting"
    assert saved["deletion_status"] == "provider_delete_pending"
    assert saved["custom_route_enabled"] is False


@pytest.mark.asyncio
async def test_stale_probe_writer_releases_only_its_lease_after_revision_change(
    setup_worker,
):
    worker, mongo, _, _, _, _, now = setup_worker
    domain = _record(now)
    mongo.raw.storefront_domains.insert_one(domain)

    class ObservationChangedDuringProbe:
        async def verify(self, leased: dict) -> bool:
            mongo.raw.storefront_domains.update_one(
                {"_id": leased["_id"]},
                {
                    "$set": {
                        "revision": leased["revision"] + 1,
                        "observation_requested_at": now,
                        "retry_due_at": now,
                    }
                },
            )
            return False

    worker._https = ObservationChangedDuringProbe()

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["revision"] == 2
    assert saved["application_status"] == "certificate_validation"
    assert saved["https_status"] == "pending"
    assert saved["retry_due_at"].replace(tzinfo=timezone.utc) == now
    assert "lease_token" not in saved
    assert "lease_expires_at" not in saved
    assert "reconciliation_started_at" not in saved


@pytest.mark.asyncio
@pytest.mark.parametrize("stale_writer", ["defer", "release", "authorization"])
async def test_every_leased_followup_write_loses_to_disconnect_revision(
    setup_worker, stale_writer
):
    worker, mongo, _, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status=(
            "authorization_pending"
            if stale_writer == "authorization"
            else "certificate_validation"
        ),
        provider_hostname_id=(
            None if stale_writer == "authorization" else "cf-hostname-1"
        ),
    )
    mongo.raw.storefront_domains.insert_one(domain)
    if stale_writer == "authorization":
        mongo.raw.storefront_domain_flows.insert_one(
            {
                "_id": ObjectId(),
                "domain_id": str(domain["_id"]),
                "attempt_id": domain["claim_attempt_id"],
                "planner_id": OWNER_ID,
                "state": "authorized",
                "expires_at": now + timedelta(minutes=10),
            }
        )
    leased = await worker._lease_one()
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {
            "$set": {
                "revision": leased["revision"] + 1,
                "application_status": "disconnecting",
                "status": "deleting",
                "deletion_status": "provider_delete_pending",
                "custom_route_enabled": False,
                "action": "processing",
                "last_error": {"code": "disconnect_requested"},
            }
        },
    )

    if stale_writer == "defer":
        await worker._defer_failure(leased, RuntimeError("stale provider read"))
    elif stale_writer == "release":
        await worker._release_if_still_leased(leased, timedelta(minutes=5))
    else:
        await worker._reconcile_authorization_flow(leased)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["revision"] == leased["revision"] + 1
    assert saved["application_status"] == "disconnecting"
    assert saved["deletion_status"] == "provider_delete_pending"
    assert saved["last_error"] == {"code": "disconnect_requested"}


@pytest.mark.asyncio
async def test_two_spaced_routing_mismatches_revoke_only_custom_route(setup_worker):
    worker, mongo, _, dns, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="active",
        status="active",
        https_status="verified",
        custom_route_enabled=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    mongo.raw.storefront_settings.insert_one(
        {"planner_id": OWNER_ID, "slug": "still-public", "is_published": True}
    )
    dns.cname_values = ["wrong.example.net"]

    await worker.sweep_due(batch_size=1)
    first = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert first["routing_mismatch_count"] == 1
    assert first["custom_route_enabled"] is True

    later = now + timedelta(minutes=10)
    worker._now = lambda: later
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]}, {"$set": {"retry_due_at": later}}
    )
    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["routing_mismatch_count"] == 2
    assert saved["application_status"] == "action_required"
    assert saved["custom_route_enabled"] is False
    settings = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert settings == {
        "_id": settings["_id"],
        "planner_id": OWNER_ID,
        "slug": "still-public",
        "is_published": True,
    }


@pytest.mark.asyncio
async def test_transient_provider_failure_releases_lease_with_bounded_backoff(
    setup_worker,
):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="active",
        status="active",
        https_status="verified",
        custom_route_enabled=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    cloudflare.error = CloudflareServiceError(
        "provider unavailable",
        operation="get_custom_hostname",
        kind="transport",
        errors=[{"code": "transport", "message": "raw provider diagnostic"}],
    )

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == "active"
    assert saved["custom_route_enabled"] is True
    assert saved["last_error"]["code"] == "domain_reconciliation_failed"
    assert "errors" not in saved["last_error"]["provider"]
    assert saved["provider_last_error"] == cloudflare.error.as_dict()
    assert (
        now
        < saved["retry_due_at"].replace(tzinfo=timezone.utc)
        <= now + timedelta(hours=1)
    )
    assert "lease_token" not in saved
    assert "lease_expires_at" not in saved


@pytest.mark.asyncio
async def test_provider_5xx_alert_resolves_after_a_successful_provider_read(
    setup_worker,
):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="certificate_validation",
        custom_route_enabled=False,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    cloudflare.error = CloudflareServiceError(
        "provider unavailable",
        operation="get_custom_hostname",
        kind="provider",
        provider_status_code=503,
        errors=[{"code": 1000, "message": "bounded provider failure"}],
    )

    await worker.sweep_due(batch_size=1)

    failed = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert failed["provider_last_error"]["provider_status_code"] == 503
    alert = mongo.raw.notifications.find_one(
        {"metadata.category": "provider_server_error"}
    )
    assert alert["target_audience"] == "root_admin"
    assert (
        mongo.raw.storefront_domain_operational_metrics.find_one(
            {"name": "storefront.domain.provider_outcome"}
        )["value"]
        == 1
    )

    cloudflare.error = None
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]},
        {"$set": {"retry_due_at": now}},
    )
    await worker.sweep_due(batch_size=1)

    recovered = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert "provider_last_error" not in recovered
    assert recovered["operational_alerts"]["provider_server_error"]["active"] is False
    assert recovered["operational_alerts"]["provider_outcome_metric"]["active"] is False
    assert (
        mongo.raw.notifications.count_documents(
            {"metadata.category": "provider_server_error"}
        )
        == 1
    )


@pytest.mark.asyncio
async def test_authoritative_provider_404_fails_closed_and_preserves_raw_error(
    setup_worker,
):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="active",
        status="active",
        https_status="verified",
        custom_route_enabled=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    cloudflare.error = CloudflareServiceError(
        "provider hostname not found",
        operation="get_custom_hostname",
        kind="provider",
        provider_status_code=404,
        errors=[{"code": 1001, "message": "missing"}],
    )

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == "operator_review"
    assert saved["action"] == "operator_review"
    assert saved["custom_route_enabled"] is False
    assert saved["provider_status"] == "not_found"
    assert saved["provider_hostname_status"] == "not_found"
    assert saved["https_status"] == "pending"
    assert saved["last_error"]["code"] == "provider_hostname_missing"
    assert saved["last_error"]["retryable"] is False
    assert saved["last_error"]["customer_action"]
    assert saved["provider_last_error"] == cloudflare.error.as_dict()
    assert "lease_token" not in saved
    assert "lease_expires_at" not in saved


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mismatch",
    [
        {"id": "different-provider-id"},
        {"hostname": "another.customer.example"},
        {"hostname": "not a hostname"},
    ],
)
async def test_provider_identity_mismatch_fails_closed_for_operator_review(
    setup_worker, mismatch
):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="active",
        status="active",
        https_status="verified",
        custom_route_enabled=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    cloudflare.result.update(mismatch)

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == "operator_review"
    assert saved["action"] == "operator_review"
    assert saved["custom_route_enabled"] is False
    assert saved["provider_hostname_status"] == "identity_mismatch"
    assert saved["https_status"] == "pending"
    assert saved["last_error"]["code"] == "provider_hostname_identity_mismatch"
    assert saved["last_error"]["retryable"] is False
    assert saved["provider_last_observation"] == cloudflare.result
    assert "lease_token" not in saved


@pytest.mark.asyncio
async def test_provider_identity_mismatch_loses_to_concurrent_disconnect(
    setup_worker, monkeypatch
):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="active",
        status="active",
        https_status="verified",
        custom_route_enabled=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    original_get = cloudflare.get_custom_hostname

    async def disconnect_before_provider_result(hostname_id: str) -> dict:
        result = await original_get(hostname_id)
        mongo.raw.storefront_domains.update_one(
            {"_id": domain["_id"]},
            {
                "$set": {
                    "revision": 2,
                    "application_status": "disconnecting",
                    "status": "deleting",
                    "deletion_status": "provider_delete_pending",
                    "custom_route_enabled": False,
                    "last_error": {"code": "disconnect_requested"},
                }
            },
        )
        result["id"] = "mismatched-provider-id"
        return result

    monkeypatch.setattr(
        cloudflare, "get_custom_hostname", disconnect_before_provider_result
    )

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["revision"] == 2
    assert saved["application_status"] == "disconnecting"
    assert saved["deletion_status"] == "provider_delete_pending"
    assert saved["custom_route_enabled"] is False
    assert saved["last_error"] == {"code": "disconnect_requested"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_status", "application_status", "action", "error_code"),
    [
        ("blocked", "operator_review", "operator_review", "provider_hostname_blocked"),
        (
            "pending_blocked",
            "operator_review",
            "operator_review",
            "provider_hostname_blocked",
        ),
        (
            "test_blocked",
            "operator_review",
            "operator_review",
            "provider_hostname_blocked",
        ),
        ("moved", "action_required", "action_required", "provider_hostname_inactive"),
        ("deleted", "action_required", "action_required", "provider_hostname_inactive"),
        (
            "pending_deletion",
            "action_required",
            "action_required",
            "provider_hostname_inactive",
        ),
        (
            "test_failed",
            "action_required",
            "action_required",
            "provider_hostname_inactive",
        ),
    ],
)
async def test_terminal_provider_statuses_have_actionable_fail_closed_state(
    setup_worker, provider_status, application_status, action, error_code
):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="active",
        status="active",
        https_status="verified",
        custom_route_enabled=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    cloudflare.result.update(
        {
            "status": provider_status,
            "verification_errors": [
                "  Custom hostname does not CNAME to this zone.  ",
                "Custom hostname does not CNAME to this zone.",
            ],
        }
    )

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == application_status
    assert saved["action"] == action
    assert saved["custom_route_enabled"] is False
    assert saved["provider_status"] == provider_status
    assert saved["provider_hostname_status"] == provider_status
    assert saved["https_status"] == "pending"
    assert saved["last_error"]["code"] == error_code
    assert saved["last_error"]["customer_action"]
    assert saved["provider_last_observation"]["status"] == provider_status
    assert saved["provider_verification_errors"] == [
        "Custom hostname does not CNAME to this zone."
    ]


@pytest.mark.asyncio
async def test_terminal_provider_status_fails_closed_without_waiting_on_dns(
    setup_worker, monkeypatch
):
    worker, mongo, cloudflare, dns, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="active",
        status="active",
        https_status="verified",
        custom_route_enabled=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    cloudflare.result["status"] = "blocked"

    async def unavailable_dns(*_args, **_kwargs):
        raise RuntimeError("DNS observation must not mask terminal provider state")

    monkeypatch.setattr(dns, "query_authoritative", unavailable_dns)

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == "operator_review"
    assert saved["custom_route_enabled"] is False
    assert saved["last_error"]["code"] == "provider_hostname_blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ssl_status",
    [
        "deleted",
        "expired",
        "inactive",
        "initializing_timed_out",
        "validation_timed_out",
        "issuance_timed_out",
        "deployment_timed_out",
        "deletion_timed_out",
    ],
)
async def test_terminal_ssl_statuses_have_actionable_fail_closed_state(
    setup_worker, ssl_status
):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="active",
        status="active",
        https_status="verified",
        custom_route_enabled=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    cloudflare.result["ssl"] = {
        "status": ssl_status,
        "validation_errors": [
            {"message": "  Certificate validation record was not found.  "}
        ],
        "validation_records": [],
    }

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == "action_required"
    assert saved["action"] == "action_required"
    assert saved["custom_route_enabled"] is False
    assert saved["ssl_status"] == ssl_status
    assert saved["https_status"] == "pending"
    assert saved["last_error"]["code"] == "provider_certificate_inactive"
    assert saved["last_error"]["customer_action"]
    assert saved["ssl_validation_errors"] == [
        "Certificate validation record was not found."
    ]


@pytest.mark.asyncio
async def test_worker_reconciles_one_demonstrably_new_ambiguous_create(setup_worker):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="operator_review",
        provider_hostname_id=None,
        provider_hostname_status="unknown",
        provider_status="unknown",
        ssl_status="not_started",
        provider_reconciliation_required=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    mongo.raw.storefront_domain_operations.insert_one(
        {
            "_id": ObjectId(),
            "operation_id": "create-1",
            "domain_id": str(domain["_id"]),
            "attempt_id": "create-1",
            "kind": "provider_create",
            "state": "operator_review",
            "provider_ids_before": [],
            "created_at": now,
        }
    )

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["provider_hostname_id"] == "cf-hostname-1"
    assert saved["application_status"] == "active"
    receipt = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": "create-1"}
    )
    assert receipt["state"] == "completed"
    assert cloudflare.listed == [HOSTNAME]


@pytest.mark.asyncio
async def test_worker_rejects_provider_row_created_before_ambiguous_attempt(
    setup_worker,
):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="operator_review",
        provider_hostname_id=None,
        provider_hostname_status="unknown",
        provider_status="unknown",
        ssl_status="not_started",
        provider_reconciliation_required=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    mongo.raw.storefront_domain_operations.insert_one(
        {
            "_id": ObjectId(),
            "operation_id": "create-stale",
            "domain_id": str(domain["_id"]),
            "attempt_id": "create-stale",
            "kind": "provider_create",
            "state": "operator_review",
            "provider_ids_before": [],
            "created_at": now,
        }
    )
    cloudflare.result["created_at"] = "2026-07-15T20:00:00Z"

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["provider_hostname_id"] is None
    assert saved["application_status"] == "operator_review"


@pytest.mark.asyncio
async def test_ambiguous_provider_adoption_loses_to_concurrent_disconnect(
    setup_worker, monkeypatch
):
    worker, mongo, cloudflare, _, _, _, now = setup_worker
    domain = _record(
        now,
        application_status="operator_review",
        provider_hostname_id=None,
        provider_hostname_status="unknown",
        provider_status="unknown",
        ssl_status="not_started",
        provider_reconciliation_required=True,
    )
    mongo.raw.storefront_domains.insert_one(domain)
    mongo.raw.storefront_domain_operations.insert_one(
        {
            "_id": ObjectId(),
            "operation_id": "create-race",
            "domain_id": str(domain["_id"]),
            "attempt_id": "create-race",
            "kind": "provider_create",
            "state": "operator_review",
            "provider_ids_before": [],
            "created_at": now,
        }
    )
    original_list = cloudflare.list_custom_hostnames

    async def disconnect_before_list_returns(hostname: str) -> list[dict]:
        result = await original_list(hostname)
        current = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
        mongo.raw.storefront_domains.update_one(
            {"_id": domain["_id"]},
            {
                "$set": {
                    "revision": current["revision"] + 1,
                    "application_status": "disconnecting",
                    "status": "deleting",
                    "deletion_status": "provider_delete_pending",
                    "custom_route_enabled": False,
                }
            },
        )
        return result

    monkeypatch.setattr(
        cloudflare, "list_custom_hostnames", disconnect_before_list_returns
    )

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["provider_hostname_id"] is None
    assert saved["application_status"] == "disconnecting"
    receipt = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": "create-race"}
    )
    assert receipt["state"] == "operator_review"


@pytest.mark.asyncio
async def test_migration_waits_at_cutover_ready_without_counting_pre_cutover_drift(
    setup_worker,
):
    worker, mongo, _, dns, https, _, now = setup_worker
    domain = _record(
        now,
        intent="migration",
        application_status="certificate_validation",
        routing_dns_status="pending",
    )
    mongo.raw.storefront_domains.insert_one(domain)
    dns.cname_values = ["legacy-origin.customer.example"]

    await worker.sweep_due(batch_size=1)

    waiting = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert waiting["application_status"] == "cutover_ready"
    assert waiting["action"] == "action_required"
    assert waiting["custom_route_enabled"] is False
    assert "routing_mismatch_count" not in waiting
    assert https.calls == []

    later = now + timedelta(minutes=1)
    worker._now = lambda: later
    dns.cname_values = [CNAME_TARGET]
    mongo.raw.storefront_domains.update_one(
        {"_id": domain["_id"]}, {"$set": {"retry_due_at": later}}
    )

    await worker.sweep_due(batch_size=1)

    active = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert active["application_status"] == "active"
    assert active["custom_route_enabled"] is True
    assert active["migration_cutover_completed_at"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application_status", "deletion_status"),
    [
        ("disconnecting", "provider_delete_pending"),
        ("disconnect_failed", "retry_pending"),
        ("disconnected", "local_cleanup_pending"),
    ],
)
async def test_worker_leases_every_durable_disconnect_stage(
    setup_worker, application_status, deletion_status
):
    worker, mongo, _, _, _, lifecycle, now = setup_worker
    domain = _record(
        now,
        application_status=application_status,
        deletion_status=deletion_status,
    )
    mongo.raw.storefront_domains.insert_one(domain)

    await worker.sweep_due(batch_size=1)

    assert lifecycle.disconnect_calls == [OWNER_ID]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flow_state", "completion_outcome", "expected_status"),
    [
        ("authorization_pending", None, "expired"),
        ("authorized", None, "authorization_pending"),
        ("completing", None, "authorization_pending"),
        ("consumed", "authorized", "dns_setup_pending"),
        ("consumed", "cancelled", "authorization_cancelled"),
        ("consumed", "failed", "action_required"),
        ("consumed", None, "action_required"),
        ("cancelled", None, "authorization_pending"),
        ("failed", None, "authorization_pending"),
    ],
)
async def test_worker_advances_domain_connect_only_after_authenticated_completion(
    setup_worker, flow_state, completion_outcome, expected_status
):
    worker, mongo, cloudflare, _, _, lifecycle, now = setup_worker
    domain = _record(
        now,
        application_status="authorization_pending",
        provider_hostname_id=None,
        provider_status="not_created",
        provider_hostname_status="not_created",
        ssl_status="not_started",
    )
    mongo.raw.storefront_domains.insert_one(domain)
    mongo.raw.storefront_domain_flows.insert_one(
        {
            "_id": ObjectId(),
            "domain_id": str(domain["_id"]),
            "attempt_id": domain["claim_attempt_id"],
            "planner_id": OWNER_ID,
            "state": flow_state,
            "completion_outcome": completion_outcome,
            "expires_at": (
                now - timedelta(seconds=1)
                if flow_state == "authorization_pending"
                else now + timedelta(minutes=10)
            ),
        }
    )

    await worker.sweep_due(batch_size=1)

    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert saved["application_status"] == expected_status
    if flow_state not in {"authorization_pending", "consumed"}:
        assert saved["retry_due_at"].replace(tzinfo=timezone.utc) == (
            now + timedelta(minutes=10)
        )
    assert cloudflare.read == []
    assert lifecycle.verify_calls == []


@pytest.mark.asyncio
async def test_worker_leases_cleanup_retry_without_cross_owner_mutation(setup_worker):
    worker, mongo, _, _, _, lifecycle, now = setup_worker
    domain = _record(
        now,
        application_status="disconnect_failed",
        deletion_status="retry_pending",
    )
    mongo.raw.storefront_domains.insert_one(domain)

    await worker.sweep_due(batch_size=1)

    assert lifecycle.disconnect_calls == [OWNER_ID]
    saved = mongo.raw.storefront_domains.find_one({"_id": domain["_id"]})
    assert "lease_token" not in saved
    assert "lease_expires_at" not in saved


@pytest.mark.asyncio
async def test_worker_alerts_on_verified_conflict_review_outside_domain_leases(
    setup_worker,
):
    worker, mongo, cloudflare, _, _, lifecycle, now = setup_worker
    mongo.raw.storefront_domain_conflict_claims.insert_one(
        {
            "_id": ObjectId(),
            "claimant_planner_id": "planner-conflict-secret",
            "hostname": "reserved.customer-secret.example",
            "attempt_id": "sdc_attempt_secret",
            "revision": 2,
            "application_status": "operator_review",
            "ownership_status": "verified",
            "last_error": {
                "code": "hostname_conflict_requires_review",
                "support_id": "sfd_conflict_worker",
            },
            "updated_at": now,
        }
    )

    processed = await worker.sweep_due(batch_size=1)

    assert processed == 0
    alert = mongo.raw.notifications.find_one(
        {"metadata.support_id": "sfd_conflict_worker"}
    )
    assert alert["target_audience"] == "root_admin"
    assert alert["action_url"] == "/admin/platform?tab=storefront"
    serialized = repr(alert)
    assert "reserved.customer-secret.example" not in serialized
    assert "planner-conflict-secret" not in serialized
    assert "sdc_attempt_secret" not in serialized
    assert cloudflare.read == []
    assert lifecycle.verify_calls == []
