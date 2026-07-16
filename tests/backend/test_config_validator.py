import asyncio
import importlib
import time
from types import SimpleNamespace

import pytest

from app.core.cache import cache
from app.core.settings import Environment
from app.services import config_validator


def test_slug_only_storefront_does_not_warn_for_optional_custom_domains(monkeypatch):
    monkeypatch.setattr(
        config_validator.settings, "storefront_custom_domains_enabled", False
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_api_token", None)
    monkeypatch.setattr(config_validator.settings, "cloudflare_saas_api_token", None)
    monkeypatch.setattr(config_validator.settings, "cloudflare_zone_id", None)
    monkeypatch.setattr(config_validator.settings, "storefront_fallback_origin", None)
    monkeypatch.setattr(config_validator.settings, "storefront_cname_target", None)
    monkeypatch.setattr(
        config_validator.settings, "s3_storefront_staging_bucket_name", None
    )

    assert config_validator._collect_storefront_configuration_recommendations() == []


def test_production_storefront_inquiry_protection_observes_redis_outage(
    monkeypatch,
):
    monkeypatch.setattr(
        config_validator.settings, "environment", Environment.PRODUCTION
    )
    monkeypatch.setattr(config_validator.settings, "redis_enabled", True)
    monkeypatch.setattr(config_validator.settings, "redis_host", "redis")
    monkeypatch.setattr(config_validator.settings, "redis_password", "secret")
    monkeypatch.setattr(
        config_validator.settings, "trusted_proxy_cidrs", ["172.26.0.0/16"]
    )
    monkeypatch.setattr(
        config_validator.settings,
        "trusted_proxy_client_ip_header",
        "X-Real-IP",
    )
    monkeypatch.setattr(cache, "enabled", False)
    monkeypatch.setattr(cache, "redis_client", None)

    recommendations = (
        config_validator._collect_storefront_inquiry_protection_recommendations()
    )

    assert recommendations == [
        "REDIS_RUNTIME: Shared Redis is configured but unavailable. New storefront "
        "inquiries remain fail-closed until connectivity is restored; storefront "
        "pages and the platform slug are unaffected."
    ]
    assert "secret" not in recommendations[0]


def test_production_storefront_inquiry_protection_requires_trusted_ingress_pair(
    monkeypatch,
):
    monkeypatch.setattr(
        config_validator.settings, "environment", Environment.PRODUCTION
    )
    monkeypatch.setattr(config_validator.settings, "redis_enabled", True)
    monkeypatch.setattr(config_validator.settings, "redis_host", "redis")
    monkeypatch.setattr(config_validator.settings, "redis_password", "secret")
    monkeypatch.setattr(config_validator.settings, "trusted_proxy_cidrs", [])
    monkeypatch.setattr(
        config_validator.settings, "trusted_proxy_client_ip_header", None
    )
    monkeypatch.setattr(cache, "enabled", True)
    monkeypatch.setattr(cache, "redis_client", object())

    recommendations = (
        config_validator._collect_storefront_inquiry_protection_recommendations()
    )

    assert len(recommendations) == 1
    assert recommendations[0].startswith(
        "TRUSTED_PROXY_CIDRS/TRUSTED_PROXY_CLIENT_IP_HEADER:"
    )


def test_partial_custom_domain_configuration_reports_missing_settings(monkeypatch):
    monkeypatch.setattr(
        config_validator.settings, "storefront_custom_domains_enabled", True
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_api_token", None)
    monkeypatch.setattr(config_validator.settings, "cloudflare_saas_api_token", None)
    monkeypatch.setattr(config_validator.settings, "cloudflare_zone_id", "zone-id")
    monkeypatch.setattr(config_validator.settings, "storefront_fallback_origin", None)
    monkeypatch.setattr(config_validator.settings, "storefront_cname_target", None)
    monkeypatch.setattr(
        config_validator.settings, "s3_storefront_staging_bucket_name", None
    )

    recommendations = (
        config_validator._collect_storefront_configuration_recommendations()
    )

    assert recommendations == [
        "CLOUDFLARE_SAAS_API_TOKEN: Custom domains are configured but the "
        "dedicated Cloudflare for SaaS token is missing.",
        "STOREFRONT_FALLBACK_ORIGIN: Custom domains are configured but the "
        "Cloudflare for SaaS fallback origin is missing.",
        "STOREFRONT_CNAME_TARGET: Custom domains are configured but the customer "
        "CNAME target is missing.",
    ]


def test_storefront_configuration_uses_settings_loaded_values_not_os_environ(
    monkeypatch,
):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_SAAS_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ZONE_ID", raising=False)
    monkeypatch.delenv("STOREFRONT_FALLBACK_ORIGIN", raising=False)
    monkeypatch.delenv("STOREFRONT_CNAME_TARGET", raising=False)
    monkeypatch.setattr(
        config_validator.settings, "storefront_custom_domains_enabled", True
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_api_token", "token")
    monkeypatch.setattr(
        config_validator.settings, "cloudflare_saas_api_token", "saas-token"
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_zone_id", "zone-id")
    monkeypatch.setattr(
        config_validator.settings,
        "storefront_fallback_origin",
        "storefront-origin.example.com",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "storefront_cname_target",
        "storefronts.example.com",
    )
    monkeypatch.setattr(
        config_validator.settings, "s3_storefront_staging_bucket_name", None
    )

    assert config_validator._collect_storefront_configuration_recommendations() == []


def test_storefront_configuration_warns_when_rollout_can_strand_cleanup(monkeypatch):
    monkeypatch.setattr(
        config_validator.settings, "storefront_custom_domains_enabled", True
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_api_token", None)
    monkeypatch.setattr(
        config_validator.settings, "cloudflare_saas_api_token", "saas-token"
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_zone_id", "zone-id")
    monkeypatch.setattr(
        config_validator.settings,
        "storefront_fallback_origin",
        "storefront-origin.example.com",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "storefront_cname_target",
        "storefronts.example.com",
    )
    monkeypatch.setattr(
        config_validator.settings, "s3_storefront_staging_bucket_name", None
    )
    monkeypatch.setattr(
        config_validator.settings, "storefront_cloudflare_mutations_enabled", True
    )
    monkeypatch.setattr(
        config_validator.settings, "storefront_cloudflare_cleanup_enabled", False
    )
    monkeypatch.setattr(
        config_validator.settings, "storefront_custom_domain_rollout_mode", "general"
    )

    recommendations = (
        config_validator._collect_storefront_configuration_recommendations()
    )

    assert any("disconnect cleanup is disabled" in item for item in recommendations)
    assert any(
        "external-provider acceptance receipt" in item for item in recommendations
    )


@pytest.mark.asyncio
async def test_storefront_privacy_is_preflighted_before_the_first_upload(monkeypatch):
    monkeypatch.setattr(
        config_validator.settings,
        "s3_storefront_staging_bucket_name",
        "storefront-staging",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "cloudflare_account_id",
        "0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_api_token", "secret")

    calls = []

    class FakeMediaStorage:
        async def require_private_storefront_staging(self, *, force_refresh=False):
            calls.append(force_refresh)
            raise RuntimeError(
                "Storefront staging requires an enabled expiry lifecycle rule"
            )

    recommendations = (
        await config_validator._collect_storefront_infrastructure_recommendations(
            FakeMediaStorage()
        )
    )

    assert calls == [True]
    assert recommendations == [
        "S3_STOREFRONT_STAGING_BUCKET_NAME: Storefront image uploads are unavailable "
        "because the private staging controls failed validation "
        "(Storefront staging requires an enabled expiry lifecycle rule)."
    ]


@pytest.mark.asyncio
async def test_storefront_privacy_warning_redacts_configured_secrets(monkeypatch):
    secret = "super-secret-cloudflare-token"
    monkeypatch.setattr(
        config_validator.settings,
        "s3_storefront_staging_bucket_name",
        "storefront-staging",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "cloudflare_account_id",
        "0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_api_token", secret)
    monkeypatch.setattr(config_validator.settings, "s3_access_key_id", "access-key")
    monkeypatch.setattr(
        config_validator.settings, "s3_secret_access_key", "s3-secret-key"
    )

    class FakeMediaStorage:
        async def require_private_storefront_staging(self, *, force_refresh=False):
            raise RuntimeError(
                f"provider denied {secret}, access-key, and s3-secret-key"
            )

    recommendations = (
        await config_validator._collect_storefront_infrastructure_recommendations(
            FakeMediaStorage()
        )
    )
    warning = recommendations[0]

    assert secret not in warning
    assert "access-key" not in warning
    assert "s3-secret-key" not in warning
    assert warning.count("[redacted]") == 3


def test_invalid_storefront_cname_is_reported_without_a_provider_call(monkeypatch):
    monkeypatch.setattr(
        config_validator.settings, "storefront_custom_domains_enabled", True
    )
    monkeypatch.setattr(
        config_validator.settings,
        "storefront_cname_target",
        "https://storefronts.example.com/path",
    )
    monkeypatch.setattr(
        config_validator.settings, "cloudflare_saas_api_token", "saas-token"
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_zone_id", "zone-id")
    monkeypatch.setattr(
        config_validator.settings,
        "storefront_fallback_origin",
        "storefront-origin.example.com",
    )
    monkeypatch.setattr(
        config_validator.settings, "s3_storefront_staging_bucket_name", None
    )

    recommendations = (
        config_validator._collect_storefront_configuration_recommendations()
    )

    assert recommendations == [
        "STOREFRONT_CNAME_TARGET: Custom domains are unavailable because the "
        "configured CNAME target is not a bare valid hostname."
    ]


@pytest.mark.asyncio
async def test_storefront_privacy_preflight_has_a_short_aggregate_timeout(monkeypatch):
    monkeypatch.setattr(
        config_validator.settings,
        "s3_storefront_staging_bucket_name",
        "storefront-staging",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "cloudflare_account_id",
        "0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_api_token", "token")

    class HangingMediaStorage:
        async def require_private_storefront_staging(self, *, force_refresh=False):
            await asyncio.Event().wait()

    recommendations = (
        await config_validator._collect_storefront_infrastructure_recommendations(
            HangingMediaStorage(), timeout_seconds=0.001
        )
    )

    assert recommendations == [
        "S3_STOREFRONT_STAGING_BUCKET_NAME: Storefront private-bucket preflight "
        "timed out; uploads remain fail-closed until Cloudflare can be verified."
    ]


@pytest.mark.asyncio
async def test_external_storage_preflight_has_one_total_startup_timeout(monkeypatch):
    monkeypatch.setattr(
        config_validator.settings, "frontend_url", "https://app.example.com"
    )
    monkeypatch.setattr(
        config_validator.settings, "api_base_url", "https://api.example.com"
    )
    monkeypatch.setattr(config_validator.settings, "cors_origins", [])
    monkeypatch.setattr(
        config_validator.settings,
        "s3_storefront_staging_bucket_name",
        "storefront-staging",
    )
    monkeypatch.setattr(
        config_validator.settings,
        "cloudflare_account_id",
        "0123456789abcdef0123456789abcdef",
    )
    monkeypatch.setattr(config_validator.settings, "cloudflare_api_token", "token")

    class HangingMediaStorage:
        def target_health(self, target):
            return SimpleNamespace(
                bucket_name="configured-bucket",
                status="ready",
                issue=None,
                is_ready=True,
            )

        async def browser_upload_health(self, target, origins):
            await asyncio.Event().wait()

        async def require_private_storefront_staging(self, *, force_refresh=False):
            await asyncio.Event().wait()

    recommendations = await config_validator._collect_external_storage_recommendations(
        HangingMediaStorage(), timeout_seconds=0.001
    )

    assert recommendations == [
        "STOREFRONT_INFRASTRUCTURE: Read-only Cloudflare/R2 startup preflight "
        "timed out; optional upload capabilities remain fail-closed."
    ]


def test_local_storage_recommendations_can_skip_network_health_probes(monkeypatch):
    monkeypatch.setattr(config_validator.settings, "s3_endpoint_url", "configured")
    monkeypatch.setattr(config_validator.settings, "s3_access_key_id", "configured")
    monkeypatch.setattr(config_validator.settings, "s3_secret_access_key", "configured")

    class NetworkMustNotRun:
        def target_health(self, target):
            raise AssertionError("target health belongs inside the timed preflight")

    config_validator._collect_storage_recommendations(
        NetworkMustNotRun(), include_target_health=False
    )


@pytest.mark.asyncio
async def test_external_storage_deadline_is_not_blocked_by_sync_s3_health(monkeypatch):
    monkeypatch.setattr(
        config_validator.settings, "frontend_url", "https://app.example.com"
    )
    monkeypatch.setattr(
        config_validator.settings, "api_base_url", "https://api.example.com"
    )
    monkeypatch.setattr(config_validator.settings, "cors_origins", [])
    monkeypatch.setattr(
        config_validator.settings, "s3_storefront_staging_bucket_name", None
    )

    class BlockingMediaStorage:
        def target_health(self, target):
            time.sleep(0.1)
            return SimpleNamespace(
                bucket_name="configured-bucket",
                status="ready",
                issue=None,
                is_ready=True,
            )

    started_at = time.monotonic()
    recommendations = await config_validator._collect_external_storage_recommendations(
        BlockingMediaStorage(), timeout_seconds=0.005
    )
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.05
    assert recommendations == [
        "STOREFRONT_INFRASTRUCTURE: Read-only Cloudflare/R2 startup preflight "
        "timed out; optional upload capabilities remain fail-closed."
    ]


@pytest.mark.asyncio
async def test_browser_upload_unverifiable_issue_is_not_silently_dropped(monkeypatch):
    monkeypatch.setattr(
        config_validator.settings, "frontend_url", "https://app.example.com"
    )
    monkeypatch.setattr(
        config_validator.settings, "api_base_url", "https://api.example.com"
    )
    monkeypatch.setattr(config_validator.settings, "cors_origins", [])

    class FakeMediaStorage:
        def target_health(self, target):
            return SimpleNamespace(
                bucket_name="configured-bucket",
                status="ready",
                issue=None,
                is_ready=True,
            )

        async def browser_upload_health(self, target, origins):
            if target == config_validator.StorageTarget.STOREFRONT_STAGING:
                return SimpleNamespace(
                    status="unverifiable",
                    issue=(
                        "Cloudflare API credentials are not configured, so bucket "
                        "CORS could not be verified."
                    ),
                )
            return SimpleNamespace(status="ready", issue=None)

    recommendations = await config_validator._collect_browser_upload_recommendations(
        FakeMediaStorage()
    )

    assert recommendations == [
        "S3_STOREFRONT_STAGING_BUCKET_NAME: Cloudflare API credentials are not "
        "configured, so bucket CORS could not be verified."
    ]


@pytest.mark.asyncio
async def test_guest_media_domain_is_not_reported_as_missing_recommended_env(
    monkeypatch,
):
    for key in config_validator.CRITICAL_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    for key in config_validator.RECOMMENDED_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    monkeypatch.delenv("GUEST_MEDIA_DOMAIN", raising=False)

    calls = []
    clears = []

    async def fake_create_root_admin_notification(*, title, message, priority="high"):
        calls.append(
            {
                "title": title,
                "message": message,
                "priority": priority,
            }
        )

    async def fake_clear_config_notifications():
        clears.append("cleared")

    class FakeMediaStorage:
        def target_health(self, target):
            return SimpleNamespace(bucket_name="ok", status="ready", issue=None)

        async def browser_upload_health(self, target, origins):
            return SimpleNamespace(status="ready", issue=None)

    monkeypatch.setattr(
        config_validator,
        "_create_root_admin_notification",
        fake_create_root_admin_notification,
    )
    monkeypatch.setattr(
        config_validator,
        "clear_config_notifications",
        fake_clear_config_notifications,
    )
    monkeypatch.setattr(config_validator, "MediaStorage", FakeMediaStorage)

    importlib.reload(config_validator)
    monkeypatch.setattr(
        config_validator,
        "_create_root_admin_notification",
        fake_create_root_admin_notification,
    )
    monkeypatch.setattr(
        config_validator,
        "clear_config_notifications",
        fake_clear_config_notifications,
    )
    monkeypatch.setattr(config_validator, "MediaStorage", FakeMediaStorage)

    result = await config_validator.validate_environment_and_notify()

    assert "GUEST_MEDIA_DOMAIN" not in config_validator.RECOMMENDED_ENV_VARS
    assert result["missing_critical"] == []
    assert not any(
        "GUEST_MEDIA_DOMAIN" in item for item in result["missing_recommended"]
    )
    assert not any("GUEST_MEDIA_DOMAIN" in c["message"] for c in calls)
    if not result["missing_recommended"]:
        assert clears == ["cleared"]


@pytest.mark.asyncio
async def test_storage_recommendations_are_target_aware(monkeypatch):
    for key in config_validator.CRITICAL_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    for key in config_validator.RECOMMENDED_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    monkeypatch.setattr(
        config_validator.settings, "s3_endpoint_url", "https://storage.example.com"
    )
    monkeypatch.setattr(config_validator.settings, "s3_access_key_id", "access")
    monkeypatch.setattr(config_validator.settings, "s3_secret_access_key", "secret")
    monkeypatch.setattr(config_validator.settings, "s3_bucket_name", "primary-bucket")
    monkeypatch.setattr(
        config_validator.settings, "s3_guest_media_bucket_name", "guest-bucket"
    )
    monkeypatch.setattr(config_validator.settings, "s3_ad_bucket_name", None)
    monkeypatch.setattr(config_validator.settings, "s3_blog_bucket_name", "blog-bucket")
    monkeypatch.setattr(
        config_validator.settings, "s3_storefront_staging_bucket_name", None
    )
    monkeypatch.setattr(config_validator.settings, "ad_media_domain", None)
    monkeypatch.setattr(config_validator.settings, "blog_media_domain", None)

    calls = []

    async def fake_create_root_admin_notification(*, title, message, priority="high"):
        calls.append(
            {
                "title": title,
                "message": message,
                "priority": priority,
            }
        )

    async def fake_clear_config_notifications():
        raise AssertionError(
            "clear_config_notifications should not run when warnings exist"
        )

    class FakeMediaStorage:
        def target_health(self, target):
            if target == config_validator.StorageTarget.BLOG_ASSETS:
                return SimpleNamespace(
                    bucket_name="blog-bucket",
                    status="unavailable",
                    issue="Storage bucket 'blog-bucket' for target 'blog_assets' is configured but currently inaccessible (AccessDenied).",
                )
            return SimpleNamespace(bucket_name="ok", status="ready", issue=None)

        async def browser_upload_health(self, target, origins):
            return SimpleNamespace(status="ready", issue=None)

    monkeypatch.setattr(
        config_validator,
        "_create_root_admin_notification",
        fake_create_root_admin_notification,
    )
    monkeypatch.setattr(
        config_validator, "clear_config_notifications", fake_clear_config_notifications
    )
    monkeypatch.setattr(config_validator, "MediaStorage", FakeMediaStorage)

    result = await config_validator.validate_environment_and_notify()

    assert (
        "S3_AD_BUCKET_NAME: Dedicated ad-assets R2 bucket"
        in result["missing_recommended"]
    )
    assert (
        "BLOG_MEDIA_DOMAIN: Public CDN/domain for blog asset URLs"
        in result["missing_recommended"]
    )
    assert (
        "S3_STOREFRONT_STAGING_BUCKET_NAME: Private storefront-upload staging R2 bucket"
        in result["missing_recommended"]
    )
    assert any(
        item.startswith("S3_BLOG_BUCKET_NAME: Storage bucket 'blog-bucket'")
        for item in result["missing_recommended"]
    )
    assert not any("AD_MEDIA_DOMAIN" in item for item in result["missing_recommended"])
    assert (
        calls
        and calls[0]["title"] == "Configuration Warning: Missing Recommended Settings"
    )


@pytest.mark.asyncio
async def test_browser_upload_cors_warnings_are_target_aware(monkeypatch):
    for key in config_validator.CRITICAL_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    for key in config_validator.RECOMMENDED_ENV_VARS:
        monkeypatch.setenv(key, "configured")

    monkeypatch.setattr(
        config_validator.settings, "frontend_url", "http://localhost:3000"
    )
    monkeypatch.setattr(
        config_validator.settings, "api_base_url", "http://localhost:8000"
    )
    monkeypatch.setattr(
        config_validator.settings, "cors_origins", ["http://localhost:3000"]
    )
    monkeypatch.setattr(
        config_validator.settings, "s3_endpoint_url", "https://storage.example.com"
    )
    monkeypatch.setattr(config_validator.settings, "s3_access_key_id", "access")
    monkeypatch.setattr(config_validator.settings, "s3_secret_access_key", "secret")
    monkeypatch.setattr(config_validator.settings, "s3_bucket_name", "primary-bucket")
    monkeypatch.setattr(
        config_validator.settings, "s3_guest_media_bucket_name", "guest-bucket"
    )
    monkeypatch.setattr(config_validator.settings, "s3_ad_bucket_name", "ad-bucket")
    monkeypatch.setattr(config_validator.settings, "s3_blog_bucket_name", "blog-bucket")

    calls = []

    async def fake_create_root_admin_notification(*, title, message, priority="high"):
        calls.append(
            {
                "title": title,
                "message": message,
                "priority": priority,
            }
        )

    async def fake_clear_config_notifications():
        raise AssertionError(
            "clear_config_notifications should not run when warnings exist"
        )

    class FakeMediaStorage:
        def target_health(self, target):
            return SimpleNamespace(
                bucket_name="ok", status="ready", issue=None, is_ready=True
            )

        async def browser_upload_health(self, target, origins):
            if target == config_validator.StorageTarget.GUEST_MEDIA:
                return SimpleNamespace(
                    status="misconfigured",
                    issue=(
                        "Bucket 'guest-bucket' allows storage access but its CORS policy "
                        "does not allow browser PUT uploads with the Content-Type header "
                        "from: http://localhost:3000."
                    ),
                )
            return SimpleNamespace(status="ready", issue=None)

    monkeypatch.setattr(
        config_validator,
        "_create_root_admin_notification",
        fake_create_root_admin_notification,
    )
    monkeypatch.setattr(
        config_validator, "clear_config_notifications", fake_clear_config_notifications
    )
    monkeypatch.setattr(config_validator, "MediaStorage", FakeMediaStorage)

    result = await config_validator.validate_environment_and_notify()

    assert any(
        item.startswith(
            "S3_GUEST_MEDIA_BUCKET_NAME: Bucket 'guest-bucket' allows storage access"
        )
        for item in result["missing_recommended"]
    )
    assert not any(
        "S3_BUCKET_NAME:" in item and "CORS policy" in item
        for item in result["missing_recommended"]
    )
    assert (
        calls
        and calls[0]["title"] == "Configuration Warning: Missing Recommended Settings"
    )
