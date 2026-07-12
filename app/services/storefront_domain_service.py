"""Owner-scoped storefront custom-domain lifecycle.

Custom domains are child records, separate from storefront settings. The
service reserves a normalized hostname locally before provisioning it at the
provider, persists validation state, compensates partial creates, and never
deletes or rewrites a mapping merely because its entitlement is later lost.
"""

from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import logging
import re
from typing import Any, Iterable
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.constants.roles import is_wedding_planner_role
from app.core.database import mongo
from app.core.settings import settings
from app.services.cloudflare_service import CloudflareService, CloudflareServiceError
from app.services.storefront_entitlement_service import (
    StorefrontEntitlementResolutionError,
    StorefrontEntitlementService,
    storefront_entitlement_service,
)
from app.utils.planner_ownership import normalize_planner_id


logger = logging.getLogger(__name__)

_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_DEFAULT_PLATFORM_DOMAINS = frozenset({"thespecialwedding.io", "thespecialwedding.com"})
_PROVIDER_DELETE_PENDING = "provider_delete_pending"
_PROVIDER_DELETE_RETRY_PENDING = "retry_pending"
_LOCAL_CLEANUP_PENDING = "local_cleanup_pending"
_DELETION_STATUSES = frozenset(
    {
        _PROVIDER_DELETE_PENDING,
        _PROVIDER_DELETE_RETRY_PENDING,
        _LOCAL_CLEANUP_PENDING,
    }
)
_NON_ROUTABLE_DOMAIN_STATUSES = frozenset(
    {"deleting", "delete_failed", "provider_deleted"}
)


def _ascii_hostname(value: str) -> str:
    labels: list[str] = []
    for label in value.split("."):
        if not label:
            raise ValueError("Custom domain contains an empty hostname label")
        try:
            ascii_label = label.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ValueError("Custom domain contains an invalid IDNA label") from exc
        if len(ascii_label) > 63 or not _HOST_LABEL.fullmatch(ascii_label):
            raise ValueError("Custom domain contains an invalid hostname label")
        labels.append(ascii_label)
    return ".".join(labels)


def normalize_custom_hostname(
    value: str,
    *,
    platform_domains: Iterable[str] | None = None,
) -> str:
    """Normalize a hostname-only custom domain or reject unsafe input."""

    if not isinstance(value, str) or not value:
        raise ValueError("Custom domain must be a hostname")
    if value != value.strip() or any(character.isspace() for character in value):
        raise ValueError("Custom domain cannot contain whitespace")
    if any(marker in value for marker in ("://", "@", ":", "/", "?", "#", "*")):
        raise ValueError(
            "Enter a hostname only, without a URL, port, path, or wildcard"
        )
    if value.endswith("."):
        raise ValueError("Custom domain must not end with a dot")

    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses cannot be used as custom domains")

    hostname = _ascii_hostname(value)
    if len(hostname) > 253 or "." not in hostname:
        raise ValueError("Custom domain must be a fully qualified hostname")
    if hostname.rsplit(".", 1)[-1].isdigit():
        raise ValueError("Custom domain must not use a numeric top-level label")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Localhost cannot be used as a custom domain")

    blocked_domains: set[str] = set()
    blocked_source = (
        _DEFAULT_PLATFORM_DOMAINS if platform_domains is None else platform_domains
    )
    for platform_domain in blocked_source:
        if not isinstance(platform_domain, str):
            continue
        candidate = platform_domain.strip().lower().rstrip(".")
        if not candidate:
            continue
        try:
            blocked_domains.add(_ascii_hostname(candidate))
        except ValueError:
            continue
    if any(
        hostname == platform_domain or hostname.endswith(f".{platform_domain}")
        for platform_domain in blocked_domains
    ):
        raise ValueError("Platform-owned hostnames cannot be mapped as custom domains")
    return hostname


class StorefrontDomainService:
    """Provision and resolve planner-owned custom storefront hostnames."""

    def __init__(
        self,
        mongo_client: Any | None = None,
        cloudflare_service: CloudflareService | None = None,
        entitlement_service: StorefrontEntitlementService | None = None,
        *,
        cname_target: str | None = None,
        platform_domains: Iterable[str] | None = None,
    ) -> None:
        self._mongo = mongo_client or mongo
        self._cloudflare = cloudflare_service or CloudflareService()
        self._entitlements = entitlement_service or storefront_entitlement_service
        configured_cname = (
            settings.storefront_cname_target if cname_target is None else cname_target
        )
        try:
            self._cname_target = (
                normalize_custom_hostname(configured_cname, platform_domains=())
                if configured_cname
                else None
            )
        except (TypeError, ValueError):
            self._cname_target = None
        configured_platform_domains = (
            settings.storefront_platform_domains
            if platform_domains is None
            else platform_domains
        )
        self._platform_domains = set(
            configured_platform_domains or _DEFAULT_PLATFORM_DOMAINS
        )
        frontend_hostname = urlparse(settings.frontend_url or "").hostname
        if frontend_hostname:
            self._platform_domains.add(frontend_hostname)
        if self._cname_target:
            self._platform_domains.add(self._cname_target)

    @staticmethod
    def _owner_data(owner: Any) -> dict:
        if isinstance(owner, dict):
            return owner
        user_data = dict(getattr(owner, "user_data", None) or {})
        role = getattr(owner, "role", None)
        if role:
            user_data["role"] = role
        return user_data

    @classmethod
    def _owner_id(cls, owner: Any) -> str:
        user_data = cls._owner_data(owner)
        owner_id = normalize_planner_id(user_data.get("_id"))
        if not owner_id or not is_wedding_planner_role(user_data.get("role")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Planner-owner access required",
            )
        return owner_id

    async def _require_custom_domain(self, owner: Any):
        user_data = self._owner_data(owner)
        self._owner_id(user_data)
        try:
            entitlements = await self._entitlements.resolve_for_owner(user_data)
        except StorefrontEntitlementResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain eligibility is temporarily unavailable",
            ) from exc
        if not (entitlements.storefront_enabled and entitlements.custom_domain_enabled):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "message": "Custom Domain is not included in the current plan",
                    "feature": "custom_domain",
                    "upgrade_required": True,
                },
            )
        return entitlements

    @staticmethod
    def _record_dict(value: object, allowed_fields: tuple[str, ...]) -> dict | None:
        if not isinstance(value, dict):
            return None
        result = {
            field: value[field]
            for field in allowed_fields
            if isinstance(value.get(field), (str, int, bool))
        }
        return result or None

    @classmethod
    def _validation_records(cls, ssl: object) -> list[dict]:
        if not isinstance(ssl, dict) or not isinstance(
            ssl.get("validation_records"), list
        ):
            return []
        records: list[dict] = []
        for record in ssl["validation_records"]:
            sanitized = cls._record_dict(
                record,
                (
                    "status",
                    "txt_name",
                    "txt_value",
                    "cname_name",
                    "cname_target",
                    "emails",
                ),
            )
            if sanitized:
                records.append(sanitized)
        return records

    @staticmethod
    def _status(value: object, fallback: str = "pending") -> str:
        if not isinstance(value, str) or not value.strip():
            return fallback
        return value.strip().lower()

    @classmethod
    def _provider_projection(cls, provider_result: dict) -> dict:
        ssl = provider_result.get("ssl")
        ssl_status = cls._status(ssl.get("status") if isinstance(ssl, dict) else None)
        provider_status = cls._status(provider_result.get("status"))
        return {
            "provider_status": provider_status,
            "ssl_status": ssl_status,
            "status": (
                "active"
                if provider_status == "active" and ssl_status == "active"
                else "pending"
            ),
            "ownership_verification": cls._record_dict(
                provider_result.get("ownership_verification"),
                ("type", "name", "value"),
            ),
            "ownership_verification_http": cls._record_dict(
                provider_result.get("ownership_verification_http"),
                ("http_url", "http_body"),
            ),
            "ssl_validation_records": cls._validation_records(ssl),
        }

    def _serialize(self, record: dict) -> dict:
        return {
            "hostname": record["hostname"],
            "status": self._status(record.get("status")),
            "provider_status": self._status(record.get("provider_status")),
            "ssl_status": self._status(record.get("ssl_status")),
            "ownership_verification": record.get("ownership_verification"),
            "ownership_verification_http": record.get("ownership_verification_http"),
            "ssl_validation_records": list(record.get("ssl_validation_records") or []),
            "cname_target": record.get("cname_target") or self._cname_target,
            "deletion_status": record.get("deletion_status"),
            "last_error": record.get("last_error"),
        }

    @staticmethod
    def _has_deletion_intent(record: dict) -> bool:
        deletion_status = record.get("deletion_status")
        return (
            isinstance(deletion_status, str)
            and deletion_status.strip().lower() in _DELETION_STATUSES
        ) or StorefrontDomainService._status(record.get("status")) in (
            _NON_ROUTABLE_DOMAIN_STATUSES
        )

    @staticmethod
    def _provider_not_found(exc: CloudflareServiceError) -> bool:
        """Return true only for an authoritative provider-level HTTP 404."""

        return exc.kind == "provider" and exc.provider_status_code == 404

    @staticmethod
    def _provider_http_error(exc: CloudflareServiceError) -> HTTPException:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.kind == "configuration"
            else status.HTTP_502_BAD_GATEWAY
        )
        return HTTPException(
            status_code=status_code,
            detail={
                "error": "custom_domain_provider_error",
                "message": exc.message,
                "provider": exc.as_dict(),
            },
        )

    async def get_for_owner(self, owner: Any) -> dict | None:
        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        record = await self._mongo.db["storefront_domains"].find_one(
            {"planner_id": owner_id}
        )
        return self._serialize(record) if record else None

    async def connect(self, owner: Any, raw_hostname: str) -> dict:
        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        try:
            hostname = normalize_custom_hostname(
                raw_hostname, platform_domains=self._platform_domains
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        if not self._cname_target:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront custom-domain CNAME target is not configured",
            )

        collection = self._mongo.db["storefront_domains"]
        now = datetime.now(timezone.utc)
        reservation = {
            "planner_id": owner_id,
            "hostname": hostname,
            "provider": "cloudflare",
            "provider_hostname_id": None,
            "status": "pending",
            "provider_status": "pending",
            "ssl_status": "pending",
            "ownership_verification": None,
            "ownership_verification_http": None,
            "ssl_validation_records": [],
            "cname_target": self._cname_target,
            "deletion_status": None,
            "delete_attempts": 0,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            inserted = await collection.insert_one(reservation)
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This planner or hostname already has a custom-domain mapping",
            ) from exc
        reservation_id = inserted.inserted_id

        try:
            provider_result = await self._cloudflare.create_custom_hostname(hostname)
        except CloudflareServiceError as exc:
            try:
                await collection.delete_one(
                    {
                        "_id": reservation_id,
                        "planner_id": owner_id,
                        "provider_hostname_id": None,
                    }
                )
            except Exception:
                logger.exception(
                    "Failed to release custom-domain reservation for owner %s",
                    owner_id,
                )
            raise self._provider_http_error(exc) from exc

        provider_id = provider_result.get("id")
        provider_hostname = provider_result.get("hostname")
        try:
            normalized_provider_hostname = normalize_custom_hostname(
                provider_hostname, platform_domains=self._platform_domains
            )
        except (TypeError, ValueError):
            normalized_provider_hostname = None
        if (
            not isinstance(provider_id, str)
            or not provider_id.strip()
            or normalized_provider_hostname != hostname
        ):
            await self._compensate_failed_create(
                collection,
                reservation_id=reservation_id,
                owner_id=owner_id,
                provider_id=provider_id if isinstance(provider_id, str) else None,
                failure_message="Cloudflare returned an invalid hostname mapping",
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloudflare returned an invalid custom-hostname result",
            )

        projection = self._provider_projection(provider_result)
        try:
            update_result = await collection.update_one(
                {
                    "_id": reservation_id,
                    "planner_id": owner_id,
                    "hostname": hostname,
                    "provider_hostname_id": None,
                },
                {
                    "$set": {
                        "provider_hostname_id": provider_id,
                        **projection,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except Exception as exc:
            await self._compensate_failed_create(
                collection,
                reservation_id=reservation_id,
                owner_id=owner_id,
                provider_id=provider_id,
                failure_message="The provider mapping could not be persisted",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain mapping could not be persisted",
            ) from exc

        if not getattr(update_result, "matched_count", 0):
            await self._compensate_failed_create(
                collection,
                reservation_id=reservation_id,
                owner_id=owner_id,
                provider_id=provider_id,
                failure_message="The local reservation no longer exists",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain reservation changed during provisioning",
            )

        saved = await collection.find_one(
            {"_id": reservation_id, "planner_id": owner_id}
        )
        if not saved:
            await self._compensate_failed_create(
                collection,
                reservation_id=reservation_id,
                owner_id=owner_id,
                provider_id=provider_id,
                failure_message="The saved mapping could not be read",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain mapping could not be read after provisioning",
            )
        return self._serialize(saved)

    async def _compensate_failed_create(
        self,
        collection: Any,
        *,
        reservation_id: Any,
        owner_id: str,
        provider_id: str | None,
        failure_message: str,
    ) -> None:
        provider_deleted = not provider_id
        provider_error: str | None = None
        if provider_id:
            try:
                await self._cloudflare.delete_custom_hostname(provider_id)
                provider_deleted = True
            except CloudflareServiceError as exc:
                provider_error = exc.message
                logger.exception(
                    "Failed to compensate custom-domain create for owner %s", owner_id
                )

        if provider_deleted:
            await collection.delete_one({"_id": reservation_id, "planner_id": owner_id})
            return

        # If compensation itself failed, preserve enough identity to retry the
        # provider deletion rather than orphaning an external hostname.
        await collection.update_one(
            {"_id": reservation_id, "planner_id": owner_id},
            {
                "$set": {
                    "provider_hostname_id": provider_id,
                    "status": "delete_failed",
                    "deletion_status": "retry_pending",
                    "last_error": provider_error or failure_message,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$inc": {"delete_attempts": 1},
            },
        )

    async def refresh(self, owner: Any) -> dict | None:
        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        collection = self._mongo.db["storefront_domains"]
        record = await collection.find_one({"planner_id": owner_id})
        if not record:
            return None
        # Disconnect intent is monotonic. A status poll must never ask the
        # provider for an activation projection and thereby resurrect a
        # hostname whose owner already requested removal.
        if self._has_deletion_intent(record):
            return self._serialize(record)
        provider_id = record.get("provider_hostname_id")
        if not isinstance(provider_id, str) or not provider_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain provisioning is still in progress",
            )

        try:
            provider_result = await self._cloudflare.get_custom_hostname(provider_id)
        except CloudflareServiceError as exc:
            await collection.update_one(
                {"_id": record["_id"], "planner_id": owner_id},
                {
                    "$set": {
                        "last_error": exc.message,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            raise self._provider_http_error(exc) from exc

        provider_result_id = provider_result.get("id")
        try:
            provider_result_hostname = normalize_custom_hostname(
                provider_result.get("hostname"),
                platform_domains=self._platform_domains,
            )
        except (TypeError, ValueError):
            provider_result_hostname = None
        if provider_result_id != provider_id or provider_result_hostname != record.get(
            "hostname"
        ):
            await collection.update_one(
                {"_id": record["_id"], "planner_id": owner_id},
                {
                    "$set": {
                        "last_error": (
                            "Cloudflare returned a mismatched hostname mapping"
                        ),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloudflare returned a mismatched custom-hostname result",
            )

        projection = self._provider_projection(provider_result)
        updated = await collection.update_one(
            {
                "_id": record["_id"],
                "planner_id": owner_id,
                "provider_hostname_id": provider_id,
            },
            {
                "$set": {
                    **projection,
                    "last_error": None,
                    "deletion_status": None,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if not getattr(updated, "matched_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain mapping changed during refresh",
            )
        saved = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        return self._serialize(saved) if saved else None

    async def disconnect(self, owner: Any) -> None:
        owner_id = self._owner_id(owner)
        await self._require_custom_domain(owner)
        collection = self._mongo.db["storefront_domains"]
        record = await collection.find_one({"planner_id": owner_id})
        if not record:
            return None

        if (
            record.get("deletion_status") == _LOCAL_CLEANUP_PENDING
            or self._status(record.get("status")) == "provider_deleted"
        ):
            await self._finish_local_cleanup(collection, record, owner_id)
            return None

        # Claim deletion intent locally before making an irreversible provider
        # call. The compare-and-set prevents two requests that read the same
        # state from both acting on the provider mapping.
        deletion_attempt_id = uuid4().hex
        claim_filter = {
            "_id": record["_id"],
            "planner_id": owner_id,
            "provider_hostname_id": record.get("provider_hostname_id"),
            "status": record.get("status"),
            "deletion_status": record.get("deletion_status"),
            "deletion_attempt_id": record.get("deletion_attempt_id"),
        }
        try:
            claimed = await collection.update_one(
                claim_filter,
                {
                    "$set": {
                        "status": "deleting",
                        "deletion_status": _PROVIDER_DELETE_PENDING,
                        "deletion_attempt_id": deletion_attempt_id,
                        "last_error": None,
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$inc": {"delete_attempts": 1},
                },
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain deletion could not be reserved",
            ) from exc
        if not getattr(claimed, "matched_count", 0):
            current = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            if not current:
                return None
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain mapping changed during deletion",
            )

        provider_id = record.get("provider_hostname_id")
        if isinstance(provider_id, str) and provider_id:
            try:
                await self._cloudflare.delete_custom_hostname(provider_id)
            except CloudflareServiceError as exc:
                if not self._provider_not_found(exc):
                    try:
                        await collection.update_one(
                            {
                                "_id": record["_id"],
                                "planner_id": owner_id,
                                "deletion_status": _PROVIDER_DELETE_PENDING,
                                "deletion_attempt_id": deletion_attempt_id,
                            },
                            {
                                "$set": {
                                    "status": "delete_failed",
                                    "deletion_status": (_PROVIDER_DELETE_RETRY_PENDING),
                                    "last_error": exc.message,
                                    "updated_at": datetime.now(timezone.utc),
                                },
                                "$unset": {"deletion_attempt_id": ""},
                            },
                        )
                    except Exception:
                        logger.exception(
                            "Failed to persist custom-domain delete retry for owner %s",
                            owner_id,
                        )
                    raise self._provider_http_error(exc) from exc

        # Provider success is durable before local cleanup. If Mongo cleanup
        # fails, retries can skip the already-completed external deletion.
        provider_deleted_at = datetime.now(timezone.utc)
        try:
            persisted = await collection.update_one(
                {
                    "_id": record["_id"],
                    "planner_id": owner_id,
                    "deletion_status": _PROVIDER_DELETE_PENDING,
                    "deletion_attempt_id": deletion_attempt_id,
                },
                {
                    "$set": {
                        "status": "provider_deleted",
                        "provider_status": "deleted",
                        "ssl_status": "inactive",
                        "deletion_status": _LOCAL_CLEANUP_PENDING,
                        "provider_deleted_at": provider_deleted_at,
                        "last_error": None,
                        "updated_at": provider_deleted_at,
                    },
                    "$unset": {"deletion_attempt_id": ""},
                },
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Custom-domain provider deletion succeeded but local state "
                    "could not be advanced"
                ),
            ) from exc
        if not getattr(persisted, "matched_count", 0):
            current = await collection.find_one(
                {"_id": record["_id"], "planner_id": owner_id}
            )
            if not current:
                return None
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Custom-domain mapping changed after provider deletion",
            )

        await self._finish_local_cleanup(
            collection,
            {
                **record,
                "status": "provider_deleted",
                "deletion_status": _LOCAL_CLEANUP_PENDING,
            },
            owner_id,
        )
        return None

    async def _finish_local_cleanup(
        self,
        collection: Any,
        record: dict,
        owner_id: str,
    ) -> None:
        cleanup_filter = {
            "_id": record["_id"],
            "planner_id": owner_id,
            "status": "provider_deleted",
            "deletion_status": _LOCAL_CLEANUP_PENDING,
        }
        try:
            deleted = await collection.delete_one(cleanup_filter)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Custom-domain provider mapping was deleted; local cleanup "
                    "is pending"
                ),
            ) from exc
        if getattr(deleted, "deleted_count", 0):
            return
        remaining = await collection.find_one(
            {"_id": record["_id"], "planner_id": owner_id}
        )
        if not remaining:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Custom-domain provider mapping was deleted; local cleanup is pending"
            ),
        )

    async def resolve_active_hostname(self, raw_hostname: str) -> dict | None:
        try:
            hostname = normalize_custom_hostname(
                raw_hostname, platform_domains=self._platform_domains
            )
        except (TypeError, ValueError):
            return None

        record = await self._mongo.db["storefront_domains"].find_one(
            {
                "hostname": hostname,
                "status": "active",
                "provider_status": "active",
                "ssl_status": "active",
                "deletion_status": None,
            }
        )
        if not record:
            return None
        owner_id = normalize_planner_id(record.get("planner_id"))
        if not owner_id:
            return None
        try:
            entitlements = await self._entitlements.resolve_for_planner_id(owner_id)
        except StorefrontEntitlementResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom-domain eligibility is temporarily unavailable",
            ) from exc
        if not (entitlements.storefront_enabled and entitlements.custom_domain_enabled):
            return None
        return {"planner_id": owner_id, "hostname": hostname}


storefront_domain_service = StorefrontDomainService()
