from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.settings import Settings
from app.services.cloudflare_service import CloudflareService
from app.services import config_validator
from testbed.validate_storefront_domain_connect_template import (
    TemplateValidationError,
    validate_template,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


DOMAIN_SETTING_ALIASES = {
    "storefront_custom_domains_enabled": "STOREFRONT_CUSTOM_DOMAINS_ENABLED",
    "storefront_domain_connect_discovery_enabled": (
        "STOREFRONT_DOMAIN_CONNECT_DISCOVERY_ENABLED"
    ),
    "storefront_domain_connect_authorization_enabled": (
        "STOREFRONT_DOMAIN_CONNECT_AUTHORIZATION_ENABLED"
    ),
    "storefront_cloudflare_mutations_enabled": (
        "STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED"
    ),
    "storefront_cloudflare_cleanup_enabled": ("STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED"),
    "storefront_custom_domain_rollout_mode": ("STOREFRONT_CUSTOM_DOMAIN_ROLLOUT_MODE"),
    "storefront_custom_domain_pilot_hostnames": (
        "STOREFRONT_CUSTOM_DOMAIN_PILOT_HOSTNAMES"
    ),
    "storefront_custom_domain_pilot_owner_ids": (
        "STOREFRONT_CUSTOM_DOMAIN_PILOT_OWNER_IDS"
    ),
    "cloudflare_saas_api_token": "CLOUDFLARE_SAAS_API_TOKEN",
    "storefront_fallback_origin": "STOREFRONT_FALLBACK_ORIGIN",
    "storefront_probe_ingress_secret": "STOREFRONT_PROBE_INGRESS_SECRET",
    "domain_connect_provider_id": "DOMAIN_CONNECT_PROVIDER_ID",
    "domain_connect_service_id": "DOMAIN_CONNECT_SERVICE_ID",
    "domain_connect_template_version": "DOMAIN_CONNECT_TEMPLATE_VERSION",
    "domain_connect_private_key": "DOMAIN_CONNECT_PRIVATE_KEY",
    "domain_connect_key_id": "DOMAIN_CONNECT_KEY_ID",
    "domain_connect_public_key_domain": "DOMAIN_CONNECT_PUBLIC_KEY_DOMAIN",
    "domain_connect_callback_url": "DOMAIN_CONNECT_CALLBACK_URL",
}


def test_storefront_domain_control_plane_has_typed_independent_feature_flags():
    fields = Settings.model_fields

    for field_name, alias in DOMAIN_SETTING_ALIASES.items():
        assert fields[field_name].alias == alias

    for field_name in (
        "storefront_custom_domains_enabled",
        "storefront_domain_connect_discovery_enabled",
        "storefront_domain_connect_authorization_enabled",
        "storefront_cloudflare_mutations_enabled",
        "storefront_cloudflare_cleanup_enabled",
    ):
        assert fields[field_name].annotation is bool
        assert fields[field_name].default is False

    assert fields["storefront_custom_domain_rollout_mode"].default == "allowlist"
    assert fields["storefront_custom_domain_pilot_hostnames"].default_factory() == []
    assert fields["storefront_custom_domain_pilot_owner_ids"].default_factory() == []


class _ProviderResponse:
    status_code = 200
    is_success = True

    @staticmethod
    def json():
        return {"success": True, "result": []}


class _RecordingHttpClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return _ProviderResponse()


@pytest.mark.asyncio
async def test_cloudflare_custom_hostnames_use_only_the_dedicated_saas_token(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.cloudflare_service.settings",
        SimpleNamespace(
            cloudflare_saas_api_token="saas-token",
            cloudflare_api_token="r2-control-token",
            cloudflare_zone_id="zone-id",
        ),
    )
    transport = _RecordingHttpClient()
    service = CloudflareService(http_client=transport)

    await service.list_custom_hostnames("events.customer.example")

    authorization = transport.calls[0]["headers"]["Authorization"]
    assert authorization == "Bearer saas-token"
    assert "r2-control-token" not in authorization


def test_legacy_r2_control_token_does_not_silently_enable_custom_hostnames(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.cloudflare_service.settings",
        SimpleNamespace(
            cloudflare_saas_api_token=None,
            cloudflare_api_token="r2-control-token",
            cloudflare_zone_id="zone-id",
        ),
    )

    assert CloudflareService().is_configured is False


def test_domain_readiness_fails_closed_without_disabling_the_platform_storefront(
    monkeypatch,
):
    monkeypatch.setattr(
        config_validator,
        "settings",
        SimpleNamespace(
            storefront_custom_domains_enabled=True,
            storefront_cloudflare_mutations_enabled=True,
            cloudflare_saas_api_token=None,
            cloudflare_zone_id=None,
            storefront_fallback_origin=None,
            storefront_cname_target=None,
            storefront_probe_ingress_secret=None,
            storefront_platform_domains=["thespecialwedding.io"],
        ),
    )

    readiness = config_validator.get_storefront_domain_readiness()

    assert readiness == {
        "enabled": True,
        "ready": False,
        "reason_code": "configuration_unavailable",
        "missing": [
            "CLOUDFLARE_SAAS_API_TOKEN",
            "CLOUDFLARE_ZONE_ID",
            "STOREFRONT_FALLBACK_ORIGIN",
            "STOREFRONT_CNAME_TARGET",
            "STOREFRONT_PROBE_INGRESS_SECRET",
        ],
    }
    assert "storefront_enabled" not in readiness
    assert "publication" not in readiness


def test_env_compose_and_testbed_expose_the_same_storefront_runtime_contract():
    root_env = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    testbed_env = (REPO_ROOT / "testbed" / ".env.example").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")

    required = {
        *DOMAIN_SETTING_ALIASES.values(),
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_ZONE_ID",
        "STOREFRONT_CNAME_TARGET",
        "STOREFRONT_PLATFORM_DOMAINS",
        "STOREFRONT_PROBE_INGRESS_SECRET",
        "S3_STOREFRONT_STAGING_BUCKET_NAME",
        "S3_REGION",
        "BLOG_MEDIA_DOMAIN",
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
        "RESEND_FROM_NAME",
        "REDIS_ENABLED",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_PASSWORD",
        "REDIS_DB",
        "REDIS_MAX_CONNECTIONS",
        "TRUSTED_PROXY_CIDRS",
        "TRUSTED_PROXY_CLIENT_IP_HEADER",
    }
    for variable in sorted(required):
        assert f"{variable}=" in root_env
        assert f"{variable}=" in testbed_env
        assert f"- {variable}=${{{variable}" in compose


def test_storefront_probe_ingress_secret_rejects_weak_values():
    with pytest.raises(ValueError, match="STOREFRONT_PROBE_INGRESS_SECRET"):
        Settings.model_validate(
            {
                "SECRET_KEY": "test-secret-key-that-is-longer-than-32-bytes",
                "CORS_ORIGINS": ["http://127.0.0.1:3000"],
                "STOREFRONT_PROBE_INGRESS_SECRET": "too-short",
            }
        )


def test_production_compose_matches_cache_manager_and_trusted_ingress_contract():
    fields = Settings.model_fields
    compose = (REPO_ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
    nginx = (REPO_ROOT / "nginx-load-balancer.conf").read_text(encoding="utf-8")

    expected_aliases = {
        "redis_enabled": "REDIS_ENABLED",
        "redis_host": "REDIS_HOST",
        "redis_port": "REDIS_PORT",
        "redis_password": "REDIS_PASSWORD",
        "redis_db": "REDIS_DB",
        "redis_max_connections": "REDIS_MAX_CONNECTIONS",
        "trusted_proxy_cidrs": "TRUSTED_PROXY_CIDRS",
        "trusted_proxy_client_ip_header": "TRUSTED_PROXY_CLIENT_IP_HEADER",
    }
    for field_name, alias in expected_aliases.items():
        assert fields[field_name].alias == alias
        assert f"- {alias}=${{{alias}" in compose

    for required_fragment in (
        "REDIS_ENABLED=${REDIS_ENABLED:-true}",
        "REDIS_HOST=${REDIS_HOST:-redis}",
        "REDIS_PASSWORD=${REDIS_PASSWORD:?",
        '--requirepass "$$REDIS_PASSWORD"',
        "REDISCLI_AUTH=$$REDIS_PASSWORD",
        'TRUSTED_PROXY_CIDRS=${TRUSTED_PROXY_CIDRS:-["172.26.0.0/16"]}',
        "TRUSTED_PROXY_CLIENT_IP_HEADER=${TRUSTED_PROXY_CLIENT_IP_HEADER:-X-Real-IP}",
    ):
        assert required_fragment in compose

    assert "proxy_set_header X-Real-IP $remote_addr;" in nginx
    assert "ports:" not in compose.split("  redis:", 1)[1].split("  mongo:", 1)[0]


def test_domain_connect_template_and_operator_runbook_are_shipped_but_unapproved():
    template_path = (
        REPO_ROOT
        / "domain-connect"
        / "templates"
        / "thespecialwedding.com.storefront-subdomain.json"
    )
    validator_path = (
        REPO_ROOT / "testbed" / "validate_storefront_domain_connect_template.py"
    )
    guide = (
        REPO_ROOT / "docs" / "guides" / "STOREFRONT_INFRASTRUCTURE_SETUP.md"
    ).read_text(encoding="utf-8")

    assert template_path.is_file()
    assert validator_path.is_file()
    for required_text in (
        "storefront-origin.thespecialwedding.com",
        "domains.thespecialwedding.com",
        "domainconnect.thespecialwedding.com",
        "Cloudflare",
        "GoDaddy",
        "Namecheap",
        "Squarespace",
        "Route 53",
        "operator_review",
        "tombstone",
        "official Domain Connect templates repository",
    ):
        assert required_text in guide
    assert "automatic configuration is approved" not in guide.lower()


def test_domain_connect_template_matches_the_fixed_signed_subdomain_contract():
    payload = validate_template()

    assert payload["syncBlock"] is False
    assert payload["hostRequired"] is True
    assert payload["syncPubKeyDomain"] == "domainconnect.thespecialwedding.com"
    assert payload["records"][1]["pointsTo"] == "domains.thespecialwedding.com"


def test_domain_connect_validator_rejects_an_unreviewed_routing_target(tmp_path):
    source = (
        REPO_ROOT
        / "domain-connect"
        / "templates"
        / "thespecialwedding.com.storefront-subdomain.json"
    )
    tampered = tmp_path / source.name
    tampered.write_text(
        source.read_text(encoding="utf-8").replace(
            "domains.thespecialwedding.com", "attacker.example"
        ),
        encoding="utf-8",
    )

    with pytest.raises(TemplateValidationError, match="CNAME target drift"):
        validate_template(tampered)
