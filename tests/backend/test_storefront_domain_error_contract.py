from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
import httpx
import pytest

from app.api.storefront import router
from app.dependencies.auth_extended import ExtendedAuthUser
import app.api.storefront as storefront_api
from app.services.storefront_entitlement_service import StorefrontEntitlements
from app.utils.storefront_domain_errors import (
    storefront_domain_http_exception_handler,
    storefront_domain_validation_exception_handler,
)


def _owner() -> ExtendedAuthUser:
    return ExtendedAuthUser(
        email="planner@example.com",
        role="wedding_planner",
        user_data={
            "_id": "507f1f77bcf86cd799439011",
            "role": "wedding_planner",
        },
    )


def _app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(HTTPException, storefront_domain_http_exception_handler)
    app.add_exception_handler(
        RequestValidationError, storefront_domain_validation_exception_handler
    )
    app.include_router(router, prefix="/admin")
    app.dependency_overrides[storefront_api.require_storefront_owner] = _owner
    app.dependency_overrides[storefront_api.require_custom_domain] = lambda: (
        StorefrontEntitlements(
            owner_id="507f1f77bcf86cd799439011",
            plan_id="plan_signature",
            storefront_enabled=True,
            custom_domain_enabled=True,
        )
    )
    return app


@pytest.mark.asyncio
async def test_custom_domain_service_error_uses_production_envelope(monkeypatch):
    async def reject(*_args, **_kwargs):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "hostname_claim_conflict",
                "message": "This hostname already has a protected claim.",
                "customer_action": "Add a fresh TXT proof.",
                "retryable": False,
                "support_id": "sfd_contract_123",
            },
        )

    monkeypatch.setattr(storefront_api.storefront_domain_service, "claim", reject)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/admin/storefront/custom-domain/claim",
            json={"domain": "events.example.com", "intent": "new"},
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "hostname_claim_conflict",
            "message": "This hostname already has a protected claim.",
            "customer_action": "Add a fresh TXT proof.",
            "retryable": False,
            "support_id": "sfd_contract_123",
            "field_errors": {},
        }
    }


@pytest.mark.asyncio
async def test_custom_domain_validation_error_identifies_fields_without_raw_json():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/admin/storefront/custom-domain/claim",
            json={"domain": "events.example.com", "intent": "unsupported"},
        )

    payload = response.json()
    assert response.status_code == 422
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["field_errors"] == {
        "intent": "Input should be 'new' or 'migration'"
    }
    assert "detail" not in payload
