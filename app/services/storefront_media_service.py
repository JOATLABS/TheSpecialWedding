"""Planner-owned storefront image reservation and cleanup lifecycle."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
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
        assets = self._mongo.db["storefront_assets"]

        existing = await assets.find_one(
            {
                "owner_id": owner_id,
                "slot": normalized_slot,
                "state": "reserved",
            },
            {"_id": 1},
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An upload is already pending for this storefront image slot",
            )

        asset_object_id = ObjectId()
        asset_id = str(asset_object_id)
        extension = _CONTENT_TYPE_EXTENSIONS[content_type]
        key = f"storefront/{owner_id}/{normalized_slot}/{asset_id}{extension}"
        cdn_url = self._storage.build_public_url(StorageTarget.BLOG_ASSETS, key)
        now = datetime.now(timezone.utc)
        reservation = {
            "_id": asset_object_id,
            "owner_id": owner_id,
            "slot": normalized_slot,
            "key": key,
            "cdn_url": cdn_url,
            "declared_content_type": content_type,
            "declared_size_bytes": size_bytes,
            "state": "reserved",
            "cleanup_attempts": 0,
            "created_at": now,
            "updated_at": now,
        }

        try:
            await assets.insert_one(reservation)
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An upload is already pending for this storefront image slot",
            ) from exc
        except Exception as exc:
            logger.exception(
                "Failed to reserve storefront asset for owner %s", owner_id
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image reservation is temporarily unavailable",
            ) from exc

        try:
            upload_url = await asyncio.to_thread(
                self._storage.generate_presigned_put_url,
                StorageTarget.BLOG_ASSETS,
                key=key,
                expires_in=STOREFRONT_UPLOAD_URL_TTL_SECONDS,
                content_type=content_type,
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
            "cdn_url": cdn_url,
            "key": key,
            "max_size_bytes": MAX_STOREFRONT_ASSET_SIZE_BYTES,
        }

    @staticmethod
    def _asset_query_id(asset_id: str) -> Any:
        return normalize_query_id(asset_id)

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
        return None

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

    async def _discard_invalid_upload(self, asset: dict, reason: str) -> None:
        assets = self._mongo.db["storefront_assets"]
        try:
            await asyncio.to_thread(
                self._storage.delete_object,
                StorageTarget.BLOG_ASSETS,
                asset["key"],
            )
        except Exception as exc:
            logger.exception(
                "Failed to delete invalid storefront upload %s", asset["_id"]
            )
            await self._record_cleanup_retry(
                asset,
                reason="invalid_upload",
                error=exc,
                expected_states=["reserved"],
            )
        else:
            await assets.delete_one(
                {
                    "_id": asset["_id"],
                    "owner_id": asset["owner_id"],
                    "state": "reserved",
                }
            )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=reason,
        )

    async def finalize(self, owner: Any, asset_id: str) -> dict:
        """HEAD-validate a browser upload before making it settings-eligible."""

        owner_id = await self._require_storefront(owner)
        asset = await self._find_owned_asset(owner_id, asset_id)
        if asset.get("state") in _FINALIZED_STATES:
            return self._serialize_asset(asset)
        if asset.get("state") != "reserved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset is not awaiting finalization",
            )

        try:
            head = await asyncio.to_thread(
                self._storage.head_object,
                StorageTarget.BLOG_ASSETS,
                asset["key"],
            )
        except Exception as exc:
            logger.exception("Failed to inspect storefront upload %s", asset["_id"])
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront image storage is temporarily unavailable",
            ) from exc

        contract_error = self._head_contract_error(asset, head)
        if contract_error:
            await self._discard_invalid_upload(asset, contract_error)

        now = datetime.now(timezone.utc)
        update = {
            "state": "ready",
            "actual_size_bytes": head["ContentLength"],
            "actual_content_type": head["ContentType"],
            "etag": head.get("ETag"),
            "finalized_at": now,
            "updated_at": now,
        }
        result = await self._mongo.db["storefront_assets"].update_one(
            {
                "_id": asset["_id"],
                "owner_id": owner_id,
                "state": "reserved",
            },
            {
                "$set": update,
                "$unset": {
                    "cleanup_reason": "",
                    "last_cleanup_error": "",
                    "last_cleanup_attempt_at": "",
                },
            },
        )
        if not getattr(result, "modified_count", 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Storefront asset changed concurrently; reload and retry",
            )
        return self._serialize_asset({**asset, **update})

    async def _is_referenced(self, owner_id: str, asset_id: str) -> bool:
        settings = await self._mongo.db["storefront_settings"].find_one(
            {
                "planner_id": owner_id,
                "$or": [
                    {"hero_asset_id": asset_id},
                    {"about_asset_id": asset_id},
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
            await asyncio.to_thread(
                self._storage.delete_object,
                StorageTarget.BLOG_ASSETS,
                asset["key"],
            )
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
        self, owner_id: str, asset_id: str, slot: str
    ) -> dict:
        normalized_slot = self._validate_slot(slot)
        asset = await self._find_owned_asset(owner_id, asset_id)
        if asset.get("slot") != normalized_slot:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Storefront asset was not uploaded for the {normalized_slot} slot",
            )
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
