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
from app.core.database import mongo
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
STOREFRONT_RESERVATION_TTL_SECONDS = STOREFRONT_UPLOAD_URL_TTL_SECONDS
STOREFRONT_ASSET_OPERATION_LEASE_SECONDS = 10 * 60
MAX_STOREFRONT_IMAGE_DIMENSION = 12_000
MAX_STOREFRONT_IMAGE_PIXELS = 40_000_000

_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_FINALIZED_STATES = frozenset({"ready", "attached"})
_CLEANABLE_STATES = frozenset({"reserved", "ready", "cleanup_retry", "deleting"})


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

        existing = await assets.find_one(
            {
                "owner_id": owner_id,
                "slot": normalized_slot,
                "state": "reserved",
            }
        )
        if existing:
            expires_at = existing.get("reservation_expires_at")
            if not isinstance(expires_at, datetime) or not self._datetime_is_expired(
                expires_at
            ):
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

    async def _reap_expired_reservation(self, owner_id: str, asset: dict) -> None:
        assets = self._mongo.db["storefront_assets"]
        reap_token = uuid4().hex
        claimed = await assets.update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "slot": asset["slot"],
                "state": "reserved",
                "reservation_expires_at": {"$lte": datetime.now(timezone.utc)},
            },
            {
                "$set": {
                    "state": "reaping",
                    "reap_token": reap_token,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if not getattr(claimed, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront upload reservation changed; reload and retry",
            )
        try:
            await self._delete_storage_keys(
                [asset["staging_key"]],
                target=StorageTarget.STOREFRONT_STAGING,
            )
        except Exception as exc:
            await assets.update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "reaping",
                    "reap_token": reap_token,
                },
                {
                    "$set": {
                        "state": "cleanup_retry",
                        "cleanup_reason": "expired_reservation",
                        "last_cleanup_error": exc.__class__.__name__,
                        "last_cleanup_attempt_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$inc": {"cleanup_attempts": 1},
                    "$unset": {"reap_token": ""},
                },
            )
            return
        try:
            await assets.delete_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": "reaping",
                    "reap_token": reap_token,
                }
            )
        except Exception:
            logger.exception(
                "Failed to remove reaped storefront reservation %s", asset["_id"]
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
            sanitized.save(output, format=image_format, quality=90, optimize=True)
        elif image_format == "PNG":
            sanitized.save(output, format=image_format, optimize=True)
        elif image_format == "WEBP":
            sanitized.save(output, format=image_format, quality=90, method=6)
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
    ) -> None:
        await self._mongo.db["storefront_assets"].update_one(
            {
                "_id": asset["_id"],
                "owner_id": asset["owner_id"],
                "state": {"$in": expected_states},
            },
            {
                "$set": {
                    "state": "cleanup_retry",
                    "cleanup_reason": reason,
                    "last_cleanup_error": error.__class__.__name__,
                    "last_cleanup_attempt_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
                "$inc": {"cleanup_attempts": 1},
            },
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
                    "cleanup_candidate_key": candidate_key,
                    "cleanup_reason": "invalid_upload",
                    "updated_at": datetime.now(timezone.utc),
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
            try:
                await self._delete_storage_keys([candidate_key])
            except Exception:
                logger.exception(
                    "Failed to remove abandoned storefront candidate %s",
                    candidate_key,
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront finalization lease changed; reload and retry",
            )

        cleanup_asset = {
            **asset,
            "state": "deleting",
            "cleanup_token": cleanup_token,
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
            reservation_expires_at = asset.get("reservation_expires_at")
            if not isinstance(
                reservation_expires_at, datetime
            ) or self._datetime_is_expired(reservation_expires_at):
                if isinstance(reservation_expires_at, datetime):
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
            try:
                await self._delete_storage_keys([candidate_key])
            except Exception:
                logger.exception(
                    "Lost finalizer could not remove its candidate %s",
                    candidate_key,
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
                    logger.exception(
                        "Lost finalizer could not remove its candidate %s",
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
            try:
                await self._delete_storage_keys([candidate_key])
            except Exception:
                logger.exception(
                    "Lost finalizer could not remove its candidate %s",
                    candidate_key,
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
        if asset.get("state") != "deleting":
            claim = await assets.update_one(
                {
                    "_id": asset["_id"],
                    "owner_id": owner_id,
                    "state": asset["state"],
                },
                {
                    "$set": {
                        "state": "deleting",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            if not getattr(claim, "modified_count", 0):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Storefront asset changed concurrently; reload and retry",
                )
            asset = {**asset, "state": "deleting"}

        # Recheck after the delete claim. Attachment helpers require a ready
        # state, so this closes the attach/delete race for service-owned flows.
        if await self._is_referenced(owner_id, normalized_asset_id):
            await assets.update_one(
                {"_id": asset["_id"], "owner_id": owner_id, "state": "deleting"},
                {
                    "$set": {
                        "state": "attached",
                        "updated_at": datetime.now(timezone.utc),
                    }
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
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image cleanup is pending; retry later",
            ) from exc

        await assets.delete_one(
            {"_id": asset["_id"], "owner_id": owner_id, "state": "deleting"}
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
        for entry in entries:
            if not isinstance(entry, dict) or not all(
                isinstance(entry.get(field), str)
                for field in ("asset_id", "slot", "field_name")
            ):
                raise RuntimeError("Invalid storefront asset claim receipt")
            normalized_entries.append(entry)
        return claim_id, normalized_entries

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
                        }
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

        return {
            "owner_id": owner_id,
            "claim_id": claim_id,
            "values": values,
            "claimed_assets": claimed_assets,
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
            else:
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
                {"state": 1},
            )
            if current and current.get("state") in _FINALIZED_STATES:
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
        assets = self._mongo.db["storefront_assets"]
        settings = self._mongo.db["storefront_settings"]
        for entry in entries:
            pending_asset_field = f"pending_{entry['slot']}_asset_id"
            pending_claim_field = f"pending_{entry['slot']}_claim_id"
            referenced = await settings.find_one(
                {
                    "planner_id": owner_id,
                    pending_asset_field: entry["asset_id"],
                    pending_claim_field: claim_id,
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

    async def promote_settings_asset_claims(self, owner: Any, claim: dict) -> None:
        """Atomically replace stable settings IDs after every claim is attached."""

        owner_id = self._owner_id(owner)
        if claim.get("owner_id") != owner_id:
            raise RuntimeError("Storefront asset claim owner mismatch")
        claim_id, entries = self._claim_entries(claim)
        if not entries:
            return
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

        promote_filter: dict[str, Any] = {"planner_id": owner_id}
        stable_updates: dict[str, str] = {}
        pending_unsets: dict[str, str] = {}
        for entry in entries:
            pending_asset_field = f"pending_{entry['slot']}_asset_id"
            pending_claim_field = f"pending_{entry['slot']}_claim_id"
            promote_filter[pending_asset_field] = entry["asset_id"]
            promote_filter[pending_claim_field] = claim_id
            stable_updates[entry["field_name"]] = entry["asset_id"]
            pending_unsets[pending_asset_field] = ""
            pending_unsets[pending_claim_field] = ""

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

        current = await settings.find_one({"planner_id": owner_id})
        if current and all(
            current.get(entry["field_name"]) == entry["asset_id"]
            and current.get(f"pending_{entry['slot']}_asset_id") is None
            and current.get(f"pending_{entry['slot']}_claim_id") is None
            for entry in entries
        ):
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Storefront asset promotion lost its pending settings fence",
        )

    async def reconcile_settings_asset_claims(self, owner: Any, claim: dict) -> None:
        """Resolve an ambiguous settings write without exposing cleanup races."""

        owner_id = self._owner_id(owner)
        if claim.get("owner_id") != owner_id:
            raise RuntimeError("Storefront asset claim owner mismatch")
        claim_id, entries = self._claim_entries(claim)
        settings = self._mongo.db["storefront_settings"]
        referenced: list[dict[str, str]] = []
        unreferenced: list[dict[str, str]] = []
        for entry in entries:
            row = await settings.find_one(
                {
                    "planner_id": owner_id,
                    f"pending_{entry['slot']}_asset_id": entry["asset_id"],
                    f"pending_{entry['slot']}_claim_id": claim_id,
                },
                {"_id": 1},
            )
            (referenced if row else unreferenced).append(entry)

        if referenced:
            referenced_claim = {**claim, "claimed_assets": referenced}
            await self.attach_settings_asset_claims(owner, referenced_claim)
            await self.promote_settings_asset_claims(owner, referenced_claim)
        if unreferenced:
            await self.release_settings_asset_claims(
                owner, {**claim, "claimed_assets": unreferenced}
            )

    async def recover_pending_settings_assets(self, owner: Any) -> None:
        """Complete or safely discard durable pending handoffs after a crash."""

        owner_id = self._owner_id(owner)
        settings = self._mongo.db["storefront_settings"]
        assets = self._mongo.db["storefront_assets"]
        row = await settings.find_one({"planner_id": owner_id})
        if not row:
            return

        claims_by_token: dict[str, list[dict[str, str]]] = {}
        invalid_pending: list[tuple[str, Any, Any]] = []
        for slot in ("hero", "about"):
            pending_asset_field = f"pending_{slot}_asset_id"
            pending_claim_field = f"pending_{slot}_claim_id"
            pending_asset_id = row.get(pending_asset_field)
            pending_claim_id = row.get(pending_claim_field)
            if pending_asset_id is None and pending_claim_id is None:
                continue
            if not isinstance(pending_asset_id, str) or not isinstance(
                pending_claim_id, str
            ):
                invalid_pending.append((slot, pending_asset_id, pending_claim_id))
                continue
            asset = await assets.find_one(
                {
                    "_id": self._asset_query_id(pending_asset_id),
                    "owner_id": owner_id,
                    "slot": slot,
                    "$or": [
                        {
                            "state": "attaching",
                            "attach_claim_id": pending_claim_id,
                        },
                        {
                            "state": "attached",
                            "attached_claim_id": pending_claim_id,
                        },
                    ],
                },
                {"_id": 1},
            )
            if not asset:
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
            claim = {
                "owner_id": owner_id,
                "claim_id": claim_id,
                "claimed_assets": entries,
            }
            await self.attach_settings_asset_claims(owner, claim)
            await self.promote_settings_asset_claims(owner, claim)

        for slot, pending_asset_id, pending_claim_id in invalid_pending:
            pending_asset_field = f"pending_{slot}_asset_id"
            pending_claim_field = f"pending_{slot}_claim_id"
            cleared = await settings.update_one(
                {
                    "planner_id": owner_id,
                    pending_asset_field: pending_asset_id,
                    pending_claim_field: pending_claim_id,
                },
                {
                    "$unset": {
                        pending_asset_field: "",
                        pending_claim_field: "",
                    },
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                    "$inc": {"revision": 1},
                },
            )
            if not getattr(cleared, "modified_count", 0):
                logger.info(
                    "Skipped stale pending storefront %s recovery for owner %s",
                    slot,
                    owner_id,
                )

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
                {"$set": {"state": "attached", "attached_at": now, "updated_at": now}},
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
                "$set": {"state": "ready", "updated_at": now},
                "$unset": {"attached_at": ""},
            },
        )
        if not getattr(result, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset changed concurrently; reload and retry",
            )
        return self._serialize_asset({**asset, "state": "ready", "updated_at": now})


storefront_media_service = StorefrontMediaService()
