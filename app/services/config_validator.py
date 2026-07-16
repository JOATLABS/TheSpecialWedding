"""
Configuration Validator Service

Validates critical environment variables at startup and notifies root admin
of any missing configuration through:
1. Platform notification system (in-app notification)
2. Web Push notification (if admin has subscribed)
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlsplit

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.database import mongo
from app.core.settings import settings
from app.services.media_storage import MediaStorage, StorageTarget

logger = logging.getLogger(__name__)

# Lazy import to avoid circular imports
_web_push_service = None
_web_push_checked = False


def _get_web_push_service():
    """Lazy load web push service to avoid circular imports"""
    global _web_push_service, _web_push_checked
    if not _web_push_checked:
        _web_push_checked = True
        try:
            from app.services.web_push_service import web_push_service

            _web_push_service = web_push_service
        except ImportError:
            logger.warning("Web Push service not available")
            _web_push_service = None
    return _web_push_service


# Root admin email - the platform developer
ROOT_ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")

# Critical environment variables that MUST be set for the platform to function
CRITICAL_ENV_VARS = {
    "SECRET_KEY": "JWT/session signing key - SECURITY CRITICAL",
    "FRONTEND_URL": "Frontend URL for email links and redirects",
    "NEXT_PUBLIC_API_BASE_URL": "API base URL for backend services",
    "MEDIA_DOMAIN": "Media domain for S3/R2 file URLs",
    "GOOGLE_REDIRECT_URI": "Google OAuth callback URL",
}

# Optional but recommended environment variables that are not storage-target specific
RECOMMENDED_ENV_VARS = {
    "VAPID_PUBLIC_KEY": "Web Push VAPID public key for notifications",
    "VAPID_PRIVATE_KEY": "Web Push VAPID private key for notifications",
    "RESEND_API_KEY": "Email service API key",
    "STRIPE_SECRET_KEY": "Payment processing API key",
    "STRIPE_WEBHOOK_SECRET": "Stripe webhook signature verification",
    "TWILIO_ACCOUNT_SID": "SMS service credentials",
    "CLOUDFLARE_ACCOUNT_ID": "Cloudflare account identifier for Stream and R2 controls",
    "CLOUDFLARE_STREAM_API_TOKEN": "Cloudflare API token with Stream permissions",
}

STORAGE_RECOMMENDED_ENV_VARS = {
    "S3_ENDPOINT_URL": "S3/R2 storage endpoint URL",
    "S3_ACCESS_KEY_ID": "S3/R2 access key ID",
    "S3_SECRET_ACCESS_KEY": "S3/R2 secret access key",
    "S3_BUCKET_NAME": "S3/R2 bucket name for file uploads",
    "S3_GUEST_MEDIA_BUCKET_NAME": "Dedicated guest memories R2 bucket",
    "S3_AD_BUCKET_NAME": "Dedicated ad-assets R2 bucket",
    "S3_BLOG_BUCKET_NAME": "Dedicated blog-assets R2 bucket",
    "S3_STOREFRONT_STAGING_BUCKET_NAME": "Private storefront-upload staging R2 bucket",
}

STORAGE_TARGET_ENV_MAP = {
    StorageTarget.PRIMARY: "S3_BUCKET_NAME",
    StorageTarget.GUEST_MEDIA: "S3_GUEST_MEDIA_BUCKET_NAME",
    StorageTarget.AD_ASSETS: "S3_AD_BUCKET_NAME",
    StorageTarget.BLOG_ASSETS: "S3_BLOG_BUCKET_NAME",
    StorageTarget.STOREFRONT_STAGING: "S3_STOREFRONT_STAGING_BUCKET_NAME",
}


_DOMAIN_CONNECT_PROVIDER_ID = "thespecialwedding.com"
_DOMAIN_CONNECT_SERVICE_ID = "storefront-subdomain"
_DOMAIN_CONNECT_TEMPLATE_VERSION = 1
_DOMAIN_CONNECT_PUBLIC_KEY_DOMAIN = "domainconnect.thespecialwedding.com"
_DOMAIN_CONNECT_CALLBACK_PATH = (
    "/admin/storefront/custom-domain/domain-connect/callback"
)
_DOMAIN_CONNECT_CNAME_TARGET = "domains.thespecialwedding.com"
_DOMAIN_CONNECT_SERVICE_ID_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_DOMAIN_CONNECT_KEY_ID_PATTERN = re.compile(r"_[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def _collect_storage_target_health_recommendations(
    storage: MediaStorage,
) -> List[str]:
    recommendations: List[str] = []
    for target, env_name in STORAGE_TARGET_ENV_MAP.items():
        health = storage.target_health(target)
        if health.bucket_name and health.status == "unavailable":
            recommendations.append(
                f"{env_name}: {health.issue} Verify the bucket name and signer permissions."
            )
    return recommendations


def _collect_storage_recommendations(
    storage: MediaStorage | None = None,
    *,
    include_target_health: bool = True,
) -> List[str]:
    recommended: List[str] = []

    if not settings.s3_endpoint_url:
        recommended.append(
            f"S3_ENDPOINT_URL: {STORAGE_RECOMMENDED_ENV_VARS['S3_ENDPOINT_URL']}"
        )
    if not settings.s3_access_key_id:
        recommended.append(
            f"S3_ACCESS_KEY_ID: {STORAGE_RECOMMENDED_ENV_VARS['S3_ACCESS_KEY_ID']}"
        )
    if not settings.s3_secret_access_key:
        recommended.append(
            f"S3_SECRET_ACCESS_KEY: {STORAGE_RECOMMENDED_ENV_VARS['S3_SECRET_ACCESS_KEY']}"
        )
    if not settings.primary_media_bucket_name:
        recommended.append(
            f"S3_BUCKET_NAME: {STORAGE_RECOMMENDED_ENV_VARS['S3_BUCKET_NAME']}"
        )
    if not settings.guest_media_bucket_name:
        recommended.append(
            "S3_GUEST_MEDIA_BUCKET_NAME: "
            f"{STORAGE_RECOMMENDED_ENV_VARS['S3_GUEST_MEDIA_BUCKET_NAME']}"
        )
    if not settings.ad_media_bucket_name:
        recommended.append(
            f"S3_AD_BUCKET_NAME: {STORAGE_RECOMMENDED_ENV_VARS['S3_AD_BUCKET_NAME']}"
        )
    if not settings.blog_media_bucket_name:
        recommended.append(
            f"S3_BLOG_BUCKET_NAME: {STORAGE_RECOMMENDED_ENV_VARS['S3_BLOG_BUCKET_NAME']}"
        )
    if not settings.storefront_staging_bucket_name:
        recommended.append(
            "S3_STOREFRONT_STAGING_BUCKET_NAME: "
            f"{STORAGE_RECOMMENDED_ENV_VARS['S3_STOREFRONT_STAGING_BUCKET_NAME']}"
        )

    if settings.ad_media_bucket_name and not settings.ad_media_domain:
        recommended.append("AD_MEDIA_DOMAIN: Public CDN/domain for ad asset URLs")
    if settings.blog_media_bucket_name and not settings.blog_media_domain:
        recommended.append("BLOG_MEDIA_DOMAIN: Public CDN/domain for blog asset URLs")

    if include_target_health and settings.s3_credentials_configured:
        storage = storage or MediaStorage()
        recommended.extend(_collect_storage_target_health_recommendations(storage))

    return recommended


async def _collect_browser_upload_recommendations(storage: MediaStorage) -> List[str]:
    recommendations: List[str] = []
    browser_origins = settings.browser_upload_origins
    if not browser_origins:
        return recommendations

    for target, env_name in STORAGE_TARGET_ENV_MAP.items():
        target_health = await asyncio.to_thread(storage.target_health, target)
        if not getattr(target_health, "is_ready", target_health.status == "ready"):
            continue

        upload_health = await storage.browser_upload_health(
            target, settings.browser_upload_origins
        )
        if (
            upload_health.status
            in {
                "misconfigured",
                "error",
                "unverifiable",
            }
            and upload_health.issue
        ):
            recommendations.append(f"{env_name}: {upload_health.issue}")

    return recommendations


def _is_nonempty(value: object) -> bool:
    return bool(str(value or "").strip())


def _is_valid_bare_hostname(value: object) -> bool:
    if not _is_nonempty(value):
        return False
    try:
        # Function-local import avoids the domain-service/settings import cycle.
        from app.services.storefront_domain_service import normalize_custom_hostname

        normalize_custom_hostname(str(value), platform_domains=())
    except (TypeError, ValueError):
        return False
    return True


def _is_valid_domain_connect_private_key(value: object) -> bool:
    """Validate the signing-key contract without logging or returning key material."""

    if not isinstance(value, str) or not value.strip():
        return False
    try:
        key = serialization.load_pem_private_key(value.encode(), password=None)
    except (TypeError, ValueError, UnsupportedAlgorithm):
        return False
    return isinstance(key, rsa.RSAPrivateKey) and key.key_size >= 2048


def _domain_connect_callback_is_safe(value: object, public_key_domain: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        split = urlsplit(value.strip())
        port = split.port
    except ValueError:
        return False
    return bool(
        split.scheme == "https"
        and split.hostname
        and split.hostname.lower()
        == str(public_key_domain or "").strip().rstrip(".").lower()
        and split.username is None
        and split.password is None
        and port in {None, 443}
        and split.path == _DOMAIN_CONNECT_CALLBACK_PATH
        and not split.query
        and not split.fragment
    )


def _collect_storefront_configuration_recommendations() -> List[str]:
    """Validate optional storefront capabilities from canonical loaded settings."""

    recommendations: List[str] = []
    upload_configured = bool(settings.storefront_staging_bucket_name)
    custom_domains_enabled = bool(settings.storefront_custom_domains_enabled)
    discovery_enabled = bool(
        getattr(settings, "storefront_domain_connect_discovery_enabled", False)
    )
    authorization_enabled = bool(
        getattr(settings, "storefront_domain_connect_authorization_enabled", False)
    )
    mutations_enabled = bool(
        getattr(settings, "storefront_cloudflare_mutations_enabled", False)
    )
    cleanup_enabled = bool(
        getattr(settings, "storefront_cloudflare_cleanup_enabled", False)
    )
    custom_domain_configured = bool(
        custom_domains_enabled
        or mutations_enabled
        or cleanup_enabled
        or settings.cloudflare_saas_api_token
        or settings.cloudflare_zone_id
        or settings.storefront_fallback_origin
        or settings.storefront_cname_target
    )

    if upload_configured and not settings.cloudflare_api_token:
        recommendations.append(
            "CLOUDFLARE_API_TOKEN: Storefront image uploads are configured but the "
            "scoped Cloudflare R2-control token is missing."
        )

    if custom_domain_configured:
        if not settings.cloudflare_saas_api_token:
            recommendations.append(
                "CLOUDFLARE_SAAS_API_TOKEN: Custom domains are configured but the "
                "dedicated Cloudflare for SaaS token is missing."
            )
        if not settings.cloudflare_zone_id:
            recommendations.append(
                "CLOUDFLARE_ZONE_ID: Custom domains are configured but the "
                "Cloudflare for SaaS zone identifier is missing."
            )
        if not settings.storefront_fallback_origin:
            recommendations.append(
                "STOREFRONT_FALLBACK_ORIGIN: Custom domains are configured but the "
                "Cloudflare for SaaS fallback origin is missing."
            )
        if not settings.storefront_cname_target:
            recommendations.append(
                "STOREFRONT_CNAME_TARGET: Custom domains are configured but the "
                "customer CNAME target is missing."
            )
        if not getattr(settings, "storefront_probe_ingress_secret", None):
            recommendations.append(
                "STOREFRONT_PROBE_INGRESS_SECRET: Custom domains are configured but "
                "the server-only Next-to-FastAPI verification credential is missing."
            )
        if mutations_enabled and not custom_domains_enabled:
            recommendations.append(
                "STOREFRONT_CUSTOM_DOMAINS_ENABLED: Cloudflare hostname mutations "
                "are enabled while the owner-scoped custom-domain capability is "
                "disabled. Provider mutations remain unavailable."
            )
        if mutations_enabled and not cleanup_enabled:
            recommendations.append(
                "STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED: New Cloudflare hostname "
                "mutations are enabled but disconnect cleanup is disabled. Enable "
                "cleanup before creating any provider hostname."
            )
        rollout_mode = getattr(
            settings, "storefront_custom_domain_rollout_mode", "allowlist"
        )
        if rollout_mode == "general":
            recommendations.append(
                "STOREFRONT_CUSTOM_DOMAIN_ROLLOUT_MODE: General availability is "
                "enabled. Confirm the external-provider acceptance receipt before "
                "leaving allowlist mode."
            )
        elif mutations_enabled and rollout_mode == "allowlist":
            # Use the same normalizer as the mutation gate. Invalid/wildcard entries
            # therefore cannot make startup diagnostics disagree with runtime policy.
            from app.services.storefront_domain_rollout import (
                StorefrontDomainRolloutPolicy,
            )

            rollout = StorefrontDomainRolloutPolicy.build(
                mode=rollout_mode,
                hostnames=getattr(
                    settings, "storefront_custom_domain_pilot_hostnames", ()
                ),
                owner_ids=getattr(
                    settings, "storefront_custom_domain_pilot_owner_ids", ()
                ),
            )
            if not rollout.hostnames and not rollout.owner_ids:
                recommendations.append(
                    "STOREFRONT_CUSTOM_DOMAIN_PILOT_HOSTNAMES/OWNER_IDS: Cloudflare "
                    "hostname mutations are enabled in allowlist mode, but no valid "
                    "exact pilot hostname or owner is configured. New setup remains "
                    "fail-closed."
                )

    cloudflare_api_token = getattr(settings, "cloudflare_api_token", None)
    cloudflare_saas_api_token = getattr(settings, "cloudflare_saas_api_token", None)
    if (
        _is_nonempty(cloudflare_api_token)
        and _is_nonempty(cloudflare_saas_api_token)
        and str(cloudflare_api_token) == str(cloudflare_saas_api_token)
    ):
        recommendations.append(
            "CLOUDFLARE_SAAS_API_TOKEN: The Cloudflare for SaaS token must be "
            "separate from the R2/Stream control token."
        )

    cname_target = settings.storefront_cname_target
    fallback_origin = settings.storefront_fallback_origin
    if cname_target and not _is_valid_bare_hostname(cname_target):
        recommendations.append(
            "STOREFRONT_CNAME_TARGET: Custom domains are unavailable because "
            "the configured CNAME target is not a bare valid hostname."
        )
    if fallback_origin and not _is_valid_bare_hostname(fallback_origin):
        recommendations.append(
            "STOREFRONT_FALLBACK_ORIGIN: Custom domains are unavailable because "
            "the configured fallback origin is not a bare valid hostname."
        )

    if discovery_enabled or authorization_enabled:
        if not custom_domains_enabled:
            recommendations.append(
                "STOREFRONT_CUSTOM_DOMAINS_ENABLED: Domain Connect is enabled while "
                "the custom-domain capability is disabled."
            )

        provider_id = getattr(settings, "domain_connect_provider_id", None)
        service_id = getattr(settings, "domain_connect_service_id", None)
        template_version = getattr(settings, "domain_connect_template_version", None)
        if str(provider_id or "").strip().lower() != _DOMAIN_CONNECT_PROVIDER_ID:
            recommendations.append(
                "DOMAIN_CONNECT_PROVIDER_ID: The configured provider does not match "
                "the reviewed storefront Domain Connect template."
            )
        if (
            not isinstance(service_id, str)
            or not _DOMAIN_CONNECT_SERVICE_ID_PATTERN.fullmatch(service_id.strip())
            or service_id.strip() != _DOMAIN_CONNECT_SERVICE_ID
        ):
            recommendations.append(
                "DOMAIN_CONNECT_SERVICE_ID: The configured service does not match "
                "the reviewed storefront Domain Connect template."
            )
        if template_version != _DOMAIN_CONNECT_TEMPLATE_VERSION:
            recommendations.append(
                "DOMAIN_CONNECT_TEMPLATE_VERSION: The configured version does not "
                "match the reviewed storefront Domain Connect template."
            )

    if authorization_enabled:
        if not discovery_enabled:
            recommendations.append(
                "STOREFRONT_DOMAIN_CONNECT_DISCOVERY_ENABLED: Automatic DNS "
                "authorization requires exact-template discovery to be enabled first."
            )
        if not mutations_enabled:
            recommendations.append(
                "STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED: Automatic DNS "
                "authorization requires the downstream hostname provisioning path."
            )

        private_key = getattr(settings, "domain_connect_private_key", None)
        if not _is_nonempty(private_key):
            recommendations.append(
                "DOMAIN_CONNECT_PRIVATE_KEY: Automatic DNS authorization is enabled "
                "but the RS256 signing key is missing."
            )
        elif not _is_valid_domain_connect_private_key(private_key):
            recommendations.append(
                "DOMAIN_CONNECT_PRIVATE_KEY: The configured signing key must be an "
                "unencrypted RSA private key of at least 2048 bits."
            )

        key_id = getattr(settings, "domain_connect_key_id", None)
        if not isinstance(key_id, str) or not _DOMAIN_CONNECT_KEY_ID_PATTERN.fullmatch(
            key_id.strip()
        ):
            recommendations.append(
                "DOMAIN_CONNECT_KEY_ID: Automatic DNS authorization requires a "
                "valid DNS public-key label."
            )

        public_key_domain = getattr(settings, "domain_connect_public_key_domain", None)
        if (
            not _is_valid_bare_hostname(public_key_domain)
            or str(public_key_domain).strip().rstrip(".").lower()
            != _DOMAIN_CONNECT_PUBLIC_KEY_DOMAIN
        ):
            recommendations.append(
                "DOMAIN_CONNECT_PUBLIC_KEY_DOMAIN: The configured public-key domain "
                "does not match the reviewed signed template."
            )

        callback_url = getattr(settings, "domain_connect_callback_url", None)
        if not _is_nonempty(callback_url):
            recommendations.append(
                "DOMAIN_CONNECT_CALLBACK_URL: Automatic DNS authorization is "
                "enabled but the HTTPS callback URL is missing."
            )
        elif not _domain_connect_callback_is_safe(callback_url, public_key_domain):
            recommendations.append(
                "DOMAIN_CONNECT_CALLBACK_URL: The callback must be the exact HTTPS "
                "storefront callback on DOMAIN_CONNECT_PUBLIC_KEY_DOMAIN with no "
                "credentials, custom port, query, or fragment."
            )

        if str(cname_target or "").strip().rstrip(".").lower() != (
            _DOMAIN_CONNECT_CNAME_TARGET
        ):
            recommendations.append(
                "STOREFRONT_CNAME_TARGET: Automatic DNS authorization does not "
                "match the fixed CNAME target in the reviewed Domain Connect template."
            )

    return list(dict.fromkeys(recommendations))


def _collect_storefront_inquiry_protection_recommendations() -> List[str]:
    """Report production inquiry-protection gaps without exposing Redis secrets."""

    if not settings.is_production():
        return []

    recommendations: List[str] = []
    redis_enabled = bool(getattr(settings, "redis_enabled", False))
    if not redis_enabled:
        recommendations.append(
            "REDIS_ENABLED: Production storefront inquiries require the shared "
            "Redis rate limiter. New inquiry submissions remain fail-closed until "
            "Redis is enabled; storefront pages and the platform slug are unaffected."
        )
    else:
        if not _is_nonempty(getattr(settings, "redis_host", None)):
            recommendations.append(
                "REDIS_HOST: Production storefront inquiry protection requires a "
                "shared Redis host."
            )
        if not _is_nonempty(getattr(settings, "redis_password", None)):
            recommendations.append(
                "REDIS_PASSWORD: Production storefront Redis must require a "
                "deployment-managed password."
            )

        # Startup validation runs after init_cache(). A configured-but-disconnected
        # cache is therefore an operational failure, not merely a missing setting.
        from app.core.cache import cache

        if not (cache.enabled and cache.redis_client):
            recommendations.append(
                "REDIS_RUNTIME: Shared Redis is configured but unavailable. New "
                "storefront inquiries remain fail-closed until connectivity is "
                "restored; storefront pages and the platform slug are unaffected."
            )

    trusted_cidrs = list(getattr(settings, "trusted_proxy_cidrs", ()) or ())
    trusted_header = getattr(settings, "trusted_proxy_client_ip_header", None)
    if not trusted_cidrs or not trusted_header:
        recommendations.append(
            "TRUSTED_PROXY_CIDRS/TRUSTED_PROXY_CLIENT_IP_HEADER: Production "
            "storefront inquiry limits require an explicitly trusted ingress CIDR "
            "and one ingress-overwritten client-IP header. Do not trust a forwarded "
            "header from arbitrary peers."
        )

    return recommendations


def get_storefront_domain_readiness() -> dict[str, object]:
    """Return non-secret, non-mutating readiness for new custom-domain setup.

    This capability state is deliberately separate from the platform storefront
    and publication state. A disabled or incomplete custom-domain control plane
    must never make an internal slug unavailable.
    """

    enabled = bool(settings.storefront_custom_domains_enabled)
    if not enabled:
        return {
            "enabled": False,
            "ready": False,
            "reason_code": "disabled",
            "missing": [],
        }

    if not settings.storefront_cloudflare_mutations_enabled:
        return {
            "enabled": True,
            "ready": False,
            "reason_code": "provider_mutations_disabled",
            "missing": [],
        }

    required = {
        "CLOUDFLARE_SAAS_API_TOKEN": settings.cloudflare_saas_api_token,
        "CLOUDFLARE_ZONE_ID": settings.cloudflare_zone_id,
        "STOREFRONT_FALLBACK_ORIGIN": settings.storefront_fallback_origin,
        "STOREFRONT_CNAME_TARGET": settings.storefront_cname_target,
        "STOREFRONT_PROBE_INGRESS_SECRET": getattr(
            settings, "storefront_probe_ingress_secret", None
        ),
    }
    missing = [name for name, value in required.items() if not str(value or "").strip()]
    if missing:
        return {
            "enabled": True,
            "ready": False,
            "reason_code": "configuration_unavailable",
            "missing": missing,
        }

    if not bool(getattr(settings, "storefront_cloudflare_cleanup_enabled", False)):
        return {
            "enabled": True,
            "ready": False,
            "reason_code": "configuration_unavailable",
            "missing": ["STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED"],
        }

    if _is_nonempty(getattr(settings, "cloudflare_api_token", None)) and str(
        settings.cloudflare_api_token
    ) == str(settings.cloudflare_saas_api_token):
        return {
            "enabled": True,
            "ready": False,
            "reason_code": "configuration_invalid",
            "missing": [],
        }

    if not _is_valid_bare_hostname(
        settings.storefront_fallback_origin
    ) or not _is_valid_bare_hostname(settings.storefront_cname_target):
        return {
            "enabled": True,
            "ready": False,
            "reason_code": "configuration_invalid",
            "missing": [],
        }

    if (
        getattr(settings, "storefront_custom_domain_rollout_mode", "allowlist")
        == "allowlist"
    ):
        from app.services.storefront_domain_rollout import (
            StorefrontDomainRolloutPolicy,
        )

        rollout = StorefrontDomainRolloutPolicy.build(
            mode="allowlist",
            hostnames=getattr(settings, "storefront_custom_domain_pilot_hostnames", ()),
            owner_ids=getattr(settings, "storefront_custom_domain_pilot_owner_ids", ()),
        )
        if not rollout.hostnames and not rollout.owner_ids:
            return {
                "enabled": True,
                "ready": False,
                "reason_code": "rollout_unavailable",
                "missing": [],
            }

    return {
        "enabled": True,
        "ready": True,
        "reason_code": "ready",
        "missing": [],
    }


async def _collect_storefront_infrastructure_recommendations(
    storage: MediaStorage | None,
    *,
    timeout_seconds: float = 3.0,
) -> List[str]:
    """Preflight optional storefront infrastructure without mutating provider state."""

    recommendations: List[str] = []
    if not (
        storage
        and settings.storefront_staging_bucket_name
        and settings.cloudflare_account_id
        and settings.cloudflare_api_token
    ):
        return recommendations

    try:
        await asyncio.wait_for(
            storage.require_private_storefront_staging(force_refresh=True),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        recommendations.append(
            "S3_STOREFRONT_STAGING_BUCKET_NAME: Storefront private-bucket preflight "
            "timed out; uploads remain fail-closed until Cloudflare can be verified."
        )
    except Exception as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        configured_secrets = {
            settings.cloudflare_api_token,
            settings.s3_access_key_id,
            settings.s3_secret_access_key,
        }
        for secret in sorted(
            (value for value in configured_secrets if value),
            key=len,
            reverse=True,
        ):
            detail = detail.replace(secret, "[redacted]")
        recommendations.append(
            "S3_STOREFRONT_STAGING_BUCKET_NAME: Storefront image uploads are "
            "unavailable because the private staging controls failed validation "
            f"({detail})."
        )

    return recommendations


async def _collect_external_storage_recommendations(
    storage: MediaStorage,
    *,
    timeout_seconds: float = 3.0,
) -> List[str]:
    """Bound all optional Cloudflare/R2 startup reads to one short deadline."""

    try:
        target_health, browser, storefront = await asyncio.wait_for(
            asyncio.gather(
                asyncio.to_thread(
                    _collect_storage_target_health_recommendations,
                    storage,
                ),
                _collect_browser_upload_recommendations(storage),
                _collect_storefront_infrastructure_recommendations(
                    storage,
                    timeout_seconds=timeout_seconds * 2,
                ),
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        return [
            "STOREFRONT_INFRASTRUCTURE: Read-only Cloudflare/R2 startup preflight "
            "timed out; optional upload capabilities remain fail-closed."
        ]
    return list(dict.fromkeys([*target_health, *browser, *storefront]))


async def validate_environment_and_notify() -> Dict[str, List[str]]:
    """
    Validate environment variables and create root admin notification if any are missing.

    Returns:
        Dict with 'missing_critical' and 'missing_recommended' lists
    """
    missing_critical = []
    missing_recommended = []

    # Check critical vars
    for var_name, description in CRITICAL_ENV_VARS.items():
        if not os.getenv(var_name):
            missing_critical.append(f"{var_name}: {description}")
            logger.error(
                f"CRITICAL: Missing environment variable {var_name} - {description}"
            )

    # Check recommended vars
    for var_name, description in RECOMMENDED_ENV_VARS.items():
        if not os.getenv(var_name):
            missing_recommended.append(f"{var_name}: {description}")
    missing_recommended.extend(_collect_storefront_configuration_recommendations())
    missing_recommended.extend(_collect_storefront_inquiry_protection_recommendations())
    storage = MediaStorage() if settings.s3_credentials_configured else None
    missing_recommended.extend(
        _collect_storage_recommendations(storage, include_target_health=False)
    )
    if storage is not None:
        missing_recommended.extend(
            await _collect_external_storage_recommendations(storage)
        )
    missing_recommended = list(dict.fromkeys(missing_recommended))
    for item in missing_recommended:
        logger.warning(f"RECOMMENDED: {item}")

    # If any critical vars are missing, notify root admin
    if missing_critical:
        await _create_root_admin_notification(
            title="CRITICAL: Missing Environment Configuration",
            message=_build_notification_message(missing_critical, missing_recommended),
            priority="critical",
        )
    elif missing_recommended:
        # Only notify about recommended if there are no critical issues
        await _create_root_admin_notification(
            title="Configuration Warning: Missing Recommended Settings",
            message=_build_notification_message([], missing_recommended),
            priority="high",
        )
    else:
        await clear_config_notifications()

    return {
        "missing_critical": missing_critical,
        "missing_recommended": missing_recommended,
    }


def _build_notification_message(critical: List[str], recommended: List[str]) -> str:
    """Build a detailed notification message"""
    parts = []

    if critical:
        parts.append("CRITICAL - These environment variables MUST be set:")
        for item in critical:
            parts.append(f"  • {item}")
        parts.append("")

    if recommended:
        parts.append(
            "RECOMMENDED - These variables should be set for full functionality:"
        )
        for item in recommended:
            parts.append(f"  • {item}")
        parts.append("")

    parts.append(
        "Update your .env file or deployment environment variables and restart the server."
    )

    return "\n".join(parts)


async def _create_root_admin_notification(
    title: str, message: str, priority: str = "high"
):
    """
    Create a notification for the root admin about configuration issues.
    Sends both:
    1. In-app notification (stored in database)
    2. Web Push notification (if admin has subscribed to push notifications)
    """
    # Send Web Push notification for immediate alerting
    await _send_push_alert(title, message, priority)

    try:
        notifications_collection = mongo.db["notifications"]

        # Check if we already have an unread notification about this
        existing = await notifications_collection.find_one(
            {
                "title": title,
                "type": "system_config",
                "status": "active",
                "read_by.user_id": {"$ne": ROOT_ADMIN_EMAIL},
            }
        )

        if existing:
            # Update the existing notification instead of creating a new one
            await notifications_collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "message": message,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            logger.info("Updated existing config notification for root admin")
            return

        # Create new notification
        notification = {
            "title": title,
            "message": message,
            "type": "system_config",
            "target_audience": "root_admin",
            "created_by": "system",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "is_dismissible": True,
            "priority": priority,
            "status": "active",
            "read_by": [],
            "dismissed_by": [],
            "metadata": {"source": "config_validator", "auto_generated": True},
        }

        await notifications_collection.insert_one(notification)
        logger.info(f"Created config notification for root admin: {title}")

    except Exception as e:
        # If we can't create the notification, at least log it prominently
        logger.critical(f"FAILED TO NOTIFY ROOT ADMIN: {title}")
        logger.critical(f"Message: {message}")
        logger.critical(f"Error: {str(e)}")


async def _send_push_alert(title: str, message: str, priority: str):
    """Send Web Push notification for critical config alerts to root admin"""
    web_push = _get_web_push_service()
    if not web_push or not web_push.enabled:
        logger.debug("Web Push service not available for config alert")
        return

    try:
        # Send to root admin if they have subscribed
        await web_push.send_notification(
            user_id=ROOT_ADMIN_EMAIL,
            title=title,
            body=message[:200] + "..." if len(message) > 200 else message,
            url="/admin/platform",
            tag="config-alert",
        )
    except Exception as e:
        logger.warning(f"Failed to send Web Push config alert: {e}")


async def clear_config_notifications():
    """
    Clear resolved configuration notifications.
    Call this when all config issues are fixed.
    """
    try:
        notifications_collection = mongo.db["notifications"]
        result = await notifications_collection.update_many(
            {"type": "system_config", "status": "active"},
            {"$set": {"status": "resolved", "resolved_at": datetime.now(timezone.utc)}},
        )
        if result.modified_count > 0:
            logger.info(
                f"Cleared {result.modified_count} resolved config notifications"
            )
    except Exception as e:
        logger.error(f"Error clearing config notifications: {str(e)}")
