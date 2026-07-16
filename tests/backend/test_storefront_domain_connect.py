from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from urllib.parse import parse_qsl, parse_qs, urlsplit

from bson import ObjectId
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import HTTPException
import mongomock
import pytest

from app.services.storefront_domain_connect_service import (
    DomainConnectDiscovery,
    DomainConnectDiscoveryError,
    StorefrontDomainConnectService,
)
from app.services.storefront_domain_rollout import StorefrontDomainRolloutPolicy
from app.services.storefront_entitlement_service import StorefrontEntitlements
from app.models.storefront import StorefrontDomainResponse


OWNER_ID = "507f1f77bcf86cd799439011"
SECOND_OWNER_ID = "507f1f77bcf86cd799439012"
HOSTNAME = "events.customer.example"
ZONE = "customer.example"
ATTEMPT_ID = "claim-attempt-1"
SYNC_URL = "https://domainconnect.cloudflare.com"
API_URL = "https://api.domainconnect.cloudflare.com"


class AsyncCollection:
    def __init__(self, collection):
        self._collection = collection

    async def find_one(self, *args, **kwargs):
        return self._collection.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._collection.update_one(*args, **kwargs)


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
        self.raw = mongomock.MongoClient()["storefront_domain_connect_test"]
        self.db = AsyncDatabase(self.raw)
        self.raw.storefront_domain_flows.create_index("flow_id", unique=True)
        self.raw.storefront_domain_flows.create_index(
            [("domain_id", 1), ("attempt_id", 1)], unique=True
        )
        self.raw.storefront_domain_flows.create_index("flow_token_digest", unique=True)


class FakeDnsResolver:
    def __init__(self, value: str = "domainconnect.cloudflare.com"):
        self.value = value
        self.queries: list[tuple[str, str]] = []

    async def query(self, name: str, record_type: str) -> list[str]:
        self.queries.append((name, record_type))
        if name == f"_domainconnect.{ZONE}" and record_type == "TXT":
            return [self.value]
        return []


class FakeAddressResolver:
    def __init__(self, answers: dict[str, list[list[str]]] | None = None):
        self.answers = answers or {
            "domainconnect.cloudflare.com": [["1.1.1.1"]],
            "api.domainconnect.cloudflare.com": [["1.0.0.1"]],
        }
        self.calls: list[str] = []

    async def resolve(self, hostname: str) -> list[str]:
        self.calls.append(hostname)
        available = self.answers.get(hostname, [])
        if not available:
            return []
        if len(available) > 1:
            return available.pop(0)
        return list(available[0])


@dataclass
class FakeResponse:
    status_code: int
    payload: object = None
    headers: dict[str, str] | None = None
    raw: bytes | None = None

    @property
    def content(self) -> bytes:
        if self.raw is not None:
            return self.raw
        if self.payload is None:
            return b""
        import json

        return json.dumps(self.payload).encode()

    def json(self):
        return self.payload


class FakeTransport:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def request(self, method: str, url: str, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def _settings_response(
    *,
    provider_id: str = "cloudflare.com",
    sync_url: str = SYNC_URL,
    api_url: str = API_URL,
) -> FakeResponse:
    return FakeResponse(
        200,
        {
            "providerId": provider_id,
            "providerName": "Cloudflare",
            "urlSyncUX": sync_url,
            "urlAPI": api_url,
            "urlControlPanel": "https://dash.cloudflare.com",
        },
    )


def _discovery(
    responses: list[FakeResponse],
    *,
    txt_value: str = "domainconnect.cloudflare.com",
    addresses: dict[str, list[list[str]]] | None = None,
    enabled: bool = True,
):
    dns = FakeDnsResolver(txt_value)
    address_resolver = FakeAddressResolver(addresses)
    transport = FakeTransport(responses)
    service = DomainConnectDiscovery(
        dns_resolver=dns,
        address_resolver=address_resolver,
        http_transport=transport,
        discovery_enabled=enabled,
        provider_id="thespecialwedding.com",
        service_id="storefront-subdomain",
        template_version=1,
        allowed_dns_provider_ids={"cloudflare.com"},
    )
    return service, dns, address_resolver, transport


@pytest.mark.asyncio
async def test_discovery_requires_exact_live_template_version_and_revalidates_dns():
    discovery, dns, addresses, transport = _discovery(
        [_settings_response(), FakeResponse(200, {"version": 1})]
    )

    result = await discovery.discover(ZONE)

    assert result["supported"] is True
    assert result["provider_id"] == "cloudflare.com"
    assert result["provider_name"] == "Cloudflare"
    assert result["template_version"] == 1
    assert dns.queries == [(f"_domainconnect.{ZONE}", "TXT")]
    assert addresses.calls.count("domainconnect.cloudflare.com") == 4
    assert addresses.calls.count("api.domainconnect.cloudflare.com") == 3
    assert addresses.calls[-1] == "dash.cloudflare.com"
    assert transport.calls[1]["url"].endswith(
        "/v2/domainTemplates/providers/thespecialwedding.com/services/storefront-subdomain"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("txt_value", "addresses"),
    [
        ("http://domainconnect.cloudflare.com", None),
        ("https://user@domainconnect.cloudflare.com", None),
        ("https://domainconnect.cloudflare.com:8443", None),
        ("https://domainconnect.cloudflare.com/#fragment", None),
        ("https://127.0.0.1", None),
        ("https://metadata.internal", {"metadata.internal": [["1.1.1.1"]]}),
        (
            "https://domainconnect.cloudflare.com",
            {"domainconnect.cloudflare.com": [["10.0.0.5"]]},
        ),
    ],
)
async def test_discovery_rejects_unsafe_https_destinations(txt_value, addresses):
    discovery, _, _, transport = _discovery(
        [_settings_response()], txt_value=txt_value, addresses=addresses
    )

    with pytest.raises(DomainConnectDiscoveryError) as blocked:
        await discovery.discover(ZONE)

    assert blocked.value.code == "unsafe_domain_connect_destination"
    assert transport.calls == []


@pytest.mark.asyncio
async def test_discovery_revalidates_and_blocks_private_redirect_or_rebinding():
    redirect_discovery, _, _, redirect_transport = _discovery(
        [
            FakeResponse(
                302,
                headers={"location": "https://redirect.internal/settings"},
            )
        ],
        addresses={
            "domainconnect.cloudflare.com": [["1.1.1.1"]],
            "redirect.internal": [["127.0.0.1"]],
        },
    )
    with pytest.raises(DomainConnectDiscoveryError):
        await redirect_discovery.discover(ZONE)
    assert len(redirect_transport.calls) == 1

    rebinding_discovery, _, _, rebinding_transport = _discovery(
        [_settings_response(), FakeResponse(200, {"version": 1})],
        addresses={
            "domainconnect.cloudflare.com": [
                ["1.1.1.1"],
                ["10.0.0.7"],
            ],
            "api.domainconnect.cloudflare.com": [["1.0.0.1"]],
        },
    )
    with pytest.raises(DomainConnectDiscoveryError):
        await rebinding_discovery.discover(ZONE)
    assert rebinding_transport.calls == []


@pytest.mark.asyncio
async def test_discovery_rejects_public_non_cloudflare_origins_and_redirects():
    arbitrary_origin, _, _, arbitrary_transport = _discovery(
        [_settings_response()],
        txt_value="https://dns-consent.attacker.example",
        addresses={"dns-consent.attacker.example": [["8.8.8.8"]]},
    )
    result = await arbitrary_origin.discover(ZONE)
    assert result == {"supported": False, "reason_code": "provider_not_allowed"}
    assert arbitrary_transport.calls == []

    public_redirect, _, _, redirect_transport = _discovery(
        [
            FakeResponse(
                302,
                headers={"location": "https://consent.attacker.example/settings"},
            )
        ],
        addresses={
            "domainconnect.cloudflare.com": [["1.1.1.1"]],
            "api.domainconnect.cloudflare.com": [["1.0.0.1"]],
            "consent.attacker.example": [["8.8.4.4"]],
        },
    )
    with pytest.raises(DomainConnectDiscoveryError) as blocked_redirect:
        await public_redirect.discover(ZONE)
    assert blocked_redirect.value.code == "domain_connect_provider_not_allowed"
    assert len(redirect_transport.calls) == 1

    unsafe_sync, _, _, _ = _discovery(
        [
            _settings_response(sync_url="https://consent.attacker.example"),
        ],
        addresses={
            "domainconnect.cloudflare.com": [["1.1.1.1"]],
            "api.domainconnect.cloudflare.com": [["1.0.0.1"]],
            "consent.attacker.example": [["8.8.4.4"]],
        },
    )
    assert (await unsafe_sync.discover(ZONE)) == {
        "supported": False,
        "reason_code": "provider_not_allowed",
    }


@pytest.mark.asyncio
async def test_discovery_rejects_oversized_responses_wrong_provider_and_version_drift():
    oversized, _, _, _ = _discovery([FakeResponse(200, raw=b"x" * 65_537)])
    with pytest.raises(DomainConnectDiscoveryError) as too_large:
        await oversized.discover(ZONE)
    assert too_large.value.code == "domain_connect_response_too_large"

    wrong_provider, _, _, _ = _discovery(
        [_settings_response(provider_id="attacker.example")]
    )
    assert (await wrong_provider.discover(ZONE))["supported"] is False

    wrong_version, _, _, _ = _discovery(
        [_settings_response(), FakeResponse(200, {"version": 2})]
    )
    assert (await wrong_version.discover(ZONE))["supported"] is False


@pytest.mark.asyncio
async def test_discovery_flag_fails_closed_without_dns_or_network_calls():
    discovery, dns, addresses, transport = _discovery([], enabled=False)

    result = await discovery.discover(ZONE)

    assert result == {"supported": False, "reason_code": "discovery_disabled"}
    assert dns.queries == []
    assert addresses.calls == []
    assert transport.calls == []


class FakeEntitlements:
    def __init__(self):
        self.enabled = {OWNER_ID: True, SECOND_OWNER_ID: True}

    async def resolve_for_owner(self, user_data: dict) -> StorefrontEntitlements:
        owner_id = str(user_data.get("_id") or "")
        enabled = self.enabled.get(owner_id, False)
        return StorefrontEntitlements(
            owner_id=owner_id,
            plan_id="plan_signature" if enabled else "plan_boutique",
            storefront_enabled=enabled,
            custom_domain_enabled=enabled,
        )


class SupportedDiscovery:
    def __init__(self):
        self.calls: list[str] = []

    async def discover(self, zone: str) -> dict:
        self.calls.append(zone)
        return {
            "supported": True,
            "provider_id": "cloudflare.com",
            "provider_name": "Cloudflare",
            "url_sync_ux": SYNC_URL,
            "url_api": API_URL,
            "template_version": 1,
        }


def _owner(owner_id: str = OWNER_ID) -> dict:
    return {"_id": ObjectId(owner_id), "role": "wedding_planner"}


def _private_key() -> tuple[str, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return pem, key


@pytest.fixture
def flow_setup():
    mongo = FakeMongo()
    entitlements = FakeEntitlements()
    discovery = SupportedDiscovery()
    private_pem, private_key = _private_key()
    now = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
    domain_id = ObjectId()
    mongo.raw.storefront_domains.insert_one(
        {
            "_id": domain_id,
            "planner_id": OWNER_ID,
            "hostname": HOSTNAME,
            "claim_attempt_id": ATTEMPT_ID,
            "claim_expires_at": now + timedelta(days=7),
            "revision": 4,
            "authoritative_dns": {"zone": ZONE},
            "application_status": "dns_setup_pending",
            "setup_method": "automatic",
            "domain_connect_authorized_at": None,
            "ownership_status": "pending",
            "routing_dns_status": "pending",
            "provider_hostname_status": "not_created",
            "provider_status": "not_created",
            "ssl_status": "not_started",
            "https_status": "pending",
            "action": "action_required",
            "status": "pending",
            "deletion_status": None,
            "updated_at": now,
        }
    )
    service = StorefrontDomainConnectService(
        mongo_client=mongo,
        entitlement_service=entitlements,
        discovery_service=discovery,
        private_key_pem=private_pem,
        provider_id="thespecialwedding.com",
        service_id="storefront-subdomain",
        template_version=1,
        key_id="_dcpubkeyv1",
        callback_url=(
            "https://api.thespecialwedding.com/admin/storefront/custom-domain/"
            "domain-connect/callback"
        ),
        cname_target="domains.thespecialwedding.com",
        authorization_enabled=True,
        readiness_resolver=lambda: {
            "enabled": True,
            "ready": True,
            "reason_code": "ready",
            "missing": [],
        },
        claim_token_reader=lambda _record: (
            base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")
        ),
        now=lambda: now,
        rollout_policy=StorefrontDomainRolloutPolicy.build(mode="general"),
    )
    return service, mongo, entitlements, discovery, private_key, now


def _flow_token(authorization_url: str) -> str:
    redirect_uri = parse_qs(urlsplit(authorization_url).query)["redirect_uri"][0]
    return parse_qs(urlsplit(redirect_uri).query)["flow"][0]


@pytest.mark.asyncio
async def test_automatic_authorization_is_hidden_behind_exact_rollout_gate(flow_setup):
    service, mongo, _, discovery, _, _ = flow_setup
    service._rollout_policy = StorefrontDomainRolloutPolicy.build(mode="allowlist")

    with pytest.raises(HTTPException) as blocked:
        await service.start(_owner(), ATTEMPT_ID)

    assert blocked.value.status_code == 403
    assert blocked.value.detail["code"] == "domain_connect_rollout_unavailable"
    assert discovery.calls == []
    assert mongo.raw.storefront_domain_flows.count_documents({}) == 0
    record = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert record["application_status"] == "dns_setup_pending"
    assert record["revision"] == 4


@pytest.mark.asyncio
async def test_automatic_authorization_requires_an_explicit_automatic_claim(flow_setup):
    service, mongo, _, discovery, _, _ = flow_setup
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {"$set": {"setup_method": "manual"}},
    )

    with pytest.raises(HTTPException) as blocked:
        await service.start(_owner(), ATTEMPT_ID)

    assert blocked.value.status_code == 409
    assert blocked.value.detail["code"] == "automatic_setup_not_selected"
    assert discovery.calls == []
    assert mongo.raw.storefront_domain_flows.count_documents({}) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application_status", "deletion_status"),
    [
        ("disconnecting", "provider_delete_pending"),
        ("disconnect_failed", "retry_pending"),
        ("disconnected", "local_cleanup_pending"),
    ],
)
async def test_automatic_authorization_rejects_every_deletion_intent_stage(
    flow_setup,
    application_status,
    deletion_status,
):
    service, mongo, _, discovery, _, _ = flow_setup
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "application_status": application_status,
                "deletion_status": deletion_status,
                "status": "deleting",
            }
        },
    )

    with pytest.raises(HTTPException) as blocked:
        await service.start(_owner(), ATTEMPT_ID)

    assert blocked.value.status_code == 409
    assert blocked.value.detail["code"] == "domain_deletion_in_progress"
    assert discovery.calls == []
    assert mongo.raw.storefront_domain_flows.count_documents({}) == 0
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["application_status"] == application_status
    assert stored["deletion_status"] == deletion_status


@pytest.mark.asyncio
async def test_authorization_url_is_rs256_canonical_and_persists_only_flow_digest(
    flow_setup,
):
    service, mongo, _, discovery, private_key, _ = flow_setup

    result = await service.start(_owner(), ATTEMPT_ID)

    authorization_url = result["authorization_url"]
    split = urlsplit(authorization_url)
    pairs = parse_qsl(split.query, keep_blank_values=True)
    assert pairs[-1][0] == "sig"
    params = dict(pairs)
    assert params["domain"] == ZONE
    assert params["host"] == "events"
    assert params["verificationToken"]
    assert params["key"] == "_dcpubkeyv1"
    assert result["attempt_id"] == ATTEMPT_ID
    assert discovery.calls == [ZONE]

    raw_without_key_and_signature = split.query.rsplit("&key=", 1)[0]
    private_key.public_key().verify(
        base64.b64decode(params["sig"]),
        raw_without_key_and_signature.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    token = _flow_token(authorization_url)
    flow = mongo.raw.storefront_domain_flows.find_one(
        {"planner_id": OWNER_ID, "attempt_id": ATTEMPT_ID}
    )
    assert flow["flow_token_digest"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in repr(flow)
    assert "authorization_url" not in flow
    assert mongo.raw.storefront_domain_operations.count_documents({}) == 0
    domain = mongo.raw.storefront_domains.find_one(
        {"planner_id": OWNER_ID, "claim_attempt_id": ATTEMPT_ID}
    )
    assert domain["application_status"] == "authorization_pending"
    assert domain["retry_due_at"].replace(tzinfo=timezone.utc) == flow[
        "expires_at"
    ].replace(tzinfo=timezone.utc)
    decoded = base64.urlsafe_b64decode(
        params["verificationToken"] + "=" * (-len(params["verificationToken"]) % 4)
    )
    assert len(decoded) == 32


@pytest.mark.asyncio
async def test_callback_never_proves_dns_and_completion_is_owner_scoped_one_time(
    flow_setup,
):
    service, mongo, _, _, _, now = flow_setup
    started = await service.start(_owner(), ATTEMPT_ID)
    token = _flow_token(started["authorization_url"])
    before_callback = deepcopy(
        mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    )

    callback = await service.record_callback(token)

    assert callback == {"attempt_id": ATTEMPT_ID, "state": "authorized"}
    before_completion = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert before_completion == before_callback
    assert before_completion["ownership_status"] == "pending"
    assert before_completion["application_status"] == "authorization_pending"
    flow = mongo.raw.storefront_domain_flows.find_one(
        {"planner_id": OWNER_ID, "attempt_id": ATTEMPT_ID}
    )
    assert before_completion["retry_due_at"].replace(tzinfo=timezone.utc) == flow[
        "expires_at"
    ].replace(tzinfo=timezone.utc)

    replay = await service.record_callback(
        token,
        error="access_denied",
        error_description="user_cancel: replay after authorization",
    )
    assert replay["state"] == "authorized"
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) == (
        before_callback
    )

    with pytest.raises(HTTPException) as cross_tenant:
        await service.complete(_owner(SECOND_OWNER_ID), ATTEMPT_ID)
    assert cross_tenant.value.status_code == 404

    completed = await service.complete(_owner(), ATTEMPT_ID)
    assert completed["application_status"] == "dns_setup_pending"
    assert completed["ownership_status"] == "pending"
    assert completed["setup_method"] == "automatic"
    assert completed["domain_connect_authorized"] is True
    stored = mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    assert stored["domain_connect_authorized_at"].replace(tzinfo=timezone.utc) == now
    assert stored["retry_due_at"].replace(tzinfo=timezone.utc) == now
    assert "planner_id" not in completed
    assert "claim_token_digest" not in completed
    StorefrontDomainResponse.model_validate(completed)

    with pytest.raises(HTTPException) as replay:
        await service.complete(_owner(), ATTEMPT_ID)
    assert replay.value.status_code == 409
    assert replay.value.detail["code"] == "domain_connect_flow_consumed"

    with pytest.raises(HTTPException) as restart:
        await service.start(_owner(), ATTEMPT_ID)
    assert restart.value.status_code == 409
    assert restart.value.detail["code"] == "domain_connect_already_authorized"


@pytest.mark.asyncio
async def test_cancellation_and_expiry_are_durable_and_never_schedule_verification(
    flow_setup,
):
    service, mongo, _, _, _, now = flow_setup
    started = await service.start(_owner(), ATTEMPT_ID)
    token = _flow_token(started["authorization_url"])
    before_callback = deepcopy(
        mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID})
    )

    callback = await service.record_callback(
        token,
        error="access_denied",
        error_description="user_cancel: no changes",
    )
    assert mongo.raw.storefront_domains.find_one({"planner_id": OWNER_ID}) == (
        before_callback
    )
    cancelled = await service.complete(_owner(), ATTEMPT_ID)

    assert callback["state"] == "cancelled"
    assert cancelled["application_status"] == "authorization_cancelled"
    assert cancelled["ownership_status"] == "pending"
    assert cancelled.get("retry_due_at") is None

    restarted = await service.start(_owner(), ATTEMPT_ID)
    expired_token = _flow_token(restarted["authorization_url"])
    mongo.raw.storefront_domain_flows.update_one(
        {"planner_id": OWNER_ID, "attempt_id": ATTEMPT_ID},
        {"$set": {"expires_at": now - timedelta(seconds=1)}},
    )
    with pytest.raises(HTTPException) as expired:
        await service.record_callback(expired_token)
    assert expired.value.status_code == 410
    assert expired.value.detail["code"] == "domain_connect_flow_expired"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("advanced_phase", "revision_offset", "ownership_status"),
    [
        # The abandoned-flow worker can schedule verification without changing
        # the revision, so the phase fence must be independently effective.
        ("dns_setup_pending", 0, "pending"),
        ("provider_provisioning", 1, "verified"),
    ],
)
async def test_delayed_cancellation_is_consumed_without_reverting_newer_domain_state(
    flow_setup,
    advanced_phase,
    revision_offset,
    ownership_status,
):
    service, mongo, _, _, _, _ = flow_setup
    started = await service.start(_owner(), ATTEMPT_ID)
    token = _flow_token(started["authorization_url"])
    assert (
        await service.record_callback(
            token,
            error="access_denied",
            error_description="user_cancel: delayed browser callback",
        )
    )["state"] == "cancelled"

    flow = mongo.raw.storefront_domain_flows.find_one(
        {"planner_id": OWNER_ID, "attempt_id": ATTEMPT_ID}
    )
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID, "claim_attempt_id": ATTEMPT_ID},
        {
            "$set": {
                "application_status": advanced_phase,
                "revision": flow["domain_revision"] + revision_offset,
                "ownership_status": ownership_status,
                "action": "processing",
                "last_error": None,
            }
        },
    )
    before = mongo.raw.storefront_domains.find_one(
        {"planner_id": OWNER_ID, "claim_attempt_id": ATTEMPT_ID}
    )

    completed = await service.complete(_owner(), ATTEMPT_ID)

    after = mongo.raw.storefront_domains.find_one(
        {"planner_id": OWNER_ID, "claim_attempt_id": ATTEMPT_ID}
    )
    assert after == before
    assert completed["application_status"] == advanced_phase
    saved_flow = mongo.raw.storefront_domain_flows.find_one({"_id": flow["_id"]})
    assert saved_flow["state"] == "consumed"
    assert saved_flow["completion_outcome"] == "superseded"
    assert saved_flow["superseded_by_domain_revision"] == before["revision"]
    assert saved_flow["superseded_by_application_status"] == advanced_phase
    assert saved_flow["consumed_at"] == saved_flow["superseded_at"]


@pytest.mark.asyncio
async def test_delayed_success_is_consumed_without_restarting_provisioning(flow_setup):
    service, mongo, _, _, _, _ = flow_setup
    started = await service.start(_owner(), ATTEMPT_ID)
    token = _flow_token(started["authorization_url"])
    assert (await service.record_callback(token))["state"] == "authorized"

    flow = mongo.raw.storefront_domain_flows.find_one(
        {"planner_id": OWNER_ID, "attempt_id": ATTEMPT_ID}
    )
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID, "claim_attempt_id": ATTEMPT_ID},
        {
            "$set": {
                "application_status": "hostname_validation",
                "revision": flow["domain_revision"] + 2,
                "ownership_status": "verified",
                "provider_hostname_id": "cf-hostname-current",
                "provider_hostname_status": "pending",
                "provider_status": "pending",
                "action": "processing",
                "last_error": None,
            }
        },
    )
    before = mongo.raw.storefront_domains.find_one(
        {"planner_id": OWNER_ID, "claim_attempt_id": ATTEMPT_ID}
    )

    completed = await service.complete(_owner(), ATTEMPT_ID)

    after = mongo.raw.storefront_domains.find_one(
        {"planner_id": OWNER_ID, "claim_attempt_id": ATTEMPT_ID}
    )
    assert after == before
    assert completed["application_status"] == "hostname_validation"
    assert completed["provider_hostname_status"] == "pending"
    saved_flow = mongo.raw.storefront_domain_flows.find_one({"_id": flow["_id"]})
    assert saved_flow["state"] == "consumed"
    assert saved_flow["completion_outcome"] == "superseded"
    assert saved_flow["superseded_by_domain_revision"] == before["revision"]
    assert saved_flow["superseded_by_application_status"] == "hostname_validation"


@pytest.mark.asyncio
async def test_authorization_and_readiness_flags_fail_before_signing_or_mutation(
    flow_setup,
):
    service, mongo, _, discovery, _, _ = flow_setup
    service._authorization_enabled = False

    with pytest.raises(HTTPException) as disabled:
        await service.start(_owner(), ATTEMPT_ID)

    assert disabled.value.status_code == 404
    assert disabled.value.detail["code"] == "domain_connect_unavailable"
    assert discovery.calls == []
    assert mongo.raw.storefront_domain_flows.count_documents({}) == 0


@pytest.mark.asyncio
async def test_authorization_rechecks_entitlement_before_discovery_or_flow_write(
    flow_setup,
):
    service, mongo, entitlements, discovery, _, _ = flow_setup
    entitlements.enabled[OWNER_ID] = False

    with pytest.raises(HTTPException) as blocked:
        await service.start(_owner(), ATTEMPT_ID)

    assert blocked.value.status_code == 403
    assert blocked.value.detail["code"] == "custom_domain_not_entitled"
    assert discovery.calls == []
    assert mongo.raw.storefront_domain_flows.count_documents({}) == 0


@pytest.mark.asyncio
async def test_authorization_is_independent_from_cloudflare_mutation_flag(flow_setup):
    service, _, _, discovery, _, _ = flow_setup
    service._readiness = lambda: {
        "enabled": True,
        "ready": False,
        "reason_code": "provider_mutations_disabled",
        "missing": [],
    }

    started = await service.start(_owner(), ATTEMPT_ID)

    assert started["authorization_url"].startswith(SYNC_URL)
    assert discovery.calls == [ZONE]


@pytest.mark.asyncio
async def test_callback_replay_is_monotonic_and_cannot_downgrade_authorization(
    flow_setup,
):
    service, _, _, _, _, _ = flow_setup
    started = await service.start(_owner(), ATTEMPT_ID)
    token = _flow_token(started["authorization_url"])

    assert (await service.record_callback(token))["state"] == "authorized"
    replay = await service.record_callback(
        token,
        error="access_denied",
        error_description="user_cancel: replay",
    )

    assert replay["state"] == "authorized"


@pytest.mark.asyncio
async def test_authenticated_completion_replay_resumes_a_completing_flow(flow_setup):
    service, mongo, _, _, _, _ = flow_setup
    started = await service.start(_owner(), ATTEMPT_ID)
    token = _flow_token(started["authorization_url"])
    assert (await service.record_callback(token))["state"] == "authorized"
    mongo.raw.storefront_domain_flows.update_one(
        {"planner_id": OWNER_ID, "attempt_id": ATTEMPT_ID},
        {"$set": {"state": "completing"}},
    )

    completed = await service.complete(_owner(), ATTEMPT_ID)

    assert completed["application_status"] == "dns_setup_pending"
    flow = mongo.raw.storefront_domain_flows.find_one(
        {"planner_id": OWNER_ID, "attempt_id": ATTEMPT_ID}
    )
    assert flow["state"] == "consumed"
    assert flow["completion_outcome"] == "authorized"


@pytest.mark.asyncio
async def test_completion_replay_recovers_after_domain_write_before_flow_consume(
    flow_setup,
):
    service, mongo, _, _, _, now = flow_setup
    started = await service.start(_owner(), ATTEMPT_ID)
    token = _flow_token(started["authorization_url"])
    assert (await service.record_callback(token))["state"] == "authorized"
    flow = mongo.raw.storefront_domain_flows.find_one(
        {"planner_id": OWNER_ID, "attempt_id": ATTEMPT_ID}
    )
    mongo.raw.storefront_domain_flows.update_one(
        {"_id": flow["_id"]},
        {"$set": {"state": "completing"}},
    )
    mongo.raw.storefront_domains.update_one(
        {"planner_id": OWNER_ID, "claim_attempt_id": ATTEMPT_ID},
        {
            "$set": {
                "application_status": "dns_setup_pending",
                "action": "processing",
                "retry_due_at": now,
                "last_error": None,
                "revision": flow["domain_revision"] + 1,
            }
        },
    )

    completed = await service.complete(_owner(), ATTEMPT_ID)

    assert completed["application_status"] == "dns_setup_pending"
    recovered_flow = mongo.raw.storefront_domain_flows.find_one({"_id": flow["_id"]})
    assert recovered_flow["state"] == "consumed"
    assert recovered_flow["completion_outcome"] == "authorized"


@pytest.mark.asyncio
async def test_completion_rechecks_entitlement_after_provider_authorization(flow_setup):
    service, _, entitlements, _, _, _ = flow_setup
    started = await service.start(_owner(), ATTEMPT_ID)
    token = _flow_token(started["authorization_url"])
    assert (await service.record_callback(token))["state"] == "authorized"
    entitlements.enabled[OWNER_ID] = False

    with pytest.raises(HTTPException) as blocked:
        await service.complete(_owner(), ATTEMPT_ID)

    assert blocked.value.status_code == 403
    assert blocked.value.detail["code"] == "custom_domain_not_entitled"
