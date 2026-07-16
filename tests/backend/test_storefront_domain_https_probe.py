from __future__ import annotations

from copy import deepcopy
import json

from bson import ObjectId
from fastapi import HTTPException
import mongomock
import pytest

from app.services.storefront_domain_https_probe import (
    PROBE_HEADER,
    StorefrontDomainHttpsProbeService,
    build_probe_attestation,
    build_probe_challenge,
    build_probe_ingress_proof,
)
from app.services.storefront_domain_reconciliation_service import (
    SystemStorefrontHttpsVerifier,
)


SECRET = "storefront-probe-test-secret-that-is-at-least-32-bytes"
INGRESS_SECRET = "storefront-ingress-test-secret-1234567890"
HOSTNAME = "events.customer.example"
OWNER_ID = "507f1f77bcf86cd799439011"


class AsyncCollection:
    def __init__(self, collection):
        self._collection = collection
        self.find_one_calls = 0

    async def find_one(self, *args, **kwargs):
        self.find_one_calls += 1
        return self._collection.find_one(*args, **kwargs)


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
        self.raw = mongomock.MongoClient()["storefront_https_probe_test"]
        self.db = AsyncDatabase(self.raw)


class FakeAddressResolver:
    def __init__(self, addresses: list[str] | None = None):
        self.addresses = addresses or ["93.184.216.34"]
        self.calls: list[str] = []

    async def resolve(self, hostname: str) -> list[str]:
        self.calls.append(hostname)
        return list(self.addresses)


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: object,
        *,
        content_type: str = "application/json",
    ):
        self.status_code = status_code
        self.content = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )
        self.headers = {"content-type": content_type}


class FakeTransport:
    def __init__(self, response_factory):
        self.response_factory = response_factory
        self.requests: list[tuple[str, str, dict]] = []

    async def request(self, method: str, url: str, **kwargs):
        self.requests.append((method, url, kwargs))
        return self.response_factory(method, url, kwargs)


def domain_record(**overrides) -> dict:
    record = {
        "_id": ObjectId(),
        "planner_id": OWNER_ID,
        "hostname": HOSTNAME,
        "revision": 7,
        "claim_attempt_id": "attempt-7",
        "ownership_status": "verified",
        "deletion_status": None,
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_probe_service_attests_exact_domain_without_requiring_publication():
    mongo = FakeMongo()
    record = domain_record()
    mongo.raw.storefront_domains.insert_one(deepcopy(record))
    # Deliberately no storefront_settings row: domain readiness is independent
    # from publication and must not expose draft storefront content.
    challenge = build_probe_challenge(record, SECRET, nonce="fixed-probe-nonce")
    service = StorefrontDomainHttpsProbeService(
        mongo_client=mongo,
        secret_key=SECRET,
        ingress_secret=INGRESS_SECRET,
        platform_domains=("thespecialwedding.com",),
    )

    response = await service.attest(
        HOSTNAME,
        challenge,
        build_probe_ingress_proof(HOSTNAME, challenge, INGRESS_SECRET),
    )

    assert response == build_probe_attestation(record, challenge, SECRET)
    assert "planner_id" not in response
    assert "storefront" not in response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "record_update",
    [
        {"deletion_status": "provider_delete_pending"},
        {"revision": 8},
        {"hostname": "other.customer.example"},
        {"planner_id": "507f191e810c19729de860ea"},
    ],
)
async def test_probe_service_fails_closed_for_stale_or_wrong_lifecycle_identity(
    record_update,
):
    mongo = FakeMongo()
    original = domain_record()
    stored = {**original, **record_update}
    mongo.raw.storefront_domains.insert_one(deepcopy(stored))
    challenge = build_probe_challenge(original, SECRET, nonce="fixed-probe-nonce")
    service = StorefrontDomainHttpsProbeService(
        mongo_client=mongo,
        secret_key=SECRET,
        ingress_secret=INGRESS_SECRET,
        platform_domains=("thespecialwedding.com",),
    )

    with pytest.raises(HTTPException) as failure:
        await service.attest(
            HOSTNAME,
            challenge,
            build_probe_ingress_proof(HOSTNAME, challenge, INGRESS_SECRET),
        )

    assert failure.value.status_code == 404


def test_probe_ingress_proof_has_a_cross_runtime_canonical_vector():
    challenge = f"v1.fixed-probe-nonce.{'a' * 64}"

    assert build_probe_ingress_proof(HOSTNAME, challenge, INGRESS_SECRET) == (
        "v1.694b6d79166112818756c1a1cf6997c7f3030ca0859f05eb5a36011f72ab7a8e"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relay_proof",
    [
        "",
        f"v1.{'0' * 64}",
        build_probe_ingress_proof(
            HOSTNAME,
            build_probe_challenge(domain_record(), SECRET, nonce="other-probe-nonce"),
            INGRESS_SECRET,
        ),
        build_probe_ingress_proof(
            "other.customer.example",
            build_probe_challenge(domain_record(), SECRET, nonce="fixed-probe-nonce"),
            INGRESS_SECRET,
        ),
        build_probe_ingress_proof(
            HOSTNAME,
            build_probe_challenge(domain_record(), SECRET, nonce="fixed-probe-nonce"),
            "different-ingress-test-secret-123456789",
        ),
    ],
)
async def test_probe_service_rejects_public_relay_without_exact_trusted_ingress(
    relay_proof,
):
    mongo = FakeMongo()
    record = domain_record()
    mongo.raw.storefront_domains.insert_one(deepcopy(record))
    challenge = build_probe_challenge(record, SECRET, nonce="fixed-probe-nonce")
    service = StorefrontDomainHttpsProbeService(
        mongo_client=mongo,
        secret_key=SECRET,
        ingress_secret=INGRESS_SECRET,
        platform_domains=("thespecialwedding.com",),
    )

    with pytest.raises(HTTPException) as failure:
        await service.attest(HOSTNAME, challenge, relay_proof)

    assert failure.value.status_code == 404
    assert mongo.db["storefront_domains"].find_one_calls == 0


@pytest.mark.asyncio
async def test_probe_service_fails_closed_when_ingress_configuration_is_missing():
    mongo = FakeMongo()
    record = domain_record()
    mongo.raw.storefront_domains.insert_one(deepcopy(record))
    challenge = build_probe_challenge(record, SECRET, nonce="fixed-probe-nonce")
    service = StorefrontDomainHttpsProbeService(
        mongo_client=mongo,
        secret_key=SECRET,
        ingress_secret="",
        platform_domains=("thespecialwedding.com",),
    )

    with pytest.raises(HTTPException) as failure:
        await service.attest(
            HOSTNAME,
            challenge,
            build_probe_ingress_proof(HOSTNAME, challenge, INGRESS_SECRET),
        )

    assert failure.value.status_code == 404
    assert mongo.db["storefront_domains"].find_one_calls == 0


@pytest.mark.asyncio
async def test_https_verifier_requires_exact_signed_binding_and_strict_200():
    record = domain_record()

    def valid_response(_method, _url, kwargs):
        challenge = kwargs["headers"][PROBE_HEADER]
        return FakeResponse(200, build_probe_attestation(record, challenge, SECRET))

    transport = FakeTransport(valid_response)
    verifier = SystemStorefrontHttpsVerifier(
        address_resolver=FakeAddressResolver(),
        http_transport=transport,
        secret_key=SECRET,
        nonce_factory=lambda: "fixed-probe-nonce",
    )

    assert await verifier.verify(record) is True
    assert transport.requests[0][0:2] == (
        "GET",
        f"https://{HOSTNAME}/.well-known/tsw-storefront-verification",
    )
    assert transport.requests[0][2]["follow_redirects"] is False

    for response in (
        FakeResponse(
            302,
            build_probe_attestation(
                record,
                build_probe_challenge(record, SECRET, nonce="fixed-probe-nonce"),
                SECRET,
            ),
        ),
        FakeResponse(200, {"ok": True}),
        FakeResponse(200, b"{"),
        FakeResponse(200, b"x" * 8193),
        FakeResponse(
            200,
            build_probe_attestation(
                {**record, "revision": 8},
                build_probe_challenge(
                    {**record, "revision": 8}, SECRET, nonce="fixed-probe-nonce"
                ),
                SECRET,
            ),
        ),
    ):
        failing = SystemStorefrontHttpsVerifier(
            address_resolver=FakeAddressResolver(),
            http_transport=FakeTransport(lambda *_args, **_kwargs: response),
            secret_key=SECRET,
            nonce_factory=lambda: "fixed-probe-nonce",
        )
        assert await failing.verify(record) is False


@pytest.mark.asyncio
async def test_https_verifier_never_contacts_private_or_rebinding_destination():
    transport = FakeTransport(lambda *_args, **_kwargs: FakeResponse(200, {}))
    verifier = SystemStorefrontHttpsVerifier(
        address_resolver=FakeAddressResolver(["127.0.0.1", "10.0.0.8"]),
        http_transport=transport,
        secret_key=SECRET,
    )

    assert await verifier.verify(domain_record()) is False
    assert transport.requests == []
