from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.storefront import public_router, router
from app.models.storefront import StorefrontSettingsUpdate


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
        "/storefront/settings": {"GET", "POST"},
        "/storefront/preview/{slug}": {"GET"},
    }
    assert public_routes == {"/storefront/{identifier}": {"GET"}}


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
    assert route_methods["/admin/storefront/settings"] == {"GET", "POST"}
    assert route_methods["/admin/storefront/preview/{slug}"] == {"GET"}
    assert route_methods["/api/storefront/{identifier}"] == {"GET"}
    assert "/api/storefront/preview/{slug}" not in route_methods
