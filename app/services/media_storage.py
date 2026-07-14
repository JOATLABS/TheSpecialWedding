from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
import re
import threading
import time
from typing import Any, Optional
from urllib.parse import urlparse

import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.settings import settings


class StorageTarget(str, Enum):
    PRIMARY = "primary"
    GUEST_MEDIA = "guest_media"
    AD_ASSETS = "ad_assets"
    BLOG_ASSETS = "blog_assets"
    STOREFRONT_STAGING = "storefront_staging"
    FORM_UPLOADS = "form_uploads"


@dataclass(frozen=True)
class StorageTargetConfig:
    target: StorageTarget
    bucket_name: Optional[str]
    public_domain: Optional[str] = None

    @property
    def is_bucket_configured(self) -> bool:
        return bool(self.bucket_name)

    @property
    def host(self) -> Optional[str]:
        if not self.public_domain:
            return None
        return urlparse(self.public_domain).hostname


@dataclass(frozen=True)
class StorageTargetHealth:
    target: StorageTarget
    bucket_name: Optional[str]
    public_domain: Optional[str]
    status: str
    issue: Optional[str] = None

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"


@dataclass(frozen=True)
class StorageBrowserUploadHealth:
    target: StorageTarget
    bucket_name: Optional[str]
    origins: tuple[str, ...]
    status: str
    issue: Optional[str] = None

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"


class MediaStorage:
    """Centralized S3/R2 config, client construction, and target resolution."""

    _health_cache: dict[
        tuple[str, str, str, str, str], tuple[float, StorageTargetHealth]
    ] = {}
    _health_cache_lock = threading.Lock()
    _storefront_privacy_cache: dict[tuple[str, str, str, int], float] = {}

    def __init__(self) -> None:
        self.endpoint_url = settings.s3_endpoint_url
        self.access_key_id = settings.s3_access_key_id
        self.secret_access_key = settings.s3_secret_access_key
        self.region_name = settings.s3_region
        self.healthcheck_ttl_seconds = max(settings.s3_healthcheck_ttl_seconds, 0)
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
            config=Config(signature_version="s3v4"),
        )

    @property
    def client(self):
        return self._client

    @property
    def is_client_configured(self) -> bool:
        return settings.s3_credentials_configured

    def _health_cache_key(
        self, target_config: StorageTargetConfig
    ) -> tuple[str, str, str, str, str]:
        return (
            self.endpoint_url or "",
            self.access_key_id or "",
            self.region_name or "",
            target_config.target.value,
            target_config.bucket_name or "",
        )

    def _probe_target_health(
        self, target_config: StorageTargetConfig
    ) -> StorageTargetHealth:
        if not self.is_client_configured:
            return StorageTargetHealth(
                target=target_config.target,
                bucket_name=target_config.bucket_name,
                public_domain=target_config.public_domain,
                status="unconfigured",
                issue="S3/R2 credentials are not configured for media storage.",
            )

        if not target_config.bucket_name:
            return StorageTargetHealth(
                target=target_config.target,
                bucket_name=None,
                public_domain=target_config.public_domain,
                status="unconfigured",
                issue=f"Storage bucket is not configured for target '{target_config.target.value}'.",
            )

        try:
            self.client.list_objects_v2(Bucket=target_config.bucket_name, MaxKeys=1)
            return StorageTargetHealth(
                target=target_config.target,
                bucket_name=target_config.bucket_name,
                public_domain=target_config.public_domain,
                status="ready",
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            return StorageTargetHealth(
                target=target_config.target,
                bucket_name=target_config.bucket_name,
                public_domain=target_config.public_domain,
                status="unavailable",
                issue=(
                    f"Storage bucket '{target_config.bucket_name}' for target "
                    f"'{target_config.target.value}' is configured but currently inaccessible "
                    f"({error_code})."
                ),
            )
        except BotoCoreError as exc:
            return StorageTargetHealth(
                target=target_config.target,
                bucket_name=target_config.bucket_name,
                public_domain=target_config.public_domain,
                status="unavailable",
                issue=(
                    f"Storage bucket '{target_config.bucket_name}' for target "
                    f"'{target_config.target.value}' is configured but currently inaccessible "
                    f"({exc.__class__.__name__})."
                ),
            )

    def target_health(
        self, target: StorageTarget | str, *, force_refresh: bool = False
    ) -> StorageTargetHealth:
        target_config = self.target(target)
        cache_key = self._health_cache_key(target_config)

        if not force_refresh and self.healthcheck_ttl_seconds > 0:
            with self._health_cache_lock:
                cached = self._health_cache.get(cache_key)
                if (
                    cached
                    and (time.monotonic() - cached[0]) < self.healthcheck_ttl_seconds
                ):
                    return cached[1]

        health = self._probe_target_health(target_config)
        with self._health_cache_lock:
            self._health_cache[cache_key] = (time.monotonic(), health)
        return health

    def is_target_ready(self, target: StorageTarget | str) -> bool:
        return self.target_health(target).is_ready

    def target(self, target: StorageTarget | str) -> StorageTargetConfig:
        normalized = StorageTarget(target)
        if normalized == StorageTarget.PRIMARY:
            return StorageTargetConfig(
                target=normalized,
                bucket_name=settings.primary_media_bucket_name,
                public_domain=settings.normalized_media_domain,
            )
        if normalized == StorageTarget.GUEST_MEDIA:
            return StorageTargetConfig(
                target=normalized,
                bucket_name=settings.guest_media_bucket_name,
                public_domain=settings.normalized_guest_media_domain,
            )
        if normalized == StorageTarget.AD_ASSETS:
            return StorageTargetConfig(
                target=normalized,
                bucket_name=settings.ad_media_bucket_name,
                public_domain=settings.normalized_ad_media_domain,
            )
        if normalized == StorageTarget.BLOG_ASSETS:
            return StorageTargetConfig(
                target=normalized,
                bucket_name=settings.blog_media_bucket_name,
                public_domain=settings.normalized_blog_media_domain,
            )
        if normalized == StorageTarget.STOREFRONT_STAGING:
            return StorageTargetConfig(
                target=normalized,
                bucket_name=settings.storefront_staging_bucket_name,
                public_domain=None,
            )
        if normalized == StorageTarget.FORM_UPLOADS:
            return StorageTargetConfig(
                target=normalized,
                bucket_name=settings.form_uploads_bucket_name,
                public_domain=settings.normalized_form_uploads_domain,
            )
        raise ValueError(f"Unsupported storage target: {target}")

    def require_target(self, target: StorageTarget | str) -> StorageTargetConfig:
        target_config = self.target(target)
        health = self.target_health(target_config.target)
        if not health.is_ready:
            raise RuntimeError(
                health.issue
                or f"Storage target '{target_config.target.value}' is not available."
            )
        return target_config

    def build_public_url(self, target: StorageTarget | str, key: str) -> str:
        target_config = self.target(target)
        if target_config.target == StorageTarget.STOREFRONT_STAGING:
            raise RuntimeError("Storefront staging objects are private")
        if target_config.public_domain:
            return f"{target_config.public_domain}/{key}"
        return key

    def allowed_public_hosts(self, *targets: StorageTarget | str) -> list[str]:
        hosts: list[str] = []
        for target in targets:
            host = self.target(target).host
            if host and host not in hosts:
                hosts.append(host)
        return hosts

    def generate_presigned_put_url(
        self,
        target: StorageTarget | str,
        key: str,
        expires_in: int,
        content_type: Optional[str] = None,
        content_length: Optional[int] = None,
    ) -> str:
        target_config = self.require_target(target)
        params: dict[str, Any] = {"Bucket": target_config.bucket_name, "Key": key}
        if content_type:
            params["ContentType"] = content_type
        if content_length is not None:
            if (
                isinstance(content_length, bool)
                or not isinstance(content_length, int)
                or content_length <= 0
            ):
                raise ValueError("Content length must be a positive integer")
            params["ContentLength"] = content_length
        return self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def generate_presigned_get_url(
        self,
        target: StorageTarget | str,
        key: str,
        expires_in: int,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> str:
        target_config = self.require_target(target)
        params: dict[str, Any] = {"Bucket": target_config.bucket_name, "Key": key}
        if extra_params:
            params.update(extra_params)
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def upload_fileobj(
        self,
        fileobj: Any,
        target: StorageTarget | str,
        key: str,
        extra_args: Optional[dict[str, Any]] = None,
    ) -> None:
        target_config = self.require_target(target)
        self.client.upload_fileobj(
            fileobj,
            target_config.bucket_name,
            key,
            ExtraArgs=extra_args or {},
        )

    def delete_object(self, target: StorageTarget | str, key: str) -> None:
        target_config = self.require_target(target)
        self.client.delete_object(Bucket=target_config.bucket_name, Key=key)

    def list_objects_page(
        self,
        target: StorageTarget | str,
        prefix: str,
        limit: int,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        target_config = self.require_target(target)
        request: dict[str, Any] = {
            "Bucket": target_config.bucket_name,
            "Prefix": prefix,
            "MaxKeys": limit,
        }
        if cursor:
            request["ContinuationToken"] = cursor
        return self.client.list_objects_v2(**request)

    def head_object(self, target: StorageTarget | str, key: str) -> dict[str, Any]:
        target_config = self.require_target(target)
        return self.client.head_object(Bucket=target_config.bucket_name, Key=key)

    def copy_object(
        self,
        target: StorageTarget | str,
        source_key: str,
        destination_key: str,
        source_target: Optional[StorageTarget | str] = None,
        *,
        source_etag: Optional[str] = None,
    ) -> None:
        destination = self.require_target(target)
        source = self.require_target(source_target or target)
        request: dict[str, Any] = {
            "Bucket": destination.bucket_name,
            "CopySource": {"Bucket": source.bucket_name, "Key": source_key},
            "Key": destination_key,
        }
        if source_etag:
            request["CopySourceIfMatch"] = source_etag
        self.client.copy_object(
            **request,
        )

    def get_object_bytes(
        self,
        target: StorageTarget | str,
        key: str,
        *,
        source_etag: Optional[str] = None,
    ) -> bytes:
        target_config = self.require_target(target)
        request: dict[str, Any] = {"Bucket": target_config.bucket_name, "Key": key}
        if source_etag:
            request["IfMatch"] = source_etag
        response = self.client.get_object(**request)
        return response["Body"].read()

    @staticmethod
    def _parse_r2_endpoint_identity(endpoint_url: str | None) -> tuple[str, str]:
        """Return the immutable Cloudflare account/jurisdiction endpoint identity."""

        invalid = RuntimeError(
            "S3_ENDPOINT_URL must be an official account-scoped R2 endpoint"
        )
        if not isinstance(endpoint_url, str) or not endpoint_url.strip():
            raise invalid
        try:
            parsed = urlparse(endpoint_url.strip())
            port = parsed.port
        except ValueError as exc:
            raise invalid from exc
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise invalid

        labels = parsed.hostname.lower().rstrip(".").split(".")
        suffix = ["r2", "cloudflarestorage", "com"]
        if labels[-3:] != suffix:
            raise invalid
        prefix = labels[:-3]
        if len(prefix) == 1:
            account_id, jurisdiction = prefix[0], "default"
        elif len(prefix) == 2 and prefix[1] in {"eu", "fedramp"}:
            account_id, jurisdiction = prefix
        else:
            raise invalid
        if re.fullmatch(r"[0-9a-f]{32}", account_id) is None:
            raise invalid
        return account_id, jurisdiction

    async def require_private_storefront_staging(
        self, *, force_refresh: bool = False
    ) -> None:
        """Fail closed unless the staging bucket is private and self-expiring."""

        staging = await asyncio.to_thread(
            self.require_target, StorageTarget.STOREFRONT_STAGING
        )
        bucket_name = staging.bucket_name or ""
        public_targets = (
            StorageTarget.PRIMARY,
            StorageTarget.GUEST_MEDIA,
            StorageTarget.AD_ASSETS,
            StorageTarget.BLOG_ASSETS,
            StorageTarget.FORM_UPLOADS,
        )
        for target in public_targets:
            public_config = self.target(target)
            if public_config.bucket_name and public_config.bucket_name == bucket_name:
                raise RuntimeError(
                    "Storefront staging bucket must differ from every public media bucket"
                )

        endpoint_account_id, jurisdiction = self._parse_r2_endpoint_identity(
            self.endpoint_url
        )
        account_id = (settings.cloudflare_account_id or "").strip().lower()
        api_token = (settings.cloudflare_api_token or "").strip()
        if not account_id or not api_token:
            raise RuntimeError(
                "Cloudflare account credentials are required to verify storefront staging privacy"
            )
        if re.fullmatch(r"[0-9a-f]{32}", account_id) is None:
            raise RuntimeError(
                "CLOUDFLARE_ACCOUNT_ID must be a 32-character hexadecimal account ID"
            )
        if account_id != endpoint_account_id:
            raise RuntimeError(
                "S3_ENDPOINT_URL and CLOUDFLARE_ACCOUNT_ID must identify the same Cloudflare account"
            )
        max_age_days = settings.storefront_staging_lifecycle_max_age_days
        cache_key = (account_id, jurisdiction, bucket_name, max_age_days)
        if not force_refresh and self.healthcheck_ttl_seconds > 0:
            with self._health_cache_lock:
                cached_at = self._storefront_privacy_cache.get(cache_key)
            if cached_at and time.monotonic() - cached_at < min(
                self.healthcheck_ttl_seconds, 60
            ):
                return

        try:
            managed, custom, lifecycle = await asyncio.gather(
                self._fetch_r2_bucket_control(
                    bucket_name,
                    "domains/managed",
                    account_id=account_id,
                    jurisdiction=jurisdiction,
                ),
                self._fetch_r2_bucket_control(
                    bucket_name,
                    "domains/custom",
                    account_id=account_id,
                    jurisdiction=jurisdiction,
                ),
                self._fetch_r2_bucket_control(
                    bucket_name,
                    "lifecycle",
                    account_id=account_id,
                    jurisdiction=jurisdiction,
                ),
            )
        except Exception as exc:
            raise RuntimeError(
                "Storefront staging privacy and lifecycle could not be verified"
            ) from exc

        if managed.get("enabled") is not False:
            raise RuntimeError(
                "Storefront staging managed public access (r2.dev) must be verifiably disabled"
            )
        domains = custom.get("domains")
        if not isinstance(domains, list):
            raise RuntimeError("Storefront staging custom domain status is invalid")
        if any(
            not isinstance(domain, dict) or domain.get("enabled") is not False
            for domain in domains
        ):
            raise RuntimeError(
                "Storefront staging custom domain access must be verifiably disabled"
            )

        rules = lifecycle.get("rules") or []
        required_prefix = "storefront/"
        lifecycle_ready = False
        max_age_seconds = max_age_days * 24 * 60 * 60
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict) or rule.get("enabled") is not True:
                    continue
                conditions = rule.get("conditions") or {}
                prefix = conditions.get("prefix", "")
                transition = rule.get("deleteObjectsTransition") or {}
                condition = transition.get("condition") or {}
                max_age = condition.get("maxAge")
                if (
                    isinstance(prefix, str)
                    and required_prefix.startswith(prefix)
                    and str(condition.get("type") or "").lower() == "age"
                    and isinstance(max_age, int)
                    and not isinstance(max_age, bool)
                    and 0 < max_age <= max_age_seconds
                ):
                    lifecycle_ready = True
                    break
        if not lifecycle_ready:
            raise RuntimeError(
                "Storefront staging requires an enabled expiry lifecycle rule for prefix "
                f"'{required_prefix}' with maxAge <= {max_age_seconds} seconds "
                f"({max_age_days} day(s))"
            )

        with self._health_cache_lock:
            self._storefront_privacy_cache[cache_key] = time.monotonic()

    async def _fetch_r2_bucket_control(
        self,
        bucket_name: str,
        suffix: str,
        *,
        account_id: str,
        jurisdiction: str,
    ) -> dict[str, Any]:
        api_token = (settings.cloudflare_api_token or "").strip()
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/r2/buckets/{bucket_name}/{suffix}"
        )
        headers = {"Authorization": f"Bearer {api_token}"}
        if jurisdiction != "default":
            headers["cf-r2-jurisdiction"] = jurisdiction
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise RuntimeError("Cloudflare returned an invalid R2 control response")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Cloudflare returned an invalid R2 control result")
        return result

    async def browser_upload_health(
        self, target: StorageTarget | str, origins: list[str] | tuple[str, ...]
    ) -> StorageBrowserUploadHealth:
        target_config = self.target(target)
        target_health = await asyncio.to_thread(
            self.target_health, target_config.target
        )
        normalized_origins = tuple(
            dict.fromkeys(origin.strip() for origin in origins if origin)
        )

        if not target_health.is_ready:
            return StorageBrowserUploadHealth(
                target=target_config.target,
                bucket_name=target_config.bucket_name,
                origins=normalized_origins,
                status=target_health.status,
                issue=target_health.issue,
            )

        if not normalized_origins:
            return StorageBrowserUploadHealth(
                target=target_config.target,
                bucket_name=target_config.bucket_name,
                origins=normalized_origins,
                status="unverifiable",
            )

        if not settings.cloudflare_account_id or not settings.cloudflare_api_token:
            return StorageBrowserUploadHealth(
                target=target_config.target,
                bucket_name=target_config.bucket_name,
                origins=normalized_origins,
                status="unverifiable",
                issue=(
                    "Cloudflare API credentials are not configured, so bucket CORS "
                    f"for '{target_config.target.value}' could not be verified."
                ),
            )

        try:
            cors_rules = await self._fetch_bucket_cors_rules(
                target_config.bucket_name or ""
            )
        except Exception as exc:
            return StorageBrowserUploadHealth(
                target=target_config.target,
                bucket_name=target_config.bucket_name,
                origins=normalized_origins,
                status="error",
                issue=(
                    f"Bucket '{target_config.bucket_name}' is reachable, but its browser-upload "
                    f"CORS policy could not be verified ({exc})."
                ),
            )

        missing_origins = [
            origin
            for origin in normalized_origins
            if not self._cors_rules_allow_browser_put(cors_rules, origin)
        ]

        if missing_origins:
            return StorageBrowserUploadHealth(
                target=target_config.target,
                bucket_name=target_config.bucket_name,
                origins=normalized_origins,
                status="misconfigured",
                issue=(
                    f"Bucket '{target_config.bucket_name}' allows storage access but its CORS "
                    "policy does not allow browser PUT uploads with the Content-Type header "
                    f"from: {', '.join(missing_origins)}."
                ),
            )

        return StorageBrowserUploadHealth(
            target=target_config.target,
            bucket_name=target_config.bucket_name,
            origins=normalized_origins,
            status="ready",
        )

    @staticmethod
    def _cors_rules_allow_browser_put(
        rules: list[dict[str, Any]],
        origin: str,
        *,
        required_headers: tuple[str, ...] = ("content-type",),
    ) -> bool:
        normalized_required_headers = {header.lower() for header in required_headers}
        for rule in rules:
            allowed = rule.get("allowed") or {}
            methods = {str(method).upper() for method in allowed.get("methods") or []}
            if "PUT" not in methods and "*" not in methods:
                continue

            origins = {str(item).rstrip("/") for item in allowed.get("origins") or []}
            if "*" not in origins and origin.rstrip("/") not in origins:
                continue

            headers = {str(header).lower() for header in allowed.get("headers") or []}
            if "*" in headers or normalized_required_headers.issubset(headers):
                return True

        return False

    async def _fetch_bucket_cors_rules(self, bucket_name: str) -> list[dict[str, Any]]:
        endpoint_account_id, jurisdiction = self._parse_r2_endpoint_identity(
            self.endpoint_url
        )
        account_id = (settings.cloudflare_account_id or "").strip().lower()
        if account_id != endpoint_account_id:
            raise RuntimeError(
                "S3_ENDPOINT_URL and CLOUDFLARE_ACCOUNT_ID must identify the same Cloudflare account"
            )
        response_schema = dict[str, Any]
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/r2/buckets/{bucket_name}/cors"
        )
        headers = {"Authorization": f"Bearer {settings.cloudflare_api_token}"}
        if jurisdiction != "default":
            headers["cf-r2-jurisdiction"] = jurisdiction
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload: response_schema = response.json()

        if not payload.get("success"):
            errors = payload.get("errors") or []
            message = (
                "; ".join(
                    str(error.get("message", "Unknown error"))
                    for error in errors
                    if isinstance(error, dict)
                )
                or "Unknown error"
            )
            raise RuntimeError(message)

        result = payload.get("result") or {}
        rules = result.get("rules") or []
        if not isinstance(rules, list):
            raise RuntimeError("Unexpected Cloudflare R2 bucket CORS response shape.")
        return rules
