from __future__ import annotations

from fastapi import FastAPI
import httpx
import pytest

import app.api.storefront as storefront_api
from app.services.storefront_domain_https_probe import (
    StorefrontDomainHttpsProbeService,
    build_probe_ingress_proof,
)


class FakeProbeService:
    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []

    async def attest(self, hostname: str, challenge: str, ingress_proof: str) -> dict:
        self.calls.append((hostname, challenge, ingress_proof))
        return {
            "version": "1",
            "hostname": hostname,
            "revision": 4,
            "nonce": "fixed-probe-nonce",
            "domain_binding": "b" * 64,
            "proof": "c" * 64,
        }


class NeverQueryCollection:
    def __init__(self):
        self.queried = False

    async def find_one(self, *_args, **_kwargs):
        self.queried = True
        return None


class NeverQueryDatabase:
    def __init__(self):
        self.collection = NeverQueryCollection()

    def __getitem__(self, _name):
        return self.collection


class NeverQueryMongo:
    def __init__(self):
        self.db = NeverQueryDatabase()


@pytest.mark.asyncio
async def test_public_probe_route_forwards_only_explicit_origin_binding_headers(
    monkeypatch,
):
    service = FakeProbeService()
    monkeypatch.setattr(
        storefront_api, "storefront_domain_https_probe_service", service
    )
    app = FastAPI()
    app.include_router(storefront_api.public_router, prefix="/api")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://backend.test",
    ) as client:
        response = await client.get(
            "/api/storefront/domain-verification-probe",
            headers={
                "x-tsw-storefront-host": "events.customer.example",
                "x-tsw-storefront-probe": "v1.fixed-probe-nonce.signed",
                "x-tsw-storefront-ingress-proof": "v1.trusted-ingress-proof",
                "x-forwarded-host": "attacker.example",
            },
        )

    assert response.status_code == 200
    assert service.calls == [
        (
            "events.customer.example",
            "v1.fixed-probe-nonce.signed",
            "v1.trusted-ingress-proof",
        )
    ]
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json()["hostname"] == "events.customer.example"


@pytest.mark.asyncio
async def test_public_probe_route_rejects_relayed_challenge_without_ingress_identity(
    monkeypatch,
):
    hostname = "events.customer.example"
    challenge = f"v1.fixed-probe-nonce.{'a' * 64}"
    ingress_secret = "storefront-ingress-test-secret-1234567890"
    mongo = NeverQueryMongo()
    monkeypatch.setattr(
        storefront_api,
        "storefront_domain_https_probe_service",
        StorefrontDomainHttpsProbeService(
            mongo_client=mongo,
            secret_key="storefront-probe-test-secret-that-is-at-least-32-bytes",
            ingress_secret=ingress_secret,
            platform_domains=("thespecialwedding.com",),
        ),
    )
    app = FastAPI()
    app.include_router(storefront_api.public_router, prefix="/api")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://backend.test",
    ) as client:
        for ingress_proof in (
            None,
            f"v1.{'0' * 64}",
            build_probe_ingress_proof(
                hostname,
                challenge,
                "different-ingress-test-secret-123456789",
            ),
        ):
            headers = {
                "x-tsw-storefront-host": hostname,
                "x-tsw-storefront-probe": challenge,
            }
            if ingress_proof is not None:
                headers["x-tsw-storefront-ingress-proof"] = ingress_proof
            response = await client.get(
                "/api/storefront/domain-verification-probe",
                headers=headers,
            )
            assert response.status_code == 404
            assert response.json() == {"detail": "Not Found"}

    assert mongo.db.collection.queried is False
