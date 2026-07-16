from __future__ import annotations

from fastapi import FastAPI
import httpx
import pytest

import app.api.storefront as storefront_api


class FakeProbeService:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def attest(self, hostname: str, challenge: str) -> dict:
        self.calls.append((hostname, challenge))
        return {
            "version": "1",
            "hostname": hostname,
            "revision": 4,
            "nonce": "fixed-probe-nonce",
            "domain_binding": "b" * 64,
            "proof": "c" * 64,
        }


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
                "x-forwarded-host": "attacker.example",
            },
        )

    assert response.status_code == 200
    assert service.calls == [("events.customer.example", "v1.fixed-probe-nonce.signed")]
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json()["hostname"] == "events.customer.example"
