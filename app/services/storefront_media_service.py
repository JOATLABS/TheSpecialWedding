"""Planner-owned storefront image reservation and cleanup lifecycle."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
import logging
from typing import Any
from uuid import uuid4
import warnings

from bson import ObjectId
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from pymongo.errors import DuplicateKeyError

from app.constants.roles import is_wedding_planner_role
from app.constants.storefront import (
    PENDING_ASSET_GROUP_FIELD,
    PENDING_ASSET_RECOVERY_ATTEMPTS_FIELD,
    PENDING_ASSET_RECOVERY_DUE_FIELD,
    PENDING_ASSET_RECOVERY_ERROR_FIELD,
    PENDING_ASSET_RECOVERY_FIELDS,
    PENDING_ASSET_RECOVERY_LEASE_FIELD,
    PENDING_ASSET_RECOVERY_STATUS_FIELD,
    PENDING_ASSET_RECOVERY_TOKEN_FIELD,
)
from app.core.database import mongo
from app.core.settings import settings
from app.services.media_storage import MediaStorage, StorageTarget
from app.services.storefront_entitlement_service import (
    StorefrontEntitlementResolutionError,
    StorefrontEntitlementService,
    storefront_entitlement_service,
)
from app.utils.planner_ownership import normalize_planner_id, normalize_query_id


logger = logging.getLogger(__name__)

ALLOWED_STOREFRONT_ASSET_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
STOREFRONT_ASSET_SLOTS = frozenset({"hero", "about"})
MAX_STOREFRONT_ASSET_SIZE_BYTES = 5 * 1024 * 1024
STOREFRONT_UPLOAD_URL_TTL_SECONDS = 300
STOREFRONT_RESERVATION_GRACE_SECONDS = 60
STOREFRONT_RESERVATION_TTL_SECONDS = (
    STOREFRONT_UPLOAD_URL_TTL_SECONDS + STOREFRONT_RESERVATION_GRACE_SECONDS
)
STOREFRONT_ASSET_OPERATION_LEASE_SECONDS = 10 * 60
STOREFRONT_READY_ASSET_CLEANUP_SECONDS = 24 * 60 * 60
STOREFRONT_CLEANUP_RETRY_SECONDS = 5 * 60
STOREFRONT_MAINTENANCE_BATCH_SIZE = 100
MAX_STOREFRONT_IMAGE_DIMENSION = 4096
MAX_STOREFRONT_IMAGE_PIXELS = 12_000_000

_STOREFRONT_IMAGE_DECODE_SEMAPHORE = asyncio.Semaphore(
    settings.storefront_image_decode_concurrency
)

_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_FINALIZED_STATES = frozenset({"ready", "attached"})
_CLEANABLE_STATES = frozenset({"reserved", "ready", "cleanup_retry", "deleting"})
_STALE_FINALIZATION_CLEANUP_REASONS = frozenset(
    {"stale_finalization", "stale_finalization_recovery"}
)


class _UnsetAssetId:
    """Distinguish an omitted settings field from an intentional clear."""


_UNSET_ASSET_ID = _UnsetAssetId()


class StorefrontMediaService:
    """Own the full lifecycle of images referenced by storefront settings.

    ``storefront_assets`` is authoritative. Browser-provided paths, URLs, and
    ownership identifiers are never accepted: callers select only a supported
    slot and declare the exact MIME type and byte length that will be uploaded.
    """

    def __init__(
        self,
        mongo_client: Any | None = None,
        storage: MediaStorage | None = None,
        entitlement_service: StorefrontEntitlementService | None = None,
    ) -> None:
        self._mongo = mongo_client or mongo
        self._storage = storage or MediaStorage()
        self._entitlements = entitlement_service or storefront_entitlement_service
        self._maintenance_queue_cursor = 0

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

    async def _require_storefront(self, owner: Any) -> str:
        user_data = self._owner_data(owner)
        owner_id = self._owner_id(user_data)
        try:
            entitlements = await self._entitlements.resolve_for_owner(user_data)
        except StorefrontEntitlementResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront eligibility is temporarily unavailable",
            ) from exc
        if not entitlements.storefront_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "message": "Planner Storefront is not included in the current plan",
                    "feature": "planner_storefront",
                    "upgrade_required": True,
                },
            )
        return owner_id

    @staticmethod
    def _validate_slot(slot: str) -> str:
        if not isinstance(slot, str) or slot not in STOREFRONT_ASSET_SLOTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Storefront asset slot must be 'hero' or 'about'",
            )
        return slot

    @staticmethod
    def _validate_reservation_contract(content_type: str, size_bytes: int) -> None:
        if content_type not in ALLOWED_STOREFRONT_ASSET_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Storefront images must be JPEG, PNG, or WebP",
            )
        if (
            isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes <= 0
            or size_bytes > MAX_STOREFRONT_ASSET_SIZE_BYTES
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Storefront image size must be greater than zero and no more "
                    f"than {MAX_STOREFRONT_ASSET_SIZE_BYTES} bytes"
                ),
            )

    async def reserve(
        self,
        owner: Any,
        *,
        slot: str,
        content_type: str,
        size_bytes: int,
    ) -> dict:
        """Reserve a planner/slot-scoped object and return its presigned PUT URL."""

        owner_id = await self._require_storefront(owner)
        normalized_slot = self._validate_slot(slot)
        self._validate_reservation_contract(content_type, size_bytes)
        try:
            # A distinct bucket name is necessary but not sufficient: the
            # control plane must also prove that no public hostname exposes
            # staging bytes and that abandoned uploads expire promptly.
            await self._storage.require_private_storefront_staging()
            staging_target = await asyncio.to_thread(
                self._storage.require_target, StorageTarget.STOREFRONT_STAGING
            )
            public_target = await asyncio.to_thread(
                self._storage.require_target, StorageTarget.BLOG_ASSETS
            )
            if staging_target.bucket_name == public_target.bucket_name:
                raise RuntimeError(
                    "Storefront staging and public assets require separate buckets"
                )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image storage is temporarily unavailable",
            ) from exc
        assets = self._mongo.db["storefront_assets"]

        while True:
            existing = await assets.find_one(
                {
                    "owner_id": owner_id,
                    "slot": normalized_slot,
                    "$or": [
                        {
                            "state": {
                                "$in": [
                                    "reserved",
                                    "finalizing",
                                    "finalization_recovery",
                                    "reaping",
                                ]
                            }
                        },
                        {
                            "state": "cleanup_retry",
                            "cleanup_reason": {
                                "$in": [
                                    "stale_finalization",
                                    "stale_finalization_recovery",
                                ]
                            },
                        },
                    ],
                }
            )
            if not existing:
                break
            if existing.get("state") == "cleanup_retry":
                await self._retry_stale_finalization_cleanup(owner_id, existing)
                continue
            if existing.get("state") == "reaping":
                if self._operation_lease_is_stale(
                    existing.get("reaping_started_at") or existing.get("updated_at")
                ):
                    await self._resume_stale_reaping(owner_id, existing)
                    continue
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront finalization cleanup is already in progress",
                )
            if existing.get("state") != "reserved":
                lease_value = existing.get("finalization_started_at") or existing.get(
                    "updated_at"
                )
                if self._operation_lease_is_stale(lease_value):
                    await self._reap_stale_finalization(owner_id, existing)
                    continue
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "A storefront image is already being finalized for this slot"
                    ),
                )
            existing = await self._ensure_reservation_expiry(owner_id, existing)
            expires_at = existing["reservation_expires_at"]
            if not self._datetime_is_expired(expires_at):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An upload is already pending for this storefront image slot",
                )
            await self._reap_expired_reservation(owner_id, existing)

        asset_object_id = ObjectId()
        asset_id = str(asset_object_id)
        extension = _CONTENT_TYPE_EXTENSIONS[content_type]
        # The browser may reuse its presigned PUT until expiry. It therefore
        # uploads only to an unprojected staging key; the public object is a
        # distinct key that only this service can create after validation.
        staging_nonce = uuid4().hex
        staging_key = (
            f"storefront/{owner_id}/_staging/{normalized_slot}/"
            f"{asset_id}-{staging_nonce}{extension}"
        )
        final_key_prefix = f"storefront/{owner_id}/{normalized_slot}/{asset_id}"
        # The reservation contract predates finalization fencing and requires
        # string key/URL hints. They are never object keys persisted on the
        # asset receipt; the actual token-scoped key is returned by finalize.
        key_hint = f"{final_key_prefix}{extension}"
        cdn_url_hint = self._storage.build_public_url(
            StorageTarget.BLOG_ASSETS, key_hint
        )
        now = datetime.now(timezone.utc)
        reservation_expires_at = now + timedelta(
            seconds=STOREFRONT_RESERVATION_TTL_SECONDS
        )
        reservation = {
            "_id": asset_object_id,
            "owner_id": owner_id,
            "slot": normalized_slot,
            "staging_key": staging_key,
            "final_key_prefix": final_key_prefix,
            "declared_content_type": content_type,
            "declared_size_bytes": size_bytes,
            "state": "reserved",
            "cleanup_attempts": 0,
            "reservation_expires_at": reservation_expires_at,
            "created_at": now,
            "updated_at": now,
        }

        insert_error: Exception | None = None
        try:
            await assets.insert_one(reservation)
        except Exception as exc:
            insert_error = exc
            committed = await assets.find_one(
                {
                    "_id": asset_object_id,
                    "owner_id": owner_id,
                    "slot": normalized_slot,
                    "state": "reserved",
                    "staging_key": staging_key,
                    "final_key_prefix": final_key_prefix,
                    "declared_content_type": content_type,
                    "declared_size_bytes": size_bytes,
                }
            )
            if not committed:
                if isinstance(exc, DuplicateKeyError):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "An upload is already pending for this storefront image slot"
                        ),
                    ) from exc
                logger.exception(
                    "Failed to reserve storefront asset for owner %s", owner_id
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storefront image reservation is temporarily unavailable",
                ) from exc
        if insert_error:
            logger.warning(
                "Reconciled committed storefront reservation %s after lost acknowledgement",
                asset_id,
            )

        try:
            upload_url = await asyncio.to_thread(
                self._storage.generate_presigned_put_url,
                StorageTarget.STOREFRONT_STAGING,
                key=staging_key,
                expires_in=STOREFRONT_UPLOAD_URL_TTL_SECONDS,
                content_type=content_type,
                content_length=size_bytes,
            )
        except Exception as exc:
            logger.exception(
                "Failed to create storefront upload URL for owner %s asset %s",
                owner_id,
                asset_id,
            )
            try:
                await assets.delete_one(
                    {
                        "_id": asset_object_id,
                        "owner_id": owner_id,
                        "state": "reserved",
                    }
                )
            except Exception:
                logger.exception(
                    "Failed to remove unusable storefront reservation %s", asset_id
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image storage is temporarily unavailable",
            ) from exc

        return {
            "asset_id": asset_id,
            "upload_url": upload_url,
            "cdn_url": cdn_url_hint,
            "key": key_hint,
            "max_size_bytes": MAX_STOREFRONT_ASSET_SIZE_BYTES,
        }

    @staticmethod
    def _asset_query_id(asset_id: str) -> Any:
        return normalize_query_id(asset_id)

    @staticmethod
    def _operation_lease_is_stale(value: object) -> bool:
        if not isinstance(value, datetime):
            return True
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value <= datetime.now(timezone.utc) - timedelta(
            seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS
        )

    @staticmethod
    def _datetime_is_expired(value: datetime) -> bool:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value <= datetime.now(timezone.utc)

    @staticmethod
    def _reservation_created_at(asset: dict) -> datetime | None:
        created_at = asset.get("created_at")
        if isinstance(created_at, datetime):
            return (
                created_at.replace(tzinfo=timezone.utc)
                if created_at.tzinfo is None
                else created_at.astimezone(timezone.utc)
            )
        asset_id = asset.get("_id")
        if isinstance(asset_id, ObjectId):
            return asset_id.generation_time
        return None

    async def _ensure_reservation_expiry(self, owner_id: str, asset: dict) -> dict:
        """Backfill legacy receipts from their durable creation time."""

        expires_at = asset.get("reservation_expires_at")
        if isinstance(expires_at, datetime):
            return asset
        created_at = self._reservation_created_at(asset)
        if created_at is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront upload reservation has no safe expiry boundary",
            )
        effective_expiry = created_at + timedelta(
            seconds=STOREFRONT_RESERVATION_TTL_SECONDS
        )
        backfilled = await self._mongo.db["storefront_assets"].update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "state": "reserved",
                "reservation_expires_at": {"$exists": False},
            },
            {
                "$set": {
                    "reservation_expires_at": effective_expiry,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if getattr(backfilled, "modified_count", 0):
            return {**asset, "reservation_expires_at": effective_expiry}
        current = await self._mongo.db["storefront_assets"].find_one(
            {"_id": asset["_id"], "owner_id": owner_id}
        )
        if current and isinstance(current.get("reservation_expires_at"), datetime):
            return current
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Storefront upload reservation changed; reload and retry",
        )

    async def _reap_expired_reservation(self, owner_id: str, asset: dict) -> None:
        assets = self._mongo.db["storefront_assets"]
        reap_token = uuid4().hex
        now = datetime.now(timezone.utc)
        claimed = await assets.update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "slot": asset["slot"],
                "state": "reserved",
                "reservation_expires_at": {"$lte": now},
            },
            {
                "$set": {
                    "state": "reaping",
                    "reap_token": reap_token,
                    "reaping_started_at": now,
                    "reap_source_state": "reserved",
                    "cleanup_reason": "expired_reservation",
                    "updated_at": now,
                }
            },
        )
        if not getattr(claimed, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront upload reservation changed; reload and retry",
            )
        await self._finish_reaping(
            owner_id,
            {
                **asset,
                "state": "reaping",
                "reap_token": reap_token,
                "reaping_started_at": now,
                "reap_source_state": "reserved",
                "cleanup_reason": "expired_reservation",
            },
        )

    async def _reap_stale_finalization(self, owner_id: str, asset: dict) -> None:
        """Token-fence and remove a crashed finalizer before slot reuse."""

        state = asset.get("state")
        if state not in {"finalizing", "finalization_recovery"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront finalization changed; reload and retry",
            )
        assets = self._mongo.db["storefront_assets"]
        reap_token = uuid4().hex
        claim_filter: dict[str, Any] = {
            "_id": asset["_id"],
            "owner_id": owner_id,
            "slot": asset["slot"],
            "state": state,
        }
        candidate_key = asset.get("cleanup_candidate_key")
        if state == "finalizing":
            finalization_token = asset.get("finalization_token")
            lease_field = (
                "finalization_started_at"
                if "finalization_started_at" in asset
                else "updated_at"
            )
            claim_filter["finalization_token"] = finalization_token
            claim_filter[lease_field] = asset.get(lease_field)
            if isinstance(finalization_token, str) and finalization_token:
                try:
                    candidate_key = self._finalization_candidate_key(
                        asset, finalization_token
                    )
                except HTTPException:
                    candidate_key = None
        else:
            claim_filter["recovery_token"] = asset.get("recovery_token")
            claim_filter["updated_at"] = asset.get("updated_at")

        cleanup_reason = (
            "stale_finalization_recovery"
            if state == "finalization_recovery"
            else "stale_finalization"
        )
        now = datetime.now(timezone.utc)
        set_fields: dict[str, Any] = {
            "state": "reaping",
            "reap_token": reap_token,
            "reaping_started_at": now,
            "reap_source_state": state,
            "cleanup_reason": cleanup_reason,
            "updated_at": now,
        }
        if isinstance(candidate_key, str) and candidate_key:
            set_fields["cleanup_candidate_key"] = candidate_key
        claimed = await assets.update_one(
            claim_filter,
            {
                "$set": set_fields,
                "$unset": {
                    "finalization_token": "",
                    "finalization_started_at": "",
                    "recovery_token": "",
                },
            },
        )
        if not getattr(claimed, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront finalization lease changed; reload and retry",
            )

        cleanup_asset = {
            **asset,
            **set_fields,
            "state": "reaping",
            "reap_token": reap_token,
        }
        await self._finish_reaping(owner_id, cleanup_asset)

    async def _retry_stale_finalization_cleanup(
        self, owner_id: str, asset: dict
    ) -> None:
        """Retry a durable stale-finalizer cleanup receipt before slot reuse."""

        cleanup_reason = asset.get("cleanup_reason")
        if cleanup_reason not in _STALE_FINALIZATION_CLEANUP_REASONS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront finalization cleanup receipt is invalid",
            )
        if await self._is_referenced(owner_id, str(asset["_id"])):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A referenced storefront image cannot be reaped",
            )
        assets = self._mongo.db["storefront_assets"]
        reap_token = uuid4().hex
        now = datetime.now(timezone.utc)
        claimed = await assets.update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "slot": asset["slot"],
                "state": "cleanup_retry",
                "cleanup_reason": cleanup_reason,
                "updated_at": asset.get("updated_at"),
            },
            {
                "$set": {
                    "state": "reaping",
                    "reap_token": reap_token,
                    "reaping_started_at": now,
                    "reap_source_state": "cleanup_retry",
                    "updated_at": now,
                }
            },
        )
        if not getattr(claimed, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront finalization cleanup changed; reload and retry",
            )
        cleanup_asset = {
            **asset,
            "state": "reaping",
            "reap_token": reap_token,
            "reaping_started_at": now,
            "reap_source_state": "cleanup_retry",
        }
        await self._finish_reaping(owner_id, cleanup_asset)

    async def _resume_stale_reaping(self, owner_id: str, asset: dict) -> None:
        """Take over an abandoned token-fenced reaping lease."""

        assets = self._mongo.db["storefront_assets"]
        previous_token = asset.get("reap_token")
        previous_started_at = asset.get("reaping_started_at")
        if not self._operation_lease_is_stale(previous_started_at):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront image cleanup is already in progress",
            )
        reap_token = uuid4().hex
        now = datetime.now(timezone.utc)
        claimed = await assets.update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "slot": asset["slot"],
                "state": "reaping",
                "reap_token": previous_token,
                "reaping_started_at": previous_started_at,
            },
            {
                "$set": {
                    "reap_token": reap_token,
                    "reaping_started_at": now,
                    "updated_at": now,
                }
            },
        )
        if not getattr(claimed, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront finalization cleanup lease changed; reload and retry",
            )
        cleanup_asset = {**asset, "reap_token": reap_token, "reaping_started_at": now}
        await self._finish_reaping(owner_id, cleanup_asset)

    async def _reap_stale_deleting(self, owner_id: str, asset: dict) -> None:
        """Fence a crashed delete worker before resuming object cleanup."""

        lease_value = asset.get("deleting_started_at") or asset.get("updated_at")
        if not self._operation_lease_is_stale(lease_value):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront image cleanup is already in progress",
            )
        cleanup_token = asset.get("cleanup_token")
        lease_field = (
            "deleting_started_at" if "deleting_started_at" in asset else "updated_at"
        )
        now = datetime.now(timezone.utc)
        reap_token = uuid4().hex
        source_state = asset.get("cleanup_source_state") or "deleting"
        claimed = await self._mongo.db["storefront_assets"].update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "slot": asset["slot"],
                "state": "deleting",
                "cleanup_token": cleanup_token,
                lease_field: asset.get(lease_field),
            },
            {
                "$set": {
                    "state": "reaping",
                    "reap_token": reap_token,
                    "reaping_started_at": now,
                    "reap_source_state": source_state,
                    "cleanup_reason": asset.get("cleanup_reason") or "stale_deleting",
                    "updated_at": now,
                },
                "$unset": {
                    "cleanup_token": "",
                    "deleting_started_at": "",
                    "cleanup_source_state": "",
                },
            },
        )
        if not getattr(claimed, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront delete lease changed; reload and retry",
            )
        await self._finish_reaping(
            owner_id,
            {
                **asset,
                "state": "reaping",
                "reap_token": reap_token,
                "reaping_started_at": now,
                "reap_source_state": source_state,
                "cleanup_reason": asset.get("cleanup_reason") or "stale_deleting",
            },
        )

    async def _finish_reaping(self, owner_id: str, asset: dict) -> None:
        """Delete storage first and remove only the exact token-owned receipt."""

        assets = self._mongo.db["storefront_assets"]
        reap_token = asset.get("reap_token")
        if not isinstance(reap_token, str) or not reap_token:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront cleanup lease is invalid",
            )

        if await self._is_referenced(owner_id, str(asset["_id"])):
            source_state = asset.get("reap_source_state")
            now = datetime.now(timezone.utc)
            if source_state in {"ready", "cleanup_retry"}:
                retention_seconds = (
                    STOREFRONT_READY_ASSET_CLEANUP_SECONDS
                    if source_state == "ready"
                    else STOREFRONT_CLEANUP_RETRY_SECONDS
                )
                await assets.update_one(
                    {
                        "_id": asset["_id"],
                        "owner_id": owner_id,
                        "state": "reaping",
                        "reap_token": reap_token,
                    },
                    {
                        "$set": {
                            "state": source_state,
                            "cleanup_due_at": now
                            + timedelta(seconds=retention_seconds),
                            "updated_at": now,
                        },
                        "$unset": {
                            "reap_token": "",
                            "reaping_started_at": "",
                            "reap_source_state": "",
                        },
                    },
                )
            else:
                # An invalid reference to a non-finalized lifecycle must fail
                # closed, but renew the lease so it cannot starve every sweep.
                await assets.update_one(
                    {
                        "_id": asset["_id"],
                        "owner_id": owner_id,
                        "state": "reaping",
                        "reap_token": reap_token,
                    },
                    {
                        "$set": {
                            "reaping_started_at": now,
                            "updated_at": now,
                        }
                    },
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A referenced storefront image cannot be reaped",
            )
        try:
            await self._delete_asset_objects(asset)
        except Exception as exc:
            await self._record_cleanup_retry(
                asset,
                reason=asset.get("cleanup_reason") or "stale_finalization",
                error=exc,
                expected_states=["reaping"],
                expected_reap_token=reap_token,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image cleanup is pending",
            ) from exc
        try:
            deleted = await assets.delete_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "reaping",
                    "reap_token": reap_token,
                }
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront cleanup receipt removal is temporarily unavailable",
            ) from exc
        if not getattr(deleted, "deleted_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront cleanup changed; reload and retry",
            )

    async def _find_owned_asset(self, owner_id: str, asset_id: str) -> dict:
        asset = await self._mongo.db["storefront_assets"].find_one(
            {"_id": self._asset_query_id(asset_id), "owner_id": owner_id}
        )
        if not asset:
            # Do not disclose whether an ID belongs to another tenant.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Storefront asset not found",
            )
        return asset

    @staticmethod
    def _serialize_asset(asset: dict) -> dict:
        return {
            "asset_id": str(asset["_id"]),
            "slot": asset["slot"],
            "state": asset["state"],
            "key": asset["key"],
            "cdn_url": asset["cdn_url"],
            "content_type": asset.get("actual_content_type")
            or asset.get("declared_content_type"),
            "size_bytes": asset.get("actual_size_bytes")
            or asset.get("declared_size_bytes"),
        }

    @staticmethod
    def _finalization_candidate_key(asset: dict, token: str) -> str:
        prefix = asset.get("final_key_prefix")
        if not isinstance(prefix, str) or not prefix:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront upload must be reserved again before finalization",
            )
        extension = _CONTENT_TYPE_EXTENSIONS.get(asset.get("declared_content_type"))
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront upload has an invalid reservation contract",
            )
        return f"{prefix}-{token}{extension}"

    @staticmethod
    def _head_contract_error(asset: dict, head: dict) -> str | None:
        actual_size = head.get("ContentLength")
        actual_type = head.get("ContentType")
        declared_size = asset.get("declared_size_bytes")
        declared_type = asset.get("declared_content_type")

        if (
            isinstance(actual_size, bool)
            or not isinstance(actual_size, int)
            or actual_size <= 0
            or actual_size > MAX_STOREFRONT_ASSET_SIZE_BYTES
        ):
            return "Uploaded image has an invalid byte length"
        if actual_size != declared_size:
            return "Uploaded image byte length does not match its reservation"
        if actual_type not in ALLOWED_STOREFRONT_ASSET_CONTENT_TYPES:
            return "Uploaded image has an unsupported content type"
        if actual_type != declared_type:
            return "Uploaded image content type does not match its reservation"
        etag = head.get("ETag")
        if not isinstance(etag, str) or not etag.strip():
            return "Uploaded image is missing a verifiable object version"
        return None

    def _read_and_sanitize_staging_image(
        self, asset: dict, expected_head: dict
    ) -> tuple[bytes, str]:
        """Decode private bytes and return a metadata-free deterministic image."""

        payload = self._storage.get_object_bytes(
            StorageTarget.STOREFRONT_STAGING,
            asset["staging_key"],
            source_etag=expected_head.get("ETag"),
        )
        expected_size = expected_head.get("ContentLength")
        if len(payload) != expected_size or len(payload) != asset.get(
            "declared_size_bytes"
        ):
            raise ValueError("Uploaded image byte length changed during validation")

        declared_type = asset.get("declared_content_type")
        mime_by_format = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }
        format_by_mime = {
            mime: image_format for image_format, mime in mime_by_format.items()
        }
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(payload)) as image:
                    detected_type = mime_by_format.get(str(image.format).upper())
                    if detected_type != declared_type:
                        raise ValueError(
                            "Uploaded image bytes do not match the declared content type"
                        )
                    width, height = image.size
                    if (
                        width <= 0
                        or height <= 0
                        or width > MAX_STOREFRONT_IMAGE_DIMENSION
                        or height > MAX_STOREFRONT_IMAGE_DIMENSION
                        or width * height > MAX_STOREFRONT_IMAGE_PIXELS
                    ):
                        raise ValueError("Uploaded image dimensions are not supported")
                    if int(getattr(image, "n_frames", 1)) != 1:
                        raise ValueError("Animated storefront images are not supported")
                    image.load()
                    if declared_type == "image/jpeg":
                        sanitized = image.convert("RGB")
                    elif image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                        sanitized = image.convert("RGBA")
                    else:
                        sanitized = image.convert("RGB")
        except ValueError:
            raise
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
            raise ValueError("Uploaded image bytes are invalid or unsafe") from exc

        output = BytesIO()
        image_format = format_by_mime.get(declared_type)
        if image_format == "JPEG":
            sanitized.save(output, format=image_format, quality=88)
        elif image_format == "PNG":
            sanitized.save(output, format=image_format, compress_level=6)
        elif image_format == "WEBP":
            sanitized.save(output, format=image_format, quality=88, method=2)
        else:
            raise ValueError("Uploaded image content type is unsupported")
        sanitized_bytes = output.getvalue()
        if (
            not sanitized_bytes
            or len(sanitized_bytes) > MAX_STOREFRONT_ASSET_SIZE_BYTES
        ):
            raise ValueError("Sanitized storefront image exceeds the size limit")
        return sanitized_bytes, declared_type

    @staticmethod
    def _storage_keys(asset: dict) -> list[str]:
        """Return public object keys owned by an asset receipt."""

        return list(
            dict.fromkeys(
                key
                for key in (
                    asset.get("key"),
                    asset.get("cleanup_candidate_key"),
                )
                if isinstance(key, str) and key
            )
        )

    async def _delete_storage_objects(
        self, objects: list[tuple[StorageTarget, str]]
    ) -> None:
        first_error: Exception | None = None
        for target, key in dict.fromkeys(objects):
            try:
                await asyncio.to_thread(
                    self._storage.delete_object,
                    target,
                    key,
                )
            except Exception as exc:
                first_error = first_error or exc
                logger.exception("Failed to delete storefront object %s", key)
        if first_error:
            raise first_error

    async def _delete_storage_keys(
        self,
        keys: list[str],
        *,
        target: StorageTarget = StorageTarget.BLOG_ASSETS,
    ) -> None:
        await self._delete_storage_objects([(target, key) for key in keys])

    async def _delete_asset_objects(self, asset: dict) -> None:
        objects: list[tuple[StorageTarget, str]] = []
        staging_key = asset.get("staging_key")
        if isinstance(staging_key, str) and staging_key:
            objects.append((StorageTarget.STOREFRONT_STAGING, staging_key))
        objects.extend(
            (StorageTarget.BLOG_ASSETS, key) for key in self._storage_keys(asset)
        )
        await self._delete_storage_objects(objects)

    async def _record_cleanup_retry(
        self,
        asset: dict,
        *,
        reason: str,
        error: Exception,
        expected_states: list[str],
        expected_reap_token: str | None = None,
        expected_cleanup_token: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        claim_filter: dict[str, Any] = {
            "_id": asset["_id"],
            "owner_id": asset["owner_id"],
            "state": {"$in": expected_states},
        }
        if expected_reap_token is not None:
            claim_filter["reap_token"] = expected_reap_token
        if expected_cleanup_token is not None:
            claim_filter["cleanup_token"] = expected_cleanup_token
        await self._mongo.db["storefront_assets"].update_one(
            claim_filter,
            {
                "$set": {
                    "state": "cleanup_retry",
                    "cleanup_reason": reason,
                    "last_cleanup_error": error.__class__.__name__,
                    "last_cleanup_attempt_at": now,
                    "cleanup_due_at": now
                    + timedelta(seconds=STOREFRONT_CLEANUP_RETRY_SECONDS),
                    "updated_at": now,
                },
                "$inc": {"cleanup_attempts": 1},
                "$unset": {
                    "reap_token": "",
                    "reaping_started_at": "",
                    "reap_source_state": "",
                    "cleanup_token": "",
                    "deleting_started_at": "",
                    "cleanup_source_state": "",
                },
            },
        )

    async def _record_detached_candidate_cleanup(
        self,
        *,
        owner_id: str,
        slot: str,
        candidate_key: str,
        reason: str,
        error: Exception,
    ) -> None:
        """Persist cleanup for a token-unique candidate after its asset row is lost."""

        if slot not in STOREFRONT_ASSET_SLOTS or not candidate_key.startswith(
            f"storefront/{owner_id}/{slot}/"
        ):
            raise RuntimeError("Detached storefront candidate ownership is invalid")
        canonical = await self._mongo.db["storefront_assets"].find_one(
            {
                "owner_id": owner_id,
                "key": candidate_key,
                "state": {"$in": list(_FINALIZED_STATES)},
            },
            {"_id": 1},
        )
        if canonical:
            return
        now = datetime.now(timezone.utc)
        receipts = self._mongo.db["storefront_asset_cleanup_receipts"]
        receipt_filter = {"owner_id": owner_id, "candidate_key": candidate_key}
        receipt_update = {
            "$set": {
                "slot": slot,
                "state": "cleanup_retry",
                "cleanup_reason": reason,
                "last_cleanup_error": error.__class__.__name__,
                "last_cleanup_attempt_at": now,
                "cleanup_due_at": now
                + timedelta(seconds=STOREFRONT_CLEANUP_RETRY_SECONDS),
                "updated_at": now,
            },
            "$setOnInsert": {
                "_id": ObjectId(),
                "owner_id": owner_id,
                "candidate_key": candidate_key,
                "cleanup_attempts": 0,
                "created_at": now,
            },
            "$inc": {"cleanup_attempts": 1},
        }
        try:
            await receipts.update_one(receipt_filter, receipt_update, upsert=True)
        except DuplicateKeyError:
            # Another lost worker won the idempotent insert. Update that exact
            # owner/key receipt rather than dropping cleanup durability.
            reconciled = await receipts.update_one(receipt_filter, receipt_update)
            if not (
                getattr(reconciled, "matched_count", 0)
                or getattr(reconciled, "modified_count", 0)
            ):
                raise

    async def _discard_lost_candidate(
        self,
        *,
        owner_id: str,
        slot: str,
        candidate_key: str,
        reason: str,
    ) -> None:
        try:
            await self._delete_storage_keys([candidate_key])
        except Exception as cleanup_error:
            await self._record_detached_candidate_cleanup(
                owner_id=owner_id,
                slot=slot,
                candidate_key=candidate_key,
                reason=reason,
                error=cleanup_error,
            )
            logger.exception(
                "Lost finalizer retained durable cleanup for candidate %s",
                candidate_key,
            )

    async def _discard_invalid_upload(
        self,
        asset: dict,
        reason: str,
        *,
        finalization_token: str,
        candidate_key: str,
    ) -> None:
        assets = self._mongo.db["storefront_assets"]
        cleanup_token = uuid4().hex
        deleting_started_at = datetime.now(timezone.utc)
        fenced = await assets.update_one(
            {
                "_id": asset["_id"],
                "owner_id": asset["owner_id"],
                "state": "finalizing",
                "finalization_token": finalization_token,
            },
            {
                "$set": {
                    "state": "deleting",
                    "cleanup_token": cleanup_token,
                    "deleting_started_at": deleting_started_at,
                    "cleanup_source_state": "finalizing",
                    "cleanup_candidate_key": candidate_key,
                    "cleanup_reason": "invalid_upload",
                    "updated_at": deleting_started_at,
                },
                "$unset": {
                    "finalization_token": "",
                    "finalization_started_at": "",
                },
            },
        )
        if not getattr(fenced, "modified_count", 0):
            # This worker lost its lease. Its candidate is token-unique and safe
            # to remove; staging and the canonical row now belong to a successor.
            await self._discard_lost_candidate(
                owner_id=asset["owner_id"],
                slot=asset["slot"],
                candidate_key=candidate_key,
                reason="lost_invalid_upload_candidate",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront finalization lease changed; reload and retry",
            )

        cleanup_asset = {
            **asset,
            "state": "deleting",
            "cleanup_token": cleanup_token,
            "deleting_started_at": deleting_started_at,
            "cleanup_source_state": "finalizing",
            "cleanup_candidate_key": candidate_key,
        }
        try:
            await self._delete_asset_objects(cleanup_asset)
        except Exception as exc:
            logger.exception(
                "Failed to delete invalid storefront upload %s", asset["_id"]
            )
            await self._record_cleanup_retry(
                cleanup_asset,
                reason="invalid_upload",
                error=exc,
                expected_states=["deleting"],
                expected_cleanup_token=cleanup_token,
            )
        else:
            await assets.delete_one(
                {
                    "_id": asset["_id"],
                    "owner_id": asset["owner_id"],
                    "state": "deleting",
                    "cleanup_token": cleanup_token,
                }
            )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=reason,
        )

    async def finalize(self, owner: Any, asset_id: str) -> dict:
        """Validate staging, then conditionally copy it to an immutable public key."""

        owner_id = await self._require_storefront(owner)
        asset = await self._find_owned_asset(owner_id, asset_id)
        if asset.get("state") in _FINALIZED_STATES:
            if asset.get("staging_cleanup_pending") and asset.get("staging_key"):
                try:
                    await self._delete_storage_keys(
                        [asset["staging_key"]],
                        target=StorageTarget.STOREFRONT_STAGING,
                    )
                except Exception as exc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Storefront image staging cleanup is pending; retry later",
                    ) from exc
                await self._mongo.db["storefront_assets"].update_one(
                    {
                        "_id": asset["_id"],
                        "owner_id": owner_id,
                        "state": {"$in": list(_FINALIZED_STATES)},
                    },
                    {
                        "$unset": {"staging_cleanup_pending": ""},
                        "$set": {
                            "staging_deleted_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        },
                    },
                )
            return self._serialize_asset(asset)
        if asset.get("state") == "reserved":
            asset = await self._ensure_reservation_expiry(owner_id, asset)
            reservation_expires_at = asset["reservation_expires_at"]
            if self._datetime_is_expired(reservation_expires_at):
                await self._reap_expired_reservation(owner_id, asset)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront upload reservation expired; reserve a new upload",
                )
        if asset.get(
            "state"
        ) == "finalization_recovery" and self._operation_lease_is_stale(
            asset.get("updated_at")
        ):
            previous_recovery_token = asset.get("recovery_token")
            cleanup_candidate_key = asset.get("cleanup_candidate_key")
            if not isinstance(previous_recovery_token, str) or not isinstance(
                cleanup_candidate_key, str
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront finalization recovery is invalid; reserve again",
                )
            recovery_token = uuid4().hex
            recovery_claim = await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "finalization_recovery",
                    "recovery_token": previous_recovery_token,
                    "updated_at": asset.get("updated_at"),
                },
                {
                    "$set": {
                        "recovery_token": recovery_token,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            if not getattr(recovery_claim, "modified_count", 0):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront finalization recovery changed; reload and retry",
                )
            try:
                await self._delete_storage_keys([cleanup_candidate_key])
            except Exception as exc:
                await self._mongo.db["storefront_assets"].update_one(
                    {
                        "_id": asset["_id"],
                        "owner_id": owner_id,
                        "state": "finalization_recovery",
                        "recovery_token": recovery_token,
                    },
                    {
                        "$set": {
                            "state": "cleanup_retry",
                            "cleanup_reason": "stale_finalization_recovery",
                            "last_cleanup_error": exc.__class__.__name__,
                            "last_cleanup_attempt_at": datetime.now(timezone.utc),
                            "cleanup_due_at": datetime.now(timezone.utc)
                            + timedelta(seconds=STOREFRONT_CLEANUP_RETRY_SECONDS),
                            "updated_at": datetime.now(timezone.utc),
                        },
                        "$inc": {"cleanup_attempts": 1},
                        "$unset": {"recovery_token": ""},
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storefront finalization recovery cleanup is pending",
                ) from exc
            recovered = await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "finalization_recovery",
                    "recovery_token": recovery_token,
                },
                {
                    "$set": {
                        "state": "reserved",
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$unset": {
                        "recovery_token": "",
                        "cleanup_candidate_key": "",
                    },
                },
            )
            if not getattr(recovered, "modified_count", 0):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront finalization recovery changed; reload and retry",
                )
            asset = {
                key: value
                for key, value in asset.items()
                if key not in {"recovery_token", "cleanup_candidate_key"}
            }
            asset.update(
                {"state": "reserved", "updated_at": datetime.now(timezone.utc)}
            )
        if asset.get("state") == "finalizing" and self._operation_lease_is_stale(
            asset.get("finalization_started_at") or asset.get("updated_at")
        ):
            stale_token = asset.get("finalization_token")
            if not isinstance(stale_token, str) or not stale_token:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront finalization lease is invalid; reserve again",
                )
            stale_candidate_key = self._finalization_candidate_key(asset, stale_token)
            recovery_token = uuid4().hex
            lease_field = (
                "finalization_started_at"
                if isinstance(asset.get("finalization_started_at"), datetime)
                else "updated_at"
            )
            # Fence the stale worker before touching storage. A successor never
            # deletes from a stale snapshot while the old token can still own
            # the receipt.
            recovery_claim = await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "finalizing",
                    "finalization_token": stale_token,
                    lease_field: asset.get(lease_field),
                },
                {
                    "$set": {
                        "state": "finalization_recovery",
                        "recovery_token": recovery_token,
                        "cleanup_candidate_key": stale_candidate_key,
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$unset": {
                        "finalization_token": "",
                        "finalization_started_at": "",
                    },
                },
            )
            if not getattr(recovery_claim, "modified_count", 0):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront finalization lease changed; reload and retry",
                )
            try:
                await self._delete_storage_keys([stale_candidate_key])
            except Exception as exc:
                await self._mongo.db["storefront_assets"].update_one(
                    {
                        "_id": asset["_id"],
                        "owner_id": owner_id,
                        "state": "finalization_recovery",
                        "recovery_token": recovery_token,
                    },
                    {
                        "$set": {
                            "state": "cleanup_retry",
                            "cleanup_reason": "stale_finalization",
                            "last_cleanup_error": exc.__class__.__name__,
                            "last_cleanup_attempt_at": datetime.now(timezone.utc),
                            "cleanup_due_at": datetime.now(timezone.utc)
                            + timedelta(seconds=STOREFRONT_CLEANUP_RETRY_SECONDS),
                            "updated_at": datetime.now(timezone.utc),
                        },
                        "$inc": {"cleanup_attempts": 1},
                        "$unset": {"recovery_token": ""},
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Stale storefront finalization cleanup is pending",
                ) from exc
            recovered = await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "finalization_recovery",
                    "recovery_token": recovery_token,
                },
                {
                    "$set": {
                        "state": "reserved",
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$unset": {
                        "recovery_token": "",
                        "cleanup_candidate_key": "",
                    },
                },
            )
            if not getattr(recovered, "modified_count", 0):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront finalization lease changed; reload and retry",
                )
            asset = {
                **asset,
                "state": "reserved",
                "updated_at": datetime.now(timezone.utc),
            }
        if asset.get("state") != "reserved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset is not awaiting finalization",
            )

        if not asset.get("staging_key") or not asset.get("final_key_prefix"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront upload must be reserved again before finalization",
            )

        finalization_token = uuid4().hex
        finalization_started_at = datetime.now(timezone.utc)
        claim = await self._mongo.db["storefront_assets"].update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "state": "reserved",
                "reservation_expires_at": {"$gt": finalization_started_at},
            },
            {
                "$set": {
                    "state": "finalizing",
                    "finalization_token": finalization_token,
                    "finalization_started_at": finalization_started_at,
                    "updated_at": finalization_started_at,
                }
            },
        )
        if not getattr(claim, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset changed concurrently; reload and retry",
            )
        asset = {
            **asset,
            "state": "finalizing",
            "finalization_token": finalization_token,
        }
        candidate_key = self._finalization_candidate_key(asset, finalization_token)
        candidate_cdn_url = self._storage.build_public_url(
            StorageTarget.BLOG_ASSETS, candidate_key
        )

        async def reset_for_retry() -> None:
            await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "finalizing",
                    "finalization_token": finalization_token,
                },
                {
                    "$set": {
                        "state": "reserved",
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$unset": {
                        "finalization_token": "",
                        "finalization_started_at": "",
                    },
                },
            )

        async def renew_finalization_lease() -> None:
            heartbeat_at = datetime.now(timezone.utc)
            heartbeat = await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "finalizing",
                    "finalization_token": finalization_token,
                },
                {
                    "$set": {
                        "finalization_started_at": heartbeat_at,
                        "updated_at": heartbeat_at,
                    }
                },
            )
            if getattr(heartbeat, "matched_count", 0) or getattr(
                heartbeat, "modified_count", 0
            ):
                return
            await self._discard_lost_candidate(
                owner_id=owner_id,
                slot=asset["slot"],
                candidate_key=candidate_key,
                reason="lost_finalizer_candidate",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront finalization lease changed; reload and retry",
            )

        async def discard_candidate_for_retry(reason: str) -> None:
            try:
                await self._delete_storage_keys([candidate_key])
            except Exception as cleanup_exc:
                receipt = await self._mongo.db["storefront_assets"].update_one(
                    {
                        "_id": asset["_id"],
                        "owner_id": owner_id,
                        "state": "finalizing",
                        "finalization_token": finalization_token,
                    },
                    {
                        "$set": {
                            "state": "cleanup_retry",
                            "cleanup_candidate_key": candidate_key,
                            "cleanup_reason": reason,
                            "last_cleanup_error": cleanup_exc.__class__.__name__,
                            "last_cleanup_attempt_at": datetime.now(timezone.utc),
                            "cleanup_due_at": datetime.now(timezone.utc)
                            + timedelta(seconds=STOREFRONT_CLEANUP_RETRY_SECONDS),
                            "updated_at": datetime.now(timezone.utc),
                        },
                        "$inc": {"cleanup_attempts": 1},
                        "$unset": {
                            "finalization_token": "",
                            "finalization_started_at": "",
                        },
                    },
                )
                if not getattr(receipt, "modified_count", 0):
                    await self._record_detached_candidate_cleanup(
                        owner_id=owner_id,
                        slot=asset["slot"],
                        candidate_key=candidate_key,
                        reason=reason,
                        error=cleanup_exc,
                    )
                    logger.exception(
                        "Lost finalizer retained durable cleanup for candidate %s",
                        candidate_key,
                        exc_info=cleanup_exc,
                    )
            else:
                await reset_for_retry()

        try:
            head = await asyncio.to_thread(
                self._storage.head_object,
                StorageTarget.STOREFRONT_STAGING,
                asset["staging_key"],
            )
        except Exception as exc:
            logger.exception("Failed to inspect storefront upload %s", asset["_id"])
            await reset_for_retry()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image storage is temporarily unavailable",
            ) from exc

        contract_error = self._head_contract_error(asset, head)
        if contract_error:
            await self._discard_invalid_upload(
                asset,
                contract_error,
                finalization_token=finalization_token,
                candidate_key=candidate_key,
            )

        try:
            async with _STOREFRONT_IMAGE_DECODE_SEMAPHORE:
                sanitized_bytes, sanitized_content_type = await asyncio.to_thread(
                    self._read_and_sanitize_staging_image, asset, head
                )
        except ValueError as exc:
            await self._discard_invalid_upload(
                asset,
                str(exc),
                finalization_token=finalization_token,
                candidate_key=candidate_key,
            )
        except Exception as exc:
            logger.exception(
                "Failed to read fenced storefront staging bytes %s", asset["_id"]
            )
            await reset_for_retry()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image finalization is temporarily unavailable",
            ) from exc

        await renew_finalization_lease()

        try:
            await asyncio.to_thread(
                self._storage.upload_fileobj,
                BytesIO(sanitized_bytes),
                StorageTarget.BLOG_ASSETS,
                candidate_key,
                extra_args={"ContentType": sanitized_content_type},
            )
        except Exception as exc:
            logger.exception("Failed to sanitize storefront upload %s", asset["_id"])
            await discard_candidate_for_retry("finalization_upload_failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image finalization is temporarily unavailable",
            ) from exc

        await renew_finalization_lease()

        try:
            final_head = await asyncio.to_thread(
                self._storage.head_object,
                StorageTarget.BLOG_ASSETS,
                candidate_key,
            )
        except Exception as exc:
            logger.exception(
                "Failed to verify finalized storefront upload %s", asset["_id"]
            )
            await discard_candidate_for_retry("finalization_verification_failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image finalization is temporarily unavailable",
            ) from exc

        final_contract_error = self._head_contract_error(
            {
                **asset,
                "declared_size_bytes": len(sanitized_bytes),
                "declared_content_type": sanitized_content_type,
            },
            final_head,
        )
        if final_contract_error:
            await self._discard_invalid_upload(
                asset,
                final_contract_error,
                finalization_token=finalization_token,
                candidate_key=candidate_key,
            )

        await renew_finalization_lease()

        now = datetime.now(timezone.utc)
        update = {
            "state": "ready",
            "key": candidate_key,
            "cdn_url": candidate_cdn_url,
            "actual_size_bytes": final_head["ContentLength"],
            "actual_content_type": final_head["ContentType"],
            "etag": final_head.get("ETag"),
            "source_etag": head["ETag"],
            "finalized_at": now,
            "cleanup_due_at": now
            + timedelta(seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS),
            "updated_at": now,
        }
        result = None
        try:
            result = await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "finalizing",
                    "finalization_token": finalization_token,
                },
                {
                    "$set": update,
                    "$unset": {
                        "finalization_token": "",
                        "finalization_started_at": "",
                        "cleanup_reason": "",
                        "last_cleanup_error": "",
                        "last_cleanup_attempt_at": "",
                    },
                },
            )
        except Exception as exc:
            # A transport error can arrive after Mongo committed. Never delete
            # the candidate until the canonical receipt proves it was not the
            # published winner.
            try:
                canonical = await self._mongo.db["storefront_assets"].find_one(
                    {"_id": asset["_id"], "owner_id": owner_id}
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storefront image finalization status is temporarily unavailable",
                ) from exc
            if (
                canonical
                and canonical.get("state") in _FINALIZED_STATES
                and canonical.get("key") == candidate_key
            ):
                finalized_asset = canonical
            else:
                await discard_candidate_for_retry("finalization_commit_failed")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storefront image finalization is temporarily unavailable",
                ) from exc
        else:
            finalized_asset = {**asset, **update}
        if result is not None and not getattr(result, "modified_count", 0):
            await self._discard_lost_candidate(
                owner_id=owner_id,
                slot=asset["slot"],
                candidate_key=candidate_key,
                reason="lost_finalizer_candidate",
            )
            await reset_for_retry()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset changed concurrently; reload and retry",
            )
        try:
            await self._delete_storage_keys(
                [asset["staging_key"]],
                target=StorageTarget.STOREFRONT_STAGING,
            )
        except Exception as exc:
            await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": {"$in": list(_FINALIZED_STATES)},
                },
                {
                    "$set": {
                        "staging_cleanup_pending": True,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image staging cleanup is pending; retry later",
            ) from exc
        await self._mongo.db["storefront_assets"].update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "state": {"$in": list(_FINALIZED_STATES)},
            },
            {
                "$set": {
                    "staging_deleted_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return self._serialize_asset(finalized_asset)

    async def _is_referenced(self, owner_id: str, asset_id: str) -> bool:
        settings = await self._mongo.db["storefront_settings"].find_one(
            {
                "planner_id": owner_id,
                "$or": [
                    {"hero_asset_id": asset_id},
                    {"about_asset_id": asset_id},
                    {"pending_hero_asset_id": asset_id},
                    {"pending_about_asset_id": asset_id},
                ],
            },
            {"_id": 1},
        )
        return settings is not None

    async def cleanup(self, owner: Any, asset_id: str) -> dict:
        """Delete an unattached owner asset, retaining a retry receipt on failure."""

        owner_id = await self._require_storefront(owner)
        asset = await self._find_owned_asset(owner_id, asset_id)
        normalized_asset_id = str(asset["_id"])
        if asset.get("state") == "attached" or await self._is_referenced(
            owner_id, normalized_asset_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A storefront image that is currently attached cannot be deleted",
            )
        if asset.get("state") not in _CLEANABLE_STATES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset is not in a cleanable state",
            )

        assets = self._mongo.db["storefront_assets"]
        if asset.get("state") == "deleting":
            await self._reap_stale_deleting(owner_id, asset)
            return {"status": "deleted", "asset_id": normalized_asset_id}
        if asset.get("state") != "deleting":
            cleanup_token = uuid4().hex
            deleting_started_at = datetime.now(timezone.utc)
            claim = await assets.update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": asset["state"],
                },
                {
                    "$set": {
                        "state": "deleting",
                        "cleanup_token": cleanup_token,
                        "deleting_started_at": deleting_started_at,
                        "cleanup_source_state": asset["state"],
                        "updated_at": deleting_started_at,
                    }
                },
            )
            if not getattr(claim, "modified_count", 0):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront asset changed concurrently; reload and retry",
                )
            asset = {
                **asset,
                "state": "deleting",
                "cleanup_token": cleanup_token,
                "deleting_started_at": deleting_started_at,
                "cleanup_source_state": asset["state"],
            }

        # Recheck after the delete claim. Attachment helpers require a ready
        # state, so this closes the attach/delete race for service-owned flows.
        if await self._is_referenced(owner_id, normalized_asset_id):
            await assets.update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "deleting",
                    "cleanup_token": asset.get("cleanup_token"),
                },
                {
                    "$set": {
                        "state": "attached",
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$unset": {
                        "cleanup_due_at": "",
                        "cleanup_token": "",
                        "deleting_started_at": "",
                        "cleanup_source_state": "",
                    },
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A storefront image that is currently attached cannot be deleted",
            )

        try:
            await self._delete_asset_objects(asset)
        except Exception as exc:
            logger.exception("Failed to delete storefront asset %s", asset["_id"])
            await self._record_cleanup_retry(
                asset,
                reason="owner_requested",
                error=exc,
                expected_states=["deleting"],
                expected_cleanup_token=asset.get("cleanup_token"),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image cleanup is pending; retry later",
            ) from exc

        await assets.delete_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "state": "deleting",
                "cleanup_token": asset.get("cleanup_token"),
            }
        )
        return {"status": "deleted", "asset_id": normalized_asset_id}

    async def _validate_owned_asset_for_slot(
        self,
        owner_id: str,
        asset_id: str,
        slot: str,
        *,
        allow_stale_claim_takeover: bool = False,
    ) -> dict:
        normalized_slot = self._validate_slot(slot)
        asset = await self._find_owned_asset(owner_id, asset_id)
        if asset.get("slot") != normalized_slot:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Storefront asset was not uploaded for the {normalized_slot} slot",
            )
        if asset.get("state") == "attaching" and self._operation_lease_is_stale(
            asset.get("attach_claimed_at")
        ):
            field_name = f"{normalized_slot}_asset_id"
            pending_asset_field = f"pending_{normalized_slot}_asset_id"
            pending_claim_field = f"pending_{normalized_slot}_claim_id"
            referenced = await self._mongo.db["storefront_settings"].find_one(
                {
                    "planner_id": owner_id,
                    "$or": [
                        {field_name: str(asset["_id"])},
                        {
                            pending_asset_field: str(asset["_id"]),
                            pending_claim_field: asset.get("attach_claim_id"),
                        },
                    ],
                },
                {
                    "_id": 1,
                    field_name: 1,
                    pending_asset_field: 1,
                    pending_claim_field: 1,
                },
            )
            pending_exact = bool(
                referenced
                and referenced.get(pending_asset_field) == str(asset["_id"])
                and referenced.get(pending_claim_field) == asset.get("attach_claim_id")
            )
            if pending_exact:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront asset attachment is still being reconciled",
                )
            if allow_stale_claim_takeover:
                # No durable pending token belongs to the paused worker. A new
                # claim may fence the asset; the old worker's settings CAS is
                # revision-guarded and its token can never promote afterward.
                return asset
            if not referenced or referenced.get(field_name) != str(asset["_id"]):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront asset attachment is still being reconciled",
                )
            recovered = await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "attaching",
                    "attach_claim_id": asset.get("attach_claim_id"),
                },
                {
                    "$set": {
                        "state": "attached",
                        "updated_at": datetime.now(timezone.utc),
                        "attached_at": datetime.now(timezone.utc),
                    },
                    "$unset": {
                        "attach_claim_id": "",
                        "attach_claimed_at": "",
                        "cleanup_due_at": "",
                    },
                },
            )
            if not getattr(recovered, "modified_count", 0):
                asset = await self._find_owned_asset(owner_id, asset_id)
            else:
                asset = {**asset, "state": "attached"}
        if asset.get("state") not in _FINALIZED_STATES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset must be finalized before it can be attached",
            )
        return asset

    async def validate_asset_for_slot(
        self, owner: Any, asset_id: str, slot: str
    ) -> dict:
        """Validate an explicit settings asset ID without accepting a URL."""

        owner_id = await self._require_storefront(owner)
        asset = await self._validate_owned_asset_for_slot(owner_id, asset_id, slot)
        return self._serialize_asset(asset)

    async def validate_settings_assets(
        self,
        owner: Any,
        *,
        hero_asset_id: str | None | _UnsetAssetId = _UNSET_ASSET_ID,
        about_asset_id: str | None | _UnsetAssetId = _UNSET_ASSET_ID,
    ) -> dict[str, str | None]:
        """Validate explicit hero/about IDs before a settings write.

        ``None`` is an intentional clear and therefore requires no asset lookup.
        The returned shape is safe to pass into the settings allowlist.
        """

        owner_id = await self._require_storefront(owner)
        validated: dict[str, str | None] = {}
        for slot, asset_id in (
            ("hero", hero_asset_id),
            ("about", about_asset_id),
        ):
            field_name = f"{slot}_asset_id"
            if asset_id is _UNSET_ASSET_ID:
                continue
            if asset_id is None:
                validated[field_name] = None
                continue
            if not isinstance(asset_id, str):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"{field_name} must be a storefront asset ID or null",
                )
            asset = await self._validate_owned_asset_for_slot(owner_id, asset_id, slot)
            validated[field_name] = str(asset["_id"])
        return validated

    @staticmethod
    def _claim_entries(claim: dict) -> tuple[str, list[dict[str, str]]]:
        claim_id = claim.get("claim_id") if isinstance(claim, dict) else None
        entries = claim.get("claimed_assets") if isinstance(claim, dict) else None
        if not isinstance(claim_id, str) or not isinstance(entries, list):
            raise RuntimeError("Invalid storefront asset claim receipt")
        normalized_entries: list[dict[str, str]] = []
        seen_slots: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict) or not all(
                isinstance(entry.get(field), str)
                for field in ("asset_id", "slot", "field_name")
            ):
                raise RuntimeError("Invalid storefront asset claim receipt")
            slot = entry["slot"]
            if (
                slot not in STOREFRONT_ASSET_SLOTS
                or slot in seen_slots
                or entry["field_name"] != f"{slot}_asset_id"
            ):
                raise RuntimeError("Invalid storefront asset claim receipt")
            seen_slots.add(slot)
            normalized_entries.append(entry)
        return claim_id, normalized_entries

    @staticmethod
    def _build_claim_manifest(
        claim_id: str, values: dict[str, str | None]
    ) -> dict[str, Any]:
        members = {
            slot: values[f"{slot}_asset_id"]
            for slot in ("hero", "about")
            if f"{slot}_asset_id" in values
        }
        return {"claim_id": claim_id, "count": len(members), "members": members}

    @classmethod
    def _claim_values(
        cls, claim: dict, entries: list[dict[str, str]]
    ) -> dict[str, str | None]:
        values = claim.get("values") if isinstance(claim, dict) else None
        if not isinstance(values, dict) or not values:
            raise RuntimeError("Invalid storefront asset claim intent")
        allowed_fields = {f"{slot}_asset_id" for slot in STOREFRONT_ASSET_SLOTS}
        if set(values) - allowed_fields or any(
            value is not None and not isinstance(value, str)
            for value in values.values()
        ):
            raise RuntimeError("Invalid storefront asset claim intent")
        entry_values = {entry["field_name"]: entry["asset_id"] for entry in entries}
        if any(
            values.get(field_name) != asset_id
            for field_name, asset_id in entry_values.items()
        ):
            raise RuntimeError("Invalid storefront asset claim intent")
        if {
            field_name: value
            for field_name, value in values.items()
            if isinstance(value, str)
        } != entry_values:
            raise RuntimeError("Invalid storefront asset claim intent")
        return values

    @classmethod
    def _claim_manifest(cls, claim: dict) -> dict[str, Any]:
        claim_id, entries = cls._claim_entries(claim)
        values = cls._claim_values(claim, entries)
        expected = cls._build_claim_manifest(claim_id, values)
        if claim.get("manifest") != expected:
            raise RuntimeError("Invalid storefront asset claim manifest")
        return expected

    @classmethod
    def _entries_from_manifest(
        cls, manifest: Any
    ) -> tuple[str, list[dict[str, str]], dict[str, str | None]] | None:
        if not isinstance(manifest, dict) or set(manifest) != {
            "claim_id",
            "count",
            "members",
        }:
            return None
        claim_id = manifest.get("claim_id")
        count = manifest.get("count")
        members = manifest.get("members")
        if (
            not isinstance(claim_id, str)
            or not claim_id
            or isinstance(count, bool)
            or not isinstance(count, int)
            or not isinstance(members, dict)
            or set(members) - STOREFRONT_ASSET_SLOTS
            or count != len(members)
            or count <= 0
        ):
            return None
        entries: list[dict[str, str]] = []
        values: dict[str, str | None] = {}
        for slot in ("hero", "about"):
            if slot not in members:
                continue
            asset_id = members[slot]
            if asset_id is not None and (not isinstance(asset_id, str) or not asset_id):
                return None
            field_name = f"{slot}_asset_id"
            values[field_name] = asset_id
            if asset_id is None:
                continue
            entries.append(
                {
                    "asset_id": asset_id,
                    "slot": slot,
                    "field_name": field_name,
                }
            )
        if cls._build_claim_manifest(claim_id, values) != manifest:
            return None
        return claim_id, entries, values

    @staticmethod
    def _row_has_exact_manifest_pairs(
        row: dict | None, claim_id: str, values: dict[str, str | None]
    ) -> bool:
        if not row:
            return False
        for slot in ("hero", "about"):
            field_name = f"{slot}_asset_id"
            asset_field = f"pending_{slot}_asset_id"
            claim_field = f"pending_{slot}_claim_id"
            if field_name in values:
                if (
                    asset_field not in row
                    or row.get(asset_field) != values[field_name]
                    or row.get(claim_field) != claim_id
                ):
                    return False
            elif asset_field in row or claim_field in row:
                return False
        return True

    @staticmethod
    def _settings_recovery_fence(claim: dict) -> dict[str, str]:
        """Fence background recovery writes without affecting request claims."""

        if "settings_recovery_token" not in claim:
            return {}
        token = claim.get("settings_recovery_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Invalid storefront settings recovery token")
        return {
            PENDING_ASSET_RECOVERY_STATUS_FIELD: "recovering",
            PENDING_ASSET_RECOVERY_TOKEN_FIELD: token,
        }

    async def claim_settings_assets(
        self,
        owner: Any,
        *,
        hero_asset_id: str | None | _UnsetAssetId = _UNSET_ASSET_ID,
        about_asset_id: str | None | _UnsetAssetId = _UNSET_ASSET_ID,
    ) -> dict:
        """Atomically protect explicit finalized assets before a settings CAS.

        Cleanup cannot claim an ``attaching`` asset. The returned opaque receipt
        must be attached after the settings write, or released/reconciled on
        every losing or ambiguous write path.
        """

        owner_id = await self._require_storefront(owner)
        claim_id = uuid4().hex
        values: dict[str, str | None] = {}
        claimed_assets: list[dict[str, str]] = []
        assets = self._mongo.db["storefront_assets"]

        try:
            for slot, asset_id in (
                ("hero", hero_asset_id),
                ("about", about_asset_id),
            ):
                field_name = f"{slot}_asset_id"
                if asset_id is _UNSET_ASSET_ID:
                    continue
                if asset_id is None:
                    values[field_name] = None
                    continue
                if not isinstance(asset_id, str):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=f"{field_name} must be a storefront asset ID or null",
                    )

                asset = await self._validate_owned_asset_for_slot(
                    owner_id,
                    asset_id,
                    slot,
                    allow_stale_claim_takeover=True,
                )
                normalized_asset_id = str(asset["_id"])
                values[field_name] = normalized_asset_id

                now = datetime.now(timezone.utc)
                claim_filter: dict[str, Any] = {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "slot": slot,
                }
                if asset.get("state") == "attaching":
                    claim_filter.update(
                        {
                            "state": "attaching",
                            "attach_claim_id": asset.get("attach_claim_id"),
                            "attach_claimed_at": asset.get("attach_claimed_at"),
                        }
                    )
                else:
                    claim_filter["state"] = {"$in": ["ready", "attached"]}
                result = await assets.update_one(
                    claim_filter,
                    {
                        "$set": {
                            "state": "attaching",
                            "attach_claim_id": claim_id,
                            "attach_claimed_at": now,
                            "updated_at": now,
                        },
                        "$unset": {"cleanup_due_at": ""},
                    },
                )
                if not getattr(result, "modified_count", 0):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Storefront asset changed concurrently; reload and retry"
                        ),
                    )
                claimed_assets.append(
                    {
                        "asset_id": normalized_asset_id,
                        "slot": slot,
                        "field_name": field_name,
                    }
                )
        except Exception:
            if claimed_assets:
                await self.release_settings_asset_claims(
                    owner,
                    {
                        "owner_id": owner_id,
                        "claim_id": claim_id,
                        "values": values,
                        "claimed_assets": claimed_assets,
                    },
                )
            raise

        for entry in claimed_assets:
            still_owned = await assets.find_one(
                {
                    "_id": self._asset_query_id(entry["asset_id"]),
                    "owner_id": owner_id,
                    "slot": entry["slot"],
                    "state": "attaching",
                    "attach_claim_id": claim_id,
                },
                {"_id": 1},
            )
            if still_owned:
                continue
            await self.release_settings_asset_claims(
                owner,
                {
                    "owner_id": owner_id,
                    "claim_id": claim_id,
                    "values": values,
                    "claimed_assets": claimed_assets,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset claim changed concurrently; reload and retry",
            )

        manifest = self._build_claim_manifest(claim_id, values)
        return {
            "owner_id": owner_id,
            "claim_id": claim_id,
            "values": values,
            "claimed_assets": claimed_assets,
            "manifest": manifest,
        }

    async def release_settings_asset_claims(self, owner: Any, claim: dict) -> None:
        """Release a losing token without disturbing a durable pending handoff."""

        owner_id = self._owner_id(owner)
        if claim.get("owner_id") != owner_id:
            raise RuntimeError("Storefront asset claim owner mismatch")
        claim_id, entries = self._claim_entries(claim)
        assets = self._mongo.db["storefront_assets"]
        settings = self._mongo.db["storefront_settings"]
        for entry in entries:
            pending_asset_field = f"pending_{entry['slot']}_asset_id"
            pending_claim_field = f"pending_{entry['slot']}_claim_id"
            now = datetime.now(timezone.utc)
            row = await settings.find_one(
                {"planner_id": owner_id},
                {
                    "_id": 1,
                    entry["field_name"]: 1,
                    pending_asset_field: 1,
                    pending_claim_field: 1,
                },
            )
            if (
                row
                and row.get(pending_asset_field) == entry["asset_id"]
                and row.get(pending_claim_field) == claim_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A durable storefront asset handoff cannot be released",
                )
            stable_reference = bool(
                row and row.get(entry["field_name"]) == entry["asset_id"]
            )
            target_state = "attached" if stable_reference else "ready"
            set_fields: dict[str, Any] = {
                "state": target_state,
                "updated_at": now,
            }
            unset_fields = {
                "attach_claim_id": "",
                "attach_claimed_at": "",
            }
            if stable_reference:
                set_fields["attached_at"] = now
                set_fields["attached_claim_id"] = claim_id
                unset_fields["cleanup_due_at"] = ""
            else:
                set_fields["cleanup_due_at"] = now + timedelta(
                    seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS
                )
                unset_fields["attached_at"] = ""
                unset_fields["attached_claim_id"] = ""
            result = await assets.update_one(
                {
                    "_id": self._asset_query_id(entry["asset_id"]),
                    "owner_id": owner_id,
                    "slot": entry["slot"],
                    "$or": [
                        {
                            "state": "attaching",
                            "attach_claim_id": claim_id,
                        },
                        {
                            "state": "attached",
                            "attached_claim_id": claim_id,
                        },
                    ],
                },
                {
                    "$set": set_fields,
                    "$unset": unset_fields,
                },
            )
            if getattr(result, "modified_count", 0):
                continue
            current = await assets.find_one(
                {
                    "_id": self._asset_query_id(entry["asset_id"]),
                    "owner_id": owner_id,
                },
                {"state": 1, "attach_claim_id": 1, "attached_claim_id": 1},
            )
            if not current:
                continue
            if current.get("state") in _FINALIZED_STATES:
                continue
            if (
                current.get("attach_claim_id") != claim_id
                and current.get("attached_claim_id") != claim_id
            ):
                continue
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset claim could not be released safely",
            )

    async def attach_settings_asset_claims(self, owner: Any, claim: dict) -> None:
        """Attach assets only for their exact durable pending ID/token pairs."""

        owner_id = self._owner_id(owner)
        if claim.get("owner_id") != owner_id:
            raise RuntimeError("Storefront asset claim owner mismatch")
        claim_id, entries = self._claim_entries(claim)
        values = self._claim_values(claim, entries)
        manifest = self._claim_manifest(claim)
        assets = self._mongo.db["storefront_assets"]
        settings = self._mongo.db["storefront_settings"]
        durable_filter: dict[str, Any] = {
            "planner_id": owner_id,
            PENDING_ASSET_GROUP_FIELD: manifest,
            **self._settings_recovery_fence(claim),
        }
        intent_slots = {field_name.removesuffix("_asset_id") for field_name in values}
        for slot in intent_slots:
            durable_filter[f"pending_{slot}_asset_id"] = values[f"{slot}_asset_id"]
            durable_filter[f"pending_{slot}_claim_id"] = claim_id
        for slot in STOREFRONT_ASSET_SLOTS - intent_slots:
            durable_filter[f"pending_{slot}_asset_id"] = {"$exists": False}
            durable_filter[f"pending_{slot}_claim_id"] = {"$exists": False}
        if not await settings.find_one(durable_filter, {"_id": 1}):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset claim has no complete durable settings reference",
            )

        for entry in entries:
            owned = await assets.find_one(
                {
                    "_id": self._asset_query_id(entry["asset_id"]),
                    "owner_id": owner_id,
                    "slot": entry["slot"],
                    "$or": [
                        {"state": "attaching", "attach_claim_id": claim_id},
                        {"state": "attached", "attached_claim_id": claim_id},
                    ],
                },
                {"_id": 1},
            )
            if not owned:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront asset token group is no longer fully owned",
                )

        for entry in entries:
            pending_asset_field = f"pending_{entry['slot']}_asset_id"
            pending_claim_field = f"pending_{entry['slot']}_claim_id"
            referenced = await settings.find_one(
                {
                    "planner_id": owner_id,
                    pending_asset_field: entry["asset_id"],
                    pending_claim_field: claim_id,
                    **self._settings_recovery_fence(claim),
                },
                {"_id": 1},
            )
            if not referenced:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=("Storefront asset claim has no durable settings reference"),
                )
            now = datetime.now(timezone.utc)
            result = await assets.update_one(
                {
                    "_id": self._asset_query_id(entry["asset_id"]),
                    "owner_id": owner_id,
                    "slot": entry["slot"],
                    "state": "attaching",
                    "attach_claim_id": claim_id,
                },
                {
                    "$set": {
                        "state": "attached",
                        "attached_claim_id": claim_id,
                        "attached_at": now,
                        "updated_at": now,
                    },
                    "$unset": {
                        "attach_claim_id": "",
                        "attach_claimed_at": "",
                        "cleanup_due_at": "",
                    },
                },
            )
            if getattr(result, "modified_count", 0):
                continue
            current = await assets.find_one(
                {
                    "_id": self._asset_query_id(entry["asset_id"]),
                    "owner_id": owner_id,
                },
                {"state": 1, "attached_claim_id": 1},
            )
            if (
                current
                and current.get("state") == "attached"
                and current.get("attached_claim_id") == claim_id
            ):
                continue
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset claim could not be attached safely",
            )

        for entry in entries:
            attached = await assets.find_one(
                {
                    "_id": self._asset_query_id(entry["asset_id"]),
                    "owner_id": owner_id,
                    "slot": entry["slot"],
                    "state": "attached",
                    "attached_claim_id": claim_id,
                },
                {"_id": 1},
            )
            if not attached:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront asset token group changed during attachment",
                )

    async def promote_settings_asset_claims(self, owner: Any, claim: dict) -> None:
        """Atomically replace stable settings IDs after every claim is attached."""

        owner_id = self._owner_id(owner)
        if claim.get("owner_id") != owner_id:
            raise RuntimeError("Storefront asset claim owner mismatch")
        claim_id, entries = self._claim_entries(claim)
        values = self._claim_values(claim, entries)
        manifest = self._claim_manifest(claim)
        assets = self._mongo.db["storefront_assets"]
        settings = self._mongo.db["storefront_settings"]

        for entry in entries:
            attached = await assets.find_one(
                {
                    "_id": self._asset_query_id(entry["asset_id"]),
                    "owner_id": owner_id,
                    "slot": entry["slot"],
                    "state": "attached",
                    "attached_claim_id": claim_id,
                },
                {"_id": 1},
            )
            if not attached:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront asset claim is not attached for promotion",
                )

        promote_filter: dict[str, Any] = {
            "planner_id": owner_id,
            PENDING_ASSET_GROUP_FIELD: manifest,
            **self._settings_recovery_fence(claim),
        }
        stable_updates: dict[str, str | None] = {}
        pending_unsets: dict[str, str] = {}
        intent_slots = {field_name.removesuffix("_asset_id") for field_name in values}
        for slot in intent_slots:
            field_name = f"{slot}_asset_id"
            pending_asset_field = f"pending_{slot}_asset_id"
            pending_claim_field = f"pending_{slot}_claim_id"
            promote_filter[pending_asset_field] = values[field_name]
            promote_filter[pending_claim_field] = claim_id
            stable_updates[field_name] = values[field_name]
            pending_unsets[pending_asset_field] = ""
            pending_unsets[pending_claim_field] = ""
        pending_unsets[PENDING_ASSET_GROUP_FIELD] = ""
        pending_unsets.update(dict.fromkeys(PENDING_ASSET_RECOVERY_FIELDS, ""))
        for slot in STOREFRONT_ASSET_SLOTS - intent_slots:
            promote_filter[f"pending_{slot}_asset_id"] = {"$exists": False}
            promote_filter[f"pending_{slot}_claim_id"] = {"$exists": False}

        promoted = await settings.update_one(
            promote_filter,
            {
                "$set": {
                    **stable_updates,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$unset": pending_unsets,
                "$inc": {"revision": 1},
            },
        )
        if getattr(promoted, "modified_count", 0):
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Storefront asset promotion lost its pending settings fence",
        )

    async def reconcile_settings_asset_claims(self, owner: Any, claim: dict) -> None:
        """Resolve one token group without ever promoting only a valid subset."""

        owner_id = self._owner_id(owner)
        if claim.get("owner_id") != owner_id:
            raise RuntimeError("Storefront asset claim owner mismatch")
        claim_id, entries = self._claim_entries(claim)
        values = self._claim_values(claim, entries)
        manifest = self._claim_manifest(claim)
        settings = self._mongo.db["storefront_settings"]
        row = await settings.find_one({"planner_id": owner_id})
        complete_pending_group = (
            bool(row)
            and row.get(PENDING_ASSET_GROUP_FIELD) == manifest
            and self._row_has_exact_manifest_pairs(row, claim_id, values)
        )
        if complete_pending_group:
            try:
                await self.attach_settings_asset_claims(owner, claim)
                await self.promote_settings_asset_claims(owner, claim)
                return
            except HTTPException as exc:
                if exc.status_code != status.HTTP_409_CONFLICT:
                    raise
                logger.info(
                    "Rolling back invalid storefront asset token group %s for owner %s",
                    claim_id,
                    owner_id,
                )

        await self._rollback_settings_asset_group(owner, claim)

    async def _clear_pending_token_group(
        self,
        owner_id: str,
        claim_id: str,
        *,
        recovery_token: str | None = None,
    ) -> None:
        """Atomically clear every current pending slot carrying one token."""

        settings = self._mongo.db["storefront_settings"]
        for _attempt in range(3):
            recovery_fence: dict[str, str] = {}
            if recovery_token is not None:
                recovery_fence = {
                    PENDING_ASSET_RECOVERY_STATUS_FIELD: "recovering",
                    PENDING_ASSET_RECOVERY_TOKEN_FIELD: recovery_token,
                }
            row = await settings.find_one({"planner_id": owner_id, **recovery_fence})
            if not row:
                return
            clear_filter: dict[str, Any] = {
                "planner_id": owner_id,
                **recovery_fence,
            }
            pending_unsets: dict[str, str] = {}
            for slot in ("hero", "about"):
                asset_field = f"pending_{slot}_asset_id"
                claim_field = f"pending_{slot}_claim_id"
                if row.get(claim_field) != claim_id:
                    continue
                clear_filter[asset_field] = row.get(asset_field)
                clear_filter[claim_field] = claim_id
                pending_unsets[asset_field] = ""
                pending_unsets[claim_field] = ""
            manifest = row.get(PENDING_ASSET_GROUP_FIELD)
            parsed_manifest = self._entries_from_manifest(manifest)
            if parsed_manifest and parsed_manifest[0] == claim_id:
                clear_filter[PENDING_ASSET_GROUP_FIELD] = manifest
                pending_unsets[PENDING_ASSET_GROUP_FIELD] = ""
                pending_unsets.update(dict.fromkeys(PENDING_ASSET_RECOVERY_FIELDS, ""))
            if not pending_unsets:
                return
            cleared = await settings.update_one(
                clear_filter,
                {
                    "$unset": pending_unsets,
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                    "$inc": {"revision": 1},
                },
            )
            if getattr(cleared, "modified_count", 0):
                return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Storefront pending asset group changed during recovery",
        )

    async def _rollback_settings_asset_group(self, owner: Any, claim: dict) -> None:
        owner_id = self._owner_id(owner)
        if claim.get("owner_id") != owner_id:
            raise RuntimeError("Storefront asset claim owner mismatch")
        claim_id, _entries = self._claim_entries(claim)
        recovery_token = claim.get("settings_recovery_token")
        if recovery_token is not None and (
            not isinstance(recovery_token, str) or not recovery_token
        ):
            raise RuntimeError("Invalid storefront settings recovery token")
        await self._clear_pending_token_group(
            owner_id,
            claim_id,
            recovery_token=recovery_token,
        )
        await self.release_settings_asset_claims(owner, claim)

    async def _recover_orphaned_owner_assets(
        self, owner_id: str, settings_row: dict | None
    ) -> None:
        """Release lifecycle receipts that no stable or pending setting owns."""

        assets = self._mongo.db["storefront_assets"]
        cursor = assets.find(
            {
                "owner_id": owner_id,
                "state": {"$in": ["attaching", "attached"]},
            }
        )
        rows = await cursor.to_list(length=None)
        settings_row = settings_row or {}
        for asset in rows:
            slot = asset.get("slot")
            if slot not in STOREFRONT_ASSET_SLOTS:
                continue
            asset_id = str(asset["_id"])
            stable_reference = settings_row.get(f"{slot}_asset_id") == asset_id
            if asset.get("state") == "attaching":
                token = asset.get("attach_claim_id")
                pending_exact = (
                    isinstance(token, str)
                    and settings_row.get(f"pending_{slot}_asset_id") == asset_id
                    and settings_row.get(f"pending_{slot}_claim_id") == token
                )
                if pending_exact:
                    continue
                if not self._operation_lease_is_stale(asset.get("attach_claimed_at")):
                    continue
                target_state = "attached" if stable_reference else "ready"
                set_fields: dict[str, Any] = {
                    "state": target_state,
                    "updated_at": datetime.now(timezone.utc),
                }
                unset_fields = {
                    "attach_claim_id": "",
                    "attach_claimed_at": "",
                }
                if stable_reference:
                    set_fields["attached_at"] = datetime.now(timezone.utc)
                    unset_fields["cleanup_due_at"] = ""
                else:
                    set_fields["cleanup_due_at"] = datetime.now(
                        timezone.utc
                    ) + timedelta(seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS)
                    unset_fields.update({"attached_at": "", "attached_claim_id": ""})
                await assets.update_one(
                    {
                        "_id": asset["_id"],
                        "owner_id": owner_id,
                        "state": "attaching",
                        "attach_claim_id": token,
                        "attach_claimed_at": asset.get("attach_claimed_at"),
                    },
                    {"$set": set_fields, "$unset": unset_fields},
                )
                continue

            token = asset.get("attached_claim_id")
            pending_exact = (
                isinstance(token, str)
                and settings_row.get(f"pending_{slot}_asset_id") == asset_id
                and settings_row.get(f"pending_{slot}_claim_id") == token
            )
            if stable_reference or pending_exact:
                continue
            await assets.update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "attached",
                    "attached_claim_id": token,
                },
                {
                    "$set": {
                        "state": "ready",
                        "cleanup_due_at": datetime.now(timezone.utc)
                        + timedelta(seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS),
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$unset": {"attached_at": "", "attached_claim_id": ""},
                },
            )

    @staticmethod
    def _due_cleanup_query(owner_id: str | None = None) -> dict[str, Any]:
        """Build the durable maintenance query without any destructive TTL."""

        now = datetime.now(timezone.utc)
        query: dict[str, Any] = {
            "$or": [
                {"state": "ready", "cleanup_due_at": {"$lte": now}},
                {
                    "state": "ready",
                    "cleanup_due_at": {"$exists": False},
                    "updated_at": {
                        "$lte": now
                        - timedelta(seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS)
                    },
                },
                {"state": "cleanup_retry", "cleanup_due_at": {"$lte": now}},
                {
                    "state": "cleanup_retry",
                    "cleanup_due_at": {"$exists": False},
                    "updated_at": {
                        "$lte": now
                        - timedelta(seconds=STOREFRONT_CLEANUP_RETRY_SECONDS)
                    },
                },
                {
                    "state": "reaping",
                    "reaping_started_at": {
                        "$lte": now
                        - timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS)
                    },
                },
                {
                    "state": "reaping",
                    "reaping_started_at": {"$exists": False},
                },
                {
                    "state": "finalizing",
                    "finalization_started_at": {
                        "$lte": now
                        - timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS)
                    },
                },
                {
                    "state": "finalizing",
                    "finalization_started_at": {"$exists": False},
                    "updated_at": {
                        "$lte": now
                        - timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS)
                    },
                },
                {
                    "state": "finalization_recovery",
                    "updated_at": {
                        "$lte": now
                        - timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS)
                    },
                },
                {
                    "state": "deleting",
                    "deleting_started_at": {
                        "$lte": now
                        - timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS)
                    },
                },
                {
                    "state": "deleting",
                    "deleting_started_at": {"$exists": False},
                    "updated_at": {
                        "$lte": now
                        - timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS)
                    },
                },
            ]
        }
        if owner_id is not None:
            query["owner_id"] = owner_id
        return query

    async def _claim_due_cleanup_asset(self, asset: dict) -> bool:
        """Claim one due receipt and delete only while its exact token is owned."""

        owner_id = asset.get("owner_id")
        slot = asset.get("slot")
        if not isinstance(owner_id, str) or slot not in STOREFRONT_ASSET_SLOTS:
            logger.error("Invalid storefront cleanup receipt %s", asset.get("_id"))
            invalid_filter: dict[str, Any] = {
                "_id": asset.get("_id"),
                "state": asset.get("state"),
                "updated_at": asset.get("updated_at"),
            }
            if "reap_token" in asset:
                invalid_filter["reap_token"] = asset.get("reap_token")
            await self._mongo.db["storefront_assets"].update_one(
                invalid_filter,
                {
                    "$set": {
                        "state": "invalid_cleanup_receipt",
                        "cleanup_validation_error": "invalid_owner_or_slot",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            return False
        if asset.get("state") == "reaping":
            await self._resume_stale_reaping(owner_id, asset)
            return True
        if asset.get("state") in {"finalizing", "finalization_recovery"}:
            await self._reap_stale_finalization(owner_id, asset)
            return True
        if asset.get("state") == "deleting":
            await self._reap_stale_deleting(owner_id, asset)
            return True
        if asset.get("state") not in {"ready", "cleanup_retry"}:
            return False
        if await self._is_referenced(owner_id, str(asset["_id"])):
            source_state = asset["state"]
            retention_seconds = (
                STOREFRONT_READY_ASSET_CLEANUP_SECONDS
                if source_state == "ready"
                else STOREFRONT_CLEANUP_RETRY_SECONDS
            )
            now = datetime.now(timezone.utc)
            due_filter: dict[str, Any] = {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "state": source_state,
                "updated_at": asset.get("updated_at"),
            }
            if "cleanup_due_at" in asset:
                due_filter["cleanup_due_at"] = asset.get("cleanup_due_at")
            else:
                due_filter["cleanup_due_at"] = {"$exists": False}
            await self._mongo.db["storefront_assets"].update_one(
                due_filter,
                {
                    "$set": {
                        "cleanup_due_at": now + timedelta(seconds=retention_seconds),
                        "updated_at": now,
                    }
                },
            )
            return False

        source_state = asset["state"]
        now = datetime.now(timezone.utc)
        reap_token = uuid4().hex
        claim_filter: dict[str, Any] = {
            "_id": asset["_id"],
            "owner_id": owner_id,
            "slot": slot,
            "state": source_state,
            "updated_at": asset.get("updated_at"),
        }
        if "cleanup_due_at" in asset:
            claim_filter["cleanup_due_at"] = asset.get("cleanup_due_at")
        else:
            claim_filter["cleanup_due_at"] = {"$exists": False}
        cleanup_reason = asset.get("cleanup_reason") or "abandoned_ready_asset"
        claimed = await self._mongo.db["storefront_assets"].update_one(
            claim_filter,
            {
                "$set": {
                    "state": "reaping",
                    "reap_token": reap_token,
                    "reaping_started_at": now,
                    "reap_source_state": source_state,
                    "cleanup_reason": cleanup_reason,
                    "updated_at": now,
                }
            },
        )
        if not getattr(claimed, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront cleanup receipt changed concurrently",
            )
        await self._finish_reaping(
            owner_id,
            {
                **asset,
                "state": "reaping",
                "reap_token": reap_token,
                "reaping_started_at": now,
                "reap_source_state": source_state,
                "cleanup_reason": cleanup_reason,
            },
        )
        return True

    async def _sweep_due_cleanup_assets(
        self, *, owner_id: str | None, limit: int
    ) -> tuple[int, int]:
        assets = self._mongo.db["storefront_assets"]
        cursor = assets.find(self._due_cleanup_query(owner_id))
        processed = 0
        candidates = await cursor.to_list(length=limit)
        for asset in candidates:
            try:
                if await self._claim_due_cleanup_asset(asset):
                    processed += 1
            except HTTPException as exc:
                if exc.status_code not in {
                    status.HTTP_409_CONFLICT,
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                }:
                    raise
                logger.info(
                    "Storefront asset %s cleanup remains pending for owner %s",
                    asset.get("_id"),
                    asset.get("owner_id"),
                )
        return processed, len(candidates)

    async def _sweep_detached_candidate_receipts(
        self, *, limit: int
    ) -> tuple[int, int]:
        receipts = self._mongo.db["storefront_asset_cleanup_receipts"]
        now = datetime.now(timezone.utc)
        cursor = receipts.find(
            {
                "$or": [
                    {"state": "cleanup_retry", "cleanup_due_at": {"$lte": now}},
                    {
                        "state": "reaping",
                        "reaping_started_at": {
                            "$lte": now
                            - timedelta(
                                seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS
                            )
                        },
                    },
                    {
                        "state": "reaping",
                        "reaping_started_at": {"$exists": False},
                    },
                ]
            }
        )
        processed = 0
        candidates = await cursor.to_list(length=limit)
        for receipt in candidates:
            owner_id = receipt.get("owner_id")
            slot = receipt.get("slot")
            candidate_key = receipt.get("candidate_key")
            if (
                not isinstance(owner_id, str)
                or slot not in STOREFRONT_ASSET_SLOTS
                or not isinstance(candidate_key, str)
                or not candidate_key.startswith(f"storefront/{owner_id}/{slot}/")
            ):
                logger.error(
                    "Invalid detached storefront cleanup receipt %s",
                    receipt.get("_id"),
                )
                invalid_filter: dict[str, Any] = {
                    "_id": receipt.get("_id"),
                    "state": receipt.get("state"),
                    "updated_at": receipt.get("updated_at"),
                }
                if "reap_token" in receipt:
                    invalid_filter["reap_token"] = receipt.get("reap_token")
                await receipts.update_one(
                    invalid_filter,
                    {
                        "$set": {
                            "state": "invalid",
                            "cleanup_validation_error": "invalid_owner_slot_or_key",
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )
                continue

            previous_state = receipt.get("state")
            previous_token = receipt.get("reap_token")
            reap_token = uuid4().hex
            claim_filter: dict[str, Any] = {
                "_id": receipt["_id"],
                "owner_id": owner_id,
                "candidate_key": candidate_key,
                "state": previous_state,
            }
            if previous_state == "reaping":
                claim_filter["reap_token"] = previous_token
                claim_filter["reaping_started_at"] = receipt.get("reaping_started_at")
            else:
                claim_filter["updated_at"] = receipt.get("updated_at")
                claim_filter["cleanup_due_at"] = receipt.get("cleanup_due_at")
            claimed = await receipts.update_one(
                claim_filter,
                {
                    "$set": {
                        "state": "reaping",
                        "reap_token": reap_token,
                        "reaping_started_at": now,
                        "updated_at": now,
                    }
                },
            )
            if not getattr(claimed, "modified_count", 0):
                continue

            canonical = await self._mongo.db["storefront_assets"].find_one(
                {
                    "owner_id": owner_id,
                    "key": candidate_key,
                    "state": {"$in": list(_FINALIZED_STATES)},
                },
                {"_id": 1},
            )
            if not canonical:
                try:
                    await self._delete_storage_keys([candidate_key])
                except Exception as exc:
                    retry_at = datetime.now(timezone.utc)
                    await receipts.update_one(
                        {
                            "_id": receipt["_id"],
                            "owner_id": owner_id,
                            "state": "reaping",
                            "reap_token": reap_token,
                        },
                        {
                            "$set": {
                                "state": "cleanup_retry",
                                "last_cleanup_error": exc.__class__.__name__,
                                "last_cleanup_attempt_at": retry_at,
                                "cleanup_due_at": retry_at
                                + timedelta(seconds=STOREFRONT_CLEANUP_RETRY_SECONDS),
                                "updated_at": retry_at,
                            },
                            "$inc": {"cleanup_attempts": 1},
                            "$unset": {
                                "reap_token": "",
                                "reaping_started_at": "",
                            },
                        },
                    )
                    continue
            deleted = await receipts.delete_one(
                {
                    "_id": receipt["_id"],
                    "owner_id": owner_id,
                    "state": "reaping",
                    "reap_token": reap_token,
                }
            )
            if getattr(deleted, "deleted_count", 0):
                processed += 1
        return processed, len(candidates)

    @staticmethod
    def _due_pending_settings_query() -> dict[str, Any]:
        """Find durable pending manifests whose recovery lease is available."""

        now = datetime.now(timezone.utc)
        return {
            PENDING_ASSET_GROUP_FIELD: {"$exists": True},
            "$or": [
                {PENDING_ASSET_RECOVERY_STATUS_FIELD: {"$exists": False}},
                {
                    PENDING_ASSET_RECOVERY_STATUS_FIELD: "retry_pending",
                    "$or": [
                        {PENDING_ASSET_RECOVERY_DUE_FIELD: {"$lte": now}},
                        {PENDING_ASSET_RECOVERY_DUE_FIELD: {"$exists": False}},
                    ],
                },
                {
                    PENDING_ASSET_RECOVERY_STATUS_FIELD: "recovering",
                    "$or": [
                        {PENDING_ASSET_RECOVERY_LEASE_FIELD: {"$lte": now}},
                        {PENDING_ASSET_RECOVERY_LEASE_FIELD: {"$exists": False}},
                    ],
                },
            ],
        }

    @staticmethod
    def _pending_manifest_snapshot(candidate: dict) -> dict[str, Any]:
        """Match an explicit manifest value without Mongo's null/missing alias."""

        return {
            PENDING_ASSET_GROUP_FIELD: candidate.get(PENDING_ASSET_GROUP_FIELD),
            "$and": [{PENDING_ASSET_GROUP_FIELD: {"$exists": True}}],
        }

    async def _claim_pending_settings_recovery(
        self, candidate: dict
    ) -> tuple[dict, str] | None:
        """Lease one exact pending manifest so concurrent leaders cannot mutate it."""

        planner_id = candidate.get("planner_id")
        recovery_token = uuid4().hex
        now = datetime.now(timezone.utc)
        claim_filter: dict[str, Any] = {
            "_id": candidate.get("_id"),
            **self._pending_manifest_snapshot(candidate),
            "$or": self._due_pending_settings_query()["$or"],
        }
        claim_filter["planner_id"] = (
            planner_id if "planner_id" in candidate else {"$exists": False}
        )
        attempts = candidate.get(PENDING_ASSET_RECOVERY_ATTEMPTS_FIELD)
        if PENDING_ASSET_RECOVERY_ATTEMPTS_FIELD in candidate:
            claim_filter[PENDING_ASSET_RECOVERY_ATTEMPTS_FIELD] = attempts
            claim_filter["$and"].append(
                {PENDING_ASSET_RECOVERY_ATTEMPTS_FIELD: {"$exists": True}}
            )
        else:
            claim_filter[PENDING_ASSET_RECOVERY_ATTEMPTS_FIELD] = {"$exists": False}
        normalized_attempts = (
            attempts
            if isinstance(attempts, int)
            and not isinstance(attempts, bool)
            and attempts >= 0
            else 0
        )
        claimed = await self._mongo.db["storefront_settings"].update_one(
            claim_filter,
            {
                "$set": {
                    PENDING_ASSET_RECOVERY_STATUS_FIELD: "recovering",
                    PENDING_ASSET_RECOVERY_TOKEN_FIELD: recovery_token,
                    PENDING_ASSET_RECOVERY_LEASE_FIELD: now
                    + timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS),
                    PENDING_ASSET_RECOVERY_ATTEMPTS_FIELD: normalized_attempts + 1,
                    "updated_at": now,
                },
                "$unset": {
                    PENDING_ASSET_RECOVERY_DUE_FIELD: "",
                    PENDING_ASSET_RECOVERY_ERROR_FIELD: "",
                },
            },
        )
        if not getattr(claimed, "modified_count", 0):
            return None
        return candidate, recovery_token

    async def _quarantine_pending_settings_recovery(
        self,
        candidate: dict,
        recovery_token: str,
        *,
        reason: str,
    ) -> bool:
        """Remove malformed settings intent from the hot queue without deleting it."""

        now = datetime.now(timezone.utc)
        result = await self._mongo.db["storefront_settings"].update_one(
            {
                "_id": candidate.get("_id"),
                "planner_id": candidate.get("planner_id"),
                **self._pending_manifest_snapshot(candidate),
                PENDING_ASSET_RECOVERY_STATUS_FIELD: "recovering",
                PENDING_ASSET_RECOVERY_TOKEN_FIELD: recovery_token,
            },
            {
                "$set": {
                    PENDING_ASSET_RECOVERY_STATUS_FIELD: "quarantined",
                    PENDING_ASSET_RECOVERY_ERROR_FIELD: reason,
                    "updated_at": now,
                },
                "$unset": {
                    PENDING_ASSET_RECOVERY_TOKEN_FIELD: "",
                    PENDING_ASSET_RECOVERY_LEASE_FIELD: "",
                    PENDING_ASSET_RECOVERY_DUE_FIELD: "",
                },
            },
        )
        return bool(getattr(result, "modified_count", 0))

    async def _defer_pending_settings_recovery(
        self,
        candidate: dict,
        recovery_token: str,
        exc: Exception,
    ) -> bool:
        """Defer a transient failure behind its exact lease token."""

        now = datetime.now(timezone.utc)
        result = await self._mongo.db["storefront_settings"].update_one(
            {
                "_id": candidate.get("_id"),
                "planner_id": candidate.get("planner_id"),
                **self._pending_manifest_snapshot(candidate),
                PENDING_ASSET_RECOVERY_STATUS_FIELD: "recovering",
                PENDING_ASSET_RECOVERY_TOKEN_FIELD: recovery_token,
            },
            {
                "$set": {
                    PENDING_ASSET_RECOVERY_STATUS_FIELD: "retry_pending",
                    PENDING_ASSET_RECOVERY_ERROR_FIELD: exc.__class__.__name__,
                    PENDING_ASSET_RECOVERY_DUE_FIELD: now
                    + timedelta(seconds=STOREFRONT_CLEANUP_RETRY_SECONDS),
                    "updated_at": now,
                },
                "$unset": {
                    PENDING_ASSET_RECOVERY_TOKEN_FIELD: "",
                    PENDING_ASSET_RECOVERY_LEASE_FIELD: "",
                },
            },
        )
        return bool(getattr(result, "modified_count", 0))

    async def _recover_pending_settings_candidate(
        self, candidate: dict, recovery_token: str
    ) -> bool:
        """Resolve one leased settings manifest without an entitlement lookup."""

        planner_id = candidate.get("planner_id")
        if not isinstance(planner_id, str) or not planner_id:
            return await self._quarantine_pending_settings_recovery(
                candidate,
                recovery_token,
                reason="invalid_planner_owner",
            )
        settings = self._mongo.db["storefront_settings"]
        assets = self._mongo.db["storefront_assets"]
        row = await settings.find_one(
            {
                "_id": candidate.get("_id"),
                "planner_id": planner_id,
                **self._pending_manifest_snapshot(candidate),
                PENDING_ASSET_RECOVERY_STATUS_FIELD: "recovering",
                PENDING_ASSET_RECOVERY_TOKEN_FIELD: recovery_token,
            }
        )
        if not row:
            return False

        manifest = row.get(PENDING_ASSET_GROUP_FIELD)
        parsed_manifest = self._entries_from_manifest(manifest)
        if not parsed_manifest:
            return await self._quarantine_pending_settings_recovery(
                candidate,
                recovery_token,
                reason="invalid_pending_manifest",
            )
        claim_id, entries, values = parsed_manifest
        if not self._row_has_exact_manifest_pairs(row, claim_id, values):
            return await self._quarantine_pending_settings_recovery(
                candidate,
                recovery_token,
                reason="invalid_pending_pairs",
            )

        claim = {
            "owner_id": planner_id,
            "claim_id": claim_id,
            "values": values,
            "claimed_assets": entries,
            "manifest": manifest,
            "settings_recovery_token": recovery_token,
        }
        for entry in entries:
            asset = await assets.find_one(
                {
                    "_id": self._asset_query_id(entry["asset_id"]),
                    "owner_id": planner_id,
                    "slot": entry["slot"],
                    "$or": [
                        {"state": "attaching", "attach_claim_id": claim_id},
                        {"state": "attached", "attached_claim_id": claim_id},
                    ],
                },
                {"_id": 1},
            )
            if asset:
                continue
            await self._rollback_settings_asset_group(
                self._maintenance_owner(planner_id), claim
            )
            return True

        owner = self._maintenance_owner(planner_id)
        await self.attach_settings_asset_claims(owner, claim)
        await self.promote_settings_asset_claims(owner, claim)
        return True

    async def _sweep_pending_settings_manifests(self, *, limit: int) -> tuple[int, int]:
        settings = self._mongo.db["storefront_settings"]
        candidates = await (
            settings.find(self._due_pending_settings_query())
            .sort(
                [
                    (PENDING_ASSET_RECOVERY_DUE_FIELD, 1),
                    (PENDING_ASSET_RECOVERY_LEASE_FIELD, 1),
                    ("updated_at", 1),
                    ("planner_id", 1),
                ]
            )
            .to_list(length=limit)
        )
        processed = 0
        for candidate in candidates:
            claimed = await self._claim_pending_settings_recovery(candidate)
            if not claimed:
                continue
            claimed_candidate, recovery_token = claimed
            try:
                if await self._recover_pending_settings_candidate(
                    claimed_candidate, recovery_token
                ):
                    processed += 1
            except Exception as exc:
                await self._defer_pending_settings_recovery(
                    claimed_candidate, recovery_token, exc
                )
                logger.warning(
                    "Deferred storefront pending manifest recovery for owner %s: %s",
                    claimed_candidate.get("planner_id"),
                    exc.__class__.__name__,
                )
        return processed, len(candidates)

    @staticmethod
    def _due_settings_claim_query() -> dict[str, Any]:
        """Return stale claim receipts eligible for global reconciliation."""

        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS)
        return {
            "$or": [
                {
                    "state": "attaching",
                    "$and": [
                        {
                            "$or": [
                                {"attach_claimed_at": {"$lte": stale_before}},
                                {
                                    "attach_claimed_at": {"$exists": False},
                                    "updated_at": {"$lte": stale_before},
                                },
                            ]
                        },
                        {
                            "$or": [
                                {"claim_reconcile_due_at": {"$lte": now}},
                                {"claim_reconcile_due_at": {"$exists": False}},
                            ]
                        },
                    ],
                },
                {
                    "state": "attached",
                    "$or": [
                        {"claim_reconcile_due_at": {"$lte": now}},
                        {
                            "claim_reconcile_due_at": {"$exists": False},
                            "updated_at": {"$lte": stale_before},
                        },
                        {
                            "claim_reconcile_due_at": {"$exists": False},
                            "updated_at": {"$exists": False},
                        },
                    ],
                },
            ]
        }

    @staticmethod
    def _maintenance_owner(owner_id: str) -> dict[str, str]:
        """Build an internal owner identity without consulting entitlements."""

        return {"_id": owner_id, "role": "wedding_planner"}

    @staticmethod
    def _settings_claim_snapshot_filter(asset: dict) -> dict[str, Any]:
        """Build an exact receipt fence, including absent malformed fields."""

        snapshot: dict[str, Any] = {"_id": asset.get("_id")}
        for field in (
            "owner_id",
            "slot",
            "state",
            "attach_claim_id",
            "attach_claimed_at",
            "attached_claim_id",
            "updated_at",
            "claim_reconcile_due_at",
        ):
            snapshot[field] = asset[field] if field in asset else {"$exists": False}
        return snapshot

    async def _quarantine_settings_claim_candidate(self, asset: dict) -> bool:
        now = datetime.now(timezone.utc)
        result = await self._mongo.db["storefront_assets"].update_one(
            self._settings_claim_snapshot_filter(asset),
            {
                "$set": {
                    "state": "claim_quarantined",
                    "claim_reconcile_error": "invalid_claim_receipt",
                    "claim_quarantined_at": now,
                    "updated_at": now,
                },
                "$unset": {"claim_reconcile_due_at": ""},
            },
        )
        return bool(getattr(result, "modified_count", 0))

    async def _defer_settings_claim_candidate(
        self, asset: dict, exc: Exception
    ) -> bool:
        now = datetime.now(timezone.utc)
        result = await self._mongo.db["storefront_assets"].update_one(
            self._settings_claim_snapshot_filter(asset),
            {
                "$set": {
                    "claim_reconcile_due_at": now
                    + timedelta(seconds=STOREFRONT_CLEANUP_RETRY_SECONDS),
                    "claim_reconcile_error": exc.__class__.__name__,
                    "updated_at": now,
                }
            },
        )
        return bool(getattr(result, "modified_count", 0))

    async def _reconcile_settings_claim_candidate(self, asset: dict) -> bool:
        """Reconcile one stale claim against canonical settings with exact fences."""

        owner_id = asset.get("owner_id")
        slot = asset.get("slot")
        state = asset.get("state")
        if (
            not isinstance(owner_id, str)
            or slot not in STOREFRONT_ASSET_SLOTS
            or state not in {"attaching", "attached"}
        ):
            return await self._quarantine_settings_claim_candidate(asset)
        token_field = "attach_claim_id" if state == "attaching" else "attached_claim_id"
        claim_id = asset.get(token_field)
        if not isinstance(claim_id, str) or not claim_id:
            return await self._quarantine_settings_claim_candidate(asset)

        settings = self._mongo.db["storefront_settings"]
        assets = self._mongo.db["storefront_assets"]
        settings_row = await settings.find_one({"planner_id": owner_id})
        settings_row = settings_row or {}
        owner = self._maintenance_owner(owner_id)
        asset_id = str(asset["_id"])

        parsed_manifest = self._entries_from_manifest(
            settings_row.get(PENDING_ASSET_GROUP_FIELD)
        )
        if parsed_manifest and parsed_manifest[0] == claim_id:
            manifest_claim_id, entries, values = parsed_manifest
            if any(
                entry["asset_id"] == asset_id and entry["slot"] == slot
                for entry in entries
            ):
                await self.reconcile_settings_asset_claims(
                    owner,
                    {
                        "owner_id": owner_id,
                        "claim_id": manifest_claim_id,
                        "claimed_assets": entries,
                        "values": values,
                        "manifest": settings_row[PENDING_ASSET_GROUP_FIELD],
                    },
                )
                return True

        pending_entries: list[dict[str, str]] = []
        for pending_slot in ("hero", "about"):
            if settings_row.get(f"pending_{pending_slot}_claim_id") != claim_id:
                continue
            pending_asset_id = settings_row.get(f"pending_{pending_slot}_asset_id")
            if isinstance(pending_asset_id, str):
                pending_entries.append(
                    {
                        "asset_id": pending_asset_id,
                        "slot": pending_slot,
                        "field_name": f"{pending_slot}_asset_id",
                    }
                )
        if pending_entries:
            await self._rollback_settings_asset_group(
                owner,
                {
                    "owner_id": owner_id,
                    "claim_id": claim_id,
                    "claimed_assets": pending_entries,
                },
            )
            return True

        stable_reference = settings_row.get(f"{slot}_asset_id") == asset_id
        now = datetime.now(timezone.utc)
        if state == "attaching":
            target_state = "attached" if stable_reference else "ready"
            set_fields: dict[str, Any] = {
                "state": target_state,
                "updated_at": now,
            }
            unset_fields = {
                "attach_claim_id": "",
                "attach_claimed_at": "",
            }
            if stable_reference:
                set_fields.update(
                    {
                        "attached_claim_id": claim_id,
                        "attached_at": now,
                        "claim_reconcile_due_at": now
                        + timedelta(seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS),
                    }
                )
                unset_fields["cleanup_due_at"] = ""
            else:
                set_fields["cleanup_due_at"] = now + timedelta(
                    seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS
                )
                unset_fields.update(
                    {
                        "attached_claim_id": "",
                        "attached_at": "",
                        "claim_reconcile_due_at": "",
                    }
                )
            result = await assets.update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "slot": slot,
                    "state": "attaching",
                    "attach_claim_id": claim_id,
                    "attach_claimed_at": asset.get("attach_claimed_at"),
                },
                {"$set": set_fields, "$unset": unset_fields},
            )
            return bool(getattr(result, "modified_count", 0))

        exact_filter = {
            "_id": asset["_id"],
            "owner_id": owner_id,
            "slot": slot,
            "state": "attached",
            "attached_claim_id": claim_id,
            "updated_at": asset.get("updated_at"),
        }
        if stable_reference:
            await assets.update_one(
                exact_filter,
                {
                    "$set": {
                        "claim_reconciled_at": now,
                        "claim_reconcile_due_at": now
                        + timedelta(seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS),
                    }
                },
            )
            return False

        released = await assets.update_one(
            exact_filter,
            {
                "$set": {
                    "state": "ready",
                    "cleanup_due_at": now
                    + timedelta(seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS),
                    "updated_at": now,
                },
                "$unset": {
                    "attached_claim_id": "",
                    "attached_at": "",
                    "claim_reconcile_due_at": "",
                    "claim_reconciled_at": "",
                },
            },
        )
        return bool(getattr(released, "modified_count", 0))

    async def _sweep_settings_claims(self, *, limit: int) -> tuple[int, int]:
        assets = self._mongo.db["storefront_assets"]
        candidates = await (
            assets.find(self._due_settings_claim_query())
            .sort(
                [
                    ("claim_reconcile_due_at", 1),
                    ("updated_at", 1),
                    ("owner_id", 1),
                    ("_id", 1),
                ]
            )
            .to_list(length=limit)
        )
        processed = 0
        for asset in candidates:
            try:
                if await self._reconcile_settings_claim_candidate(asset):
                    processed += 1
            except Exception as exc:
                await self._defer_settings_claim_candidate(asset, exc)
                logger.warning(
                    "Deferred storefront asset %s settings claim for owner %s: %s",
                    asset.get("_id"),
                    asset.get("owner_id"),
                    exc.__class__.__name__,
                )
        return processed, len(candidates)

    async def sweep_abandoned_assets(
        self, *, limit: int = STOREFRONT_MAINTENANCE_BATCH_SIZE
    ) -> int:
        """Bound one leader-elected maintenance tick across every owner."""

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 500
        ):
            raise ValueError("Storefront maintenance limit must be between 1 and 500")

        async def sweep_cleanup_assets(*, limit: int) -> tuple[int, int]:
            return await self._sweep_due_cleanup_assets(
                owner_id=None,
                limit=limit,
            )

        queues = (
            self._sweep_detached_candidate_receipts,
            sweep_cleanup_assets,
            self._sweep_settings_claims,
            self._sweep_pending_settings_manifests,
        )
        start = self._maintenance_queue_cursor % len(queues)
        queue_order = [*range(start, len(queues)), *range(0, start)]
        remaining = limit
        processed = 0
        last_attempted_queue: int | None = None

        for position, queue_index in enumerate(queue_order):
            if remaining <= 0:
                break
            queues_after = len(queue_order) - position - 1
            queue_limit = (
                remaining if remaining == 1 else max(1, remaining - queues_after)
            )
            queue_processed, queue_attempted = await queues[queue_index](
                limit=queue_limit
            )
            processed += queue_processed
            remaining -= queue_attempted
            if queue_attempted:
                last_attempted_queue = queue_index

        next_queue = start if last_attempted_queue is None else last_attempted_queue
        self._maintenance_queue_cursor = (next_queue + 1) % len(queues)
        return processed

    async def _recover_abandoned_cleanable_assets(self, owner: Any) -> None:
        """Use the same token-fenced sweep for the current owner."""

        await self._sweep_due_cleanup_assets(
            owner_id=self._owner_id(owner),
            limit=STOREFRONT_MAINTENANCE_BATCH_SIZE,
        )

    async def recover_pending_settings_assets(self, owner: Any) -> None:
        """Complete or safely discard durable pending handoffs after a crash."""

        owner_id = self._owner_id(owner)
        settings = self._mongo.db["storefront_settings"]
        assets = self._mongo.db["storefront_assets"]
        for _attempt in range(4):
            row = await settings.find_one({"planner_id": owner_id})
            if not row:
                await self._recover_orphaned_owner_assets(owner_id, None)
                await self._recover_abandoned_cleanable_assets(owner)
                return

            manifest = row.get(PENDING_ASSET_GROUP_FIELD)
            parsed_manifest = self._entries_from_manifest(manifest)
            if parsed_manifest:
                claim_id, entries, values = parsed_manifest
                claim = {
                    "owner_id": owner_id,
                    "claim_id": claim_id,
                    "values": values,
                    "claimed_assets": entries,
                    "manifest": manifest,
                }
                group_is_valid = self._row_has_exact_manifest_pairs(
                    row, claim_id, values
                )
                if group_is_valid:
                    for entry in entries:
                        asset = await assets.find_one(
                            {
                                "_id": self._asset_query_id(entry["asset_id"]),
                                "owner_id": owner_id,
                                "slot": entry["slot"],
                                "$or": [
                                    {
                                        "state": "attaching",
                                        "attach_claim_id": claim_id,
                                    },
                                    {
                                        "state": "attached",
                                        "attached_claim_id": claim_id,
                                    },
                                ],
                            },
                            {"_id": 1},
                        )
                        if not asset:
                            group_is_valid = False
                            break
                if group_is_valid:
                    await self.attach_settings_asset_claims(owner, claim)
                    await self.promote_settings_asset_claims(owner, claim)
                    continue
                await self._rollback_settings_asset_group(owner, claim)
                continue

            if manifest is not None:
                cleared_manifest = await settings.update_one(
                    {
                        "planner_id": owner_id,
                        PENDING_ASSET_GROUP_FIELD: manifest,
                    },
                    {
                        "$unset": {PENDING_ASSET_GROUP_FIELD: ""},
                        "$set": {"updated_at": datetime.now(timezone.utc)},
                        "$inc": {"revision": 1},
                    },
                )
                if not getattr(cleared_manifest, "modified_count", 0):
                    continue

            claims_by_token: dict[str, list[dict[str, str]]] = {}
            invalid_pending: list[tuple[str, Any, Any]] = []
            for slot in ("hero", "about"):
                asset_field = f"pending_{slot}_asset_id"
                claim_field = f"pending_{slot}_claim_id"
                pending_asset_id = row.get(asset_field)
                pending_claim_id = row.get(claim_field)
                if pending_asset_id is None and pending_claim_id is None:
                    continue
                if not isinstance(pending_asset_id, str) or not isinstance(
                    pending_claim_id, str
                ):
                    invalid_pending.append((slot, pending_asset_id, pending_claim_id))
                    continue
                claims_by_token.setdefault(pending_claim_id, []).append(
                    {
                        "asset_id": pending_asset_id,
                        "slot": slot,
                        "field_name": f"{slot}_asset_id",
                    }
                )

            for claim_id, entries in claims_by_token.items():
                await self._rollback_settings_asset_group(
                    owner,
                    {
                        "owner_id": owner_id,
                        "claim_id": claim_id,
                        "claimed_assets": entries,
                    },
                )

            for slot, pending_asset_id, pending_claim_id in invalid_pending:
                asset_field = f"pending_{slot}_asset_id"
                claim_field = f"pending_{slot}_claim_id"
                await settings.update_one(
                    {
                        "planner_id": owner_id,
                        asset_field: pending_asset_id,
                        claim_field: pending_claim_id,
                    },
                    {
                        "$unset": {asset_field: "", claim_field: ""},
                        "$set": {"updated_at": datetime.now(timezone.utc)},
                        "$inc": {"revision": 1},
                    },
                )

            if not claims_by_token and not invalid_pending and manifest is None:
                break

        refreshed_row = await settings.find_one({"planner_id": owner_id})
        if refreshed_row and (
            refreshed_row.get(PENDING_ASSET_GROUP_FIELD) is not None
            or any(
                refreshed_row.get(f"pending_{slot}_{suffix}") is not None
                for slot in ("hero", "about")
                for suffix in ("asset_id", "claim_id")
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset recovery changed concurrently; retry the edit",
            )
        await self._recover_orphaned_owner_assets(owner_id, refreshed_row)
        await self._recover_abandoned_cleanable_assets(owner)

    async def attach(self, owner: Any, asset_id: str, slot: str) -> dict:
        """Mark a validated asset attached after its settings write succeeds."""

        owner_id = await self._require_storefront(owner)
        asset = await self._validate_owned_asset_for_slot(owner_id, asset_id, slot)
        referenced = await self._mongo.db["storefront_settings"].find_one(
            {
                "planner_id": owner_id,
                f"{slot}_asset_id": str(asset["_id"]),
            },
            {"_id": 1},
        )
        if not referenced:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset must be saved in its settings slot before attachment",
            )
        if asset.get("state") == "ready":
            now = datetime.now(timezone.utc)
            result = await self._mongo.db["storefront_assets"].update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "slot": slot,
                    "state": "ready",
                },
                {
                    "$set": {
                        "state": "attached",
                        "attached_at": now,
                        "updated_at": now,
                    },
                    "$unset": {"cleanup_due_at": ""},
                },
            )
            if not getattr(result, "modified_count", 0):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront asset changed concurrently; reload and retry",
                )
            asset = {**asset, "state": "attached", "attached_at": now}
        return self._serialize_asset(asset)

    async def release_if_unreferenced(self, owner: Any, asset_id: str) -> dict:
        """Make a replaced attachment cleanable after settings stop using it."""

        owner_id = await self._require_storefront(owner)
        asset = await self._find_owned_asset(owner_id, asset_id)
        if asset.get("state") != "attached" or await self._is_referenced(
            owner_id, str(asset["_id"])
        ):
            return self._serialize_asset(asset)

        now = datetime.now(timezone.utc)
        result = await self._mongo.db["storefront_assets"].update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "state": "attached",
            },
            {
                "$set": {
                    "state": "ready",
                    "cleanup_due_at": now
                    + timedelta(seconds=STOREFRONT_READY_ASSET_CLEANUP_SECONDS),
                    "updated_at": now,
                },
                "$unset": {"attached_at": "", "attached_claim_id": ""},
            },
        )
        if not getattr(result, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset changed concurrently; reload and retry",
            )
        return self._serialize_asset({**asset, "state": "ready", "updated_at": now})


storefront_media_service = StorefrontMediaService()
