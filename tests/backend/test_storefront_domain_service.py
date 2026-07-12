from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.core.settings import Settings
from app.services.cloudflare_service import CloudflareService, CloudflareServiceError
from app.services.storefront_domain_service import (
    StorefrontDomainService,
    normalize_custom_hostname,
)
from app.services.storefront_entitlement_service import StorefrontEntitlements


OWNER_ID = "507f1f77bcf86cd799439011"
SECOND_OWNER_ID = "507f1f77bcf86cd799439012"


class AsyncCollection:
    def __init__(self, collection):
        self._collection = collection

    async def find_one(self, *args, **kwargs):
        return self._collection.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._collection.update_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._collection.delete_one(*args, **kwargs)


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
        self.raw = mongomock.MongoClient()["storefront_domain_test"]
        self.db = AsyncDatabase(self.raw)
        self.raw.storefront_domains.create_index("planner_id", unique=True)
        self.raw.storefront_domains.create_index("hostname", unique=True)


class FakeEntitlements:
    def __init__(self):
        self.enabled_by_owner = {OWNER_ID: True, SECOND_OWNER_ID: True}

    def _result(self, owner_id: str) -> StorefrontEntitlements:
        enabled = self.enabled_by_owner.get(owner_id, False)
        return StorefrontEntitlements(
            owner_id=owner_id,
            plan_id="plan_signature" if enabled else "plan_boutique",
            storefront_enabled=enabled,
            custom_domain_enabled=enabled,
        )

    async def resolve_for_owner(self, user_data: dict) -> StorefrontEntitlements:
        return self._result(str(user_data.get("_id") or ""))

    async def resolve_for_planner_id(self, planner_id: str) -> StorefrontEntitlements:
        return self._result(str(planner_id))


class FakeCloudflare:
    def __init__(self):
        self.created: list[str] = []
        self.read: list[str] = []
        self.deleted: list[str] = []
        self.create_result = {
            "id": "cf-hostname-1",
            "hostname": "www.luxe-events.example",
            "status": "pending",
            "ownership_verification": {
                "type": "txt",
                "name": "_cf-custom-hostname.www.luxe-events.example",
                "value": "verify-me",
            },
            "ownership_verification_http": {
                "http_url": "http://www.luxe-events.example/.well-known/cf-custom-hostname-challenge/token",
                "http_body": "verify-me",
            },
            "ssl": {
                "status": "pending_validation",
                "validation_records": [
                    {
                        "status": "pending",
                        "txt_name": "_acme-challenge.www.luxe-events.example",
                        "txt_value": "ssl-verify-me",
                    }
                ],
            },
        }
        self.status_result = deepcopy(self.create_result)
        self.delete_result = {"id": "cf-hostname-1"}
        self.create_error: CloudflareServiceError | None = None
        self.status_error: CloudflareServiceError | None = None
        self.delete_error: CloudflareServiceError | None = None

    async def create_custom_hostname(self, hostname: str) -> dict:
        self.created.append(hostname)
        if self.create_error:
            raise self.create_error
        result = deepcopy(self.create_result)
        result["hostname"] = hostname
        self.status_result["hostname"] = hostname
        return result

    async def get_custom_hostname(self, hostname_id: str) -> dict:
        self.read.append(hostname_id)
        if self.status_error:
            raise self.status_error
        return deepcopy(self.status_result)

    async def delete_custom_hostname(self, hostname_id: str) -> dict:
        self.deleted.append(hostname_id)
        if self.delete_error:
            raise self.delete_error
        return deepcopy(self.delete_result)


@dataclass
class FakeResponse:
    status_code: int
    payload: object

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return deepcopy(self.payload)


class FakeHttpClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.requests: list[tuple[str, str, dict]] = []

    async def request(self, method: str, url: str, **kwargs):
        self.requests.append((method, url, kwargs))
        return self.response


def _owner(owner_id: str = OWNER_ID) -> dict:
    return {"_id": ObjectId(owner_id), "role": "wedding_planner"}


@pytest.fixture
def domain_setup():
    mongo = FakeMongo()
    entitlements = FakeEntitlements()
    cloudflare = FakeCloudflare()
    service = StorefrontDomainService(
        mongo_client=mongo,
        cloudflare_service=cloudflare,
        entitlement_service=entitlements,
        cname_target="storefronts.edge.example.net",
        platform_domains={"thespecialwedding.io", "thespecialwedding.com"},
    )
    return service, mongo, entitlements, cloudflare


def test_hostname_normalization_is_idna_lowercase_and_hostname_only():
    assert (
        normalize_custom_hostname(
            "BÜCHER.Example", platform_domains={"thespecialwedding.io"}
        )
        == "xn--bcher-kva.example"
    )


def test_custom_hostname_configuration_is_explicit_and_centrally_typed():
    fields = Settings.model_fields
    assert fields["cloudflare_zone_id"].alias == "CLOUDFLARE_ZONE_ID"
    assert fields["cloudflare_zone_id"].default is None
    assert fields["storefront_cname_target"].alias == "STOREFRONT_CNAME_TARGET"
    assert fields["storefront_cname_target"].default is None
    assert fields["storefront_platform_domains"].alias == "STOREFRONT_PLATFORM_DOMAINS"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cname_target",
    ["", "https://storefronts.example.com", "localhost", "127.0.0.1"],
)
async def test_connect_fails_before_reservation_without_valid_cname_target(
    domain_setup, cname_target
):
    _service, mongo, entitlements, cloudflare = domain_setup
    service = StorefrontDomainService(
        mongo_client=mongo,
        cloudflare_service=cloudflare,
        entitlement_service=entitlements,
        cname_target=cname_target,
        platform_domains={"thespecialwedding.io"},
    )

    with pytest.raises(HTTPException) as unavailable:
        await service.connect(_owner(), "events.example")

    assert unavailable.value.status_code == 503
    assert mongo.raw.storefront_domains.count_documents({}) == 0
    assert cloudflare.created == []
    assert (
        normalize_custom_hostname(
            "WWW.Luxe-Events.Example", platform_domains={"thespecialwedding.io"}
        )
        == "www.luxe-events.example"
    )


@pytest.mark.parametrize(
    "hostname",
    [
        "https://events.example",
        "user:pass@events.example",
        "events.example:443",
        "events.example/path",
        "events.example?query=yes",
        "events.example#fragment",
        "*.events.example",
        "events .example",
        " events.example",
        "events.example ",
        "localhost",
        "shop.localhost",
        "127.0.0.1",
        "127.000.000.001",
        "[::1]",
        "::1",
        "singlelabel",
        "-events.example",
        "events-.example",
        "events..example",
        "events.example.",
        "events_there.example",
        "thespecialwedding.io",
        "storefront.thespecialwedding.io",
        "THESPECIALWEDDING.COM",
    ],
)
def test_hostname_normalization_rejects_unsafe_or_platform_names(hostname):
    with pytest.raises(ValueError):
        normalize_custom_hostname(
            hostname,
            platform_domains={"thespecialwedding.io", "thespecialwedding.com"},
        )


@pytest.mark.asyncio
async def test_cloudflare_requires_explicit_token_and_zone_without_mock_success():
    service = CloudflareService(api_token="", zone_id="")

    with pytest.raises(CloudflareServiceError) as failure:
        await service.create_custom_hostname("events.example")

    assert failure.value.kind == "configuration"
    assert failure.value.operation == "create_custom_hostname"


@pytest.mark.asyncio
async def test_cloudflare_surfaces_structured_provider_errors_for_all_verbs():
    response = FakeResponse(
        400,
        {
            "success": False,
            "errors": [{"code": 1406, "message": "Hostname already exists"}],
        },
    )
    client = FakeHttpClient(response)
    service = CloudflareService(
        api_token="secret", zone_id="zone-123", http_client=client
    )

    calls = (
        service.create_custom_hostname("events.example"),
        service.get_custom_hostname("provider/id"),
        service.delete_custom_hostname("provider/id"),
    )
    for call in calls:
        with pytest.raises(CloudflareServiceError) as failure:
            await call
        assert failure.value.kind == "provider"
        assert failure.value.provider_status_code == 400
        assert failure.value.errors == (
            {"code": 1406, "message": "Hostname already exists"},
        )

    assert [request[0] for request in client.requests] == ["POST", "GET", "DELETE"]
    assert all("zones/zone-123/custom_hostnames" in item[1] for item in client.requests)
    assert client.requests[1][1].endswith("/provider%2Fid")


@pytest.mark.asyncio
async def test_connect_reserves_owner_and_hostname_then_returns_pending_dns_dto(
    domain_setup,
):
    service, mongo, _, cloudflare = domain_setup

    result = await service.connect(_owner(), "WWW.Luxe-Events.Example")

    assert cloudflare.created == ["www.luxe-events.example"]
    assert result == {
        "hostname": "www.luxe-events.example",
        "status": "pending",
        "provider_status": "pending",
        "ssl_status": "pending_validation",
        "ownership_verification": cloudflare.create_result["ownership_verification"],
        "ownership_verification_http": cloudflare.create_result[
            "ownership_verification_http"
        ],
        "ssl_validation_records": cloudflare.create_result["ssl"]["validation_records"],
        "cname_target": "storefronts.edge.example.net",
        "deletion_status": None,
        "last_error": None,
    }
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["provider_hostname_id"] == "cf-hostname-1"
    assert stored["hostname"] == "www.luxe-events.example"
    assert stored["status"] == "pending"


@pytest.mark.asyncio
async def test_connect_requires_planner_owner_and_current_custom_domain_entitlement(
    domain_setup,
):
    service, mongo, entitlements, cloudflare = domain_setup
    entitlements.enabled_by_owner[OWNER_ID] = False

    with pytest.raises(HTTPException) as denied:
        await service.connect(_owner(), "events.example")
    assert denied.value.status_code == 403
    assert mongo.raw.storefront_domains.count_documents({}) == 0
    assert cloudflare.created == []

    with pytest.raises(HTTPException) as wrong_role:
        await service.connect(
            {"_id": ObjectId(OWNER_ID), "role": "team_member"}, "events.example"
        )
    assert wrong_role.value.status_code == 403


@pytest.mark.asyncio
async def test_provider_create_failure_releases_local_reservation(domain_setup):
    service, mongo, _, cloudflare = domain_setup
    cloudflare.create_error = CloudflareServiceError(
        operation="create_custom_hostname",
        kind="provider",
        message="Cloudflare rejected the hostname",
        provider_status_code=400,
        errors=({"code": 1406, "message": "invalid hostname"},),
    )

    with pytest.raises(HTTPException) as failure:
        await service.connect(_owner(), "events.example")

    assert failure.value.status_code == 502
    assert mongo.raw.storefront_domains.count_documents({}) == 0


@pytest.mark.asyncio
async def test_post_provider_local_failure_compensates_provider_and_local_reservation(
    domain_setup, monkeypatch
):
    service, mongo, _, cloudflare = domain_setup
    original_update = mongo.db["storefront_domains"].update_one

    async def lose_reservation_on_provider_update(query, update, *args, **kwargs):
        if update.get("$set", {}).get("provider_hostname_id"):
            mongo.raw.storefront_domains.delete_many({})
        return await original_update(query, update, *args, **kwargs)

    monkeypatch.setattr(
        mongo.db["storefront_domains"],
        "update_one",
        lose_reservation_on_provider_update,
    )

    with pytest.raises(HTTPException) as failure:
        await service.connect(_owner(), "events.example")

    assert failure.value.status_code == 503
    assert cloudflare.deleted == ["cf-hostname-1"]
    assert mongo.raw.storefront_domains.count_documents({}) == 0


@pytest.mark.asyncio
async def test_failed_provider_compensation_preserves_retryable_mapping(
    domain_setup, monkeypatch
):
    service, mongo, _, cloudflare = domain_setup
    original_update = mongo.db["storefront_domains"].update_one

    async def miss_only_initial_provider_binding(query, update, *args, **kwargs):
        values = update.get("$set", {})
        if values.get("provider_hostname_id") and "deletion_status" not in values:
            return SimpleNamespace(matched_count=0)
        return await original_update(query, update, *args, **kwargs)

    monkeypatch.setattr(
        mongo.db["storefront_domains"],
        "update_one",
        miss_only_initial_provider_binding,
    )
    cloudflare.delete_error = CloudflareServiceError(
        operation="delete_custom_hostname",
        kind="transport",
        message="Cloudflare cleanup request failed",
    )

    with pytest.raises(HTTPException) as failure:
        await service.connect(_owner(), "events.example")

    assert failure.value.status_code == 503
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["provider_hostname_id"] == "cf-hostname-1"
    assert stored["status"] == "delete_failed"
    assert stored["deletion_status"] == "retry_pending"
    assert stored["delete_attempts"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_status", "ssl_status", "expected_status"),
    [
        ("pending", "active", "pending"),
        ("active", "pending_validation", "pending"),
        ("active", "active", "active"),
    ],
)
async def test_refresh_requires_both_hostname_and_ssl_active(
    domain_setup, provider_status, ssl_status, expected_status
):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    cloudflare.status_result["status"] = provider_status
    cloudflare.status_result["ssl"]["status"] = ssl_status

    result = await service.refresh(_owner())

    assert result["status"] == expected_status
    assert result["provider_status"] == provider_status
    assert result["ssl_status"] == ssl_status
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["status"] == expected_status


@pytest.mark.asyncio
async def test_refresh_rejects_provider_identity_drift_without_activating_mapping(
    domain_setup,
):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    cloudflare.status_result.update(
        {
            "id": "different-provider-id",
            "hostname": "attacker.example",
            "status": "active",
            "ssl": {"status": "active", "validation_records": []},
        }
    )

    with pytest.raises(HTTPException) as failure:
        await service.refresh(_owner())

    assert failure.value.status_code == 502
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["status"] == "pending"
    assert stored["last_error"] == "Cloudflare returned a mismatched hostname mapping"


@pytest.mark.asyncio
async def test_owner_scope_prevents_other_planner_from_reading_or_deleting_mapping(
    domain_setup,
):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")

    assert await service.get_for_owner(_owner(SECOND_OWNER_ID)) is None
    assert await service.disconnect(_owner(SECOND_OWNER_ID)) is None
    assert cloudflare.deleted == []
    assert mongo.raw.storefront_domains.count_documents({}) == 1


@pytest.mark.asyncio
async def test_delete_failure_preserves_mapping_with_retry_state(domain_setup):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    cloudflare.delete_error = CloudflareServiceError(
        operation="delete_custom_hostname",
        kind="transport",
        message="Cloudflare request failed",
    )

    with pytest.raises(HTTPException) as failure:
        await service.disconnect(_owner())

    assert failure.value.status_code == 502
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored is not None
    assert stored["status"] == "delete_failed"
    assert stored["deletion_status"] == "retry_pending"
    assert stored["delete_attempts"] == 1
    assert stored["last_error"] == "Cloudflare request failed"


@pytest.mark.asyncio
async def test_delete_failure_refresh_preserves_intent_and_retry_can_finish(
    domain_setup,
):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    cloudflare.status_result["status"] = "active"
    cloudflare.status_result["ssl"]["status"] = "active"
    await service.refresh(_owner())
    cloudflare.delete_error = CloudflareServiceError(
        operation="delete_custom_hostname",
        kind="transport",
        message="Cloudflare request failed",
    )

    with pytest.raises(HTTPException) as failure:
        await service.disconnect(_owner())

    assert failure.value.status_code == 502
    reads_before_refresh = list(cloudflare.read)
    refreshed = await service.refresh(_owner())
    assert refreshed["status"] == "delete_failed"
    assert refreshed["deletion_status"] == "retry_pending"
    assert cloudflare.read == reads_before_refresh
    assert await service.resolve_active_hostname("events.example") is None

    cloudflare.delete_error = None
    await service.disconnect(_owner())

    assert cloudflare.deleted == ["cf-hostname-1", "cf-hostname-1"]
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) is None


@pytest.mark.asyncio
async def test_refresh_started_before_disconnect_cannot_resurrect_deleted_mapping(
    domain_setup, monkeypatch
):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    cloudflare.status_result["status"] = "active"
    cloudflare.status_result["ssl"]["status"] = "active"

    refresh_started = asyncio.Event()
    allow_refresh_result = asyncio.Event()
    delete_started = asyncio.Event()
    allow_delete_result = asyncio.Event()

    async def delayed_refresh(hostname_id: str) -> dict:
        cloudflare.read.append(hostname_id)
        result = deepcopy(cloudflare.status_result)
        refresh_started.set()
        await allow_refresh_result.wait()
        return result

    async def delayed_delete(hostname_id: str) -> dict:
        cloudflare.deleted.append(hostname_id)
        delete_started.set()
        await allow_delete_result.wait()
        return deepcopy(cloudflare.delete_result)

    monkeypatch.setattr(cloudflare, "get_custom_hostname", delayed_refresh)
    monkeypatch.setattr(cloudflare, "delete_custom_hostname", delayed_delete)

    refresh_task = asyncio.create_task(service.refresh(_owner()))
    await refresh_started.wait()
    disconnect_task = asyncio.create_task(service.disconnect(_owner()))
    await delete_started.wait()

    allow_refresh_result.set()
    refresh_result = await refresh_task
    assert refresh_result["status"] == "deleting"
    assert refresh_result["deletion_status"] == "provider_delete_pending"
    assert await service.resolve_active_hostname("events.example") is None

    allow_delete_result.set()
    assert await disconnect_task is None
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) is None


@pytest.mark.asyncio
async def test_disconnect_claim_failure_never_calls_provider(domain_setup, monkeypatch):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    collection = mongo.db["storefront_domains"]
    original_update = collection.update_one

    async def miss_deletion_claim(query, update, *args, **kwargs):
        if update.get("$set", {}).get("deletion_status") == "provider_delete_pending":
            return SimpleNamespace(matched_count=0)
        return await original_update(query, update, *args, **kwargs)

    monkeypatch.setattr(collection, "update_one", miss_deletion_claim)

    with pytest.raises(HTTPException) as failure:
        await service.disconnect(_owner())

    assert failure.value.status_code == 409
    assert cloudflare.deleted == []
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) is not None


@pytest.mark.asyncio
async def test_provider_delete_success_local_exception_is_durable_and_retryable(
    domain_setup, monkeypatch
):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    collection = mongo.db["storefront_domains"]
    original_delete = collection.delete_one

    async def fail_local_cleanup(query, *args, **kwargs):
        if query.get("deletion_status") == "local_cleanup_pending":
            raise RuntimeError("local cleanup unavailable")
        return await original_delete(query, *args, **kwargs)

    monkeypatch.setattr(collection, "delete_one", fail_local_cleanup)

    with pytest.raises(HTTPException) as failure:
        await service.disconnect(_owner())

    assert failure.value.status_code == 503
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["status"] == "provider_deleted"
    assert stored["deletion_status"] == "local_cleanup_pending"
    assert await service.resolve_active_hostname("events.example") is None

    monkeypatch.setattr(collection, "delete_one", original_delete)
    await service.disconnect(_owner())

    assert cloudflare.deleted == ["cf-hostname-1"]
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) is None


@pytest.mark.asyncio
async def test_provider_delete_success_local_miss_is_durable_and_retryable(
    domain_setup, monkeypatch
):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    collection = mongo.db["storefront_domains"]
    original_delete = collection.delete_one

    async def miss_local_cleanup(query, *args, **kwargs):
        if query.get("deletion_status") == "local_cleanup_pending":
            return SimpleNamespace(deleted_count=0)
        return await original_delete(query, *args, **kwargs)

    monkeypatch.setattr(collection, "delete_one", miss_local_cleanup)

    with pytest.raises(HTTPException) as failure:
        await service.disconnect(_owner())

    assert failure.value.status_code == 503
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["status"] == "provider_deleted"
    assert stored["deletion_status"] == "local_cleanup_pending"

    monkeypatch.setattr(collection, "delete_one", original_delete)
    await service.disconnect(_owner())

    assert cloudflare.deleted == ["cf-hostname-1"]
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) is None


@pytest.mark.asyncio
async def test_provider_not_found_is_idempotent_on_delete_retry(domain_setup):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    cloudflare.delete_error = CloudflareServiceError(
        operation="delete_custom_hostname",
        kind="transport",
        message="Cloudflare request failed",
    )
    with pytest.raises(HTTPException):
        await service.disconnect(_owner())

    cloudflare.delete_error = CloudflareServiceError(
        operation="delete_custom_hostname",
        kind="provider",
        message="Cloudflare could not find the hostname",
        provider_status_code=404,
        errors=({"code": 1000, "message": "not found"},),
    )
    await service.disconnect(_owner())

    assert cloudflare.deleted == ["cf-hostname-1", "cf-hostname-1"]
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) is None


@pytest.mark.asyncio
async def test_successful_delete_removes_only_owner_mapping(domain_setup):
    service, mongo, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    mongo.raw.storefront_domains.insert_one(
        {
            "planner_id": SECOND_OWNER_ID,
            "hostname": "other.example",
            "provider_hostname_id": "cf-hostname-2",
            "status": "active",
        }
    )

    result = await service.disconnect(_owner())

    assert result is None
    assert cloudflare.deleted == ["cf-hostname-1"]
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) is None
    assert (
        mongo.raw.storefront_domains.find_one({"planner_id": SECOND_OWNER_ID})
        is not None
    )


@pytest.mark.asyncio
async def test_entitlement_loss_blocks_management_and_serving_without_deleting_state(
    domain_setup,
):
    service, mongo, entitlements, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")
    cloudflare.status_result["status"] = "active"
    cloudflare.status_result["ssl"]["status"] = "active"
    await service.refresh(_owner())

    active = await service.resolve_active_hostname("events.example")
    assert active is not None
    assert active["planner_id"] == OWNER_ID

    entitlements.enabled_by_owner[OWNER_ID] = False
    assert await service.resolve_active_hostname("events.example") is None
    with pytest.raises(HTTPException) as denied:
        await service.get_for_owner(_owner())
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as disconnect_denied:
        await service.disconnect(_owner())
    assert disconnect_denied.value.status_code == 403
    assert cloudflare.deleted == []
    assert mongo.raw.storefront_domains.count_documents({}) == 1


@pytest.mark.asyncio
async def test_resolver_returns_only_exact_active_hostname(domain_setup):
    service, _, _, cloudflare = domain_setup
    await service.connect(_owner(), "events.example")

    assert await service.resolve_active_hostname("events.example") is None
    cloudflare.status_result["status"] = "active"
    cloudflare.status_result["ssl"]["status"] = "active"
    await service.refresh(_owner())
    assert await service.resolve_active_hostname("other.example") is None
    assert (await service.resolve_active_hostname("EVENTS.EXAMPLE"))["hostname"] == (
        "events.example"
    )
