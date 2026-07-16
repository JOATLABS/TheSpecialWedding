from __future__ import annotations

import asyncio
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from types import SimpleNamespace
from urllib.parse import urlsplit

from bson import ObjectId
from cryptography.fernet import Fernet
from fastapi import HTTPException
import mongomock
import pytest

import app.services.storefront_domain_service as storefront_domain_service_module
from app.models.storefront import StorefrontDomainResponse
from app.services.cloudflare_service import CloudflareServiceError
from app.services.storefront_domain_service import StorefrontDomainService
from app.services.storefront_domain_operator_service import (
    StorefrontDomainOperatorService,
)
from app.services.storefront_domain_rollout import StorefrontDomainRolloutPolicy
from app.services.storefront_entitlement_service import StorefrontEntitlements


OWNER_ID = "507f1f77bcf86cd799439011"
SECOND_OWNER_ID = "507f1f77bcf86cd799439012"
HOSTNAME = "events.customer.example"
ZONE = "customer.example"
CNAME_TARGET = "storefronts.edge.example.net"


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
        self.raw = mongomock.MongoClient()["storefront_domain_claim_test"]
        self.db = AsyncDatabase(self.raw)
        self.raw.storefront_domains.create_index("planner_id", unique=True)
        self.raw.storefront_domains.create_index("hostname", unique=True)
        self.raw.storefront_domain_conflict_claims.create_index(
            "attempt_id", unique=True
        )
        self.raw.storefront_domain_conflict_claims.create_index(
            "claim_token_digest", unique=True
        )
        self.raw.storefront_domain_conflict_claims.create_index(
            "current_owner_key",
            unique=True,
            partialFilterExpression={"current_owner_key": {"$type": "string"}},
        )
        self.raw.storefront_domain_operations.create_index("operation_id", unique=True)
        self.raw.storefront_domain_operations.create_index(
            [("domain_id", 1), ("attempt_id", 1), ("kind", 1)], unique=True
        )
        self.raw.storefront_domain_instruction_links.create_index(
            "link_id", unique=True
        )
        self.raw.storefront_domain_instruction_links.create_index(
            "token_digest",
            unique=True,
            partialFilterExpression={"token_digest": {"$type": "string"}},
        )
        self.raw.storefront_domain_instruction_links.create_index(
            [("domain_id", 1), ("claim_attempt_id", 1), ("recipient_hash", 1)],
            unique=True,
        )
        self.raw.storefront_domain_instruction_quotas.create_index(
            "quota_key", unique=True
        )
        self.raw.storefront_domain_tombstones.create_index(
            "deletion_receipt_id", unique=True
        )


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


class FakeDnsResolver:
    def __init__(self):
        self.queries: list[tuple[str, str]] = []
        self.authoritative_queries: list[tuple[str, str, tuple[str, ...]]] = []
        self.on_query = None
        self.on_authoritative_query = None
        self.records: dict[tuple[str, str], list[str]] = {
            (ZONE, "NS"): [
                "ns-cloud-a1.googledomains.com",
                "ns-cloud-a2.googledomains.com",
            ]
        }

    async def query(self, name: str, record_type: str) -> list[str]:
        key = (name.lower().rstrip("."), record_type.upper())
        self.queries.append(key)
        callback = self.on_query
        if callback is not None:
            self.on_query = None
            callback(key)
        return list(self.records.get(key, []))

    async def query_authoritative(
        self, name: str, record_type: str, nameservers: list[str]
    ) -> list[str]:
        key = (name.lower().rstrip("."), record_type.upper())
        self.authoritative_queries.append((key[0], key[1], tuple(nameservers)))
        callback = self.on_authoritative_query
        if callback is not None:
            self.on_authoritative_query = None
            callback(key)
        return list(self.records.get(key, []))

    def set(self, name: str, record_type: str, *values: str) -> None:
        self.records[(name.lower().rstrip("."), record_type.upper())] = list(values)


class FakeCloudflare:
    is_configured = True

    def __init__(self):
        self.created: list[str] = []
        self.listed: list[str] = []
        self.read: list[str] = []
        self.deleted: list[str] = []
        self.list_results: list[list[dict]] = [[]]
        self.create_error: CloudflareServiceError | None = None
        self.create_result = {
            "id": "cf-hostname-1",
            "hostname": HOSTNAME,
            "status": "pending",
            "ownership_verification": {
                "type": "txt",
                "name": f"_cf-custom-hostname.{HOSTNAME}",
                "value": "cloudflare-ownership-token",
            },
            "ownership_verification_http": None,
            "ssl": {
                "status": "pending_validation",
                "validation_records": [
                    {
                        "status": "pending",
                        "txt_name": f"_acme-challenge.{HOSTNAME}",
                        "txt_value": "acme-token",
                    }
                ],
            },
        }

    async def list_custom_hostnames(self, hostname: str) -> list[dict]:
        self.listed.append(hostname)
        if len(self.list_results) > 1:
            return deepcopy(self.list_results.pop(0))
        return deepcopy(self.list_results[0])

    async def create_custom_hostname(self, hostname: str) -> dict:
        self.created.append(hostname)
        if self.create_error:
            raise self.create_error
        result = deepcopy(self.create_result)
        result["hostname"] = hostname
        return result

    async def get_custom_hostname(self, hostname_id: str) -> dict:
        self.read.append(hostname_id)
        return deepcopy(self.create_result)

    async def delete_custom_hostname(self, hostname_id: str) -> dict:
        self.deleted.append(hostname_id)
        return {"id": hostname_id}


class FakeInstructionEmail:
    def __init__(self):
        self.calls: list[dict] = []

    async def send_email(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"success": True, "message_id": "email-1"}


class FailingInstructionEmail(FakeInstructionEmail):
    async def send_email(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"success": False}


class BlockingInstructionEmail(FakeInstructionEmail):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def send_email(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        self.started.set()
        await self.release.wait()
        return {"success": True, "message_id": "email-1"}


class SupportedDomainConnectDiscovery:
    def __init__(self):
        self.zones: list[str] = []

    async def discover(self, zone: str) -> dict:
        self.zones.append(zone)
        return {
            "supported": True,
            "provider_name": "cloudflare",
            "control_panel_url": "https://dash.cloudflare.com/example/dns",
            "provider_id": "thespecialwedding",
            "service_id": "storefront",
            "template_version": "1",
        }


class UnsupportedDomainConnectDiscovery:
    async def discover(self, _zone: str) -> dict:
        return {
            "supported": False,
            "reason_code": "exact_template_not_supported",
        }


def _owner(owner_id: str = OWNER_ID) -> dict:
    return {"_id": ObjectId(owner_id), "role": "wedding_planner"}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@pytest.fixture
def claim_setup():
    mongo = FakeMongo()
    entitlements = FakeEntitlements()
    dns = FakeDnsResolver()
    cloudflare = FakeCloudflare()
    service = StorefrontDomainService(
        mongo_client=mongo,
        cloudflare_service=cloudflare,
        entitlement_service=entitlements,
        dns_resolver=dns,
        claim_encryption_key="storefront-domain-claim-test-key",
        cname_target=CNAME_TARGET,
        platform_domains={"thespecialwedding.io", "thespecialwedding.com"},
        readiness_resolver=lambda: {
            "enabled": True,
            "ready": True,
            "reason_code": "ready",
            "missing": [],
        },
        rollout_policy=StorefrontDomainRolloutPolicy.build(mode="general"),
        instruction_public_base_url="https://thespecialwedding.com",
    )
    return service, mongo, entitlements, dns, cloudflare


def _record(response: dict, record_type: str) -> dict:
    return next(
        record
        for record in response["expected_records"]
        if record["type"] == record_type
    )


def _set_current_dns(dns: FakeDnsResolver, claim: dict) -> None:
    txt = _record(claim, "TXT")
    cname = _record(claim, "CNAME")
    dns.set(txt["name"], "TXT", txt["value"])
    dns.set(cname["name"], "CNAME", cname["value"])


@pytest.mark.asyncio
async def test_rollout_preflight_is_observe_only_but_claim_fails_closed(claim_setup):
    service, mongo, _, _, cloudflare = claim_setup
    service._rollout_policy = StorefrontDomainRolloutPolicy.build(mode="allowlist")

    preflight = await service.preflight(_owner(), HOSTNAME, intent="new")

    assert preflight["self_service_allowed"] is False
    assert preflight["domain_connect_supported"] is False
    assert preflight["recommended_flow"] == "manual"
    assert "production pilot" in preflight["customer_action"]
    assert cloudflare.created == []
    assert cloudflare.listed == []

    with pytest.raises(HTTPException) as blocked:
        await service.claim(_owner(), HOSTNAME, intent="new")

    assert blocked.value.status_code == 403
    assert blocked.value.detail["code"] == "custom_domain_rollout_unavailable"
    assert mongo.raw.storefront_domains.count_documents({}) == 0


@pytest.mark.asyncio
async def test_preflight_collects_authoritative_evidence_and_has_no_provider_mutation(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    dns.set(HOSTNAME, "A", "203.0.113.10")
    dns.set(HOSTNAME, "CAA", '0 issue "letsencrypt.org"')
    dns.set(HOSTNAME, "TXT", "existing-verification=value")

    result = await service.preflight(_owner(), HOSTNAME.upper(), intent="migration")

    assert result["hostname"] == HOSTNAME
    assert result["host_type"] == "subdomain"
    assert result["intent"] == "migration"
    assert result["recommended_flow"] == "assisted_migration"
    assert result["authoritative_dns"] == {
        "zone": ZONE,
        "provider": "google_or_squarespace_dns",
        "provider_name": "Google Cloud DNS or Squarespace DNS",
        "control_panel_url": None,
        "nameservers": [
            "ns-cloud-a1.googledomains.com",
            "ns-cloud-a2.googledomains.com",
        ],
    }
    assert {item["type"] for item in result["observed_records"]} == {
        "NS",
        "A",
        "AAAA",
        "CNAME",
        "CAA",
        "TXT",
    }
    assert result["conflicts"] == [
        {
            "code": "existing_routing_record",
            "record_type": "A",
            "values": ["203.0.113.10"],
        }
    ]
    assert result["registrar"] == "unknown"
    assert result["platform_provider"] == "Cloudflare for The Special Wedding"
    assert {record["type"] for record in result["expected_records"]} == {"TXT"}
    assert _record(result, "TXT")["value"] is None
    assert dns.authoritative_queries
    assert all(
        nameservers
        == (
            "ns-cloud-a1.googledomains.com",
            "ns-cloud-a2.googledomains.com",
        )
        for _name, _record_type, nameservers in dns.authoritative_queries
    )
    assert cloudflare.created == []
    assert cloudflare.listed == []


def test_dns_provider_detection_is_honest_for_shared_and_branded_nameservers():
    assert StorefrontDomainService._dns_provider_details(
        StorefrontDomainService._dns_provider(
            ["ns-cloud-a1.googledomains.com", "ns-cloud-a2.googledomains.com"]
        )
    ) == ("Google Cloud DNS or Squarespace DNS", None)
    assert StorefrontDomainService._dns_provider_details(
        StorefrontDomainService._dns_provider(
            ["dns1.squarespacedns.com", "dns2.squarespacedns.com"]
        )
    ) == (
        "Squarespace DNS",
        "https://account.squarespace.com/domains",
    )
    assert StorefrontDomainService._dns_provider_details(
        StorefrontDomainService._dns_provider(["dns1.nsone.net", "dns2.systemdns.com"])
    ) == ("DNS provider not detected", None)


@pytest.mark.parametrize(
    ("nameservers", "expected_provider"),
    [
        (["Ada.NS.Cloudflare.COM."], "cloudflare"),
        (["ns.cloudflare.com.example.net"], "unknown"),
        (["evilcloudflare.com"], "unknown"),
        (["ns-123.awsdns-45.net"], "amazon_route53"),
        (["ns-123.awsdns-45.net.example.org"], "unknown"),
    ],
)
def test_dns_provider_detection_requires_exact_suffix_or_label_boundaries(
    nameservers, expected_provider
):
    assert StorefrontDomainService._dns_provider(nameservers) == expected_provider


@pytest.mark.asyncio
async def test_preflight_advertises_live_domain_connect_only_for_safe_new_host(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    discovery = SupportedDomainConnectDiscovery()
    service._domain_connect_discovery = discovery
    dns.set(
        ZONE,
        "NS",
        "ada.ns.cloudflare.com",
        "bob.ns.cloudflare.com",
    )

    result = await service.preflight(_owner(), HOSTNAME, intent="new")

    assert discovery.zones == [ZONE]
    assert result["domain_connect_supported"] is True
    assert result["domain_connect_provider"] == "cloudflare"
    assert result["recommended_flow"] == "automatic"
    assert result["conflicts"] == []
    assert result["authoritative_dns"] == {
        "zone": ZONE,
        "provider": "cloudflare",
        "provider_name": "Cloudflare",
        "control_panel_url": "https://dash.cloudflare.com/example/dns",
        "nameservers": [
            "ada.ns.cloudflare.com",
            "bob.ns.cloudflare.com",
        ],
    }
    assert cloudflare.created == []
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_preflight_routes_cloudflare_o2o_migration_to_assisted_flow(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    dns.set(
        ZONE,
        "NS",
        "ada.ns.cloudflare.com",
        "bob.ns.cloudflare.com",
    )

    result = await service.preflight(_owner(), HOSTNAME, intent="migration")

    assert result["recommended_flow"] == "assisted_migration"
    assert result["domain_connect_supported"] is False
    assert result["self_service_allowed"] is False
    assert "request an assisted" in result["customer_action"]
    assert {record["type"] for record in result["expected_records"]} == {"TXT"}
    constraint = next(
        conflict
        for conflict in result["conflicts"]
        if conflict["code"] == "cloudflare_o2o_migration_requires_assistance"
    )
    assert constraint["record_type"] == "NS"
    assert constraint["values"] == [
        "ada.ns.cloudflare.com",
        "bob.ns.cloudflare.com",
    ]
    assert "Keep the current routing unchanged" in constraint["message"]
    assert cloudflare.created == []
    assert cloudflare.listed == []

    claim = await service.claim(_owner(), HOSTNAME, intent="migration")
    txt = _record(claim, "TXT")
    dns.set(txt["name"], "TXT", txt["value"])

    reviewed = await service.verify(_owner())

    assert reviewed["application_status"] == "operator_review"
    assert reviewed["action"] == "operator_review"
    assert reviewed["ownership_status"] == "verified"
    assert reviewed["routing_dns_status"] == "pending"
    assert reviewed["provider_hostname_id"] is None
    assert reviewed["provider_hostname_status"] == "not_created"
    assert reviewed["last_error"]["code"] == (
        "cloudflare_o2o_migration_requires_assistance"
    )
    assert {record["type"] for record in reviewed["expected_records"]} == {"TXT"}
    assert cloudflare.created == []
    assert cloudflare.listed == []

    await service.disconnect(_owner())

    assert cloudflare.created == []
    assert cloudflare.listed == []
    assert cloudflare.deleted == []
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) is None
    tombstone = mongo.raw.storefront_domain_tombstones.find_one(
        {"planner_id": OWNER_ID}
    )
    assert tombstone["hostname"] == HOSTNAME
    assert tombstone["provider_hostname_id"] is None
    assert tombstone["removal_kind"] == "setup_cancelled"
    assert {record["type"] for record in tombstone["cleanup_records"]} == {"TXT"}
    operation = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": tombstone["provider_delete_operation_id"]}
    )
    assert operation["kind"] == "provider_delete"
    assert operation["state"] == "completed"
    assert operation["provider_hostname_id"] is None
    assert operation["provider_receipt"]["outcome"] == "not_created"
    assert tombstone["provider_delete_receipt"] == operation["provider_receipt"]


@pytest.mark.asyncio
async def test_operator_o2o_approval_is_attempt_bound_and_consumed_once(claim_setup):
    service, mongo, _, dns, cloudflare = claim_setup
    dns.set(ZONE, "NS", "ada.ns.cloudflare.com", "bob.ns.cloudflare.com")
    claim = await service.claim(_owner(), HOSTNAME, intent="migration")
    txt = _record(claim, "TXT")
    dns.set(txt["name"], "TXT", txt["value"])
    reviewed = await service.verify(_owner())
    assert reviewed["application_status"] == "operator_review"

    operator = StorefrontDomainOperatorService(
        mongo_client=mongo,
        cloudflare_service=cloudflare,
    )
    actor = SimpleNamespace(
        is_root_admin=True,
        email="thedeveloper@thespecialwedding.io",
    )
    approval = await operator.approve_o2o_cutover(
        actor,
        planner_id=OWNER_ID,
        hostname=HOSTNAME,
        attempt_id=reviewed["attempt_id"],
        revision=reviewed["revision"],
        reason="Ownership proof and O2O cutover risk were independently reviewed.",
    )

    assert approval["decision"] == "approved"
    assert approval["application_status"] == "migration_prevalidation"
    assert cloudflare.created == []
    assert cloudflare.listed == []

    continued = await service.verify(_owner())
    assert continued["application_status"] == "hostname_validation"
    assert cloudflare.created == [HOSTNAME]
    assert cloudflare.listed == [HOSTNAME]
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    marker = stored["operator_assisted_cutover_approval"]
    assert marker["claim_attempt_id"] == reviewed["attempt_id"]
    assert marker["consumed_at"] is not None
    assert (
        marker["consumed_by_provider_attempt_id"]
        == stored["provider_create_attempt_id"]
    )
    receipt = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": approval["operation_id"]}
    )
    assert receipt["kind"] == "operator_o2o_cutover_approval"
    assert receipt["state"] == "completed"


@pytest.mark.asyncio
async def test_preflight_rejects_authoritative_apex_with_structured_error(claim_setup):
    service, _, _, _, cloudflare = claim_setup

    with pytest.raises(HTTPException) as failure:
        await service.preflight(_owner(), ZONE, intent="new")

    assert failure.value.status_code == 422
    assert failure.value.detail.keys() >= {
        "code",
        "message",
        "customer_action",
        "retryable",
        "support_id",
        "field",
    }
    assert failure.value.detail["code"] == "apex_self_service_not_supported"
    assert failure.value.detail["field"] == "domain"
    assert cloudflare.created == []


@pytest.mark.asyncio
async def test_claim_stores_only_encrypted_256_bit_token_and_never_calls_cloudflare(
    claim_setup,
):
    service, mongo, _, _, cloudflare = claim_setup
    before = datetime.now(timezone.utc)

    result = await service.claim(_owner(), HOSTNAME, intent="new")

    txt = _record(result, "TXT")
    token = txt["value"].removeprefix("tsw-verification=")
    decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    assert len(decoded) == 32
    assert result["application_status"] == "dns_setup_pending"
    assert result["action"] == "action_required"
    assert _record(result, "CNAME") == {
        "type": "CNAME",
        "name": HOSTNAME,
        "value": CNAME_TARGET,
        "ttl": 300,
        "purpose": "storefront_routing",
    }
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["claim_token_digest"] == hashlib.sha256(token.encode()).hexdigest()
    assert stored["claim_token_encrypted"] != token
    assert token not in repr(stored)
    assert (
        Fernet(service._claim_cipher_key)
        .decrypt(stored["claim_token_encrypted"].encode())
        .decode()
        == token
    )
    claim_expires_at = _aware(stored["claim_expires_at"])
    assert before + timedelta(days=6, hours=23) < claim_expires_at
    assert claim_expires_at < before + timedelta(days=7, minutes=1)
    assert cloudflare.created == []
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_claim_persists_resumable_setup_method_without_provider_mutation(
    claim_setup,
):
    service, mongo, _, _, cloudflare = claim_setup
    service._domain_connect_discovery = SupportedDomainConnectDiscovery()

    automatic = await service.claim(
        _owner(), HOSTNAME, intent="new", setup_method="automatic"
    )

    assert automatic["setup_method"] == "automatic"
    assert automatic["domain_connect_authorized"] is False
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["setup_method"] == "automatic"
    assert stored.get("domain_connect_authorized_at") is None
    assert cloudflare.created == []
    assert cloudflare.listed == []

    manual = await service.claim(
        _owner(), HOSTNAME, intent="new", setup_method="manual"
    )

    assert manual["attempt_id"] == automatic["attempt_id"]
    assert manual["setup_method"] == "manual"
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["setup_method"] == "manual"
    assert stored.get("domain_connect_authorized_at") is None
    StorefrontDomainResponse.model_validate(manual)


@pytest.mark.asyncio
async def test_claim_rejects_automatic_mode_without_exact_live_template_support(
    claim_setup,
):
    service, mongo, _, _, cloudflare = claim_setup
    service._domain_connect_discovery = UnsupportedDomainConnectDiscovery()

    with pytest.raises(HTTPException) as blocked:
        await service.claim(_owner(), HOSTNAME, intent="new", setup_method="automatic")

    assert blocked.value.status_code == 409
    assert blocked.value.detail["code"] == "automatic_domain_setup_unavailable"
    assert mongo.raw.storefront_domains.count_documents({}) == 0
    assert cloudflare.created == []
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_worker_activation_of_authorized_automatic_claim_rechecks_dns_and_entitlement(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    service._domain_connect_discovery = SupportedDomainConnectDiscovery()
    claim = await service.claim(
        _owner(), HOSTNAME, intent="new", setup_method="automatic"
    )
    authorized_at = datetime.now(timezone.utc)
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {"$set": {"domain_connect_authorized_at": authorized_at}},
    )
    _set_current_dns(dns, claim)

    result = await service.verify_authorized_automatic_for_owner_id(
        OWNER_ID, claim["attempt_id"]
    )

    assert result["provider_hostname_id"] == "cf-hostname-1"
    assert result["ownership_status"] == "verified"
    assert result["routing_dns_status"] == "verified"
    assert cloudflare.created == [HOSTNAME]
    assert cloudflare.listed == [HOSTNAME]


@pytest.mark.asyncio
async def test_worker_automatic_activation_fails_closed_after_entitlement_loss(
    claim_setup,
):
    service, mongo, entitlements, dns, cloudflare = claim_setup
    service._domain_connect_discovery = SupportedDomainConnectDiscovery()
    claim = await service.claim(
        _owner(), HOSTNAME, intent="new", setup_method="automatic"
    )
    authorized_at = datetime.now(timezone.utc)
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {"$set": {"domain_connect_authorized_at": authorized_at}},
    )
    _set_current_dns(dns, claim)
    entitlements.enabled_by_owner[OWNER_ID] = False

    result = await service.verify_authorized_automatic_for_owner_id(
        OWNER_ID, claim["attempt_id"]
    )

    assert result["application_status"] == "dns_setup_pending"
    assert result["action"] == "action_required"
    assert result["provider_hostname_id"] is None
    assert result["last_error"]["code"] == "custom_domain_entitlement_required"
    assert cloudflare.created == []
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_claim_digest_detects_encrypted_token_tampering(claim_setup):
    service, mongo, _, _, _ = claim_setup
    await service.claim(_owner(), HOSTNAME, intent="new")
    forged_token = secrets.token_urlsafe(32)
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "claim_token_encrypted": service._claim_cipher.encrypt(
                    forged_token.encode()
                ).decode()
            }
        },
    )
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})

    assert service._decrypt_claim_token(stored) is None
    assert service._serialize(stored)["expected_records"] == []


@pytest.mark.asyncio
async def test_claim_is_owner_scoped_and_rotates_only_an_expired_attempt(claim_setup):
    service, mongo, _, _, cloudflare = claim_setup
    first = await service.claim(_owner(), HOSTNAME, intent="new")
    resumed = await service.claim(_owner(), HOSTNAME, intent="new")

    assert resumed["attempt_id"] == first["attempt_id"]
    assert _record(resumed, "TXT")["value"] == _record(first, "TXT")["value"]

    conflict = await service.claim(_owner(SECOND_OWNER_ID), HOSTNAME, intent="new")
    assert conflict["conflict_code"] == "hostname_reserved"
    assert StorefrontDomainResponse.model_validate(conflict).conflict_code == (
        "hostname_reserved"
    )
    assert conflict["application_status"] == "dns_setup_pending"
    assert {record["type"] for record in conflict["expected_records"]} == {"TXT"}
    assert conflict["provider_hostname_id"] is None

    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "claim_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)
            }
        },
    )
    rotated = await service.claim(_owner(), HOSTNAME, intent="new")

    assert rotated["attempt_id"] != first["attempt_id"]
    assert _record(rotated, "TXT")["value"] != _record(first, "TXT")["value"]
    assert rotated["revision"] == first["revision"] + 1
    assert cloudflare.created == []


@pytest.mark.asyncio
async def test_cross_owner_conflict_claim_is_append_only_encrypted_and_non_leaking(
    claim_setup,
):
    service, mongo, _, _, cloudflare = claim_setup
    await service.claim(_owner(), HOSTNAME, intent="new")
    reserved_before = deepcopy(
        mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    )

    conflict = await service.claim(_owner(SECOND_OWNER_ID), HOSTNAME, intent="new")
    stored = mongo.raw.storefront_domain_conflict_claims.find_one(
        {"claimant_planner_id": SECOND_OWNER_ID}
    )

    assert stored is not None
    assert stored["attempt_id"] == conflict["attempt_id"]
    assert stored["claim_token_encrypted"]
    assert (
        stored["claim_token_digest"]
        == hashlib.sha256(service._decrypt_claim_token(stored).encode()).hexdigest()
    )
    assert (
        len(base64.urlsafe_b64decode(service._decrypt_claim_token(stored) + "==")) == 32
    )
    assert _aware(stored["claim_expires_at"]) > datetime.now(timezone.utc) + timedelta(
        days=6, hours=23
    )
    assert "reserved_owner" not in stored
    assert OWNER_ID not in repr(conflict)
    assert OWNER_ID not in repr(stored)
    assert (
        mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
        == reserved_before
    )
    assert conflict["conflict_code"] == "hostname_reserved"
    assert conflict["observed_records"] == []
    assert {record["type"] for record in conflict["expected_records"]} == {"TXT"}
    assert cloudflare.created == []
    assert cloudflare.listed == []
    assert cloudflare.deleted == []


@pytest.mark.asyncio
async def test_conflict_claim_resumes_rotates_and_stale_txt_stays_pending(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    await service.claim(_owner(), HOSTNAME, intent="new")
    first = await service.claim(_owner(SECOND_OWNER_ID), HOSTNAME, intent="new")
    resumed = await service.claim(_owner(SECOND_OWNER_ID), HOSTNAME, intent="new")
    first_txt = _record(first, "TXT")

    assert resumed["attempt_id"] == first["attempt_id"]
    assert _record(resumed, "TXT")["value"] == first_txt["value"]

    mongo.raw.storefront_domain_conflict_claims.update_one(
        {"attempt_id": first["attempt_id"]},
        {
            "$set": {
                "claim_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)
            }
        },
    )
    expired_status = await service.get_status(
        _owner(SECOND_OWNER_ID), attempt_id=first["attempt_id"]
    )
    assert expired_status["application_status"] == "expired"
    assert expired_status["expected_records"] == []
    rotated = await service.claim(_owner(SECOND_OWNER_ID), HOSTNAME, intent="new")

    assert rotated["attempt_id"] != first["attempt_id"]
    assert _record(rotated, "TXT")["value"] != first_txt["value"]
    assert mongo.raw.storefront_domain_conflict_claims.count_documents({}) == 2
    expired = mongo.raw.storefront_domain_conflict_claims.find_one(
        {"attempt_id": first["attempt_id"]}
    )
    assert expired["application_status"] == "expired"
    assert "current_owner_key" not in expired

    dns.set(first_txt["name"], "TXT", first_txt["value"])
    pending = await service.verify(
        _owner(SECOND_OWNER_ID), attempt_id=rotated["attempt_id"]
    )
    assert pending["ownership_status"] == "pending"
    assert pending["application_status"] == "dns_setup_pending"

    current_txt = _record(rotated, "TXT")
    dns.set(current_txt["name"], "TXT", current_txt["value"])
    reviewed = await service.observe(_owner(SECOND_OWNER_ID), rotated["attempt_id"])
    assert reviewed["ownership_status"] == "verified"
    assert reviewed["application_status"] == "operator_review"
    assert reviewed["action"] == "operator_review"
    assert reviewed["last_error"]["code"] == "hostname_conflict_requires_review"
    assert (
        _record(reviewed, "TXT")["value"] in reviewed["observed_records"][0]["values"]
    )
    assert mongo.raw.storefront_domain_conflict_claims.find_one(
        {"attempt_id": rotated["attempt_id"]}
    )["ownership_verified_at"]
    assert cloudflare.created == []
    assert cloudflare.listed == []
    assert cloudflare.deleted == []


@pytest.mark.asyncio
async def test_conflict_proof_expires_when_authoritative_delegation_changes(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    await service.claim(_owner(), HOSTNAME, intent="new")
    conflict = await service.claim(_owner(SECOND_OWNER_ID), HOSTNAME, intent="new")
    proof = _record(conflict, "TXT")
    dns.set(proof["name"], "TXT", proof["value"])
    dns.authoritative_queries.clear()
    dns.set(
        ZONE,
        "NS",
        "ns1.redelegated.example.net",
        "ns2.redelegated.example.net",
    )

    expired = await service.verify(
        _owner(SECOND_OWNER_ID), attempt_id=conflict["attempt_id"]
    )

    assert expired["application_status"] == "expired"
    assert expired["ownership_status"] == "expired"
    assert expired["last_error"]["code"] == "authoritative_dns_delegation_changed"
    assert expired["expected_records"] == []
    stored = mongo.raw.storefront_domain_conflict_claims.find_one(
        {"attempt_id": conflict["attempt_id"]}
    )
    assert "current_owner_key" not in stored
    assert dns.authoritative_queries == []
    assert cloudflare.listed == []
    assert cloudflare.created == []
    assert cloudflare.deleted == []


@pytest.mark.asyncio
async def test_conflict_claimant_with_another_domain_must_disconnect_first(
    claim_setup,
):
    service, _, _, _, cloudflare = claim_setup
    await service.claim(_owner(), HOSTNAME, intent="new")
    await service.claim(_owner(SECOND_OWNER_ID), "shop.customer.example", intent="new")

    with pytest.raises(HTTPException) as failure:
        await service.claim(_owner(SECOND_OWNER_ID), HOSTNAME, intent="new")

    assert failure.value.status_code == 409
    assert failure.value.detail["code"] == "existing_custom_domain_must_be_disconnected"
    assert cloudflare.created == []
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_reserved_cloudflare_hostname_still_gets_proof_only_conflict_journey(
    claim_setup,
):
    service, _, _, dns, cloudflare = claim_setup
    await service.claim(_owner(), HOSTNAME, intent="new")
    dns.set(
        ZONE,
        "NS",
        "ada.ns.cloudflare.com",
        "bob.ns.cloudflare.com",
    )

    conflict = await service.claim(
        _owner(SECOND_OWNER_ID), HOSTNAME, intent="migration"
    )

    assert conflict["conflict_code"] == "hostname_reserved"
    assert conflict["intent"] == "migration"
    assert {record["type"] for record in conflict["expected_records"]} == {"TXT"}
    assert conflict["domain_connect_supported"] is False
    assert cloudflare.created == []
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_active_conflict_journey_blocks_a_different_domain_until_cancelled(
    claim_setup,
):
    service, mongo, _, _, _ = claim_setup
    await service.claim(_owner(), HOSTNAME, intent="new")
    await service.claim(_owner(SECOND_OWNER_ID), HOSTNAME, intent="new")

    with pytest.raises(HTTPException) as failure:
        await service.claim(
            _owner(SECOND_OWNER_ID), "shop.customer.example", intent="new"
        )

    assert failure.value.status_code == 409
    assert failure.value.detail["code"] == "conflict_claim_already_active"
    assert (
        mongo.raw.storefront_domains.find_one({"planner_id": SECOND_OWNER_ID}) is None
    )

    await service.disconnect(_owner(SECOND_OWNER_ID))
    claimed = await service.claim(
        _owner(SECOND_OWNER_ID), "shop.customer.example", intent="new"
    )
    assert claimed["hostname"] == "shop.customer.example"
    assert claimed["conflict_code"] is None


@pytest.mark.asyncio
async def test_conflict_attempt_status_verify_observe_and_cancel_are_owner_scoped(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    await service.claim(_owner(), HOSTNAME, intent="new")
    reserved_before = deepcopy(
        mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    )
    conflict = await service.claim(_owner(SECOND_OWNER_ID), HOSTNAME, intent="new")

    assert (
        await service.get_status(
            _owner(SECOND_OWNER_ID), attempt_id=conflict["attempt_id"]
        )
    )["attempt_id"] == conflict["attempt_id"]

    for operation in (
        lambda: service.get_status(_owner(), attempt_id=conflict["attempt_id"]),
        lambda: service.verify(_owner(), attempt_id=conflict["attempt_id"]),
        lambda: service.observe(_owner(), conflict["attempt_id"]),
        lambda: service.disconnect(_owner(), attempt_id=conflict["attempt_id"]),
    ):
        with pytest.raises(HTTPException) as failure:
            await operation()
        assert failure.value.status_code == 404

    proof = _record(conflict, "TXT")
    dns.set(proof["name"], "TXT", proof["value"])
    reviewed = await service.verify(
        _owner(SECOND_OWNER_ID), attempt_id=conflict["attempt_id"]
    )
    assert reviewed["application_status"] == "operator_review"

    await service.disconnect(_owner(SECOND_OWNER_ID), attempt_id=conflict["attempt_id"])
    cancelled = await service.get_status(
        _owner(SECOND_OWNER_ID), attempt_id=conflict["attempt_id"]
    )
    assert cancelled["application_status"] == "disconnected"
    assert cancelled["ownership_status"] == "cancelled"
    assert cancelled["expected_records"] == []
    stored_cancelled = mongo.raw.storefront_domain_conflict_claims.find_one(
        {"attempt_id": conflict["attempt_id"]}
    )
    assert stored_cancelled["ownership_verified_at"]
    assert (
        mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
        == reserved_before
    )
    assert cloudflare.created == []
    assert cloudflare.listed == []
    assert cloudflare.deleted == []


@pytest.mark.asyncio
@pytest.mark.parametrize("proof", ["missing", "mismatched", "expired", "rotated"])
async def test_verify_rejects_noncurrent_txt_proof_without_provider_mutation(
    claim_setup, proof
):
    service, mongo, _, dns, cloudflare = claim_setup
    first = await service.claim(_owner(), HOSTNAME, intent="new")
    stale_txt = _record(first, "TXT")
    cname = _record(first, "CNAME")
    dns.set(cname["name"], "CNAME", cname["value"])

    if proof == "mismatched":
        dns.set(stale_txt["name"], "TXT", "tsw-verification=wrong-token")
    elif proof == "expired":
        dns.set(stale_txt["name"], "TXT", stale_txt["value"])
        mongo.raw.storefront_domains.update_one(
            {"planner_id": OWNER_ID},
            {
                "$set": {
                    "claim_expires_at": datetime.now(timezone.utc)
                    - timedelta(seconds=1)
                }
            },
        )
    elif proof == "rotated":
        mongo.raw.storefront_domains.update_one(
            {"planner_id": OWNER_ID},
            {
                "$set": {
                    "claim_expires_at": datetime.now(timezone.utc)
                    - timedelta(seconds=1)
                }
            },
        )
        rotated = await service.claim(_owner(), HOSTNAME, intent="new")
        assert _record(rotated, "TXT")["value"] != stale_txt["value"]
        dns.set(stale_txt["name"], "TXT", stale_txt["value"])

    result = await service.verify(_owner())

    assert result["application_status"] == "dns_setup_pending"
    assert result["action"] == "action_required"
    assert result["ownership_status"] in {"pending", "expired"}
    if proof == "mismatched":
        txt_observation = next(
            item for item in result["observed_records"] if item["type"] == "TXT"
        )
        assert txt_observation["values"] == ["tsw-verification=wrong-token"]
    assert cloudflare.created == []
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_expired_claim_write_cannot_overwrite_concurrent_claim_rotation(
    claim_setup, monkeypatch
):
    service, mongo, _, _, cloudflare = claim_setup
    first = await service.claim(_owner(), HOSTNAME, intent="new")
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "claim_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)
            }
        },
    )
    collection = mongo.db["storefront_domains"]
    original_update = collection.update_one
    rotated_fields: dict = {}

    async def rotate_before_expiry_write(query, update, *args, **kwargs):
        if update.get("$set", {}).get("ownership_status") == "expired":
            assert query["revision"] == first["revision"]
            assert query["claim_attempt_id"] == first["attempt_id"]
            assert query["authoritative_dns.zone"] == ZONE
            assert query["authoritative_dns.nameservers"] == [
                "ns-cloud-a1.googledomains.com",
                "ns-cloud-a2.googledomains.com",
            ]
            assert query["deletion_status"] is None
            rotated, _token = service._new_claim_fields(
                HOSTNAME,
                revision=first["revision"] + 1,
                intent="new",
            )
            rotated_fields.update(rotated)
            mongo.raw.storefront_domains.update_one(
                {"planner_id": OWNER_ID}, {"$set": rotated}
            )
        return await original_update(query, update, *args, **kwargs)

    monkeypatch.setattr(collection, "update_one", rotate_before_expiry_write)

    current = await service.verify(_owner())

    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert current["attempt_id"] == rotated_fields["claim_attempt_id"]
    assert current["revision"] == first["revision"] + 1
    assert current["ownership_status"] == "pending"
    assert stored["claim_attempt_id"] == rotated_fields["claim_attempt_id"]
    assert stored["last_error"] is None
    assert cloudflare.created == []
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_unavailable_claim_material_write_cannot_overwrite_disconnect_intent(
    claim_setup, monkeypatch
):
    service, mongo, _, _, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {"$set": {"claim_token_encrypted": "not-a-valid-fernet-token"}},
    )
    collection = mongo.db["storefront_domains"]
    original_update = collection.update_one
    deletion_attempt_id = "disconnect-race-attempt"

    async def disconnect_before_quarantine_write(query, update, *args, **kwargs):
        last_error = update.get("$set", {}).get("last_error") or {}
        if last_error.get("code") == "claim_material_unavailable":
            assert query["revision"] == claim["revision"]
            assert query["claim_attempt_id"] == claim["attempt_id"]
            assert query["authoritative_dns.zone"] == ZONE
            assert query["deletion_status"] is None
            mongo.raw.storefront_domains.update_one(
                {"planner_id": OWNER_ID},
                {
                    "$set": {
                        "status": "deleting",
                        "application_status": "disconnecting",
                        "action": "processing",
                        "custom_route_enabled": False,
                        "deletion_status": "provider_delete_pending",
                        "deletion_attempt_id": deletion_attempt_id,
                        "provider_delete_operation_id": "delete-operation-race",
                        "last_error": None,
                    },
                    "$inc": {"revision": 1},
                },
            )
        return await original_update(query, update, *args, **kwargs)

    monkeypatch.setattr(collection, "update_one", disconnect_before_quarantine_write)

    current = await service.verify(_owner())

    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert current["application_status"] == "disconnecting"
    assert current["deletion_status"] == "provider_delete_pending"
    assert current["revision"] == claim["revision"] + 1
    assert stored["deletion_attempt_id"] == deletion_attempt_id
    assert stored["last_error"] is None
    assert "provider_create_attempt_id" not in stored
    assert cloudflare.created == []
    assert cloudflare.listed == []


@pytest.mark.asyncio
async def test_exact_current_txt_proof_creates_provider_once_and_is_idempotent(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)

    first = await service.verify(_owner())
    second = await service.verify(_owner())

    assert first["ownership_status"] == "verified"
    assert first["application_status"] == "hostname_validation"
    assert first["provider_hostname_status"] == "pending"
    assert first["ssl_status"] == "pending_validation"
    assert first["routing_dns_status"] == "verified"
    assert first["https_status"] == "pending"
    expected_txt = _record(first, "TXT")["value"]
    response_txt = next(
        item for item in first["observed_records"] if item["type"] == "TXT"
    )
    assert expected_txt in response_txt["values"]
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    stored_txt = next(
        item for item in stored["observed_records"] if item["type"] == "TXT"
    )
    assert expected_txt not in stored_txt["values"]
    assert stored["last_checked_at"]
    assert {record["purpose"] for record in first["expected_records"]} >= {
        "application_ownership",
        "storefront_routing",
        "provider_hostname_validation",
        "certificate_validation",
    }
    assert second["provider_hostname_id"] == "cf-hostname-1"
    assert cloudflare.created == [HOSTNAME]
    assert cloudflare.listed == [HOSTNAME]
    operation = mongo.raw.storefront_domain_operations.find_one(
        {"planner_id": OWNER_ID, "kind": "provider_create"}
    )
    assert operation["provider_ids_before"] == []
    assert operation["provider_request_started_at"]
    assert _aware(operation["provider_request_window_ends_at"]) - _aware(
        operation["provider_request_started_at"]
    ) == timedelta(minutes=2)
    assert operation["provider_hostname_id"] == "cf-hostname-1"
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert _aware(stored["retry_due_at"]) <= datetime.now(timezone.utc)
    authoritative_nameservers = tuple(stored["authoritative_dns"]["nameservers"])
    assert (
        f"_tsw-storefront.{HOSTNAME}",
        "TXT",
        authoritative_nameservers,
    ) in dns.authoritative_queries


@pytest.mark.asyncio
async def test_delegation_change_expires_claim_before_stale_nameserver_proof(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)
    original_attempt = claim["attempt_id"]
    original_txt = _record(claim, "TXT")["value"]
    dns.authoritative_queries.clear()
    dns.set(
        ZONE,
        "NS",
        "ns1.redelegated.example.net",
        "ns2.redelegated.example.net",
    )

    expired = await service.verify(_owner())

    assert expired["application_status"] == "expired"
    assert expired["ownership_status"] == "expired"
    assert expired["action"] == "action_required"
    assert expired["last_error"]["code"] == "authoritative_dns_delegation_changed"
    assert expired["expected_records"] == []
    assert dns.authoritative_queries == []
    assert cloudflare.listed == []
    assert cloudflare.created == []

    rotated = await service.claim(_owner(), HOSTNAME, intent="new")

    assert rotated["attempt_id"] != original_attempt
    assert _record(rotated, "TXT")["value"] != original_txt
    assert rotated["authoritative_dns"]["nameservers"] == [
        "ns1.redelegated.example.net",
        "ns2.redelegated.example.net",
    ]


@pytest.mark.asyncio
async def test_delegation_expiry_cas_cannot_overwrite_refreshed_snapshot(claim_setup):
    service, mongo, _, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)
    dns.authoritative_queries.clear()
    new_nameservers = [
        "ns1.redelegated.example.net",
        "ns2.redelegated.example.net",
    ]
    dns.set(ZONE, "NS", *new_nameservers)

    def refresh_snapshot(_query):
        mongo.raw.storefront_domains.update_one(
            {"planner_id": OWNER_ID},
            {
                "$set": {
                    "authoritative_dns.nameservers": new_nameservers,
                    "last_error": {"code": "newer_claim_state"},
                }
            },
        )

    dns.on_query = refresh_snapshot

    observed = await service.verify(_owner())

    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert observed["application_status"] == "dns_setup_pending"
    assert stored["authoritative_dns"]["nameservers"] == new_nameservers
    assert stored["last_error"] == {"code": "newer_claim_state"}
    assert stored["ownership_status"] == "pending"
    assert dns.authoritative_queries == []
    assert cloudflare.listed == []
    assert cloudflare.created == []


@pytest.mark.asyncio
async def test_delegation_change_during_dns_proof_expires_before_provider_io(
    claim_setup,
):
    service, _, _, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)

    def redelegate_after_first_proof(_query):
        dns.set(
            ZONE,
            "NS",
            "ns1.redelegated.example.net",
            "ns2.redelegated.example.net",
        )

    dns.on_authoritative_query = redelegate_after_first_proof

    expired = await service.verify(_owner())

    assert expired["application_status"] == "expired"
    assert expired["ownership_status"] == "expired"
    assert expired["last_error"]["code"] == "authoritative_dns_delegation_changed"
    assert cloudflare.listed == []
    assert cloudflare.created == []


@pytest.mark.asyncio
async def test_migration_prevalidates_txt_before_exposing_cutover_cname(claim_setup):
    service, _, _, dns, cloudflare = claim_setup
    cloudflare.create_result["status"] = "active"
    cloudflare.create_result["ssl"]["status"] = "active"

    claim = await service.claim(_owner(), HOSTNAME, intent="migration")

    assert claim["application_status"] == "migration_prevalidation"
    assert {record["type"] for record in claim["expected_records"]} == {"TXT"}
    txt = _record(claim, "TXT")
    dns.set(txt["name"], "TXT", txt["value"])

    verified = await service.verify(_owner())

    assert verified["application_status"] == "cutover_ready"
    assert verified["ownership_status"] == "verified"
    assert verified["routing_dns_status"] == "pending"
    assert {record["type"] for record in verified["expected_records"]} == {
        "TXT",
        "CNAME",
    }
    assert cloudflare.created == [HOSTNAME]


@pytest.mark.asyncio
async def test_provider_mutation_readiness_blocks_verified_claim_before_cloudflare_io(
    claim_setup,
):
    service, mongo, _, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)
    service._readiness = lambda: {
        "enabled": True,
        "ready": False,
        "reason_code": "provider_mutations_disabled",
        "missing": [],
    }

    with pytest.raises(HTTPException) as blocked:
        await service.verify(_owner())

    assert blocked.value.status_code == 503
    assert blocked.value.detail["code"] == "custom_domain_provider_unavailable"
    assert cloudflare.listed == []
    assert cloudflare.created == []
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["ownership_status"] == "verified"
    assert stored["routing_dns_status"] == "verified"
    assert stored["application_status"] == "provider_provisioning"
    assert stored["last_error"]["code"] == "custom_domain_provider_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application_status", "deletion_status"),
    [
        ("disconnecting", "provider_delete_pending"),
        ("disconnect_failed", "retry_pending"),
        ("disconnected", "local_cleanup_pending"),
    ],
)
async def test_dns_verification_rejects_every_deletion_intent_stage(
    claim_setup,
    application_status,
    deletion_status,
):
    service, mongo, _, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    dns_queries_before = list(dns.authoritative_queries)
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "application_status": application_status,
                "status": "deleting",
                "deletion_status": deletion_status,
            }
        },
    )

    with pytest.raises(HTTPException) as blocked:
        await service.verify(_owner(), claim["attempt_id"])

    assert blocked.value.status_code == 409
    assert blocked.value.detail["code"] == "domain_deletion_in_progress"
    assert dns.authoritative_queries == dns_queries_before
    assert cloudflare.listed == []
    assert cloudflare.created == []
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["application_status"] == application_status
    assert stored["deletion_status"] == deletion_status


@pytest.mark.asyncio
async def test_dns_verification_provider_reservation_loses_to_disconnect(
    claim_setup,
    monkeypatch,
):
    service, mongo, _, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)

    async def disconnect_during_provider_snapshot(hostname: str) -> list[dict]:
        cloudflare.listed.append(hostname)
        mongo.raw.storefront_domains.update_one(
            {"planner_id": OWNER_ID},
            {
                "$set": {
                    "application_status": "disconnecting",
                    "status": "deleting",
                    "deletion_status": "provider_delete_pending",
                }
            },
        )
        return []

    monkeypatch.setattr(
        cloudflare,
        "list_custom_hostnames",
        disconnect_during_provider_snapshot,
    )

    result = await service.verify(_owner(), claim["attempt_id"])

    assert result["application_status"] == "disconnecting"
    assert result["deletion_status"] == "provider_delete_pending"
    assert cloudflare.listed == [HOSTNAME]
    assert cloudflare.created == []
    operation = mongo.raw.storefront_domain_operations.find_one(
        {"kind": "provider_create"}
    )
    assert operation["state"] == "cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application_status", "deletion_status"),
    [
        ("disconnecting", "provider_delete_pending"),
        ("disconnect_failed", "retry_pending"),
        ("disconnected", "local_cleanup_pending"),
    ],
)
async def test_instruction_send_rejects_every_deletion_intent_stage(
    claim_setup,
    application_status,
    deletion_status,
):
    service, mongo, _, _, _ = claim_setup
    email = FakeInstructionEmail()
    service._instruction_email_service = email
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "application_status": application_status,
                "status": "deleting",
                "deletion_status": deletion_status,
            }
        },
    )

    with pytest.raises(HTTPException) as blocked:
        await service.send_instructions(
            _owner(),
            claim["attempt_id"],
            email="dns-admin@example.com",
        )

    assert blocked.value.status_code == 409
    assert blocked.value.detail["code"] == "domain_deletion_in_progress"
    assert email.calls == []
    assert mongo.raw.storefront_domain_instruction_links.count_documents({}) == 0
    assert mongo.raw.storefront_domain_operations.count_documents({}) == 0
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["application_status"] == application_status
    assert stored["deletion_status"] == deletion_status


@pytest.mark.asyncio
async def test_instruction_send_cas_loses_to_concurrent_disconnect(
    claim_setup,
    monkeypatch,
):
    service, mongo, _, _, _ = claim_setup
    email = FakeInstructionEmail()
    service._instruction_email_service = email
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    domains = mongo.db["storefront_domains"]
    original_update = domains.update_one

    async def disconnect_before_instruction_reservation(query, update, *args, **kwargs):
        if "instruction_delivery_requested_at" in update.get("$set", {}):
            mongo.raw.storefront_domains.update_one(
                {"planner_id": OWNER_ID},
                {
                    "$set": {
                        "application_status": "disconnecting",
                        "status": "deleting",
                        "deletion_status": "provider_delete_pending",
                    }
                },
            )
        return await original_update(query, update, *args, **kwargs)

    monkeypatch.setattr(
        domains,
        "update_one",
        disconnect_before_instruction_reservation,
    )

    with pytest.raises(HTTPException) as changed:
        await service.send_instructions(
            _owner(),
            claim["attempt_id"],
            email="dns-admin@example.com",
        )

    assert changed.value.status_code == 409
    assert changed.value.detail["code"] == "domain_instructions_changed"
    assert email.calls == []
    assert mongo.raw.storefront_domain_instruction_links.count_documents({}) == 0
    assert mongo.raw.storefront_domain_operations.count_documents({}) == 0
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["application_status"] == "disconnecting"
    assert stored["deletion_status"] == "provider_delete_pending"


@pytest.mark.asyncio
async def test_dns_instructions_are_owner_scoped_exact_escaped_and_receipted(
    claim_setup,
):
    service, mongo, _, dns, _ = claim_setup
    email = FakeInstructionEmail()
    service._instruction_email_service = email
    claim = await service.claim(_owner(), HOSTNAME, intent="new")

    result = await service.send_instructions(
        _owner(),
        claim["attempt_id"],
        email="dns-admin@example.com",
        note="Use <production> change control.",
    )

    assert result["status"] == "sent"
    assert result["link_id"]
    assert result["state"] == "active"
    assert result["recipient_hint"] == "d***@e***.com"
    assert _aware(result["expires_at"]) > datetime.now(timezone.utc) + timedelta(
        days=6, hours=23
    )
    assert len(email.calls) == 1
    html = email.calls[0]["html_content"]
    for record in claim["expected_records"]:
        assert record["value"] not in html
    assert "&lt;production&gt;" in html
    assert "View secure read-only DNS instructions" in html
    link_url = next(
        part.split('"', 1)[0]
        for part in html.split('href="')[1:]
        if "/domain-instructions/" in part
    )
    public_token = urlsplit(link_url).path.rsplit("/", 1)[-1]
    stored_link = mongo.raw.storefront_domain_instruction_links.find_one(
        {"link_id": result["link_id"]}
    )
    assert (
        stored_link["token_digest"] == hashlib.sha256(public_token.encode()).hexdigest()
    )
    assert public_token not in repr(stored_link)
    assert stored_link["token_ciphertext"] != public_token
    assert stored_link["state"] == "active"
    assert stored_link["delivery_state"] == "completed"
    assert stored_link["recipient_hint"] == "d***@e***.com"
    assert stored_link["recipient_hash"]
    assert "dns-admin@example.com" not in repr(stored_link)
    assert "records" not in stored_link
    assert _record(claim, "TXT")["value"] not in repr(stored_link)

    public = await service.read_instruction_link(public_token)
    assert public["hostname"] == HOSTNAME
    assert [
        {
            key: value
            for key, value in record.items()
            if key not in {"relative_host", "proxy"}
        }
        for record in public["records"]
    ] == claim["expected_records"]
    assert public["provider"] == {
        "name": "Google Cloud DNS or Squarespace DNS",
        "zone": ZONE,
        "control_panel_url": None,
    }
    public_txt = next(record for record in public["records"] if record["type"] == "TXT")
    public_cname = next(
        record for record in public["records"] if record["type"] == "CNAME"
    )
    assert public_txt["relative_host"] == (
        f"_tsw-storefront.{HOSTNAME.removesuffix('.' + ZONE)}"
    )
    assert public_cname["relative_host"] == "events"
    assert public["note"] == "Use <production> change control."
    assert "planner_id" not in public
    assert "domain_id" not in public

    _set_current_dns(dns, claim)
    verified = await service.verify(_owner())
    refreshed_public = await service.read_instruction_link(public_token)
    assert refreshed_public["records"] == [
        {
            **record,
            "relative_host": (
                "@"
                if record["name"] == ZONE
                else (
                    record["name"][: -(len(ZONE) + 1)]
                    if record["name"].endswith(f".{ZONE}")
                    else None
                )
            ),
            "proxy": None,
        }
        for record in verified["expected_records"]
    ]
    receipt = mongo.raw.storefront_domain_operations.find_one(
        {"kind": "instruction_email"}
    )
    assert receipt["state"] == "completed"
    assert receipt["provider_message_id"] == "email-1"
    assert receipt["recipient_hash"]
    assert "dns-admin@example.com" not in repr(receipt)

    listed = await service.list_instruction_links(_owner(), claim["attempt_id"])
    assert listed == {
        "links": [
            {
                "link_id": result["link_id"],
                "state": "active",
                "created_at": stored_link["created_at"].replace(
                    tzinfo=stored_link["created_at"].tzinfo or timezone.utc
                ),
                "expires_at": stored_link["expires_at"].replace(
                    tzinfo=stored_link["expires_at"].tzinfo or timezone.utc
                ),
                "recipient_hint": "d***@e***.com",
            }
        ]
    }

    replay = await service.send_instructions(
        _owner(),
        claim["attempt_id"],
        email="dns-admin@example.com",
    )
    assert replay["status"] == "sent"
    assert replay["link_id"] == result["link_id"]
    assert len(email.calls) == 1

    with pytest.raises(HTTPException) as cross_owner:
        await service.send_instructions(
            _owner(SECOND_OWNER_ID),
            claim["attempt_id"],
            email="dns-admin@example.com",
        )
    assert cross_owner.value.status_code == 404

    entitlements = claim_setup[2]
    entitlements.enabled_by_owner[OWNER_ID] = False
    retained = await service.list_instruction_links(_owner(), claim["attempt_id"])
    assert retained["links"][0]["link_id"] == result["link_id"]
    with pytest.raises(HTTPException) as cross_owner_list:
        await service.list_instruction_links(
            _owner(SECOND_OWNER_ID), claim["attempt_id"]
        )
    assert cross_owner_list.value.status_code == 404
    with pytest.raises(HTTPException) as cross_owner_revoke:
        await service.revoke_instruction_link(
            _owner(SECOND_OWNER_ID), result["link_id"]
        )
    assert cross_owner_revoke.value.status_code == 404

    revoked = await service.revoke_instruction_link(_owner(), result["link_id"])
    assert revoked == {"status": "revoked"}
    revoked_link = mongo.raw.storefront_domain_instruction_links.find_one(
        {"link_id": result["link_id"]}
    )
    assert "token_digest" not in revoked_link
    assert "token_ciphertext" not in revoked_link
    assert await service.list_instruction_links(_owner(), claim["attempt_id"]) == {
        "links": []
    }
    with pytest.raises(HTTPException) as unavailable:
        await service.read_instruction_link(public_token)
    assert unavailable.value.status_code == 404


@pytest.mark.asyncio
async def test_instruction_links_fail_closed_after_disconnect_intent_and_cleanup_failure(
    claim_setup,
    monkeypatch,
):
    service, mongo, _, dns, cloudflare = claim_setup
    email = FakeInstructionEmail()
    service._instruction_email_service = email
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    receipt = await service.send_instructions(
        _owner(), claim["attempt_id"], email="dns-admin@example.com"
    )
    sent_html = email.calls[0]["html_content"]
    link_url = next(
        part.split('"', 1)[0]
        for part in sent_html.split('href="')[1:]
        if "/domain-instructions/" in part
    )
    public_token = urlsplit(link_url).path.rsplit("/", 1)[-1]
    assert (await service.list_instruction_links(_owner(), claim["attempt_id"]))[
        "links"
    ][0]["link_id"] == receipt["link_id"]

    _set_current_dns(dns, claim)
    await service.verify(_owner())

    async def fail_provider_delete(hostname_id: str) -> dict:
        cloudflare.deleted.append(hostname_id)
        raise CloudflareServiceError(
            "provider cleanup is unavailable",
            operation="delete_custom_hostname",
            kind="transport",
            provider_status_code=503,
        )

    monkeypatch.setattr(cloudflare, "delete_custom_hostname", fail_provider_delete)
    with pytest.raises(HTTPException) as disconnect_failed:
        await service.disconnect(_owner())

    assert disconnect_failed.value.status_code == 502
    current = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert current["application_status"] == "disconnect_failed"
    assert current["deletion_status"] == "retry_pending"
    assert await service.list_instruction_links(_owner(), claim["attempt_id"]) == {
        "links": []
    }
    with pytest.raises(HTTPException) as public_unavailable:
        await service.read_instruction_link(public_token)
    assert public_unavailable.value.status_code == 404


@pytest.mark.asyncio
async def test_instruction_delivery_failure_reuses_encrypted_token_and_idempotency_key(
    claim_setup,
):
    service, mongo, _, _, _ = claim_setup
    email = FailingInstructionEmail()
    service._instruction_email_service = email
    claim = await service.claim(_owner(), HOSTNAME, intent="new")

    for _ in range(3):
        with pytest.raises(HTTPException) as delivery_failed:
            await service.send_instructions(
                _owner(), claim["attempt_id"], email="dns-admin@example.com"
            )
        assert delivery_failed.value.status_code == 503
        assert (
            delivery_failed.value.detail["code"]
            == "domain_instructions_delivery_failed"
        )

    stored_links = list(mongo.raw.storefront_domain_instruction_links.find({}))
    assert len(stored_links) == 1
    assert stored_links[0]["state"] == "active"
    assert stored_links[0]["delivery_state"] == "failed"
    listed = await service.list_instruction_links(_owner(), claim["attempt_id"])
    assert listed["links"][0]["state"] == "delivery_failed"
    assert len({call["idempotency_key"] for call in email.calls}) == 1
    assert (
        len(
            {
                part.split('"', 1)[0]
                for call in email.calls
                for part in call["html_content"].split('href="')[1:]
                if "/domain-instructions/" in part
            }
        )
        == 1
    )
    operation = mongo.raw.storefront_domain_operations.find_one(
        {"kind": "instruction_email"}
    )
    assert operation["delivery_attempts"] == 3

    with pytest.raises(HTTPException) as rate_limited:
        await service.send_instructions(
            _owner(), claim["attempt_id"], email="dns-admin@example.com"
        )
    assert rate_limited.value.status_code == 429
    assert rate_limited.value.detail["code"] == "domain_instruction_send_rate_limited"
    assert len(email.calls) == 3


@pytest.mark.asyncio
async def test_instruction_link_configuration_fails_before_persisting_delivery_state(
    claim_setup,
):
    service, mongo, _, _, _ = claim_setup
    email = FakeInstructionEmail()
    service._instruction_email_service = email
    service._instruction_public_base_url = "http://unsafe.example.com"
    claim = await service.claim(_owner(), HOSTNAME, intent="new")

    with pytest.raises(HTTPException) as unavailable:
        await service.send_instructions(
            _owner(), claim["attempt_id"], email="dns-admin@example.com"
        )

    assert unavailable.value.status_code == 503
    assert unavailable.value.detail["code"] == "domain_instruction_link_unavailable"
    assert email.calls == []
    assert mongo.raw.storefront_domain_instruction_links.count_documents({}) == 0
    assert mongo.raw.storefront_domain_instruction_quotas.count_documents({}) == 0


@pytest.mark.asyncio
async def test_concurrent_instruction_sends_share_one_link_and_one_provider_send(
    claim_setup,
):
    service, mongo, _, _, _ = claim_setup
    email = BlockingInstructionEmail()
    service._instruction_email_service = email
    claim = await service.claim(_owner(), HOSTNAME, intent="new")

    first_send = asyncio.create_task(
        service.send_instructions(
            _owner(), claim["attempt_id"], email="dns-admin@example.com"
        )
    )
    await email.started.wait()
    with pytest.raises(HTTPException) as concurrent_send:
        await service.send_instructions(
            _owner(), claim["attempt_id"], email="dns-admin@example.com"
        )
    assert concurrent_send.value.status_code == 409
    assert (
        concurrent_send.value.detail["code"]
        == "domain_instructions_delivery_in_progress"
    )

    email.release.set()
    receipt = await first_send
    assert receipt["status"] == "sent"
    assert len(email.calls) == 1
    assert mongo.raw.storefront_domain_instruction_links.count_documents({}) == 1
    assert (
        mongo.raw.storefront_domain_operations.count_documents(
            {"kind": "instruction_email"}
        )
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_limit", "attempt_limit", "recipient_limit", "emails"),
    [
        (2, 10, 10, ["one@example.com", "two@example.com", "three@example.com"]),
        (10, 2, 10, ["one@example.com", "two@example.com", "three@example.com"]),
        (10, 10, 2, ["same@example.com", "same@example.com", "same@example.com"]),
    ],
)
async def test_instruction_send_quotas_are_bounded_by_owner_attempt_and_recipient(
    claim_setup,
    monkeypatch,
    owner_limit,
    attempt_limit,
    recipient_limit,
    emails,
):
    service, _, _, _, _ = claim_setup
    email = FailingInstructionEmail()
    service._instruction_email_service = email
    monkeypatch.setattr(
        storefront_domain_service_module,
        "_INSTRUCTION_OWNER_SEND_LIMIT",
        owner_limit,
    )
    monkeypatch.setattr(
        storefront_domain_service_module,
        "_INSTRUCTION_ATTEMPT_SEND_LIMIT",
        attempt_limit,
    )
    monkeypatch.setattr(
        storefront_domain_service_module,
        "_INSTRUCTION_RECIPIENT_SEND_LIMIT",
        recipient_limit,
    )
    claim = await service.claim(_owner(), HOSTNAME, intent="new")

    for recipient in emails[:2]:
        with pytest.raises(HTTPException) as failed:
            await service.send_instructions(
                _owner(), claim["attempt_id"], email=recipient
            )
        assert failed.value.status_code == 503

    with pytest.raises(HTTPException) as limited:
        await service.send_instructions(_owner(), claim["attempt_id"], email=emails[2])
    assert limited.value.status_code == 429
    assert limited.value.detail["code"] == "domain_instruction_send_rate_limited"
    assert len(email.calls) == 2


@pytest.mark.asyncio
async def test_instruction_active_link_limit_is_released_only_by_owner_revocation(
    claim_setup,
    monkeypatch,
):
    service, _, _, _, _ = claim_setup
    email = FakeInstructionEmail()
    service._instruction_email_service = email
    monkeypatch.setattr(
        storefront_domain_service_module,
        "_INSTRUCTION_ACTIVE_LINK_LIMIT",
        1,
    )
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    first = await service.send_instructions(
        _owner(), claim["attempt_id"], email="one@example.com"
    )

    with pytest.raises(HTTPException) as limited:
        await service.send_instructions(
            _owner(), claim["attempt_id"], email="two@example.com"
        )
    assert limited.value.status_code == 429
    assert len(email.calls) == 1

    assert await service.revoke_instruction_link(_owner(), first["link_id"]) == {
        "status": "revoked"
    }
    second = await service.send_instructions(
        _owner(), claim["attempt_id"], email="two@example.com"
    )
    assert second["status"] == "sent"
    assert len(email.calls) == 2


@pytest.mark.asyncio
async def test_retry_and_instruction_creation_recheck_entitlement_before_external_io(
    claim_setup,
):
    service, mongo, entitlements, _, cloudflare = claim_setup
    email = FakeInstructionEmail()
    service._instruction_email_service = email
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    entitlements.enabled_by_owner[OWNER_ID] = False

    with pytest.raises(HTTPException) as instructions_blocked:
        await service.send_instructions(
            _owner(),
            claim["attempt_id"],
            email="dns-admin@example.com",
        )
    assert instructions_blocked.value.status_code == 403
    assert email.calls == []
    assert mongo.raw.storefront_domain_instruction_links.count_documents({}) == 0

    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "provider_hostname_id": "cf-hostname-1",
                "provider_ssl_method": "txt",
                "provider_ssl_type": "dv",
            }
        },
    )
    with pytest.raises(HTTPException) as retry_blocked:
        await service.retry_provider(_owner(), claim["attempt_id"])
    assert retry_blocked.value.status_code == 403
    assert getattr(cloudflare, "retried", []) == []


@pytest.mark.asyncio
async def test_ambiguous_create_never_adopts_preexisting_provider_row(claim_setup):
    service, mongo, _, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)
    preexisting = {
        **deepcopy(cloudflare.create_result),
        "id": "cf-preexisting",
        "hostname": HOSTNAME,
    }
    cloudflare.list_results = [[preexisting], [preexisting]]
    cloudflare.create_error = CloudflareServiceError(
        operation="create_custom_hostname",
        kind="transport",
        message="response lost after an unknown provider outcome",
    )

    result = await service.verify(_owner())

    assert result["application_status"] == "operator_review"
    assert result["action"] == "operator_review"
    assert result["provider_hostname_id"] is None
    assert result["last_error"]["code"] == "ambiguous_provider_create"
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["provider_hostname_id"] is None
    operation = mongo.raw.storefront_domain_operations.find_one(
        {"planner_id": OWNER_ID, "kind": "provider_create"}
    )
    assert operation["provider_outcome_unknown_at"]
    assert _aware(operation["provider_outcome_unknown_at"]) <= _aware(
        operation["provider_request_window_ends_at"]
    )
    assert cloudflare.created == [HOSTNAME]
    assert cloudflare.listed == [HOSTNAME, HOSTNAME]


@pytest.mark.asyncio
async def test_disconnect_cannot_erase_an_inflight_provider_create_receipt(
    claim_setup, monkeypatch
):
    service, mongo, _, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)
    provider_call_started = asyncio.Event()
    release_provider_call = asyncio.Event()
    create_custom_hostname = cloudflare.create_custom_hostname

    async def delayed_create(hostname: str) -> dict:
        provider_call_started.set()
        await release_provider_call.wait()
        return await create_custom_hostname(hostname)

    monkeypatch.setattr(cloudflare, "create_custom_hostname", delayed_create)
    verification = asyncio.create_task(service.verify(_owner()))
    await provider_call_started.wait()

    with pytest.raises(HTTPException) as blocked:
        await service.disconnect(_owner())

    assert blocked.value.status_code == 409
    assert blocked.value.detail["code"] == "provider_operation_in_progress"
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["application_status"] == "provider_provisioning"
    assert stored["provider_create_attempt_id"]

    release_provider_call.set()
    verified = await verification
    assert verified["provider_hostname_id"] == "cf-hostname-1"


@pytest.mark.asyncio
async def test_local_status_and_disconnect_survive_entitlement_loss_with_tombstone(
    claim_setup,
):
    service, mongo, entitlements, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)
    active = await service.verify(_owner())
    provider_calls_before_status = (
        list(cloudflare.created),
        list(cloudflare.listed),
        list(cloudflare.read),
    )
    entitlements.enabled_by_owner[OWNER_ID] = False
    service._readiness = lambda: {
        "enabled": True,
        "ready": False,
        "reason_code": "provider_mutations_disabled",
        "missing": [],
    }
    service._rollout_policy = StorefrontDomainRolloutPolicy.build(mode="allowlist")

    status = await service.get_status(_owner())
    await service.disconnect(_owner())

    assert status["provider_hostname_id"] == active["provider_hostname_id"]
    assert provider_calls_before_status == (
        cloudflare.created,
        cloudflare.listed,
        cloudflare.read,
    )
    assert cloudflare.deleted == ["cf-hostname-1"]
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) is None
    tombstone = mongo.raw.storefront_domain_tombstones.find_one(
        {"planner_id": OWNER_ID}
    )
    assert tombstone["hostname"] == HOSTNAME
    assert tombstone["provider_hostname_id"] == "cf-hostname-1"
    # Provider activation alone is not a customer-visible connection: the
    # lifecycle still lacks the independent HTTPS storefront proof.
    assert tombstone["removal_kind"] == "setup_cancelled"
    assert tombstone["deletion_receipt_id"]
    operation = mongo.raw.storefront_domain_operations.find_one(
        {"operation_id": tombstone["provider_delete_operation_id"]}
    )
    assert operation["kind"] == "provider_delete"
    assert operation["state"] == "completed"
    assert operation["planner_id"] == OWNER_ID
    assert operation["hostname"] == HOSTNAME
    assert operation["provider_hostname_id"] == "cf-hostname-1"
    assert len(operation["request_fingerprint"]) == 64
    assert operation["provider_receipt"]["outcome"] == "deleted"
    assert tombstone["provider_delete_receipt"] == operation["provider_receipt"]
    tombstone_expires_at = _aware(tombstone["expires_at"])
    assert datetime.now(timezone.utc) + timedelta(days=89) < tombstone_expires_at
    assert tombstone_expires_at < datetime.now(timezone.utc) + timedelta(
        days=90, minutes=1
    )
    assert "claim_token" not in repr(tombstone)
    assert tombstone["cleanup_records"] == [
        {
            "type": "TXT",
            "name": f"_tsw-storefront.{HOSTNAME}",
            "value": None,
            "ttl": 300,
            "purpose": "remove_application_ownership",
        },
        {
            "type": "CNAME",
            "name": HOSTNAME,
            "value": CNAME_TARGET,
            "ttl": 300,
            "purpose": "remove_storefront_routing",
        },
    ]
    disconnected = await service.get_status(_owner())
    assert disconnected["application_status"] == "disconnected"
    assert disconnected["removal_kind"] == "setup_cancelled"
    assert disconnected["cleanup_records"] == tombstone["cleanup_records"]
    assert disconnected["expected_records"] == []


@pytest.mark.asyncio
async def test_pending_dns_diagnostics_refresh_after_entitlement_loss_without_activation(
    claim_setup,
):
    service, mongo, entitlements, dns, cloudflare = claim_setup
    claim = await service.claim(_owner(), HOSTNAME, intent="new")
    _set_current_dns(dns, claim)
    entitlements.enabled_by_owner[OWNER_ID] = False

    observed = await service.observe_pending_for_owner_id(OWNER_ID)

    assert observed["ownership_status"] == "verified"
    assert observed["routing_dns_status"] == "verified"
    assert observed["application_status"] == "dns_setup_pending"
    assert observed["provider_hostname_id"] is None
    assert cloudflare.listed == []
    assert cloudflare.created == []
    assert mongo.raw.storefront_domain_operations.count_documents({}) == 0

    with pytest.raises(HTTPException) as activation_blocked:
        await service.verify(_owner())
    assert activation_blocked.value.status_code == 403
    assert cloudflare.listed == []
    assert cloudflare.created == []
