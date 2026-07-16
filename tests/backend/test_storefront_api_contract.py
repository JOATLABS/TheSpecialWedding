from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

from fastapi import FastAPI, HTTPException
import httpx
import pytest
from pydantic import ValidationError

import app.api.storefront as storefront_api
from app.api.storefront import public_router, router
from app.dependencies.auth_extended import ExtendedAuthUser, get_current_user_extended
from app.models.storefront import StorefrontSettingsUpdate
from app.services.storefront_entitlement_service import StorefrontEntitlements


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _route_methods(api_router) -> dict[str, set[str]]:
    methods: dict[str, set[str]] = {}
    for route in api_router.routes:
        if hasattr(route, "methods"):
            methods.setdefault(route.path, set()).update(route.methods or set())
    return methods


def _app_route_methods(app) -> dict[str, set[str]]:
    methods: dict[str, set[str]] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is not None:
            methods.setdefault(path, set()).update(getattr(route, "methods", set()))
            continue
        contexts = getattr(route, "effective_route_contexts", None)
        if contexts is None:
            continue
        for context in contexts():
            methods.setdefault(context.path, set()).update(context.methods or set())
    return methods


def test_admin_and_public_route_families_are_explicit_and_non_overlapping():
    admin_routes = _route_methods(router)
    public_routes = _route_methods(public_router)

    assert admin_routes == {
        "/storefront/access": {"GET"},
        "/storefront/provider-readiness": {"GET"},
        "/storefront/settings": {"GET", "POST"},
        "/storefront/preview-data": {"GET"},
        "/storefront/preview/{slug}": {"GET"},
        "/storefront/custom-domain": {"POST", "DELETE"},
        "/storefront/custom-domain/preflight": {"POST"},
        "/storefront/custom-domain/claim": {"POST"},
        "/storefront/custom-domain/verify": {"POST"},
        "/storefront/custom-domain/domain-connect/authorize": {"POST"},
        "/storefront/custom-domain/domain-connect/start": {"POST"},
        "/storefront/custom-domain/domain-connect/callback": {"GET"},
        "/storefront/custom-domain/domain-connect/complete": {"POST"},
        "/storefront/custom-domain/retry": {"POST"},
        "/storefront/custom-domain/observe": {"POST"},
        "/storefront/custom-domain/instructions": {"GET", "POST"},
        "/storefront/custom-domain/instructions/{link_id}": {"DELETE"},
        "/storefront/custom-domain/status": {"GET"},
        "/storefront/upload-url": {"GET"},
        "/storefront/upload-complete": {"POST"},
        "/storefront/upload": {"DELETE"},
    }
    assert public_routes == {
        "/storefront/domain-instructions/{token}": {"GET"},
        "/storefront/domain-verification-probe": {"GET"},
        "/storefront/{identifier}": {"GET"},
        "/storefront/{identifier}/inquiries": {"POST"},
    }


def test_settings_contract_rejects_domain_provider_and_image_url_smuggling():
    for field in (
        "custom_domain",
        "cloudflare_hostname_id",
        "cloudflare_hostname_status",
        "ownership_verification",
        "hero_image_url",
        "about_image_url",
    ):
        with pytest.raises(ValidationError):
            StorefrontSettingsUpdate.model_validate(
                {"slug": "valid-slug", field: "not-allowed"}
            )


def test_legacy_public_fallback_and_broad_auth_gate_are_removed():
    source = (PROJECT_ROOT / "app" / "api" / "storefront.py").read_text()

    assert "domain_or_planner_id" not in source
    assert "require_admin_or_planner" not in source
    assert "ObjectId(domain_or_planner_id)" not in source
    assert "settings = {" not in source
    assert "folder: str = Query" not in source
    assert "custom_domain: Optional[str]" not in source


def test_main_mounts_exact_full_route_prefixes():
    from app.main import app

    route_methods = _app_route_methods(app)
    assert route_methods["/admin/storefront/access"] == {"GET"}
    assert route_methods["/admin/storefront/provider-readiness"] == {"GET"}
    assert route_methods["/admin/storefront/settings"] == {"GET", "POST"}
    assert route_methods["/admin/storefront/preview-data"] == {"GET"}
    assert route_methods["/admin/storefront/preview/{slug}"] == {"GET"}
    assert route_methods["/admin/storefront/custom-domain"] == {"POST", "DELETE"}
    assert route_methods["/admin/storefront/custom-domain/preflight"] == {"POST"}
    assert route_methods["/admin/storefront/custom-domain/claim"] == {"POST"}
    assert route_methods["/admin/storefront/custom-domain/verify"] == {"POST"}
    assert route_methods[
        "/admin/storefront/custom-domain/domain-connect/authorize"
    ] == {"POST"}
    assert route_methods["/admin/storefront/custom-domain/domain-connect/start"] == {
        "POST"
    }
    assert route_methods["/admin/storefront/custom-domain/domain-connect/callback"] == {
        "GET"
    }
    assert route_methods["/admin/storefront/custom-domain/domain-connect/complete"] == {
        "POST"
    }
    assert route_methods["/admin/storefront/custom-domain/retry"] == {"POST"}
    assert route_methods["/admin/storefront/custom-domain/observe"] == {"POST"}
    assert route_methods["/admin/storefront/custom-domain/instructions"] == {
        "GET",
        "POST",
    }
    assert route_methods["/admin/storefront/custom-domain/instructions/{link_id}"] == {
        "DELETE"
    }
    assert route_methods["/admin/storefront/custom-domain/status"] == {"GET"}
    assert route_methods["/admin/storefront/upload-url"] == {"GET"}
    assert route_methods["/admin/storefront/upload-complete"] == {"POST"}
    assert route_methods["/admin/storefront/upload"] == {"DELETE"}
    assert route_methods["/api/storefront/{identifier}"] == {"GET"}
    assert route_methods["/api/storefront/domain-instructions/{token}"] == {"GET"}
    assert route_methods["/api/storefront/domain-verification-probe"] == {"GET"}
    assert route_methods["/api/storefront/{identifier}/inquiries"] == {"POST"}
    assert "/api/storefront/preview/{slug}" not in route_methods


def _public_dto(slug: str = "luxe-events") -> dict:
    return {
        "slug": slug,
        "storefront": {
            "title": "Draft preview",
            "description": None,
            "contact_email": None,
            "contact_phone": None,
            "hero_image_url": None,
            "about_image_url": None,
            "theme_color": "#0f172a",
            "packages_enabled": True,
            "reviews_enabled": True,
        },
        "planner": {
            "company_name": "Luxe Events",
            "first_name": "Ada",
            "profile_image_url": None,
        },
        "packages": [],
        "reviews": [],
    }


def _test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(public_router, prefix="/api")
    app.include_router(router, prefix="/admin")
    return app


def _owner(role: str = "wedding_planner") -> ExtendedAuthUser:
    return ExtendedAuthUser(
        email=f"{role}@example.com",
        role=role,
        user_data={"_id": "507f1f77bcf86cd799439011", "role": role},
    )


@pytest.mark.asyncio
async def test_provider_readiness_attests_booleans_without_exposing_configuration(
    monkeypatch,
):
    monkeypatch.setattr(
        storefront_api,
        "storefront_media_service",
        SimpleNamespace(provider_operational_readiness=AsyncMock(return_value=False)),
    )
    monkeypatch.setattr(
        storefront_api,
        "storefront_domain_service",
        SimpleNamespace(provider_configuration_present=True),
    )
    app = _test_app()
    app.dependency_overrides[storefront_api.require_storefront_owner] = lambda: _owner()
    app.dependency_overrides[storefront_api.require_planner_storefront] = lambda: (
        StorefrontEntitlements(
            owner_id="507f1f77bcf86cd799439011",
            plan_id="plan_signature",
            storefront_enabled=True,
            custom_domain_enabled=True,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/admin/storefront/provider-readiness")

    assert response.status_code == 200
    assert response.json() == {
        "image_uploads_configured": False,
        "custom_domains_configured": True,
        "runtime_revision": None,
    }


@pytest.mark.asyncio
async def test_provider_readiness_hides_custom_domain_configuration_from_ineligible_plan(
    monkeypatch,
):
    monkeypatch.setattr(
        storefront_api,
        "storefront_media_service",
        SimpleNamespace(provider_operational_readiness=AsyncMock(return_value=True)),
    )
    monkeypatch.setattr(
        storefront_api,
        "storefront_domain_service",
        SimpleNamespace(provider_configuration_present=True),
    )
    monkeypatch.setattr(storefront_api.settings, "storefront_runtime_revision", None)
    app = _test_app()
    app.dependency_overrides[storefront_api.require_storefront_owner] = lambda: _owner()
    app.dependency_overrides[storefront_api.require_planner_storefront] = lambda: (
        StorefrontEntitlements(
            owner_id="507f1f77bcf86cd799439011",
            plan_id="plan_boutique",
            storefront_enabled=True,
            custom_domain_enabled=False,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/admin/storefront/provider-readiness")

    assert response.status_code == 200
    assert response.json() == {
        "image_uploads_configured": True,
        "custom_domains_configured": False,
        "runtime_revision": None,
    }


@pytest.mark.asyncio
async def test_provider_readiness_requires_an_authenticated_storefront_owner():
    app = _test_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/admin/storefront/provider-readiness")

    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_owner_can_read_settings_for_existing_domain_management_without_feature_gate(
    monkeypatch,
):
    settings = {
        "slug": "retained-storefront",
        "title": "Retained storefront",
        "description": None,
        "contact_email": None,
        "contact_phone": None,
        "hero_asset_id": None,
        "about_asset_id": None,
        "theme_color": "#0f172a",
        "packages_enabled": True,
        "reviews_enabled": True,
        "is_published": True,
        "published_at": None,
        "created_at": None,
        "updated_at": None,
        "revision": 3,
        "slug_editable": False,
        "slug_persisted": True,
    }
    fake_service = SimpleNamespace(get_settings=AsyncMock(return_value=settings))
    monkeypatch.setattr(storefront_api, "storefront_service", fake_service)
    app = _test_app()
    owner = _owner()
    app.dependency_overrides[get_current_user_extended] = lambda: owner

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/admin/storefront/settings")

    assert response.status_code == 200
    assert response.json()["settings"]["slug"] == "retained-storefront"
    fake_service.get_settings.assert_awaited_once()


@pytest.mark.asyncio
async def test_unauthenticated_request_cannot_reach_draft_preview(monkeypatch):
    fake_service = SimpleNamespace(
        get_owner_preview=AsyncMock(return_value=_public_dto())
    )
    monkeypatch.setattr(storefront_api, "storefront_service", fake_service)
    app = _test_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/admin/storefront/preview/luxe-events")

    assert response.status_code in {401, 403}
    fake_service.get_owner_preview.assert_not_awaited()


@pytest.mark.asyncio
async def test_forbidden_role_cannot_write_settings_through_http(monkeypatch):
    fake_service = SimpleNamespace(update_settings=AsyncMock())
    monkeypatch.setattr(storefront_api, "storefront_service", fake_service)
    app = _test_app()
    app.dependency_overrides[get_current_user_extended] = lambda: _owner("team_member")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/admin/storefront/settings", json={"slug": "team-bypass"}
        )

    assert response.status_code == 403
    fake_service.update_settings.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticated_owner_can_preview_unpublished_dto(monkeypatch):
    fake_service = SimpleNamespace(
        get_owner_preview=AsyncMock(return_value=_public_dto())
    )
    monkeypatch.setattr(storefront_api, "storefront_service", fake_service)
    app = _test_app()
    owner = _owner()
    app.dependency_overrides[get_current_user_extended] = lambda: owner
    app.dependency_overrides[storefront_api.require_planner_storefront] = lambda: (
        StorefrontEntitlements(
            owner_id=owner.user_data["_id"],
            plan_id="plan_signature",
            storefront_enabled=True,
            custom_domain_enabled=True,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/admin/storefront/preview/luxe-events")

    assert response.status_code == 200
    assert response.json()["slug"] == "luxe-events"
    fake_service.get_owner_preview.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticated_owner_can_load_canonical_preview_seed(monkeypatch):
    fake_service = SimpleNamespace(
        get_owner_preview_seed=AsyncMock(return_value=_public_dto("storefront-owner"))
    )
    monkeypatch.setattr(storefront_api, "storefront_service", fake_service)
    app = _test_app()
    owner = _owner()
    app.dependency_overrides[get_current_user_extended] = lambda: owner
    app.dependency_overrides[storefront_api.require_planner_storefront] = lambda: (
        StorefrontEntitlements(
            owner_id=owner.user_data["_id"],
            plan_id="plan_signature",
            storefront_enabled=True,
            custom_domain_enabled=True,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/admin/storefront/preview-data")

    assert response.status_code == 200
    assert response.json()["planner"]["company_name"] == "Luxe Events"
    fake_service.get_owner_preview_seed.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", ["draft", "invalid", "ineligible"])
async def test_public_denials_remain_404_through_response_boundary(
    monkeypatch, identifier: str
):
    fake_service = SimpleNamespace(
        get_public_storefront=AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Storefront not found")
        )
    )
    monkeypatch.setattr(storefront_api, "storefront_service", fake_service)
    app = _test_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(f"/api/storefront/{identifier}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Storefront not found"}


@pytest.mark.asyncio
async def test_public_inquiry_route_uses_server_request_metadata_and_forbids_owner_fields(
    monkeypatch,
):
    fake_inquiries = SimpleNamespace(
        capture=AsyncMock(
            return_value={
                "success": True,
                "inquiry_id": "inquiry-1",
                "message": "Thanks — your inquiry was received by the wedding planner.",
            }
        )
    )
    monkeypatch.setattr(storefront_api, "storefront_inquiry_service", fake_inquiries)
    app = _test_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("8.8.8.8", 443)),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/storefront/luxe-events/inquiries",
            headers={"user-agent": "Contract Browser/1.0"},
            json={
                "name": "Ayo Couple",
                "email": "ayo@example.com",
                "message": "We would love to learn more.",
                "idempotency_key": "inquiry-key-contract-00000001",
            },
        )
        smuggled = await client.post(
            "/api/storefront/luxe-events/inquiries",
            json={
                "name": "Ayo Couple",
                "email": "ayo@example.com",
                "message": "Hello",
                "idempotency_key": "inquiry-key-contract-00000002",
                "planner_id": "attacker-controlled",
            },
        )

    assert response.status_code == 201
    assert response.json()["inquiry_id"] == "inquiry-1"
    call = fake_inquiries.capture.await_args
    assert call.args[0] == "luxe-events"
    assert call.args[1].email == "ayo@example.com"
    assert call.args[1].idempotency_key == "inquiry-key-contract-00000001"
    assert call.kwargs == {
        "client_ip": "8.8.8.8",
        "user_agent": "Contract Browser/1.0",
    }
    assert smuggled.status_code == 422
    fake_inquiries.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_public_inquiry_route_accepts_legacy_payload_without_idempotency_key(
    monkeypatch,
):
    fake_inquiries = SimpleNamespace(
        capture=AsyncMock(
            return_value={
                "success": True,
                "inquiry_id": "legacy-inquiry-1",
                "message": "Thanks — your inquiry was received by the wedding planner.",
            }
        )
    )
    monkeypatch.setattr(storefront_api, "storefront_inquiry_service", fake_inquiries)
    app = _test_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/storefront/luxe-events/inquiries",
            json={
                "name": "Legacy Couple",
                "email": "legacy@example.com",
                "message": "Backend-first rolling deployment",
            },
        )

    assert response.status_code == 201
    assert fake_inquiries.capture.await_args.args[1].idempotency_key is None


@pytest.mark.asyncio
async def test_domain_routes_use_separate_capability_and_never_accept_team_member(
    monkeypatch,
):
    fake_domains = SimpleNamespace(
        connect=AsyncMock(
            return_value={
                "hostname": "events.example.com",
                "status": "pending",
                "provider_status": "pending",
                "ssl_status": "pending_validation",
                "ownership_verification": None,
                "ownership_verification_http": None,
                "ssl_validation_records": [],
                "cname_target": "storefronts.example.com",
                "deletion_status": None,
                "last_error": None,
            }
        )
    )
    monkeypatch.setattr(storefront_api, "storefront_domain_service", fake_domains)

    denied_app = _test_app()
    denied_app.dependency_overrides[get_current_user_extended] = lambda: _owner(
        "team_member"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=denied_app), base_url="http://testserver"
    ) as client:
        denied = await client.post(
            "/admin/storefront/custom-domain",
            json={"domain": "events.example.com"},
        )
    assert denied.status_code == 403
    fake_domains.connect.assert_not_awaited()

    owner = _owner()
    allowed_app = _test_app()
    allowed_app.dependency_overrides[get_current_user_extended] = lambda: owner
    allowed_app.dependency_overrides[storefront_api.require_custom_domain] = lambda: (
        StorefrontEntitlements(
            owner_id=owner.user_data["_id"],
            plan_id="plan_signature",
            storefront_enabled=True,
            custom_domain_enabled=True,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=allowed_app), base_url="http://testserver"
    ) as client:
        allowed = await client.post(
            "/admin/storefront/custom-domain",
            json={"domain": "events.example.com"},
        )
    assert allowed.status_code == 201
    fake_domains.connect.assert_awaited_once_with(owner, "events.example.com")


@pytest.mark.asyncio
async def test_domain_status_and_disconnect_remain_owner_accessible_without_capability(
    monkeypatch,
):
    fake_domains = SimpleNamespace(
        get_status=AsyncMock(return_value=None),
        observe=AsyncMock(return_value=None),
        disconnect=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(storefront_api, "storefront_domain_service", fake_domains)
    owner = _owner()
    app = _test_app()
    app.dependency_overrides[storefront_api.require_storefront_owner] = lambda: owner

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        status_response = await client.get("/admin/storefront/custom-domain/status")
        attempt_status_response = await client.get(
            "/admin/storefront/custom-domain/status",
            params={"attempt_id": "attempt-1"},
        )
        observe_response = await client.post(
            "/admin/storefront/custom-domain/observe",
            json={"attempt_id": "attempt-1"},
        )
        default_delete_response = await client.delete("/admin/storefront/custom-domain")
        delete_response = await client.delete(
            "/admin/storefront/custom-domain",
            params={"attempt_id": "attempt-1"},
        )

    assert status_response.status_code == 200
    assert status_response.json() is None
    assert attempt_status_response.status_code == 200
    assert attempt_status_response.json() is None
    assert observe_response.status_code == 200
    assert observe_response.json() is None
    assert default_delete_response.status_code == 200
    assert default_delete_response.json() == {
        "application_status": "disconnected",
        "attempt_id": None,
    }
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "application_status": "disconnected",
        "attempt_id": "attempt-1",
    }
    fake_domains.get_status.assert_has_awaits(
        [call(owner), call(owner, attempt_id="attempt-1")]
    )
    fake_domains.observe.assert_awaited_once_with(owner, "attempt-1")
    fake_domains.disconnect.assert_has_awaits(
        [call(owner), call(owner, attempt_id="attempt-1")]
    )


@pytest.mark.asyncio
async def test_callback_shaped_verify_input_cannot_bypass_typed_dns_verification(
    monkeypatch,
):
    fake_domains = SimpleNamespace(verify=AsyncMock())
    monkeypatch.setattr(storefront_api, "storefront_domain_service", fake_domains)
    owner = _owner()
    app = _test_app()
    app.dependency_overrides[storefront_api.require_storefront_owner] = lambda: owner
    app.dependency_overrides[storefront_api.require_custom_domain] = lambda: (
        StorefrontEntitlements(
            owner_id=owner.user_data["_id"],
            plan_id="plan_signature",
            storefront_enabled=True,
            custom_domain_enabled=True,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/admin/storefront/custom-domain/verify",
            json={"callback": {"success": True, "provider": "forged"}},
        )

    assert response.status_code == 422
    fake_domains.verify.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_verify_body_and_domain_connect_routes_match_frontend_contract(
    monkeypatch,
):
    domain_response = {
        "hostname": "events.example.com",
        "status": "pending",
        "provider_status": "pending",
        "ssl_status": "pending_validation",
        "application_status": "dns_setup_pending",
        "ownership_status": "pending",
        "provider_hostname_status": "pending",
        "routing_dns_status": "pending",
        "https_status": "pending",
        "action": "action_required",
        "provider_hostname_id": None,
        "attempt_id": "attempt-1",
        "revision": 1,
        "claim_expires_at": None,
        "expected_records": [],
        "ownership_verification": None,
        "ownership_verification_http": None,
        "ssl_validation_records": [],
        "cname_target": "domains.thespecialwedding.com",
        "deletion_status": None,
        "last_error": None,
    }
    fake_domains = SimpleNamespace(
        verify=AsyncMock(return_value=domain_response),
        observe=AsyncMock(return_value=domain_response),
        retry_provider=AsyncMock(return_value=domain_response),
        send_instructions=AsyncMock(
            return_value={
                "status": "sent",
                "link_id": "link-1",
                "state": "active",
                "created_at": "2026-07-15T18:00:00Z",
                "expires_at": "2026-07-22T18:00:00Z",
                "recipient_hint": "d***@e***.com",
            }
        ),
        list_instruction_links=AsyncMock(
            return_value={
                "links": [
                    {
                        "link_id": "link-1",
                        "state": "active",
                        "created_at": "2026-07-15T18:00:00Z",
                        "expires_at": "2026-07-22T18:00:00Z",
                        "recipient_hint": "d***@e***.com",
                    }
                ]
            }
        ),
        revoke_instruction_link=AsyncMock(return_value={"status": "revoked"}),
        read_instruction_link=AsyncMock(
            return_value={
                "hostname": "events.example.com",
                "records": [],
                "note": None,
                "expires_at": "2026-07-22T18:00:00Z",
            }
        ),
    )
    fake_connect = SimpleNamespace(
        start=AsyncMock(
            return_value={
                "authorization_url": "https://dash.cloudflare.com/domain-connect",
                "attempt_id": "attempt-1",
            }
        ),
        record_callback=AsyncMock(
            return_value={"attempt_id": "attempt-1", "state": "authorized"}
        ),
        complete=AsyncMock(return_value=domain_response),
    )
    monkeypatch.setattr(storefront_api, "storefront_domain_service", fake_domains)
    monkeypatch.setattr(
        storefront_api, "storefront_domain_connect_service", fake_connect
    )
    monkeypatch.setattr(
        storefront_api.settings,
        "frontend_url",
        "https://thespecialwedding.com",
    )
    owner = _owner()
    app = _test_app()
    app.dependency_overrides[storefront_api.require_storefront_owner] = lambda: owner
    app.dependency_overrides[storefront_api.require_custom_domain] = lambda: (
        StorefrontEntitlements(
            owner_id=owner.user_data["_id"],
            plan_id="plan_signature",
            storefront_enabled=True,
            custom_domain_enabled=True,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        verified = await client.post("/admin/storefront/custom-domain/verify")
        verified_attempt = await client.post(
            "/admin/storefront/custom-domain/verify",
            json={"attempt_id": "attempt-1"},
        )
        authorized = await client.post(
            "/admin/storefront/custom-domain/domain-connect/authorize",
            json={"attempt_id": "attempt-1"},
        )
        started = await client.post(
            "/admin/storefront/custom-domain/domain-connect/start",
            json={"attempt_id": "attempt-1"},
        )
        callback = await client.get(
            "/admin/storefront/custom-domain/domain-connect/callback",
            params={"flow": "x" * 43},
            follow_redirects=False,
        )
        completed = await client.post(
            "/admin/storefront/custom-domain/domain-connect/complete",
            json={"attempt_id": "attempt-1"},
            headers={"Authorization": "Bearer route-test-token"},
        )
        retried = await client.post(
            "/admin/storefront/custom-domain/retry",
            json={"attempt_id": "attempt-1"},
        )
        observed = await client.post(
            "/admin/storefront/custom-domain/observe",
            json={"attempt_id": "attempt-1"},
        )
        instructions = await client.post(
            "/admin/storefront/custom-domain/instructions",
            json={
                "attempt_id": "attempt-1",
                "email": "dns@example.com",
                "note": "Please update these records.",
            },
        )
        listed_instructions = await client.get(
            "/admin/storefront/custom-domain/instructions",
            params={"attempt_id": "attempt-1"},
        )
        revoked = await client.delete(
            "/admin/storefront/custom-domain/instructions/link-1"
        )
        public_instructions = await client.get(
            "/api/storefront/domain-instructions/" + "t" * 43
        )

    assert verified.status_code == 200
    assert verified_attempt.status_code == 200
    assert authorized.status_code == 200
    assert started.status_code == 200
    assert callback.status_code == 303
    assert callback.headers["location"] == (
        "https://thespecialwedding.com/admin/packages?storefront=domain&attempt=attempt-1"
    )
    assert completed.status_code == 200
    assert retried.status_code == 200
    assert observed.status_code == 200
    assert instructions.json()["status"] == "sent"
    assert instructions.json()["link_id"] == "link-1"
    assert listed_instructions.status_code == 200
    assert listed_instructions.json()["links"][0]["recipient_hint"] == ("d***@e***.com")
    assert revoked.json() == {"status": "revoked"}
    assert public_instructions.status_code == 200
    assert public_instructions.headers["cache-control"] == "no-store, max-age=0"
    assert public_instructions.json()["hostname"] == "events.example.com"
    fake_domains.verify.assert_has_awaits(
        [call(owner), call(owner, attempt_id="attempt-1")]
    )
    fake_domains.list_instruction_links.assert_awaited_once_with(owner, "attempt-1")
    fake_connect.start.assert_has_awaits(
        [
            call(owner, "attempt-1"),
            call(owner, "attempt-1"),
        ]
    )
    fake_connect.complete.assert_awaited_once_with(owner, "attempt-1")


@pytest.mark.asyncio
async def test_domain_connect_completion_rejects_ambient_cookie_without_bearer(
    monkeypatch,
):
    fake_connect = SimpleNamespace(complete=AsyncMock())
    monkeypatch.setattr(
        storefront_api, "storefront_domain_connect_service", fake_connect
    )
    owner = _owner()
    app = _test_app()
    app.dependency_overrides[storefront_api.require_storefront_owner] = lambda: owner

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        cookies={"admin_token": "ambient-cookie-session"},
    ) as client:
        response = await client.post(
            "/admin/storefront/custom-domain/domain-connect/complete",
            json={"attempt_id": "attempt-1"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"]["code"] == "bearer_auth_required"
    fake_connect.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_domain_connect_callback_fails_closed_for_unsafe_frontend_origin(
    monkeypatch,
):
    fake_connect = SimpleNamespace(
        record_callback=AsyncMock(
            return_value={"attempt_id": "attempt-1", "state": "authorized"}
        )
    )
    monkeypatch.setattr(
        storefront_api, "storefront_domain_connect_service", fake_connect
    )
    monkeypatch.setattr(storefront_api.settings, "frontend_url", "http://example.com")
    app = _test_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/admin/storefront/custom-domain/domain-connect/callback",
            params={"flow": "x" * 43},
            follow_redirects=False,
        )

    assert response.status_code == 503
    assert "location" not in response.headers


@pytest.mark.asyncio
async def test_upload_route_requires_exact_file_contract_before_service_call(
    monkeypatch,
):
    fake_media = SimpleNamespace(
        reserve=AsyncMock(
            return_value={
                "asset_id": "asset-1",
                "upload_url": "https://upload.example.com/asset-1",
                "cdn_url": "https://cdn.example.com/asset-1.webp",
                "key": "storefront/owner/hero/asset-1.webp",
                "max_size_bytes": 5 * 1024 * 1024,
            }
        )
    )
    monkeypatch.setattr(storefront_api, "storefront_media_service", fake_media)
    app = _test_app()
    owner = _owner()
    app.dependency_overrides[get_current_user_extended] = lambda: owner
    app.dependency_overrides[storefront_api.require_planner_storefront] = lambda: (
        StorefrontEntitlements(
            owner_id=owner.user_data["_id"],
            plan_id="plan_signature",
            storefront_enabled=True,
            custom_domain_enabled=True,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        invalid = await client.get(
            "/admin/storefront/upload-url",
            params={
                "filename": "hero.webp",
                "slot": "hero",
                "content_type": "image/webp",
            },
        )
        valid = await client.get(
            "/admin/storefront/upload-url",
            params={
                "filename": "../../client-name.webp",
                "slot": "hero",
                "content_type": "image/webp",
                "size_bytes": 1024,
                "folder": "attacker-controlled",
            },
        )

    assert invalid.status_code == 422
    assert valid.status_code == 200
    fake_media.reserve.assert_awaited_once_with(
        owner,
        slot="hero",
        content_type="image/webp",
        size_bytes=1024,
    )
    assert "client-name" not in valid.json()["key"]
    assert "attacker-controlled" not in valid.json()["key"]
