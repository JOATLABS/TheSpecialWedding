from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import mongomock
import pytest

from app.api.storefront_domain_operator import router as operator_router
from app.dependencies.auth_extended import get_current_user_extended
from app.services.cloudflare_service import CloudflareServiceError
from app.services.storefront_domain_operator_service import (
    StorefrontDomainOperatorService,
)


OWNER_ID = "507f1f77bcf86cd799439011"
OTHER_OWNER_ID = "507f1f77bcf86cd799439012"
HOSTNAME = "events.customer.example"
ATTEMPT_ID = "claim-attempt-1"
PROVIDER_ATTEMPT_ID = "provider-attempt-1"


class AsyncCollection:
    def __init__(self, collection):
        self._collection = collection

    async def find_one(self, *args, **kwargs):
        return self._collection.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._collection.update_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return AsyncCursor(self._collection.find(*args, **kwargs))


class AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, value: int):
        self._cursor = self._cursor.limit(value)
        return self

    async def to_list(self, *, length: int):
        return list(self._cursor)[:length]


class AsyncDatabase:
    def __init__(self, raw_database):
        self.raw = raw_database
        self._collections: dict[str, AsyncCollection] = {}

    def __getitem__(self, name: str) -> AsyncCollection:
        if name not in self._collections:
            self._collections[name] = AsyncCollection(self.raw[name])
        return self._collections[name]


class FakeMongo:
    def __init__(self):
        self.raw = mongomock.MongoClient()["storefront_operator_test"]
        self.db = AsyncDatabase(self.raw)
        self.raw.storefront_domain_operations.create_index("operation_id", unique=True)
        self.raw.storefront_domain_operations.create_index(
            [("domain_id", 1), ("attempt_id", 1), ("kind", 1)],
            unique=True,
        )


class FakeCloudflare:
    def __init__(self):
        self.rows: list[dict] = []
        self.listed: list[str] = []
        self.list_error: CloudflareServiceError | None = None
        self.before_return = None

    async def list_custom_hostnames(self, hostname: str) -> list[dict]:
        self.listed.append(hostname)
        if self.list_error:
            raise self.list_error
        if self.before_return:
            self.before_return()
        return deepcopy(self.rows)


def _actor(*, root: bool = True):
    return SimpleNamespace(
        is_root_admin=root,
        email="thedeveloper@thespecialwedding.io",
    )


def _o2o_record(*, revision: int = 7) -> dict:
    return {
        "_id": ObjectId(),
        "planner_id": OWNER_ID,
        "hostname": HOSTNAME,
        "claim_attempt_id": ATTEMPT_ID,
        "revision": revision,
        "status": "pending",
        "application_status": "operator_review",
        "ownership_status": "verified",
        "intent": "migration",
        "authoritative_dns": {
            "zone": "customer.example",
            "provider": "cloudflare",
            "nameservers": ["ada.ns.cloudflare.com"],
        },
        "provider_hostname_id": None,
        "deletion_status": None,
        "last_error": {
            "code": "cloudflare_o2o_migration_requires_assistance",
        },
    }


def _conflict_record(*, revision: int = 4) -> dict:
    return {
        "_id": ObjectId(),
        "claimant_planner_id": OWNER_ID,
        "current_owner_key": OWNER_ID,
        "hostname": HOSTNAME,
        "attempt_id": ATTEMPT_ID,
        "revision": revision,
        "status": "pending",
        "application_status": "operator_review",
        "ownership_status": "verified",
    }


def _ambiguous_record(*, revision: int = 11) -> dict:
    return {
        "_id": ObjectId(),
        "planner_id": OWNER_ID,
        "hostname": HOSTNAME,
        "provider_create_attempt_id": PROVIDER_ATTEMPT_ID,
        "revision": revision,
        "status": "pending",
        "application_status": "operator_review",
        "provider_reconciliation_required": True,
        "provider_hostname_id": None,
        "provider_ids_before": ["cf-before"],
        "deletion_status": None,
        "intent": "new",
    }


def _insert_create_receipt(mongo: FakeMongo, record: dict) -> None:
    started_at = datetime.now(timezone.utc) - timedelta(seconds=15)
    mongo.raw.storefront_domain_operations.insert_one(
        {
            "_id": ObjectId(),
            "operation_id": PROVIDER_ATTEMPT_ID,
            "domain_id": str(record["_id"]),
            "attempt_id": PROVIDER_ATTEMPT_ID,
            "kind": "provider_create",
            "planner_id": OWNER_ID,
            "hostname": HOSTNAME,
            "state": "operator_review",
            "provider_ids_before": ["cf-before"],
            "provider_request_started_at": started_at,
            "provider_request_window_ends_at": started_at + timedelta(minutes=2),
            "provider_outcome_unknown_at": started_at + timedelta(seconds=10),
            "created_at": started_at,
        }
    )


@pytest.mark.asyncio
async def test_o2o_approval_is_root_admin_owner_revision_and_replay_fenced():
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    record = _o2o_record()
    mongo.raw.storefront_domains.insert_one(record)
    service = StorefrontDomainOperatorService(mongo, cloudflare)

    with pytest.raises(HTTPException) as non_root:
        await service.approve_o2o_cutover(
            _actor(root=False),
            planner_id=OWNER_ID,
            hostname=HOSTNAME,
            attempt_id=ATTEMPT_ID,
            revision=7,
            reason="This is a sufficiently detailed review reason.",
        )
    assert non_root.value.status_code == 403

    with pytest.raises(HTTPException) as wrong_owner:
        await service.approve_o2o_cutover(
            _actor(),
            planner_id=OTHER_OWNER_ID,
            hostname=HOSTNAME,
            attempt_id=ATTEMPT_ID,
            revision=7,
            reason="This is a sufficiently detailed review reason.",
        )
    assert wrong_owner.value.status_code == 404

    with pytest.raises(HTTPException) as stale:
        await service.approve_o2o_cutover(
            _actor(),
            planner_id=OWNER_ID,
            hostname=HOSTNAME,
            attempt_id=ATTEMPT_ID,
            revision=6,
            reason="This is a sufficiently detailed review reason.",
        )
    assert stale.value.status_code == 409
    assert stale.value.detail["code"] == "operator_review_revision_changed"

    approved = await service.approve_o2o_cutover(
        _actor(),
        planner_id=OWNER_ID,
        hostname=HOSTNAME,
        attempt_id=ATTEMPT_ID,
        revision=7,
        reason="Ownership proof and cutover risk were independently reviewed.",
    )
    assert approved["decision"] == "approved"
    saved = mongo.raw.storefront_domains.find_one({"_id": record["_id"]})
    assert saved["revision"] == 8
    assert saved["application_status"] == "migration_prevalidation"
    assert saved["operator_assisted_cutover_approval"]["claim_attempt_id"] == (
        ATTEMPT_ID
    )
    assert cloudflare.listed == []

    with pytest.raises(HTTPException) as replay:
        await service.approve_o2o_cutover(
            _actor(),
            planner_id=OWNER_ID,
            hostname=HOSTNAME,
            attempt_id=ATTEMPT_ID,
            revision=8,
            reason="A replay must not create a second operator approval.",
        )
    assert replay.value.status_code == 409
    assert (
        mongo.raw.storefront_domain_operations.count_documents(
            {"kind": "operator_o2o_cutover_approval", "state": "completed"}
        )
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["denied", "cancelled"])
async def test_verified_conflict_resolution_never_mutates_reserved_domain(decision):
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    conflict = _conflict_record()
    reserved = {
        "_id": ObjectId(),
        "planner_id": OTHER_OWNER_ID,
        "hostname": HOSTNAME,
        "provider_hostname_id": "cf-existing",
        "application_status": "active",
        "revision": 19,
    }
    mongo.raw.storefront_domain_conflict_claims.insert_one(conflict)
    mongo.raw.storefront_domains.insert_one(deepcopy(reserved))
    service = StorefrontDomainOperatorService(mongo, cloudflare)

    result = await service.resolve_conflict_claim(
        _actor(),
        planner_id=OWNER_ID,
        hostname=HOSTNAME,
        attempt_id=ATTEMPT_ID,
        revision=4,
        decision=decision,
        reason="The verified conflict was reviewed without transferring ownership.",
    )

    assert result["decision"] == decision
    closed = mongo.raw.storefront_domain_conflict_claims.find_one(
        {"_id": conflict["_id"]}
    )
    assert closed["application_status"] == "disconnected"
    assert closed["ownership_status"] == decision
    assert closed["operator_resolution"]["decision"] == decision
    assert "current_owner_key" not in closed
    assert mongo.raw.storefront_domains.find_one({"_id": reserved["_id"]}) == reserved
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_ambiguous_adoption_requires_exact_new_provider_identity():
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    record = _ambiguous_record()
    mongo.raw.storefront_domains.insert_one(record)
    _insert_create_receipt(mongo, record)
    cloudflare.rows = [
        {
            "id": "cf-new",
            "hostname": HOSTNAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "ssl": {"status": "pending_validation", "validation_records": []},
        }
    ]
    service = StorefrontDomainOperatorService(mongo, cloudflare)

    adopted = await service.adopt_ambiguous_create(
        _actor(),
        planner_id=OWNER_ID,
        hostname=HOSTNAME,
        attempt_id=PROVIDER_ATTEMPT_ID,
        revision=11,
        provider_hostname_id="cf-new",
        reason="The exact post-attempt Cloudflare hostname was independently listed.",
    )

    assert adopted["decision"] == "adopted"
    assert adopted["provider_hostname_id"] == "cf-new"
    saved = mongo.raw.storefront_domains.find_one({"_id": record["_id"]})
    assert saved["provider_hostname_id"] == "cf-new"
    assert saved["custom_route_enabled"] is False
    assert saved["application_status"] == "hostname_validation"
    original = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": PROVIDER_ATTEMPT_ID}
    )
    assert original["state"] == "completed"
    assert original["adopted_by_operation_id"] == adopted["operation_id"]
    operator_receipt = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": adopted["operation_id"]}
    )
    assert operator_receipt["provider_receipt"] == {
        "provider": "cloudflare",
        "operation": "list_custom_hostnames",
        "provider_hostname_id": "cf-new",
        "hostname": HOSTNAME,
        "provider_status": "pending",
        "ssl_status": "pending_validation",
        "observed_at": operator_receipt["provider_receipt"]["observed_at"],
    }


@pytest.mark.asyncio
async def test_ambiguous_adoption_rejects_preexisting_id_and_lost_revision():
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    record = _ambiguous_record()
    mongo.raw.storefront_domains.insert_one(record)
    _insert_create_receipt(mongo, record)
    cloudflare.rows = [
        {
            "id": "cf-new",
            "hostname": HOSTNAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "ssl": {"status": "pending_validation"},
        }
    ]
    service = StorefrontDomainOperatorService(mongo, cloudflare)

    with pytest.raises(HTTPException) as before:
        await service.adopt_ambiguous_create(
            _actor(),
            planner_id=OWNER_ID,
            hostname=HOSTNAME,
            attempt_id=PROVIDER_ATTEMPT_ID,
            revision=11,
            provider_hostname_id="cf-before",
            reason="A preexisting provider hostname must never be adopted.",
        )
    assert before.value.detail["code"] == "provider_hostname_predates_attempt"
    assert cloudflare.listed == []

    def concurrent_change():
        mongo.raw.storefront_domains.update_one(
            {"_id": record["_id"]},
            {"$set": {"revision": 12, "application_status": "disconnecting"}},
        )

    cloudflare.before_return = concurrent_change
    with pytest.raises(HTTPException) as raced:
        await service.adopt_ambiguous_create(
            _actor(),
            planner_id=OWNER_ID,
            hostname=HOSTNAME,
            attempt_id=PROVIDER_ATTEMPT_ID,
            revision=11,
            provider_hostname_id="cf-new",
            reason="The operator selected the exact independently listed hostname.",
        )
    assert raced.value.status_code == 409
    assert raced.value.detail["code"] == "operator_review_changed"
    saved = mongo.raw.storefront_domains.find_one({"_id": record["_id"]})
    assert saved["provider_hostname_id"] is None
    receipt = mongo.raw.storefront_domain_operations.find_one(
        {"kind": "operator_ambiguous_create_adoption"}
    )
    assert receipt["state"] == "cancelled"


@pytest.mark.asyncio
async def test_ambiguous_adoption_requires_one_new_attempt_window_candidate():
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    record = _ambiguous_record()
    mongo.raw.storefront_domains.insert_one(record)
    _insert_create_receipt(mongo, record)
    now = datetime.now(timezone.utc).isoformat()
    cloudflare.rows = [
        {
            "id": "cf-new-one",
            "hostname": HOSTNAME,
            "created_at": now,
            "status": "pending",
            "ssl": {"status": "pending_validation"},
        },
        {
            "id": "cf-new-two",
            "hostname": HOSTNAME,
            "created_at": now,
            "status": "pending",
            "ssl": {"status": "pending_validation"},
        },
    ]
    service = StorefrontDomainOperatorService(mongo, cloudflare)

    with pytest.raises(HTTPException) as ambiguous:
        await service.adopt_ambiguous_create(
            _actor(),
            planner_id=OWNER_ID,
            hostname=HOSTNAME,
            attempt_id=PROVIDER_ATTEMPT_ID,
            revision=11,
            provider_hostname_id="cf-new-one",
            reason="Two new exact provider identities make adoption unsafe.",
        )

    assert ambiguous.value.status_code == 409
    assert ambiguous.value.detail["code"] == "provider_identity_ambiguous"
    saved = mongo.raw.storefront_domains.find_one({"_id": record["_id"]})
    assert saved["provider_hostname_id"] is None


@pytest.mark.asyncio
async def test_operator_queue_uses_opaque_refs_and_resolves_exact_details():
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    o2o = _o2o_record()
    conflict = _conflict_record()
    now = datetime.now(timezone.utc)
    o2o.update({"updated_at": now, "action": "operator_review"})
    conflict.update(
        {"updated_at": now - timedelta(minutes=1), "action": "operator_review"}
    )
    mongo.raw.storefront_domains.insert_one(o2o)
    mongo.raw.storefront_domain_conflict_claims.insert_one(conflict)
    service = StorefrontDomainOperatorService(
        mongo,
        cloudflare,
        review_signing_key="operator-review-test-signing-key-00000000000000000000",
    )

    queue = await service.list_reviews(_actor(), limit=10)

    assert queue["has_more"] is False
    assert [item["review_type"] for item in queue["items"]] == [
        "o2o_cutover",
        "hostname_conflict",
    ]
    o2o_summary = queue["items"][0]
    assert o2o_summary["review_id"].startswith("sfor_")
    assert HOSTNAME not in o2o_summary["review_id"]
    assert OWNER_ID not in o2o_summary["review_id"]
    assert o2o_summary["allowed_actions"] == ["approve_o2o_cutover"]

    detail = await service.get_review(_actor(), review_id=o2o_summary["review_id"])
    assert detail["planner_id"] == OWNER_ID
    assert detail["hostname"] == HOSTNAME
    assert detail["attempt_id"] == ATTEMPT_ID
    assert detail["revision"] == 7
    assert detail["authoritative_dns_provider"] == "cloudflare"

    tampered_suffix = "0" if o2o_summary["review_id"][-1] != "0" else "1"
    tampered = f"{o2o_summary['review_id'][:-1]}{tampered_suffix}"
    with pytest.raises(HTTPException) as rejected:
        await service.get_review(_actor(), review_id=tampered)
    assert rejected.value.status_code == 404


@pytest.mark.asyncio
async def test_operator_queue_ambiguous_detail_lists_only_safe_new_candidates():
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    record = _ambiguous_record()
    record["updated_at"] = datetime.now(timezone.utc)
    mongo.raw.storefront_domains.insert_one(record)
    _insert_create_receipt(mongo, record)
    cloudflare.rows = [
        {
            "id": "cf-before",
            "hostname": HOSTNAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": "cf-new",
            "hostname": HOSTNAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": "cf-wrong-host",
            "hostname": "other.customer.example",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    service = StorefrontDomainOperatorService(
        mongo,
        cloudflare,
        review_signing_key="operator-review-test-signing-key-00000000000000000000",
    )
    queue = await service.list_reviews(_actor(), limit=10)

    detail = await service.get_review(
        _actor(), review_id=queue["items"][0]["review_id"]
    )

    assert detail["review_type"] == "ambiguous_create"
    assert detail["provider_candidate_ids"] == ["cf-new"]
    assert detail["allowed_actions"] == ["adopt_ambiguous_create"]


@pytest.mark.asyncio
async def test_review_reference_is_bound_to_attempt_revision_and_expiry():
    mongo = FakeMongo()
    record = _o2o_record()
    mongo.raw.storefront_domains.insert_one(record)
    service = StorefrontDomainOperatorService(
        mongo,
        FakeCloudflare(),
        review_signing_key="operator-review-test-signing-key-00000000000000000000",
    )
    base_time = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    service._now = lambda: base_time  # type: ignore[method-assign]
    queue = await service.list_reviews(_actor())
    review_id = queue["items"][0]["review_id"]

    mongo.raw.storefront_domains.update_one(
        {"_id": record["_id"]}, {"$set": {"revision": 8}}
    )
    with pytest.raises(HTTPException) as revised:
        await service.get_review(_actor(), review_id=review_id)
    assert revised.value.status_code == 409
    assert revised.value.detail["code"] == "operator_review_reference_stale"

    mongo.raw.storefront_domains.update_one(
        {"_id": record["_id"]},
        {"$set": {"revision": 7, "claim_attempt_id": "different-attempt"}},
    )
    with pytest.raises(HTTPException) as different_attempt:
        await service.get_review(_actor(), review_id=review_id)
    assert different_attempt.value.detail["code"] == "operator_review_reference_stale"

    service._now = lambda: base_time + timedelta(minutes=16)  # type: ignore[method-assign]
    with pytest.raises(HTTPException) as expired:
        await service.get_review(_actor(), review_id=review_id)
    assert expired.value.status_code == 409
    assert expired.value.detail["code"] == "operator_review_reference_expired"


@pytest.mark.asyncio
async def test_ambiguous_candidates_use_immutable_request_window_not_review_time():
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    record = _ambiguous_record()
    record["updated_at"] = datetime.now(timezone.utc)
    mongo.raw.storefront_domains.insert_one(record)
    _insert_create_receipt(mongo, record)
    operation = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": PROVIDER_ATTEMPT_ID}
    )
    cloudflare.rows = [
        {
            "id": "cf-created-hours-later",
            "hostname": HOSTNAME,
            "created_at": (
                operation["provider_request_window_ends_at"] + timedelta(hours=2)
            ).isoformat(),
        }
    ]
    service = StorefrontDomainOperatorService(
        mongo,
        cloudflare,
        review_signing_key="operator-review-test-signing-key-00000000000000000000",
    )
    review_id = (await service.list_reviews(_actor()))["items"][0]["review_id"]

    detail = await service.get_review(_actor(), review_id=review_id)

    assert detail["provider_lookup_status"] == "available"
    assert detail["provider_candidate_ids"] == []
    with pytest.raises(HTTPException) as late:
        await service.adopt_ambiguous_create(
            _actor(),
            planner_id=OWNER_ID,
            hostname=HOSTNAME,
            attempt_id=PROVIDER_ATTEMPT_ID,
            revision=11,
            provider_hostname_id="cf-created-hours-later",
            reason="A hostname created after the immutable request window is unsafe.",
        )
    assert late.value.detail["code"] == "provider_identity_ambiguous"


@pytest.mark.asyncio
async def test_provider_lookup_outage_is_explicit_safe_evidence():
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    record = _ambiguous_record()
    record["updated_at"] = datetime.now(timezone.utc)
    mongo.raw.storefront_domains.insert_one(record)
    _insert_create_receipt(mongo, record)
    cloudflare.list_error = CloudflareServiceError(
        "secret-token failed against 10.0.0.4",
        operation="list_custom_hostnames",
        kind="transport",
    )
    service = StorefrontDomainOperatorService(
        mongo,
        cloudflare,
        review_signing_key="operator-review-test-signing-key-00000000000000000000",
    )
    review_id = (await service.list_reviews(_actor()))["items"][0]["review_id"]

    detail = await service.get_review(_actor(), review_id=review_id)

    assert detail["provider_candidate_ids"] == []
    assert detail["provider_lookup_status"] == "unavailable"
    assert detail["provider_lookup_support_id"].startswith("sfd_")
    assert "secret-token" not in detail["provider_lookup_message"]
    assert "10.0.0.4" not in detail["provider_lookup_message"]


@pytest.mark.asyncio
async def test_queue_skips_malformed_rows_without_hiding_valid_review():
    mongo = FakeMongo()
    valid = _o2o_record()
    valid["updated_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    malformed = _o2o_record()
    malformed.update(
        {
            "revision": "not-an-integer",
            "updated_at": datetime.now(timezone.utc),
        }
    )
    mongo.raw.storefront_domains.insert_many([malformed, valid])
    service = StorefrontDomainOperatorService(
        mongo,
        FakeCloudflare(),
        review_signing_key="operator-review-test-signing-key-00000000000000000000",
    )

    queue = await service.list_reviews(_actor())

    assert len(queue["items"]) == 1
    assert queue["items"][0]["revision"] == 7


@pytest.mark.asyncio
async def test_applied_o2o_decision_resumes_and_finalizes_same_receipt(monkeypatch):
    mongo = FakeMongo()
    record = _o2o_record()
    mongo.raw.storefront_domains.insert_one(record)
    service = StorefrontDomainOperatorService(mongo, FakeCloudflare())
    original_finish = service._finish_receipt
    fail_completion_once = True

    async def flaky_finish(receipt, *, state, error=None, extra=None):
        nonlocal fail_completion_once
        if state == "completed" and fail_completion_once:
            fail_completion_once = False
            raise RuntimeError("simulated receipt-store interruption")
        return await original_finish(receipt, state=state, error=error, extra=extra)

    monkeypatch.setattr(service, "_finish_receipt", flaky_finish)
    request = {
        "planner_id": OWNER_ID,
        "hostname": HOSTNAME,
        "attempt_id": ATTEMPT_ID,
        "revision": 7,
        "reason": "Ownership proof and cutover risk were independently reviewed.",
    }
    with pytest.raises(RuntimeError):
        await service.approve_o2o_cutover(_actor(), **request)

    resumed = await service.approve_o2o_cutover(_actor(), **request)

    assert resumed["decision"] == "approved"
    assert (
        mongo.raw.storefront_domain_operations.count_documents(
            {"kind": "operator_o2o_cutover_approval"}
        )
        == 1
    )
    receipt = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": resumed["operation_id"]}
    )
    assert receipt["state"] == "completed"


@pytest.mark.asyncio
async def test_adoption_cas_rejects_changed_original_provider_operation():
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    record = _ambiguous_record()
    mongo.raw.storefront_domains.insert_one(record)
    _insert_create_receipt(mongo, record)
    cloudflare.rows = [
        {
            "id": "cf-new",
            "hostname": HOSTNAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "ssl": {"status": "pending_validation"},
        }
    ]

    def change_source_receipt():
        mongo.raw.storefront_domain_operations.update_one(
            {"operation_id": PROVIDER_ATTEMPT_ID},
            {"$set": {"state": "failed"}},
        )

    cloudflare.before_return = change_source_receipt
    service = StorefrontDomainOperatorService(mongo, cloudflare)

    with pytest.raises(HTTPException) as changed:
        await service.adopt_ambiguous_create(
            _actor(),
            planner_id=OWNER_ID,
            hostname=HOSTNAME,
            attempt_id=PROVIDER_ATTEMPT_ID,
            revision=11,
            provider_hostname_id="cf-new",
            reason="The exact provider operation must remain unchanged through adoption.",
        )

    assert changed.value.detail["code"] == "provider_operation_changed"
    saved = mongo.raw.storefront_domains.find_one({"_id": record["_id"]})
    assert saved["provider_hostname_id"] is None


@pytest.mark.asyncio
async def test_applied_adoption_resumes_source_and_operator_receipts(monkeypatch):
    mongo = FakeMongo()
    cloudflare = FakeCloudflare()
    record = _ambiguous_record()
    mongo.raw.storefront_domains.insert_one(record)
    _insert_create_receipt(mongo, record)
    cloudflare.rows = [
        {
            "id": "cf-new",
            "hostname": HOSTNAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "ssl": {"status": "pending_validation"},
        }
    ]
    service = StorefrontDomainOperatorService(mongo, cloudflare)
    original_finish = service._finish_receipt
    fail_completion_once = True

    async def flaky_finish(receipt, *, state, error=None, extra=None):
        nonlocal fail_completion_once
        if state == "completed" and fail_completion_once:
            fail_completion_once = False
            raise RuntimeError("simulated adoption receipt interruption")
        return await original_finish(receipt, state=state, error=error, extra=extra)

    monkeypatch.setattr(service, "_finish_receipt", flaky_finish)
    request = {
        "planner_id": OWNER_ID,
        "hostname": HOSTNAME,
        "attempt_id": PROVIDER_ATTEMPT_ID,
        "revision": 11,
        "provider_hostname_id": "cf-new",
        "reason": "The exact post-attempt provider identity was independently reviewed.",
    }
    with pytest.raises(RuntimeError):
        await service.adopt_ambiguous_create(_actor(), **request)

    resumed = await service.adopt_ambiguous_create(_actor(), **request)

    assert resumed["decision"] == "adopted"
    assert resumed["provider_hostname_id"] == "cf-new"
    source = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": PROVIDER_ATTEMPT_ID}
    )
    assert source["state"] == "completed"
    assert source["adopted_by_operation_id"] == resumed["operation_id"]
    assert (
        mongo.raw.storefront_domain_operations.count_documents(
            {"kind": "operator_ambiguous_create_adoption"}
        )
        == 1
    )


def test_operator_routes_require_root_admin(monkeypatch):
    app = FastAPI()
    app.include_router(operator_router, prefix="/admin")
    app.dependency_overrides[get_current_user_extended] = lambda: SimpleNamespace(
        is_root_admin=False,
        email="planner@example.com",
    )
    service_call = AsyncMock()
    monkeypatch.setattr(
        "app.api.storefront_domain_operator.storefront_domain_operator_service.approve_o2o_cutover",
        service_call,
    )

    response = TestClient(app).post(
        "/admin/storefront/custom-domain/operator/o2o/approve",
        json={
            "planner_id": OWNER_ID,
            "hostname": HOSTNAME,
            "attempt_id": ATTEMPT_ID,
            "revision": 7,
            "reason": "This request must never reach the operator service.",
        },
    )

    assert response.status_code == 403
    service_call.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "path", "payload", "service_method"),
    [
        (
            "GET",
            "/admin/storefront/custom-domain/operator/reviews",
            None,
            "list_reviews",
        ),
        (
            "GET",
            "/admin/storefront/custom-domain/operator/reviews/"
            "sfor_opaqueReviewReference_0123456789abcdef0123456789abcdef0123",
            None,
            "get_review",
        ),
        (
            "POST",
            "/admin/storefront/custom-domain/operator/conflict/resolve",
            {
                "planner_id": OWNER_ID,
                "hostname": HOSTNAME,
                "attempt_id": ATTEMPT_ID,
                "revision": 4,
                "decision": "denied",
                "reason": "A non-root actor must never resolve this review.",
            },
            "resolve_conflict_claim",
        ),
        (
            "POST",
            "/admin/storefront/custom-domain/operator/ambiguous-create/adopt",
            {
                "planner_id": OWNER_ID,
                "hostname": HOSTNAME,
                "attempt_id": PROVIDER_ATTEMPT_ID,
                "revision": 11,
                "provider_hostname_id": "cf-new",
                "reason": "A non-root actor must never adopt this hostname.",
            },
            "adopt_ambiguous_create",
        ),
    ],
)
def test_list_detail_conflict_and_adoption_routes_deny_non_root(
    monkeypatch, method, path, payload, service_method
):
    app = FastAPI()
    app.include_router(operator_router, prefix="/admin")
    app.dependency_overrides[get_current_user_extended] = lambda: _actor(root=False)
    service_call = AsyncMock()
    monkeypatch.setattr(
        f"app.api.storefront_domain_operator.storefront_domain_operator_service.{service_method}",
        service_call,
    )

    response = TestClient(app).request(method, path, json=payload)

    assert response.status_code == 403
    service_call.assert_not_awaited()


def test_operator_decision_response_model_serializes_receipt(monkeypatch):
    app = FastAPI()
    app.include_router(operator_router, prefix="/admin")
    app.dependency_overrides[get_current_user_extended] = lambda: _actor()
    completed_at = datetime(2026, 7, 16, 18, 30, tzinfo=timezone.utc)
    service_call = AsyncMock(
        return_value={
            "operation_id": "sforop_serialized_receipt",
            "decision": "adopted",
            "planner_id": OWNER_ID,
            "hostname": HOSTNAME,
            "attempt_id": PROVIDER_ATTEMPT_ID,
            "before_revision": 11,
            "after_revision": 12,
            "application_status": "hostname_validation",
            "provider_hostname_id": "cf-new",
            "completed_at": completed_at,
        }
    )
    monkeypatch.setattr(
        "app.api.storefront_domain_operator.storefront_domain_operator_service.adopt_ambiguous_create",
        service_call,
    )

    response = TestClient(app).post(
        "/admin/storefront/custom-domain/operator/ambiguous-create/adopt",
        json={
            "planner_id": OWNER_ID,
            "hostname": HOSTNAME,
            "attempt_id": PROVIDER_ATTEMPT_ID,
            "revision": 11,
            "provider_hostname_id": "cf-new",
            "reason": "The response receipt must serialize through the public contract.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "operation_id": "sforop_serialized_receipt",
        "decision": "adopted",
        "planner_id": OWNER_ID,
        "hostname": HOSTNAME,
        "attempt_id": PROVIDER_ATTEMPT_ID,
        "before_revision": 11,
        "after_revision": 12,
        "application_status": "hostname_validation",
        "provider_hostname_id": "cf-new",
        "completed_at": "2026-07-16T18:30:00Z",
    }


def test_operator_review_queue_and_detail_routes_are_root_scoped(monkeypatch):
    app = FastAPI()
    app.include_router(operator_router, prefix="/admin")
    app.dependency_overrides[get_current_user_extended] = lambda: _actor()
    review_id = "sfor_opaqueReviewReference_0123456789abcdef0123456789abcdef0123"
    summary = {
        "review_id": review_id,
        "review_type": "o2o_cutover",
        "hostname": HOSTNAME,
        "application_status": "operator_review",
        "action": "operator_review",
        "revision": 7,
        "updated_at": datetime.now(timezone.utc),
        "support_id": "sfd_support_one",
        "allowed_actions": ["approve_o2o_cutover"],
    }
    list_call = AsyncMock(return_value={"items": [summary], "has_more": False})
    detail_call = AsyncMock(
        return_value={
            **summary,
            "planner_id": OWNER_ID,
            "attempt_id": ATTEMPT_ID,
            "intent": "migration",
            "ownership_status": "verified",
            "routing_dns_status": "pending",
            "provider_hostname_status": "not_started",
            "ssl_status": "not_started",
            "https_status": "not_started",
            "authoritative_dns_provider": "cloudflare",
            "authoritative_nameservers": ["ada.ns.cloudflare.com"],
            "provider_candidate_ids": [],
            "error_code": "cloudflare_o2o_migration_requires_assistance",
            "error_message": "Assisted migration review is required.",
            "customer_action": "Review the exact provider evidence.",
        }
    )
    monkeypatch.setattr(
        "app.api.storefront_domain_operator.storefront_domain_operator_service.list_reviews",
        list_call,
    )
    monkeypatch.setattr(
        "app.api.storefront_domain_operator.storefront_domain_operator_service.get_review",
        detail_call,
    )
    client = TestClient(app)

    queue_response = client.get(
        "/admin/storefront/custom-domain/operator/reviews?limit=25"
    )
    detail_response = client.get(
        f"/admin/storefront/custom-domain/operator/reviews/{review_id}"
    )

    assert queue_response.status_code == 200
    assert queue_response.json()["items"][0]["review_type"] == "o2o_cutover"
    assert detail_response.status_code == 200
    assert detail_response.json()["attempt_id"] == ATTEMPT_ID
    list_call.assert_awaited_once()
    assert list_call.await_args.kwargs["limit"] == 25
    detail_call.assert_awaited_once()
    assert detail_call.await_args.kwargs["review_id"] == review_id
