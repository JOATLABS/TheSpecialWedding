from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import threading
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException
from PIL import Image
from pymongo.errors import DuplicateKeyError

import app.services.storefront_media_service as storefront_media_module
from app.services.storefront_entitlement_service import StorefrontEntitlements
from app.services.storefront_media_service import (
    MAX_STOREFRONT_ASSET_SIZE_BYTES,
    MAX_STOREFRONT_IMAGE_DIMENSION,
    MAX_STOREFRONT_IMAGE_PIXELS,
    STOREFRONT_ASSET_OPERATION_LEASE_SECONDS,
    STOREFRONT_CLEANUP_RETRY_SECONDS,
    STOREFRONT_RESERVATION_TTL_SECONDS,
    STOREFRONT_READY_ASSET_CLEANUP_SECONDS,
    StorefrontMediaService,
)
from app.services.media_storage import StorageTarget


OWNER_ID = "507f1f77bcf86cd799439011"
SECOND_OWNER_ID = "507f1f77bcf86cd799439012"


class AsyncCollection:
    def __init__(self, collection):
        self._collection = collection

    async def find_one(self, *args, **kwargs):
        return self._collection.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._collection.update_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._collection.delete_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return AsyncCursor(self._collection.find(*args, **kwargs))


class AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    async def to_list(self, length=None):
        rows = list(self._cursor)
        return rows if length is None else rows[:length]


class AsyncDatabase:
    def __init__(self, raw_database):
        self.raw = raw_database
        self._collections: dict[str, AsyncCollection] = {}

    def __getitem__(self, name: str) -> AsyncCollection:
        if name not in self._collections:
            self._collections[name] = AsyncCollection(self.raw[name])
        return self._collections[name]


class FakeMongo:
    def __init__(self):
        self.raw = mongomock.MongoClient()["storefront_media_test"]
        self.db = AsyncDatabase(self.raw)
        self.raw.storefront_assets.create_index(
            [("owner_id", 1), ("slot", 1)],
            unique=True,
            partialFilterExpression={"state": "reserved"},
        )


class FakeEntitlements:
    def __init__(self):
        self.enabled_by_owner = {OWNER_ID: True, SECOND_OWNER_ID: True}

    async def resolve_for_owner(self, user_data: dict) -> StorefrontEntitlements:
        owner_id = str(user_data.get("_id") or "")
        enabled = self.enabled_by_owner.get(owner_id, False)
        return StorefrontEntitlements(
            owner_id=owner_id,
            plan_id="plan_signature" if enabled else "plan_boutique",
            storefront_enabled=enabled,
            custom_domain_enabled=enabled,
        )


class FakeStorage:
    def __init__(self):
        self.presign_calls: list[dict] = []
        self.head_calls: list[dict] = []
        self.delete_calls: list[dict] = []
        self.copy_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self.upload_calls: list[dict] = []
        self.head_by_key: dict[str, dict] = {}
        self.bytes_by_key: dict[str, bytes] = {}
        self.presign_error: Exception | None = None
        self.head_error: Exception | None = None
        self.delete_error: Exception | None = None
        self.copy_error: Exception | None = None
        self.copy_writes_before_error = False
        self.upload_error: Exception | None = None
        self.upload_writes_before_error = False
        self.unavailable_targets: set[StorageTarget] = set()
        self.bucket_by_target = {
            StorageTarget.STOREFRONT_STAGING: "private-storefront-staging",
            StorageTarget.BLOG_ASSETS: "public-blog-assets",
        }
        self.privacy_error: Exception | None = None

    async def require_private_storefront_staging(self, *, force_refresh=False):
        if self.privacy_error:
            raise self.privacy_error

    def require_target(self, target):
        if target in self.unavailable_targets:
            raise RuntimeError(f"{target.value} unavailable")
        return SimpleNamespace(bucket_name=self.bucket_by_target[target])

    def generate_presigned_put_url(
        self,
        target,
        key: str,
        expires_in: int,
        content_type: str | None = None,
        content_length: int | None = None,
    ) -> str:
        self.presign_calls.append(
            {
                "target": target,
                "key": key,
                "expires_in": expires_in,
                "content_type": content_type,
                "content_length": content_length,
                "thread_id": threading.get_ident(),
            }
        )
        if self.presign_error:
            raise self.presign_error
        return f"https://uploads.example.test/{key}"

    def build_public_url(self, target, key: str) -> str:
        return f"https://cdn.example.test/{key}"

    def head_object(self, target, key: str) -> dict:
        self.head_calls.append(
            {"target": target, "key": key, "thread_id": threading.get_ident()}
        )
        if self.head_error:
            raise self.head_error
        return self.head_by_key[key]

    def delete_object(self, target, key: str) -> None:
        self.delete_calls.append(
            {"target": target, "key": key, "thread_id": threading.get_ident()}
        )
        if self.delete_error:
            raise self.delete_error
        self.head_by_key.pop(key, None)

    def copy_object(
        self,
        target,
        source_key: str,
        destination_key: str,
        source_target=None,
        *,
        source_etag: str | None = None,
    ) -> None:
        self.copy_calls.append(
            {
                "target": target,
                "source_key": source_key,
                "destination_key": destination_key,
                "source_target": source_target,
                "source_etag": source_etag,
                "thread_id": threading.get_ident(),
            }
        )
        source = dict(self.head_by_key[source_key])
        if source.get("ETag") != source_etag:
            raise RuntimeError("copy source precondition failed")
        if self.copy_writes_before_error:
            self.head_by_key[destination_key] = source
        if self.copy_error:
            raise self.copy_error
        self.head_by_key[destination_key] = source

    @staticmethod
    def _default_image_bytes(content_type: str, size_bytes: int) -> bytes:
        format_by_type = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
        }
        output = BytesIO()
        Image.new("RGB", (2, 2), (20, 40, 60)).save(
            output, format=format_by_type[content_type]
        )
        payload = output.getvalue()
        if len(payload) > size_bytes:
            raise AssertionError("test image does not fit declared upload size")
        return payload + (b"\0" * (size_bytes - len(payload)))

    def get_object_bytes(self, target, key: str, *, source_etag=None) -> bytes:
        self.get_calls.append(
            {
                "target": target,
                "key": key,
                "source_etag": source_etag,
                "thread_id": threading.get_ident(),
            }
        )
        head = self.head_by_key[key]
        if source_etag != head.get("ETag"):
            raise RuntimeError("staging GET precondition failed")
        if key in self.bytes_by_key:
            return self.bytes_by_key[key]
        return self._default_image_bytes(head["ContentType"], head["ContentLength"])

    def upload_fileobj(self, fileobj, target, key: str, extra_args=None) -> None:
        payload = fileobj.read()
        content_type = (extra_args or {}).get("ContentType")
        self.upload_calls.append(
            {
                "target": target,
                "key": key,
                "payload": payload,
                "extra_args": extra_args or {},
                "thread_id": threading.get_ident(),
            }
        )
        written_head = {
            "ContentLength": len(payload),
            "ContentType": content_type,
            "ETag": f'"server-{len(payload)}"',
        }
        if self.upload_writes_before_error:
            self.bytes_by_key[key] = payload
            self.head_by_key[key] = written_head
        if self.upload_error:
            raise self.upload_error
        self.bytes_by_key[key] = payload
        self.head_by_key[key] = written_head


@pytest.fixture
def setup_media():
    mongo = FakeMongo()
    storage = FakeStorage()
    entitlements = FakeEntitlements()
    service = StorefrontMediaService(
        mongo_client=mongo,
        storage=storage,
        entitlement_service=entitlements,
    )
    return service, mongo, storage, entitlements


def _owner(owner_id: str = OWNER_ID, role: str = "wedding_planner") -> dict:
    return {"_id": ObjectId(owner_id), "role": role}


async def _reserve(
    service: StorefrontMediaService,
    *,
    owner_id: str = OWNER_ID,
    slot: str = "hero",
    content_type: str = "image/webp",
    size_bytes: int = 1024,
) -> dict:
    return await service.reserve(
        _owner(owner_id),
        slot=slot,
        content_type=content_type,
        size_bytes=size_bytes,
    )


async def _finalize_ready_asset(
    service: StorefrontMediaService,
    storage: FakeStorage,
    *,
    slot: str,
) -> dict:
    reserved = await _reserve(service, slot=slot, size_bytes=1024)
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": 1024,
        "ContentType": "image/webp",
        "ETag": f'"{slot}-source"',
    }
    await service.finalize(_owner(), reserved["asset_id"])
    return reserved


def _pending_asset_group(claim: dict) -> dict:
    return {"pending_asset_group": claim["manifest"]}


@pytest.mark.asyncio
async def test_reserve_uses_server_generated_owner_slot_key_and_offloads_presign(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    event_loop_thread = threading.get_ident()

    response = await _reserve(service)

    assert set(response) == {
        "asset_id",
        "upload_url",
        "cdn_url",
        "key",
        "max_size_bytes",
    }
    assert response["key"].startswith(f"storefront/{OWNER_ID}/hero/")
    assert response["key"].endswith(".webp")
    assert response["max_size_bytes"] == 5 * 1024 * 1024
    assert storage.presign_calls[0]["thread_id"] != event_loop_thread
    assert storage.presign_calls[0]["target"] == StorageTarget.STOREFRONT_STAGING
    assert storage.presign_calls[0]["content_length"] == 1024

    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(response["asset_id"])}
    )
    assert stored is not None
    assert stored["owner_id"] == OWNER_ID
    assert stored["slot"] == "hero"
    assert stored["state"] == "reserved"
    assert stored["declared_content_type"] == "image/webp"
    assert stored["declared_size_bytes"] == 1024
    assert response["key"].startswith(stored["final_key_prefix"])
    assert "key" not in stored
    assert "cdn_url" not in stored


@pytest.mark.asyncio
async def test_reserve_rejects_duplicate_pending_slot_but_is_owner_scoped(setup_media):
    service, _, _, _ = setup_media
    await _reserve(service)

    with pytest.raises(HTTPException) as duplicate:
        await _reserve(service)
    assert duplicate.value.status_code == 409

    second_owner = await _reserve(service, owner_id=SECOND_OWNER_ID)
    assert second_owner["key"].startswith(f"storefront/{SECOND_OWNER_ID}/hero/")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("slot", "content_type", "size_bytes"),
    [
        ("logo", "image/webp", 100),
        ("hero", "image/gif", 100),
        ("about", "image/png", 0),
        ("about", "image/jpeg", -1),
        ("about", "image/jpeg", MAX_STOREFRONT_ASSET_SIZE_BYTES + 1),
        ("about", "image/jpeg", True),
    ],
)
async def test_reserve_rejects_unsupported_slot_type_and_declared_size(
    setup_media, slot, content_type, size_bytes
):
    service, _, storage, _ = setup_media

    with pytest.raises(HTTPException) as invalid:
        await _reserve(
            service,
            slot=slot,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    assert invalid.value.status_code == 422
    assert storage.presign_calls == []


@pytest.mark.asyncio
async def test_media_operations_require_planner_owner_and_current_entitlement(
    setup_media,
):
    service, _, storage, entitlements = setup_media

    with pytest.raises(HTTPException) as wrong_role:
        await service.reserve(
            _owner(role="team_member"),
            slot="hero",
            content_type="image/png",
            size_bytes=100,
        )
    assert wrong_role.value.status_code == 403

    entitlements.enabled_by_owner[OWNER_ID] = False
    with pytest.raises(HTTPException) as disabled:
        await _reserve(service)
    assert disabled.value.status_code == 403
    assert storage.presign_calls == []


@pytest.mark.asyncio
async def test_presign_failure_removes_unusable_reservation(setup_media):
    service, mongo, storage, _ = setup_media
    storage.presign_error = RuntimeError("R2 unavailable")

    with pytest.raises(HTTPException) as unavailable:
        await _reserve(service)

    assert unavailable.value.status_code == 503
    assert mongo.raw.storefront_assets.count_documents({}) == 0


@pytest.mark.asyncio
async def test_reserve_reconciles_insert_committed_before_ack_was_lost(setup_media):
    service, mongo, storage, _ = setup_media
    assets = mongo.db["storefront_assets"]
    original_insert = assets.insert_one
    raised = False

    async def commit_then_lose_ack(document, *args, **kwargs):
        nonlocal raised
        result = await original_insert(document, *args, **kwargs)
        if not raised:
            raised = True
            raise RuntimeError("Mongo insert acknowledgement lost")
        return result

    assets.insert_one = commit_then_lose_ack

    reserved = await _reserve(service)

    assert mongo.raw.storefront_assets.count_documents({}) == 1
    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    assert stored["owner_id"] == OWNER_ID
    assert stored["slot"] == "hero"
    assert storage.presign_calls


@pytest.mark.asyncio
async def test_expired_reservation_is_atomically_reaped_before_slot_reuse(setup_media):
    service, mongo, storage, _ = setup_media
    expired = await _reserve(service)
    expired_staging_key = storage.presign_calls[-1]["key"]
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(expired["asset_id"])},
        {
            "$set": {
                "reservation_expires_at": datetime.now(timezone.utc)
                - timedelta(seconds=1)
            }
        },
    )

    replacement = await _reserve(service)

    assert replacement["asset_id"] != expired["asset_id"]
    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(expired["asset_id"])})
        is None
    )
    assert any(
        call["target"] == StorageTarget.STOREFRONT_STAGING
        and call["key"] == expired_staging_key
        for call in storage.delete_calls
    )
    with pytest.raises(HTTPException) as late_finalize:
        await service.finalize(_owner(), expired["asset_id"])
    assert late_finalize.value.status_code == 404


@pytest.mark.asyncio
async def test_old_legacy_reservation_without_expiry_is_reaped_before_reuse(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    expired = await _reserve(service)
    expired_staging_key = storage.presign_calls[-1]["key"]
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(expired["asset_id"])},
        {
            "$unset": {"reservation_expires_at": ""},
            "$set": {
                "created_at": datetime.now(timezone.utc)
                - timedelta(seconds=STOREFRONT_RESERVATION_TTL_SECONDS + 1)
            },
        },
    )

    replacement = await _reserve(service)

    assert replacement["asset_id"] != expired["asset_id"]
    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(expired["asset_id"])})
        is None
    )
    assert any(call["key"] == expired_staging_key for call in storage.delete_calls)


@pytest.mark.asyncio
async def test_recent_legacy_reservation_without_expiry_is_backfilled_and_finalizable(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service, size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(reserved["asset_id"])},
        {"$unset": {"reservation_expires_at": ""}},
    )
    storage.head_by_key[staging_key] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"legacy-source"',
    }

    finalized = await service.finalize(_owner(), reserved["asset_id"])

    assert finalized["state"] == "ready"
    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    assert isinstance(stored["reservation_expires_at"], datetime)


@pytest.mark.asyncio
@pytest.mark.parametrize("busy_state", ["finalizing", "finalization_recovery"])
async def test_reserve_blocks_slot_while_finalization_is_in_flight(
    setup_media, busy_state
):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service)
    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    token = "fresh-finalization-token"
    candidate_key = service._finalization_candidate_key(stored, token)
    state_fields = {
        "state": busy_state,
        "updated_at": datetime.now(timezone.utc),
    }
    if busy_state == "finalizing":
        state_fields.update(
            {
                "finalization_token": token,
                "finalization_started_at": datetime.now(timezone.utc),
            }
        )
    else:
        state_fields.update(
            {
                "recovery_token": token,
                "cleanup_candidate_key": candidate_key,
            }
        )
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(reserved["asset_id"])}, {"$set": state_fields}
    )
    storage.head_by_key[candidate_key] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"candidate"',
    }

    with pytest.raises(HTTPException) as conflict:
        await _reserve(service)

    assert conflict.value.status_code == 409
    assert mongo.raw.storefront_assets.count_documents({}) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("busy_state", ["finalizing", "finalization_recovery"])
async def test_reserve_reclaims_stale_finalization_before_issuing_new_slot_receipt(
    setup_media, busy_state
):
    service, mongo, storage, _ = setup_media
    abandoned = await _reserve(service)
    abandoned_row = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(abandoned["asset_id"])}
    )
    staging_key = abandoned_row["staging_key"]
    token = "abandoned-finalization-token"
    candidate_key = service._finalization_candidate_key(abandoned_row, token)
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    state_fields = {"state": busy_state, "updated_at": stale_at}
    if busy_state == "finalizing":
        state_fields.update(
            {
                "finalization_token": token,
                "finalization_started_at": stale_at,
            }
        )
    else:
        state_fields.update(
            {
                "recovery_token": token,
                "cleanup_candidate_key": candidate_key,
            }
        )
    mongo.raw.storefront_assets.update_one(
        {"_id": abandoned_row["_id"]}, {"$set": state_fields}
    )
    storage.head_by_key[staging_key] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"staging"',
    }
    storage.head_by_key[candidate_key] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"candidate"',
    }

    replacement = await _reserve(service)

    assert replacement["asset_id"] != abandoned["asset_id"]
    assert mongo.raw.storefront_assets.find_one({"_id": abandoned_row["_id"]}) is None
    deleted = {(call["target"], call["key"]) for call in storage.delete_calls}
    assert (StorageTarget.STOREFRONT_STAGING, staging_key) in deleted
    assert (StorageTarget.BLOG_ASSETS, candidate_key) in deleted


@pytest.mark.asyncio
async def test_reserve_retries_failed_stale_finalization_cleanup_before_slot_reuse(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    abandoned = await _reserve(service)
    row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(abandoned["asset_id"])})
    token = "abandoned-finalization-token"
    candidate_key = service._finalization_candidate_key(row, token)
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "state": "finalizing",
                "finalization_token": token,
                "finalization_started_at": stale_at,
                "updated_at": stale_at,
            }
        },
    )
    storage.delete_error = RuntimeError("temporary delete failure")

    with pytest.raises(HTTPException) as unavailable:
        await _reserve(service)
    assert unavailable.value.status_code == 503
    stranded = mongo.raw.storefront_assets.find_one({"_id": row["_id"]})
    assert stranded["state"] == "cleanup_retry"
    assert stranded["cleanup_reason"] == "stale_finalization"

    storage.delete_error = None
    replacement = await _reserve(service)

    assert replacement["asset_id"] != abandoned["asset_id"]
    assert mongo.raw.storefront_assets.find_one({"_id": row["_id"]}) is None
    assert any(call["key"] == candidate_key for call in storage.delete_calls)


@pytest.mark.asyncio
async def test_reserve_resumes_token_fenced_reaping_after_worker_crash(
    setup_media, monkeypatch
):
    service, mongo, storage, _ = setup_media
    abandoned = await _reserve(service)
    row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(abandoned["asset_id"])})
    token = "crashed-finalizer-token"
    candidate_key = service._finalization_candidate_key(row, token)
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "state": "finalizing",
                "finalization_token": token,
                "finalization_started_at": stale_at,
                "updated_at": stale_at,
            }
        },
    )
    storage.head_by_key[row["staging_key"]] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"staging"',
    }
    storage.head_by_key[candidate_key] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"candidate"',
    }

    original_delete = service._delete_asset_objects

    async def crash_after_reap_claim(_asset):
        raise asyncio.CancelledError

    monkeypatch.setattr(service, "_delete_asset_objects", crash_after_reap_claim)
    with pytest.raises(asyncio.CancelledError):
        await _reserve(service)

    stranded = mongo.raw.storefront_assets.find_one({"_id": row["_id"]})
    assert stranded["state"] == "reaping"
    assert isinstance(stranded["reap_token"], str)
    assert isinstance(stranded["reaping_started_at"], datetime)
    first_reap_token = stranded["reap_token"]

    mongo.raw.storefront_assets.update_one(
        {"_id": row["_id"], "reap_token": first_reap_token},
        {
            "$set": {
                "reaping_started_at": datetime.now(timezone.utc)
                - timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1)
            }
        },
    )
    monkeypatch.setattr(service, "_delete_asset_objects", original_delete)

    replacement = await _reserve(service)

    assert replacement["asset_id"] != abandoned["asset_id"]
    assert mongo.raw.storefront_assets.find_one({"_id": row["_id"]}) is None
    deleted = {(call["target"], call["key"]) for call in storage.delete_calls}
    assert (StorageTarget.STOREFRONT_STAGING, row["staging_key"]) in deleted
    assert (StorageTarget.BLOG_ASSETS, candidate_key) in deleted


@pytest.mark.asyncio
async def test_reserve_retries_finalization_recovery_cleanup_reason(setup_media):
    service, mongo, storage, _ = setup_media
    abandoned = await _reserve(service)
    row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(abandoned["asset_id"])})
    candidate_key = f"{row['final_key_prefix']}-recovery.webp"
    now = datetime.now(timezone.utc)
    mongo.raw.storefront_assets.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "state": "cleanup_retry",
                "cleanup_reason": "stale_finalization_recovery",
                "cleanup_candidate_key": candidate_key,
                "cleanup_due_at": now - timedelta(seconds=1),
                "updated_at": now,
            }
        },
    )
    storage.head_by_key[row["staging_key"]] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"staging"',
    }
    storage.head_by_key[candidate_key] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"candidate"',
    }

    replacement = await _reserve(service)

    assert replacement["asset_id"] != abandoned["asset_id"]
    assert mongo.raw.storefront_assets.find_one({"_id": row["_id"]}) is None
    assert any(call["key"] == candidate_key for call in storage.delete_calls)


@pytest.mark.asyncio
async def test_presign_failure_receipt_remains_reapable_when_db_cleanup_fails(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    assets = mongo.db["storefront_assets"]
    original_delete = assets.delete_one
    storage.presign_error = RuntimeError("R2 unavailable")

    async def delete_ack_failed(*_args, **_kwargs):
        raise RuntimeError("Mongo delete unavailable")

    assets.delete_one = delete_ack_failed
    with pytest.raises(HTTPException) as unavailable:
        await _reserve(service)
    assert unavailable.value.status_code == 503
    stranded = mongo.raw.storefront_assets.find_one({})
    assert stranded["state"] == "reserved"
    assert stranded["reservation_expires_at"] > stranded["created_at"]

    mongo.raw.storefront_assets.update_one(
        {"_id": stranded["_id"]},
        {
            "$set": {
                "reservation_expires_at": datetime.now(timezone.utc)
                - timedelta(seconds=1)
            }
        },
    )
    assets.delete_one = original_delete
    storage.presign_error = None

    replacement = await _reserve(service)
    assert replacement["asset_id"] != str(stranded["_id"])


@pytest.mark.asyncio
async def test_finalize_heads_exact_object_contract_and_marks_ready(setup_media):
    service, mongo, storage, _ = setup_media
    event_loop_thread = threading.get_ident()
    reserved = await _reserve(
        service, slot="about", content_type="image/png", size_bytes=2048
    )
    storage.head_by_key[storage.presign_calls[-1]["key"]] = {
        "ContentLength": 2048,
        "ContentType": "image/png",
        "ETag": '"upload-etag"',
    }

    finalized = await service.finalize(_owner(), reserved["asset_id"])

    assert finalized["asset_id"] == reserved["asset_id"]
    assert finalized["slot"] == "about"
    assert finalized["state"] == "ready"
    assert finalized["cdn_url"].endswith(finalized["key"])
    assert finalized["cdn_url"] != reserved["cdn_url"]
    assert storage.head_calls[0]["thread_id"] != event_loop_thread
    assert storage.get_calls[0]["source_etag"] == '"upload-etag"'
    assert storage.get_calls[0]["thread_id"] != event_loop_thread
    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    assert stored["state"] == "ready"
    assert stored["actual_size_bytes"] == len(storage.upload_calls[0]["payload"])
    assert stored["actual_content_type"] == "image/png"
    assert stored["etag"] == f'"server-{stored["actual_size_bytes"]}"'
    assert stored["source_etag"] == '"upload-etag"'


@pytest.mark.asyncio
@pytest.mark.parametrize("payload_kind", ["arbitrary", "format_mismatch", "truncated"])
async def test_finalize_rejects_non_image_or_malformed_bytes_despite_signed_metadata(
    setup_media, payload_kind
):
    service, mongo, storage, _ = setup_media
    if payload_kind == "arbitrary":
        payload = b"not-an-image" * 10
    elif payload_kind == "format_mismatch":
        payload = FakeStorage._default_image_bytes("image/png", 200)
    else:
        valid = FakeStorage._default_image_bytes("image/webp", 100)
        payload = valid[:35]
    reserved = await _reserve(service, size_bytes=len(payload))
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": len(payload),
        "ContentType": "image/webp",
        "ETag": '"signed-metadata"',
    }
    storage.bytes_by_key[staging_key] = payload

    with pytest.raises(HTTPException) as invalid:
        await service.finalize(_owner(), reserved["asset_id"])

    assert invalid.value.status_code == 422
    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(reserved["asset_id"])})
        is None
    )
    assert storage.upload_calls == []


@pytest.mark.asyncio
async def test_finalize_reencodes_image_and_strips_trailing_payload(setup_media):
    service, _, storage, _ = setup_media
    clean = FakeStorage._default_image_bytes("image/webp", 100)
    marker = b"<script>polyglot()</script>"
    uploaded = clean + marker
    reserved = await _reserve(service, size_bytes=len(uploaded))
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": len(uploaded),
        "ContentType": "image/webp",
        "ETag": '"polyglot-source"',
    }
    storage.bytes_by_key[staging_key] = uploaded

    finalized = await service.finalize(_owner(), reserved["asset_id"])

    assert storage.get_calls[0]["target"] == StorageTarget.STOREFRONT_STAGING
    assert storage.upload_calls[0]["target"] == StorageTarget.BLOG_ASSETS
    assert storage.upload_calls[0]["thread_id"] != threading.get_ident()
    sanitized = storage.upload_calls[0]["payload"]
    assert marker not in sanitized
    with Image.open(BytesIO(sanitized)) as decoded:
        decoded.load()
        assert decoded.format == "WEBP"
    assert finalized["key"] == storage.upload_calls[0]["key"]


@pytest.mark.asyncio
async def test_finalize_fails_closed_on_decompression_bomb_dimensions(
    setup_media, monkeypatch
):
    service, _, storage, _ = setup_media
    output = BytesIO()
    Image.new("RGB", (20, 20), (1, 2, 3)).save(output, format="PNG")
    payload = output.getvalue()
    reserved = await _reserve(
        service,
        content_type="image/png",
        size_bytes=len(payload),
    )
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": len(payload),
        "ContentType": "image/png",
        "ETag": '"large-pixels"',
    }
    storage.bytes_by_key[staging_key] = payload
    monkeypatch.setattr(storefront_media_module, "MAX_STOREFRONT_IMAGE_PIXELS", 100)

    with pytest.raises(HTTPException) as invalid:
        await service.finalize(_owner(), reserved["asset_id"])

    assert invalid.value.status_code == 422
    assert storage.upload_calls == []


@pytest.mark.asyncio
async def test_finalize_rejects_compressed_oversized_dimensions_before_pixel_load(
    setup_media, monkeypatch
):
    service, _, storage, _ = setup_media
    output = BytesIO()
    Image.new("1", (MAX_STOREFRONT_IMAGE_DIMENSION + 1, 1)).save(output, format="PNG")
    payload = output.getvalue()
    reserved = await _reserve(
        service, content_type="image/png", size_bytes=len(payload)
    )
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": len(payload),
        "ContentType": "image/png",
        "ETag": '"compressed-wide"',
    }
    storage.bytes_by_key[staging_key] = payload

    original_load = Image.Image.load
    load_called = False

    def tracked_load(image, *args, **kwargs):
        nonlocal load_called
        load_called = True
        return original_load(image, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "load", tracked_load)

    with pytest.raises(HTTPException) as invalid:
        await service.finalize(_owner(), reserved["asset_id"])

    assert invalid.value.status_code == 422
    assert load_called is False
    assert MAX_STOREFRONT_IMAGE_DIMENSION == 4096
    assert MAX_STOREFRONT_IMAGE_PIXELS == 12_000_000


@pytest.mark.asyncio
async def test_image_decode_is_serialized_across_concurrent_finalizations(
    setup_media, monkeypatch
):
    service, _, storage, _ = setup_media
    hero = await _reserve(service, slot="hero", size_bytes=100)
    about = await _reserve(service, slot="about", size_bytes=100)
    for call in storage.presign_calls:
        storage.head_by_key[call["key"]] = {
            "ContentLength": 100,
            "ContentType": "image/webp",
            "ETag": f'"{call["key"]}"',
        }

    original = service._read_and_sanitize_staging_image
    first_entered = threading.Event()
    release_first = threading.Event()
    active = 0
    max_active = 0
    lock = threading.Lock()

    def blocking_sanitize(asset, head):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        try:
            if not first_entered.is_set():
                first_entered.set()
                assert release_first.wait(timeout=2)
            return original(asset, head)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(service, "_read_and_sanitize_staging_image", blocking_sanitize)
    first = asyncio.create_task(service.finalize(_owner(), hero["asset_id"]))
    assert await asyncio.to_thread(first_entered.wait, 2)
    second = asyncio.create_task(service.finalize(_owner(), about["asset_id"]))
    await asyncio.sleep(0.05)
    assert max_active == 1
    release_first.set()
    await asyncio.gather(first, second)
    assert max_active == 1


@pytest.mark.asyncio
async def test_reservation_presigns_staging_not_the_final_public_key(setup_media):
    service, mongo, storage, _ = setup_media

    reserved = await _reserve(service)
    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )

    assert storage.presign_calls[0]["key"] == stored["staging_key"]
    assert storage.presign_calls[0]["key"] != reserved["key"]
    assert reserved["key"].startswith(stored["final_key_prefix"])
    assert "key" not in stored
    assert reserved["cdn_url"].endswith(reserved["key"])


@pytest.mark.asyncio
async def test_finalize_sanitizes_then_staging_put_cannot_mutate_final(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    event_loop_thread = threading.get_ident()
    reserved = await _reserve(service, size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    original = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"validated-source"',
    }
    storage.head_by_key[staging_key] = dict(original)

    finalized = await service.finalize(_owner(), reserved["asset_id"])

    assert finalized["state"] == "ready"
    assert finalized["key"] == storage.upload_calls[0]["key"]
    assert storage.upload_calls[0]["target"] == StorageTarget.BLOG_ASSETS
    assert storage.upload_calls[0]["extra_args"] == {"ContentType": "image/webp"}
    assert storage.upload_calls[0]["thread_id"] != event_loop_thread
    assert storage.head_calls[0]["target"] == StorageTarget.STOREFRONT_STAGING
    assert storage.head_calls[1]["target"] == StorageTarget.BLOG_ASSETS
    assert staging_key not in storage.head_by_key
    public_head = dict(storage.head_by_key[finalized["key"]])
    assert public_head["ContentType"] == "image/webp"
    assert public_head["ContentLength"] == len(storage.upload_calls[0]["payload"])

    # The browser's original PUT remains cryptographically valid until expiry.
    # Reusing it can only recreate staging; the validated public object is fixed.
    storage.head_by_key[staging_key] = {
        "ContentLength": MAX_STOREFRONT_ASSET_SIZE_BYTES + 1,
        "ContentType": "image/gif",
        "ETag": '"late-overwrite"',
    }
    assert storage.head_by_key[finalized["key"]] == public_head
    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    assert stored["key"] == finalized["key"]

    deleted = await service.cleanup(_owner(), reserved["asset_id"])
    assert deleted == {"status": "deleted", "asset_id": reserved["asset_id"]}
    assert staging_key not in storage.head_by_key
    assert finalized["key"] not in storage.head_by_key
    assert [call["key"] for call in storage.delete_calls[-2:]] == [
        staging_key,
        finalized["key"],
    ]
    assert [call["target"] for call in storage.delete_calls[-2:]] == [
        StorageTarget.STOREFRONT_STAGING,
        StorageTarget.BLOG_ASSETS,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unavailable_target",
    [StorageTarget.STOREFRONT_STAGING, StorageTarget.BLOG_ASSETS],
)
async def test_reserve_fails_closed_unless_private_and_public_targets_are_ready(
    setup_media, unavailable_target
):
    service, mongo, storage, _ = setup_media
    storage.unavailable_targets.add(unavailable_target)

    with pytest.raises(HTTPException) as unavailable:
        await _reserve(service)

    assert unavailable.value.status_code == 503
    assert mongo.raw.storefront_assets.count_documents({}) == 0
    assert storage.presign_calls == []


@pytest.mark.asyncio
async def test_reserve_rejects_reusing_the_public_bucket_for_private_staging(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    storage.bucket_by_target[StorageTarget.STOREFRONT_STAGING] = (
        storage.bucket_by_target[StorageTarget.BLOG_ASSETS]
    )

    with pytest.raises(HTTPException) as unavailable:
        await _reserve(service)

    assert unavailable.value.status_code == 503
    assert mongo.raw.storefront_assets.count_documents({}) == 0
    assert storage.presign_calls == []


@pytest.mark.asyncio
async def test_reserve_fails_closed_when_staging_privacy_cannot_be_verified(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    storage.privacy_error = RuntimeError("managed-domain status unreadable")

    with pytest.raises(HTTPException) as unavailable:
        await _reserve(service)

    assert unavailable.value.status_code == 503
    assert mongo.raw.storefront_assets.count_documents({}) == 0


@pytest.mark.asyncio
async def test_sanitized_upload_failure_removes_candidate_and_can_retry(setup_media):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service, size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    upload = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"source-v1"',
    }
    storage.head_by_key[staging_key] = dict(upload)
    storage.upload_writes_before_error = True
    storage.upload_error = RuntimeError("sanitized upload timed out")

    with pytest.raises(HTTPException) as unavailable:
        await service.finalize(_owner(), reserved["asset_id"])

    assert unavailable.value.status_code == 503
    assert reserved["key"] not in storage.head_by_key
    assert storage.head_by_key[staging_key] == upload
    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(reserved["asset_id"])})[
            "state"
        ]
        == "reserved"
    )

    storage.upload_error = None
    storage.upload_writes_before_error = False
    finalized = await service.finalize(_owner(), reserved["asset_id"])
    assert finalized["state"] == "ready"
    assert staging_key not in storage.head_by_key
    assert storage.head_by_key[finalized["key"]]["ContentType"] == "image/webp"


@pytest.mark.asyncio
async def test_ambiguous_finalization_commit_preserves_the_canonical_winner(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service, size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"source-v1"',
    }
    assets = mongo.db["storefront_assets"]
    original_update = assets.update_one
    raised = False

    async def commit_then_lose_response(query, update, *args, **kwargs):
        nonlocal raised
        result = await original_update(query, update, *args, **kwargs)
        if not raised and update.get("$set", {}).get("state") == "ready":
            raised = True
            raise RuntimeError("Mongo response lost after commit")
        return result

    assets.update_one = commit_then_lose_response

    finalized = await service.finalize(_owner(), reserved["asset_id"])

    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    assert finalized["key"] == stored["key"]
    assert stored["state"] == "ready"
    assert stored["key"] in storage.head_by_key
    assert staging_key not in storage.head_by_key


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "head",
    [
        {"ContentLength": 1023, "ContentType": "image/webp"},
        {"ContentLength": 1024, "ContentType": "image/jpeg"},
        {
            "ContentLength": MAX_STOREFRONT_ASSET_SIZE_BYTES + 1,
            "ContentType": "image/webp",
        },
        {"ContentLength": True, "ContentType": "image/webp"},
        {"ContentLength": 1024, "ContentType": "image/webp"},
    ],
)
async def test_invalid_finalize_deletes_object_and_reservation(setup_media, head):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service, size_bytes=1024)
    storage.head_by_key[storage.presign_calls[-1]["key"]] = head

    with pytest.raises(HTTPException) as invalid:
        await service.finalize(_owner(), reserved["asset_id"])

    assert invalid.value.status_code == 422
    deleted_keys = [call["key"] for call in storage.delete_calls]
    assert deleted_keys[0] == storage.presign_calls[-1]["key"]
    assert deleted_keys[1] != reserved["key"]
    assert deleted_keys[1].startswith(
        f"storefront/{OWNER_ID}/hero/{reserved['asset_id']}-"
    )
    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(reserved["asset_id"])})
        is None
    )


@pytest.mark.asyncio
async def test_invalid_finalize_records_cleanup_retry_when_provider_delete_fails(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service, content_type="image/jpeg", size_bytes=100)
    storage.head_by_key[storage.presign_calls[-1]["key"]] = {
        "ContentLength": 99,
        "ContentType": "image/jpeg",
    }
    storage.delete_error = RuntimeError("provider timeout")

    with pytest.raises(HTTPException) as invalid:
        await service.finalize(_owner(), reserved["asset_id"])

    assert invalid.value.status_code == 422
    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    assert stored["state"] == "cleanup_retry"
    assert stored["cleanup_reason"] == "invalid_upload"
    assert stored["cleanup_attempts"] == 1
    assert "provider timeout" not in str(invalid.value.detail)


@pytest.mark.asyncio
async def test_finalize_is_owner_scoped_and_rejects_wrong_state(setup_media):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service)

    with pytest.raises(HTTPException) as foreign:
        await service.finalize(_owner(SECOND_OWNER_ID), reserved["asset_id"])
    assert foreign.value.status_code == 404
    assert storage.head_calls == []

    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(reserved["asset_id"])}, {"$set": {"state": "deleting"}}
    )
    with pytest.raises(HTTPException) as wrong_state:
        await service.finalize(_owner(), reserved["asset_id"])
    assert wrong_state.value.status_code == 409
    assert storage.head_calls == []


@pytest.mark.asyncio
async def test_cleanup_rejects_foreign_attached_and_currently_referenced_assets(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service)
    asset_id = reserved["asset_id"]

    with pytest.raises(HTTPException) as foreign:
        await service.cleanup(_owner(SECOND_OWNER_ID), asset_id)
    assert foreign.value.status_code == 404

    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(asset_id)}, {"$set": {"state": "attached"}}
    )
    with pytest.raises(HTTPException) as attached:
        await service.cleanup(_owner(), asset_id)
    assert attached.value.status_code == 409

    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(asset_id)}, {"$set": {"state": "ready"}}
    )
    mongo.raw.storefront_settings.insert_one(
        {"planner_id": OWNER_ID, "hero_asset_id": asset_id}
    )
    with pytest.raises(HTTPException) as referenced:
        await service.cleanup(_owner(), asset_id)
    assert referenced.value.status_code == 409
    assert storage.delete_calls == []


@pytest.mark.asyncio
async def test_cleanup_failure_preserves_retry_state_then_success_removes_row(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    event_loop_thread = threading.get_ident()
    reserved = await _reserve(service, slot="about")
    asset_id = reserved["asset_id"]
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(asset_id)}, {"$set": {"state": "ready"}}
    )
    storage.delete_error = RuntimeError("provider timeout")

    with pytest.raises(HTTPException) as unavailable:
        await service.cleanup(_owner(), asset_id)

    assert unavailable.value.status_code == 503
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(asset_id)})
    assert stored["state"] == "cleanup_retry"
    assert stored["cleanup_attempts"] == 1
    assert storage.delete_calls[0]["thread_id"] != event_loop_thread

    storage.delete_error = None
    result = await service.cleanup(_owner(), asset_id)
    assert result == {"status": "deleted", "asset_id": asset_id}
    assert mongo.raw.storefront_assets.find_one({"_id": ObjectId(asset_id)}) is None


@pytest.mark.asyncio
async def test_settings_claim_blocks_cleanup_until_durable_attachment(setup_media):
    service, mongo, storage, _ = setup_media
    hero = await _reserve(service, slot="hero", size_bytes=100)
    upload_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[upload_key] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"hero-source"',
    }
    await service.finalize(_owner(), hero["asset_id"])

    claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["state"] == "attaching"

    # Exact hostile interleaving: validation/claim completes, cleanup tries to
    # claim deletion, and only then does the settings write become durable.
    with pytest.raises(HTTPException) as cleanup_lost:
        await service.cleanup(_owner(), hero["asset_id"])
    assert cleanup_lost.value.status_code == 409
    assert (
        storage.delete_calls[-1]["key"] == upload_key
    )  # finalize staging cleanup only

    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 1,
            "hero_asset_id": None,
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": claim["claim_id"],
            **_pending_asset_group(claim),
        }
    )
    await service.attach_settings_asset_claims(_owner(), claim)
    await service.promote_settings_asset_claims(_owner(), claim)
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["state"] == "attached"


@pytest.mark.asyncio
async def test_failed_settings_cas_releases_claim_for_retry_or_cleanup(setup_media):
    service, mongo, storage, _ = setup_media
    about = await _reserve(service, slot="about", size_bytes=100)
    upload_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[upload_key] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"about-source"',
    }
    await service.finalize(_owner(), about["asset_id"])

    claim = await service.claim_settings_assets(
        _owner(), about_asset_id=about["asset_id"]
    )
    await service.release_settings_asset_claims(_owner(), claim)

    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(about["asset_id"])})
    assert stored["state"] == "ready"
    deleted = await service.cleanup(_owner(), about["asset_id"])
    assert deleted["status"] == "deleted"


@pytest.mark.asyncio
async def test_pending_reference_alone_protects_ready_asset_from_cleanup(setup_media):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": "claim-after-crash",
        }
    )

    with pytest.raises(HTTPException) as protected:
        await service.cleanup(_owner(), hero["asset_id"])

    assert protected.value.status_code == 409
    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
        is not None
    )


@pytest.mark.asyncio
async def test_expired_ready_asset_cleanup_failure_keeps_durable_retry_receipt(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["cleanup_due_at"] > stored["finalized_at"]
    assert (
        stored["cleanup_due_at"] - stored["finalized_at"]
    ).total_seconds() == STOREFRONT_READY_ASSET_CLEANUP_SECONDS
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(hero["asset_id"])},
        {"$set": {"cleanup_due_at": datetime.now(timezone.utc) - timedelta(seconds=1)}},
    )
    storage.delete_error = RuntimeError("storage unavailable")

    await service.recover_pending_settings_assets(_owner())

    retry = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert retry["state"] == "cleanup_retry"
    assert retry["cleanup_reason"] == "abandoned_ready_asset"
    assert retry["cleanup_due_at"] > retry["last_cleanup_attempt_at"]
    assert (
        retry["cleanup_due_at"] - retry["last_cleanup_attempt_at"]
    ).total_seconds() == STOREFRONT_CLEANUP_RETRY_SECONDS

    storage.delete_error = None
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(hero["asset_id"])},
        {"$set": {"cleanup_due_at": datetime.now(timezone.utc) - timedelta(seconds=1)}},
    )
    await service.recover_pending_settings_assets(_owner())
    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
        is None
    )


@pytest.mark.asyncio
async def test_recovery_reclaims_due_generic_cleanup_retry_receipt(setup_media):
    service, mongo, storage, _ = setup_media
    asset = await _finalize_ready_asset(service, storage, slot="about")
    row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(asset["asset_id"])})
    mongo.raw.storefront_assets.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "state": "cleanup_retry",
                "cleanup_reason": "finalization_verification_failed",
                "cleanup_due_at": datetime.now(timezone.utc) - timedelta(seconds=1),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    await service.recover_pending_settings_assets(_owner())

    assert mongo.raw.storefront_assets.find_one({"_id": row["_id"]}) is None
    assert any(call["key"] == row["key"] for call in storage.delete_calls)


@pytest.mark.asyncio
async def test_recovery_never_deletes_due_ready_asset_with_exact_owner_reference(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    mongo.raw.storefront_assets.update_one(
        {"_id": row["_id"]},
        {"$set": {"cleanup_due_at": datetime.now(timezone.utc) - timedelta(seconds=1)}},
    )
    mongo.raw.storefront_settings.insert_one(
        {"planner_id": OWNER_ID, "hero_asset_id": hero["asset_id"]}
    )
    delete_count = len(storage.delete_calls)

    await service.recover_pending_settings_assets(_owner())

    retained = mongo.raw.storefront_assets.find_one({"_id": row["_id"]})
    assert retained is not None
    assert retained["state"] == "ready"
    retained_due_at = retained["cleanup_due_at"]
    if retained_due_at.tzinfo is None:
        retained_due_at = retained_due_at.replace(tzinfo=timezone.utc)
    assert retained_due_at > datetime.now(timezone.utc)
    assert len(storage.delete_calls) == delete_count


@pytest.mark.asyncio
async def test_global_sweep_is_bounded_and_reclaims_owners_that_never_return(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    about = await _finalize_ready_asset(service, storage, slot="about")
    due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    mongo.raw.storefront_assets.update_many(
        {"_id": {"$in": [ObjectId(hero["asset_id"]), ObjectId(about["asset_id"])]}},
        {"$set": {"cleanup_due_at": due_at}},
    )

    first_tick = await service.sweep_abandoned_assets(limit=1)

    assert first_tick == 1
    assert mongo.raw.storefront_assets.count_documents({}) == 1

    second_tick = await service.sweep_abandoned_assets(limit=1)

    assert second_tick == 1
    assert mongo.raw.storefront_assets.count_documents({}) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("stale_state", ["finalizing", "finalization_recovery"])
async def test_global_sweep_reclaims_crashed_finalization_receipts(
    setup_media, stale_state
):
    service, mongo, storage, _ = setup_media
    abandoned = await _reserve(service, slot="hero")
    row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(abandoned["asset_id"])})
    token = f"crashed-{stale_state}"
    candidate_key = service._finalization_candidate_key(row, token)
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    state_fields = {
        "state": stale_state,
        "updated_at": stale_at,
    }
    if stale_state == "finalizing":
        state_fields.update(
            {
                "finalization_token": token,
                "finalization_started_at": stale_at,
            }
        )
    else:
        state_fields.update(
            {
                "recovery_token": token,
                "cleanup_candidate_key": candidate_key,
            }
        )
    mongo.raw.storefront_assets.update_one({"_id": row["_id"]}, {"$set": state_fields})
    storage.head_by_key[row["staging_key"]] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"staging"',
    }
    storage.head_by_key[candidate_key] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"candidate"',
    }

    assert await service.sweep_abandoned_assets(limit=1) == 1

    assert mongo.raw.storefront_assets.find_one({"_id": row["_id"]}) is None
    assert row["staging_key"] not in storage.head_by_key
    assert candidate_key not in storage.head_by_key


@pytest.mark.asyncio
async def test_global_sweep_reclaims_crashed_deleting_receipt(setup_media):
    service, mongo, storage, _ = setup_media
    abandoned = await _finalize_ready_asset(service, storage, slot="about")
    row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(abandoned["asset_id"])})
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "state": "deleting",
                "cleanup_token": "crashed-delete",
                "cleanup_source_state": "ready",
                "deleting_started_at": stale_at,
                "updated_at": stale_at,
            }
        },
    )

    assert await service.sweep_abandoned_assets(limit=1) == 1

    assert mongo.raw.storefront_assets.find_one({"_id": row["_id"]}) is None
    assert row["key"] not in storage.head_by_key


@pytest.mark.asyncio
async def test_lost_inflight_finalizer_persists_detached_candidate_cleanup_receipt(
    setup_media, monkeypatch
):
    service, mongo, storage, _ = setup_media
    abandoned = await _reserve(service, slot="hero", size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"source"',
    }
    upload_entered = threading.Event()
    release_upload = threading.Event()
    original_upload = storage.upload_fileobj

    def paused_upload(*args, **kwargs):
        upload_entered.set()
        assert release_upload.wait(timeout=2)
        return original_upload(*args, **kwargs)

    monkeypatch.setattr(storage, "upload_fileobj", paused_upload)
    stale_finalizer = asyncio.create_task(
        service.finalize(_owner(), abandoned["asset_id"]),
        name="detached-candidate-finalizer",
    )
    assert await asyncio.to_thread(upload_entered.wait, 2)
    active = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(abandoned["asset_id"])}
    )
    candidate_key = service._finalization_candidate_key(
        active, active["finalization_token"]
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": active["_id"]},
        {
            "$set": {
                "finalization_started_at": datetime.now(timezone.utc)
                - timedelta(seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1)
            }
        },
    )

    replacement = await _reserve(service, slot="hero")
    assert replacement["asset_id"] != abandoned["asset_id"]
    original_delete = storage.delete_object

    def fail_only_late_candidate_delete(target, key):
        if key == candidate_key and key in storage.head_by_key:
            raise RuntimeError("candidate delete transport failure")
        return original_delete(target, key)

    monkeypatch.setattr(storage, "delete_object", fail_only_late_candidate_delete)
    release_upload.set()
    with pytest.raises(HTTPException) as lost:
        await stale_finalizer
    assert lost.value.status_code == 409
    assert candidate_key in storage.head_by_key
    receipt = mongo.raw.storefront_asset_cleanup_receipts.find_one(
        {"candidate_key": candidate_key, "owner_id": OWNER_ID}
    )
    assert receipt is not None
    assert receipt["state"] == "cleanup_retry"

    monkeypatch.setattr(storage, "delete_object", original_delete)
    mongo.raw.storefront_asset_cleanup_receipts.update_one(
        {"_id": receipt["_id"]},
        {"$set": {"cleanup_due_at": datetime.now(timezone.utc) - timedelta(seconds=1)}},
    )
    assert await service.sweep_abandoned_assets(limit=1) == 1
    assert candidate_key not in storage.head_by_key
    assert (
        mongo.raw.storefront_asset_cleanup_receipts.find_one({"_id": receipt["_id"]})
        is None
    )


@pytest.mark.asyncio
async def test_failed_candidate_discard_persists_detached_receipt_after_token_loss(
    setup_media, monkeypatch
):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service, slot="hero", size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"source"',
    }
    original_upload = storage.upload_fileobj

    def upload_then_lose_token(*args, **kwargs):
        original_upload(*args, **kwargs)
        mongo.raw.storefront_assets.update_one(
            {"_id": ObjectId(reserved["asset_id"])},
            {
                "$set": {"state": "reserved"},
                "$unset": {
                    "finalization_token": "",
                    "finalization_started_at": "",
                },
            },
        )
        raise RuntimeError("upload acknowledgement lost after token takeover")

    monkeypatch.setattr(storage, "upload_fileobj", upload_then_lose_token)
    storage.delete_error = RuntimeError("candidate delete unavailable")

    with pytest.raises(HTTPException) as unavailable:
        await service.finalize(_owner(), reserved["asset_id"])

    assert unavailable.value.status_code == 503
    candidate_key = storage.upload_calls[-1]["key"]
    receipt = mongo.raw.storefront_asset_cleanup_receipts.find_one(
        {"owner_id": OWNER_ID, "candidate_key": candidate_key}
    )
    assert receipt is not None
    assert receipt["slot"] == "hero"
    assert receipt["state"] == "cleanup_retry"
    assert receipt["cleanup_reason"] == "finalization_upload_failed"


@pytest.mark.asyncio
async def test_failed_detached_cleanup_still_honors_global_sweep_limit(setup_media):
    service, mongo, storage, _ = setup_media
    ready = await _finalize_ready_asset(service, storage, slot="about")
    ready_row = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(ready["asset_id"])}
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": ready_row["_id"]},
        {"$set": {"cleanup_due_at": datetime.now(timezone.utc) - timedelta(seconds=1)}},
    )
    candidate_key = f"storefront/{OWNER_ID}/hero/detached-candidate.webp"
    now = datetime.now(timezone.utc)
    mongo.raw.storefront_asset_cleanup_receipts.insert_one(
        {
            "_id": ObjectId(),
            "owner_id": OWNER_ID,
            "slot": "hero",
            "candidate_key": candidate_key,
            "state": "cleanup_retry",
            "cleanup_due_at": now - timedelta(seconds=1),
            "updated_at": now,
        }
    )
    storage.head_by_key[candidate_key] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"detached"',
    }
    storage.delete_error = RuntimeError("storage unavailable")
    delete_count = len(storage.delete_calls)

    assert await service.sweep_abandoned_assets(limit=1) == 0

    assert len(storage.delete_calls) == delete_count + 1
    assert mongo.raw.storefront_assets.find_one({"_id": ready_row["_id"]}) is not None


@pytest.mark.asyncio
async def test_global_sweep_alternates_queues_at_limit_one_under_persistent_failures(
    setup_media, monkeypatch
):
    service, mongo, storage, _ = setup_media
    ready = await _finalize_ready_asset(service, storage, slot="about")
    ready_row = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(ready["asset_id"])}
    )
    now = datetime.now(timezone.utc)
    mongo.raw.storefront_assets.update_one(
        {"_id": ready_row["_id"]},
        {"$set": {"cleanup_due_at": now - timedelta(seconds=1)}},
    )
    candidate_key = f"storefront/{OWNER_ID}/hero/persistent-detached.webp"
    mongo.raw.storefront_asset_cleanup_receipts.insert_one(
        {
            "_id": ObjectId(),
            "owner_id": OWNER_ID,
            "slot": "hero",
            "candidate_key": candidate_key,
            "state": "cleanup_retry",
            "cleanup_due_at": now - timedelta(seconds=1),
            "updated_at": now,
        }
    )
    storage.head_by_key[candidate_key] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"detached"',
    }
    monkeypatch.setattr(storefront_media_module, "STOREFRONT_CLEANUP_RETRY_SECONDS", 0)
    storage.delete_error = RuntimeError("persistent storage failure")
    delete_count = len(storage.delete_calls)

    for _ in range(4):
        assert await service.sweep_abandoned_assets(limit=1) == 0

    queue_keys = {candidate_key, ready_row["key"]}
    attempted_keys = [
        call["key"]
        for call in storage.delete_calls[delete_count:]
        if call["key"] in queue_keys
    ]
    assert attempted_keys == [
        candidate_key,
        ready_row["key"],
        candidate_key,
        ready_row["key"],
    ]


@pytest.mark.asyncio
async def test_invalid_detached_receipt_is_quarantined_without_starving_valid_work(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    now = datetime.now(timezone.utc)
    invalid_id = ObjectId()
    mongo.raw.storefront_asset_cleanup_receipts.insert_one(
        {
            "_id": invalid_id,
            "owner_id": OWNER_ID,
            "slot": "invalid-slot",
            "candidate_key": "not-owner-scoped.webp",
            "state": "cleanup_retry",
            "cleanup_due_at": now - timedelta(seconds=1),
            "updated_at": now,
        }
    )
    valid_key = f"storefront/{OWNER_ID}/hero/valid-detached.webp"
    valid_id = ObjectId()
    mongo.raw.storefront_asset_cleanup_receipts.insert_one(
        {
            "_id": valid_id,
            "owner_id": OWNER_ID,
            "slot": "hero",
            "candidate_key": valid_key,
            "state": "cleanup_retry",
            "cleanup_due_at": now - timedelta(seconds=1),
            "updated_at": now,
        }
    )
    storage.head_by_key[valid_key] = {
        "ContentLength": 10,
        "ContentType": "image/webp",
        "ETag": '"valid"',
    }

    assert await service.sweep_abandoned_assets(limit=1) == 0
    assert (
        mongo.raw.storefront_asset_cleanup_receipts.find_one({"_id": invalid_id})[
            "state"
        ]
        == "invalid"
    )
    assert await service.sweep_abandoned_assets(limit=1) == 1
    assert (
        mongo.raw.storefront_asset_cleanup_receipts.find_one({"_id": valid_id}) is None
    )


@pytest.mark.asyncio
async def test_invalid_asset_receipt_is_quarantined_without_starving_valid_work(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    now = datetime.now(timezone.utc)
    invalid_id = ObjectId()
    mongo.raw.storefront_assets.insert_one(
        {
            "_id": invalid_id,
            "owner_id": OWNER_ID,
            "slot": "invalid-slot",
            "state": "cleanup_retry",
            "cleanup_due_at": now - timedelta(seconds=1),
            "updated_at": now,
        }
    )
    valid = await _finalize_ready_asset(service, storage, slot="hero")
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(valid["asset_id"])},
        {"$set": {"cleanup_due_at": now - timedelta(seconds=1)}},
    )

    assert await service.sweep_abandoned_assets(limit=1) == 0
    assert mongo.raw.storefront_assets.find_one({"_id": invalid_id})["state"] == (
        "invalid_cleanup_receipt"
    )
    assert await service.sweep_abandoned_assets(limit=1) == 1
    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(valid["asset_id"])})
        is None
    )


@pytest.mark.asyncio
async def test_detached_cleanup_receipt_reconciles_concurrent_unique_insert(
    setup_media,
):
    service, mongo, _, _ = setup_media
    receipts = mongo.db["storefront_asset_cleanup_receipts"]
    original_update = receipts.update_one
    candidate_key = f"storefront/{OWNER_ID}/hero/concurrent-candidate.webp"
    raced = False

    async def duplicate_once(query, update, *args, **kwargs):
        nonlocal raced
        if kwargs.get("upsert") and not raced:
            raced = True
            mongo.raw.storefront_asset_cleanup_receipts.insert_one(
                {
                    "_id": ObjectId(),
                    "owner_id": OWNER_ID,
                    "slot": "hero",
                    "candidate_key": candidate_key,
                    "state": "cleanup_retry",
                    "cleanup_attempts": 0,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            raise DuplicateKeyError("concurrent receipt")
        return await original_update(query, update, *args, **kwargs)

    receipts.update_one = duplicate_once
    await service._record_detached_candidate_cleanup(
        owner_id=OWNER_ID,
        slot="hero",
        candidate_key=candidate_key,
        reason="lost_finalizer_candidate",
        error=RuntimeError("delete failed"),
    )

    stored = mongo.raw.storefront_asset_cleanup_receipts.find_one(
        {"owner_id": OWNER_ID, "candidate_key": candidate_key}
    )
    assert stored["cleanup_attempts"] == 1
    assert stored["cleanup_reason"] == "lost_finalizer_candidate"


@pytest.mark.asyncio
async def test_referenced_due_receipt_cannot_starve_later_orphan_in_bounded_sweep(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    referenced = await _finalize_ready_asset(service, storage, slot="hero")
    orphan = await _finalize_ready_asset(service, storage, slot="about")
    due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    mongo.raw.storefront_assets.update_many({}, {"$set": {"cleanup_due_at": due_at}})
    mongo.raw.storefront_settings.insert_one(
        {"planner_id": OWNER_ID, "hero_asset_id": referenced["asset_id"]}
    )

    assert await service.sweep_abandoned_assets(limit=1) == 0
    assert await service.sweep_abandoned_assets(limit=1) == 1

    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(referenced["asset_id"])})
        is not None
    )
    assert (
        mongo.raw.storefront_assets.find_one({"_id": ObjectId(orphan["asset_id"])})
        is None
    )


@pytest.mark.asyncio
async def test_stale_reaping_takeover_fails_closed_when_asset_became_referenced(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "state": "reaping",
                "reap_token": "crashed-reaper",
                "reaping_started_at": stale_at,
                "reap_source_state": "ready",
                "cleanup_reason": "abandoned_ready_asset",
                "updated_at": stale_at,
            }
        },
    )
    mongo.raw.storefront_settings.insert_one(
        {"planner_id": OWNER_ID, "hero_asset_id": hero["asset_id"]}
    )
    delete_count = len(storage.delete_calls)

    assert await service.sweep_abandoned_assets(limit=1) == 0

    retained = mongo.raw.storefront_assets.find_one({"_id": row["_id"]})
    assert retained["state"] == "ready"
    assert "reap_token" not in retained
    assert len(storage.delete_calls) == delete_count


def test_global_storefront_sweep_is_wired_to_the_leader_elected_scheduler():
    source = (Path(__file__).parents[2] / "app" / "main.py").read_text()

    assert "async def _storefront_media_maintenance_scheduler" in source
    assert "storefront_media_service.sweep_abandoned_assets()" in source
    assert "storefront_media_task = asyncio.create_task(" in source
    assert "storefront_media_task," in source
    assert "storefront_inquiry_service.process_pending_notifications()" in source


@pytest.mark.asyncio
async def test_recovery_promotes_first_save_only_after_exact_claim_is_attached(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 1,
            "hero_asset_id": None,
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": claim["claim_id"],
            **_pending_asset_group(claim),
        }
    )

    before = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert before["hero_asset_id"] is None
    await service.recover_pending_settings_assets(_owner())

    saved = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    asset = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert saved["hero_asset_id"] == hero["asset_id"]
    assert "pending_hero_asset_id" not in saved
    assert "pending_hero_claim_id" not in saved
    assert saved["revision"] == 2
    assert asset["state"] == "attached"
    assert asset["attached_claim_id"] == claim["claim_id"]


@pytest.mark.asyncio
async def test_recovery_promotes_mixed_clear_and_attach_as_one_intent(setup_media):
    service, mongo, storage, _ = setup_media
    about = await _finalize_ready_asset(service, storage, slot="about")
    claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=None, about_asset_id=about["asset_id"]
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 1,
            "hero_asset_id": "hero-existing",
            "about_asset_id": "about-existing",
            "pending_hero_asset_id": None,
            "pending_hero_claim_id": claim["claim_id"],
            "pending_about_asset_id": about["asset_id"],
            "pending_about_claim_id": claim["claim_id"],
            **_pending_asset_group(claim),
        }
    )

    await service.recover_pending_settings_assets(_owner())

    stored = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored["hero_asset_id"] is None
    assert stored["about_asset_id"] == about["asset_id"]
    assert not any(field.startswith("pending_") for field in stored)


@pytest.mark.asyncio
async def test_recovery_rolls_back_mixed_clear_when_attach_member_is_missing(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    about = await _finalize_ready_asset(service, storage, slot="about")
    claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=None, about_asset_id=about["asset_id"]
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 1,
            "hero_asset_id": "hero-existing",
            "about_asset_id": "about-existing",
            "pending_hero_asset_id": None,
            "pending_hero_claim_id": claim["claim_id"],
            "pending_about_asset_id": about["asset_id"],
            "pending_about_claim_id": claim["claim_id"],
            **_pending_asset_group(claim),
        }
    )
    mongo.raw.storefront_assets.delete_one({"_id": ObjectId(about["asset_id"])})

    await service.recover_pending_settings_assets(_owner())

    stored = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored["hero_asset_id"] == "hero-existing"
    assert stored["about_asset_id"] == "about-existing"
    assert not any(field.startswith("pending_") for field in stored)


@pytest.mark.asyncio
async def test_recovery_promotes_claim_attached_before_worker_crash(setup_media):
    service, mongo, storage, _ = setup_media
    about = await _finalize_ready_asset(service, storage, slot="about")
    claim = await service.claim_settings_assets(
        _owner(), about_asset_id=about["asset_id"]
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 4,
            "about_asset_id": "old-about",
            "pending_about_asset_id": about["asset_id"],
            "pending_about_claim_id": claim["claim_id"],
            **_pending_asset_group(claim),
        }
    )
    await service.attach_settings_asset_claims(_owner(), claim)

    await service.recover_pending_settings_assets(_owner())

    saved = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert saved["about_asset_id"] == about["asset_id"]
    assert "pending_about_asset_id" not in saved
    assert saved["revision"] == 5


@pytest.mark.asyncio
async def test_recovery_rolls_back_invalid_pending_without_erasing_stable_asset(
    setup_media,
):
    service, mongo, _, _ = setup_media
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 9,
            "hero_asset_id": "stable-hero",
            "pending_hero_asset_id": "missing-asset",
            "pending_hero_claim_id": "orphaned-claim",
        }
    )

    await service.recover_pending_settings_assets(_owner())

    saved = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert saved["hero_asset_id"] == "stable-hero"
    assert "pending_hero_asset_id" not in saved
    assert "pending_hero_claim_id" not in saved
    assert saved["revision"] == 10


@pytest.mark.asyncio
async def test_recovery_never_promotes_legacy_pending_pair_without_group_manifest(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 3,
            "hero_asset_id": "stable-hero",
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": claim["claim_id"],
        }
    )

    await service.recover_pending_settings_assets(_owner())

    saved = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert saved["hero_asset_id"] == "stable-hero"
    assert "pending_hero_asset_id" not in saved
    assert "pending_hero_claim_id" not in saved
    asset = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert asset["state"] == "ready"


@pytest.mark.asyncio
async def test_recovery_uses_manifest_to_rollback_group_with_missing_pending_sibling(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    about = await _finalize_ready_asset(service, storage, slot="about")
    claim = await service.claim_settings_assets(
        _owner(),
        hero_asset_id=hero["asset_id"],
        about_asset_id=about["asset_id"],
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 6,
            "hero_asset_id": "stable-hero",
            "about_asset_id": "stable-about",
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": claim["claim_id"],
            **_pending_asset_group(claim),
        }
    )

    await service.recover_pending_settings_assets(_owner())

    saved = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert saved["hero_asset_id"] == "stable-hero"
    assert saved["about_asset_id"] == "stable-about"
    assert not any(key.startswith("pending_") for key in saved)
    for asset_id in (hero["asset_id"], about["asset_id"]):
        asset = mongo.raw.storefront_assets.find_one({"_id": ObjectId(asset_id)})
        assert asset["state"] == "ready"


@pytest.mark.asyncio
async def test_explicit_clear_releases_attached_but_unpromoted_pending_claim(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 2,
            "hero_asset_id": "stable-old-hero",
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": claim["claim_id"],
            **_pending_asset_group(claim),
        }
    )
    await service.attach_settings_asset_claims(_owner(), claim)
    mongo.raw.storefront_settings.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {"hero_asset_id": None},
            "$unset": {
                "pending_hero_asset_id": "",
                "pending_hero_claim_id": "",
                "pending_asset_group": "",
            },
            "$inc": {"revision": 1},
        },
    )

    await service.release_settings_asset_claims(_owner(), claim)

    asset = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert asset["state"] == "ready"
    assert "attached_claim_id" not in asset


@pytest.mark.asyncio
async def test_stale_claim_can_be_taken_over_and_old_worker_cannot_promote(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    old_claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(hero["asset_id"])},
        {"$set": {"attach_claimed_at": stale_at}},
    )

    new_claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    assert new_claim["claim_id"] != old_claim["claim_id"]
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 1,
            "hero_asset_id": None,
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": new_claim["claim_id"],
            **_pending_asset_group(new_claim),
        }
    )
    await service.attach_settings_asset_claims(_owner(), new_claim)
    await service.promote_settings_asset_claims(_owner(), new_claim)

    with pytest.raises(HTTPException) as stale:
        await service.promote_settings_asset_claims(_owner(), old_claim)
    assert stale.value.status_code == 409
    saved = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert saved["hero_asset_id"] == hero["asset_id"]
    asset = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert asset["attached_claim_id"] == new_claim["claim_id"]


@pytest.mark.asyncio
async def test_multi_slot_claim_promotes_both_stable_ids_in_one_settings_revision(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    about = await _finalize_ready_asset(service, storage, slot="about")
    claim = await service.claim_settings_assets(
        _owner(),
        hero_asset_id=hero["asset_id"],
        about_asset_id=about["asset_id"],
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 7,
            "hero_asset_id": "old-hero",
            "about_asset_id": "old-about",
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": claim["claim_id"],
            "pending_about_asset_id": about["asset_id"],
            "pending_about_claim_id": claim["claim_id"],
            **_pending_asset_group(claim),
        }
    )

    await service.attach_settings_asset_claims(_owner(), claim)
    await service.promote_settings_asset_claims(_owner(), claim)

    saved = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert saved["hero_asset_id"] == hero["asset_id"]
    assert saved["about_asset_id"] == about["asset_id"]
    assert saved["revision"] == 8
    assert not any(key.startswith("pending_") for key in saved)


@pytest.mark.asyncio
async def test_multi_slot_claim_final_validation_releases_group_if_one_slot_is_stolen(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    about = await _finalize_ready_asset(service, storage, slot="about")
    assets = mongo.db["storefront_assets"]
    original_update = assets.update_one
    update_count = 0

    async def steal_first_slot_after_second_claim(query, update, *args, **kwargs):
        nonlocal update_count
        result = await original_update(query, update, *args, **kwargs)
        if update.get("$set", {}).get("state") == "attaching":
            update_count += 1
            if update_count == 2:
                mongo.raw.storefront_assets.update_one(
                    {"_id": ObjectId(hero["asset_id"])},
                    {
                        "$set": {
                            "state": "attaching",
                            "attach_claim_id": "successor-token",
                            "attach_claimed_at": datetime.now(timezone.utc),
                        }
                    },
                )
        return result

    assets.update_one = steal_first_slot_after_second_claim

    with pytest.raises(HTTPException) as conflict:
        await service.claim_settings_assets(
            _owner(),
            hero_asset_id=hero["asset_id"],
            about_asset_id=about["asset_id"],
        )

    assert conflict.value.status_code == 409
    about_row = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(about["asset_id"])}
    )
    assert about_row["state"] == "ready"
    hero_row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert hero_row["attach_claim_id"] == "successor-token"


@pytest.mark.asyncio
async def test_reconcile_never_promotes_only_referenced_subset_of_token_group(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    about = await _finalize_ready_asset(service, storage, slot="about")
    claim = await service.claim_settings_assets(
        _owner(),
        hero_asset_id=hero["asset_id"],
        about_asset_id=about["asset_id"],
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 7,
            "hero_asset_id": "old-hero",
            "about_asset_id": "old-about",
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": claim["claim_id"],
            "pending_about_asset_id": "new-about",
            "pending_about_claim_id": "successor-token",
            **_pending_asset_group(claim),
        }
    )

    await service.reconcile_settings_asset_claims(_owner(), claim)

    saved = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert saved["hero_asset_id"] == "old-hero"
    assert saved["about_asset_id"] == "old-about"
    assert "pending_hero_asset_id" not in saved
    assert "pending_hero_claim_id" not in saved
    assert saved["pending_about_asset_id"] == "new-about"
    assert saved["pending_about_claim_id"] == "successor-token"
    hero_row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    about_row = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(about["asset_id"])}
    )
    assert hero_row["state"] == "ready"
    assert about_row["state"] == "ready"


@pytest.mark.asyncio
async def test_recovery_rolls_back_entire_token_group_when_one_sibling_is_invalid(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    about = await _finalize_ready_asset(service, storage, slot="about")
    claim = await service.claim_settings_assets(
        _owner(),
        hero_asset_id=hero["asset_id"],
        about_asset_id=about["asset_id"],
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 12,
            "hero_asset_id": "old-hero",
            "about_asset_id": "old-about",
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": claim["claim_id"],
            "pending_about_asset_id": about["asset_id"],
            "pending_about_claim_id": claim["claim_id"],
            **_pending_asset_group(claim),
        }
    )
    await service.attach_settings_asset_claims(_owner(), claim)
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(about["asset_id"])},
        {
            "$set": {
                "state": "attaching",
                "attach_claim_id": "successor-token",
                "attach_claimed_at": datetime.now(timezone.utc),
            },
            "$unset": {"attached_claim_id": "", "attached_at": ""},
        },
    )

    await service.recover_pending_settings_assets(_owner())

    saved = mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert saved["hero_asset_id"] == "old-hero"
    assert saved["about_asset_id"] == "old-about"
    assert not any(key.startswith("pending_") for key in saved)
    assert saved["revision"] == 13
    hero_row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert hero_row["state"] == "ready"
    about_row = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(about["asset_id"])}
    )
    assert about_row["attach_claim_id"] == "successor-token"


@pytest.mark.asyncio
async def test_recovery_releases_unreferenced_attached_and_stale_attaching_orphans(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    attached = await _finalize_ready_asset(service, storage, slot="hero")
    stale = await _finalize_ready_asset(service, storage, slot="about")
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(attached["asset_id"])},
        {
            "$set": {
                "state": "attached",
                "attached_claim_id": "failed-release-token",
                "attached_at": datetime.now(timezone.utc),
            }
        },
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(stale["asset_id"])},
        {
            "$set": {
                "state": "attaching",
                "attach_claim_id": "crashed-before-settings",
                "attach_claimed_at": stale_at,
            }
        },
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 2,
            "hero_asset_id": "replacement-hero",
            "about_asset_id": "replacement-about",
        }
    )

    await service.recover_pending_settings_assets(_owner())

    for asset_id in (attached["asset_id"], stale["asset_id"]):
        row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(asset_id)})
        assert row["state"] == "ready"
        assert "attach_claim_id" not in row
        assert "attached_claim_id" not in row


@pytest.mark.asyncio
async def test_recovery_does_not_steal_fresh_claim_for_stably_referenced_asset(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _finalize_ready_asset(service, storage, slot="hero")
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 2,
            "hero_asset_id": hero["asset_id"],
        }
    )
    claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )

    await service.recover_pending_settings_assets(_owner())

    row = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert row["state"] == "attaching"
    assert row["attach_claim_id"] == claim["claim_id"]
    assert isinstance(row["attach_claimed_at"], datetime)


@pytest.mark.asyncio
async def test_stale_claim_with_durable_pending_token_stays_fenced_until_recovery(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _reserve(service, slot="hero", size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"hero-source"',
    }
    await service.finalize(_owner(), hero["asset_id"])

    first_claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(hero["asset_id"])},
        {"$set": {"attach_claimed_at": stale_at}},
    )
    mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "revision": 1,
            "hero_asset_id": None,
            "pending_hero_asset_id": hero["asset_id"],
            "pending_hero_claim_id": first_claim["claim_id"],
            **_pending_asset_group(first_claim),
        }
    )

    with pytest.raises(HTTPException) as retry_blocked:
        await service.claim_settings_assets(_owner(), hero_asset_id=hero["asset_id"])
    assert retry_blocked.value.status_code == 409
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["state"] == "attaching"
    assert stored["attach_claim_id"] == first_claim["claim_id"]
    with pytest.raises(HTTPException) as cleanup_blocked:
        await service.cleanup(_owner(), hero["asset_id"])
    assert cleanup_blocked.value.status_code == 409

    await service.recover_pending_settings_assets(_owner())
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["state"] == "attached"

    # A later crash after the settings reference exists is safely recoverable:
    # canonical settings first restore attached, then a new claim fences edits.
    second_claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    mongo.raw.storefront_settings.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "pending_hero_asset_id": hero["asset_id"],
                "pending_hero_claim_id": second_claim["claim_id"],
                **_pending_asset_group(second_claim),
            },
            "$inc": {"revision": 1},
        },
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(hero["asset_id"])},
        {"$set": {"attach_claimed_at": stale_at}},
    )
    await service.recover_pending_settings_assets(_owner())
    reconciled = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    assert reconciled["claimed_assets"][0]["asset_id"] == hero["asset_id"]
    assert reconciled["claim_id"] != second_claim["claim_id"]
    await service.release_settings_asset_claims(_owner(), reconciled)
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["state"] == "attached"


@pytest.mark.asyncio
async def test_stale_finalization_lease_discards_candidate_and_retries_safely(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service, slot="about", size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    upload = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"about-source"',
    }
    storage.head_by_key[staging_key] = dict(upload)
    reservation = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    stale_candidate = service._finalization_candidate_key(reservation, "crashed-worker")
    storage.head_by_key[stale_candidate] = {
        **upload,
        "ETag": '"partial-final"',
    }
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(reserved["asset_id"])},
        {
            "$set": {
                "state": "finalizing",
                "finalization_token": "crashed-worker",
                "updated_at": stale_at,
            }
        },
    )

    finalized = await service.finalize(_owner(), reserved["asset_id"])

    assert finalized["state"] == "ready"
    assert any(call["key"] == stale_candidate for call in storage.delete_calls)
    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    assert stored["state"] == "ready"
    assert "finalization_token" not in stored


@pytest.mark.asyncio
async def test_stale_finalization_recovery_lease_can_resume_after_second_crash(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service, slot="about", size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    upload = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"about-source"',
    }
    storage.head_by_key[staging_key] = dict(upload)
    reservation = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    abandoned_candidate = service._finalization_candidate_key(
        reservation, "abandoned-worker"
    )
    storage.head_by_key[abandoned_candidate] = dict(upload)
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(reserved["asset_id"])},
        {
            "$set": {
                "state": "finalization_recovery",
                "recovery_token": "crashed-recovery",
                "cleanup_candidate_key": abandoned_candidate,
                "updated_at": stale_at,
            }
        },
    )

    finalized = await service.finalize(_owner(), reserved["asset_id"])

    assert finalized["state"] == "ready"
    assert abandoned_candidate not in storage.head_by_key
    assert finalized["key"] in storage.head_by_key


@pytest.mark.asyncio
async def test_stale_finalizer_cannot_delete_newer_committed_candidate(setup_media):
    service, mongo, storage, _ = setup_media
    reserved = await _reserve(service, slot="about", size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"about-source"',
    }
    assets = mongo.db["storefront_assets"]
    original_update = assets.update_one
    first_commit_paused = asyncio.Event()
    resume_first_commit = asyncio.Event()

    async def pause_first_ready_commit(query, update, *args, **kwargs):
        if (
            asyncio.current_task().get_name() == "stale-finalizer"
            and update.get("$set", {}).get("state") == "ready"
        ):
            first_commit_paused.set()
            await resume_first_commit.wait()
        return await original_update(query, update, *args, **kwargs)

    assets.update_one = pause_first_ready_commit
    stale_finalizer = asyncio.create_task(
        service.finalize(_owner(), reserved["asset_id"]),
        name="stale-finalizer",
    )
    await first_commit_paused.wait()
    first_candidate = storage.upload_calls[-1]["key"]
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=STOREFRONT_ASSET_OPERATION_LEASE_SECONDS + 1
    )
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(reserved["asset_id"])},
        {"$set": {"finalization_started_at": stale_at}},
    )

    newer = await service.finalize(_owner(), reserved["asset_id"])
    second_candidate = storage.upload_calls[-1]["key"]
    resume_first_commit.set()

    with pytest.raises(HTTPException) as stale_lost:
        await stale_finalizer
    assert stale_lost.value.status_code == 409
    assert first_candidate != second_candidate
    assert newer["key"] == second_candidate
    assert second_candidate in storage.head_by_key
    stored = mongo.raw.storefront_assets.find_one(
        {"_id": ObjectId(reserved["asset_id"])}
    )
    assert stored["state"] == "ready"
    assert stored["key"] == second_candidate


@pytest.mark.asyncio
async def test_attached_asset_is_claimed_before_release_can_make_it_cleanable(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _reserve(service, slot="hero", size_bytes=100)
    staging_key = storage.presign_calls[-1]["key"]
    storage.head_by_key[staging_key] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"hero-source"',
    }
    await service.finalize(_owner(), hero["asset_id"])
    mongo.raw.storefront_assets.update_one(
        {"_id": ObjectId(hero["asset_id"])},
        {"$set": {"state": "attached", "attached_at": datetime.now(timezone.utc)}},
    )

    claim = await service.claim_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["state"] == "attaching"
    assert claim["claimed_assets"][0]["asset_id"] == hero["asset_id"]

    release_attempt = await service.release_if_unreferenced(_owner(), hero["asset_id"])
    assert release_attempt["state"] == "attaching"

    # A competing settings CAS won. Releasing this losing claim must consult
    # canonical settings and restore attached, never make the reference cleanable.
    mongo.raw.storefront_settings.insert_one(
        {"planner_id": OWNER_ID, "hero_asset_id": hero["asset_id"]}
    )
    await service.release_settings_asset_claims(_owner(), claim)
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["state"] == "attached"


@pytest.mark.asyncio
async def test_validate_and_attach_settings_assets_enforce_owner_state_and_slot(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _reserve(service, slot="hero", size_bytes=100)
    storage.head_by_key[storage.presign_calls[-1]["key"]] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"hero-source"',
    }

    with pytest.raises(HTTPException) as not_ready:
        await service.validate_asset_for_slot(_owner(), hero["asset_id"], "hero")
    assert not_ready.value.status_code == 409

    await service.finalize(_owner(), hero["asset_id"])
    validated = await service.validate_settings_assets(
        _owner(), hero_asset_id=hero["asset_id"]
    )
    assert validated == {"hero_asset_id": hero["asset_id"]}
    assert await service.validate_settings_assets(_owner(), about_asset_id=None) == {
        "about_asset_id": None
    }

    with pytest.raises(HTTPException) as wrong_slot:
        await service.validate_asset_for_slot(_owner(), hero["asset_id"], "about")
    assert wrong_slot.value.status_code == 409

    with pytest.raises(HTTPException) as foreign:
        await service.validate_asset_for_slot(
            _owner(SECOND_OWNER_ID), hero["asset_id"], "hero"
        )
    assert foreign.value.status_code == 404

    with pytest.raises(HTTPException) as not_referenced:
        await service.attach(_owner(), hero["asset_id"], "hero")
    assert not_referenced.value.status_code == 409

    mongo.raw.storefront_settings.insert_one(
        {"planner_id": OWNER_ID, "hero_asset_id": hero["asset_id"]}
    )
    attached = await service.attach(_owner(), hero["asset_id"], "hero")
    assert attached["state"] == "attached"
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["state"] == "attached"


@pytest.mark.asyncio
async def test_release_detaches_replaced_asset_only_after_settings_stop_referencing_it(
    setup_media,
):
    service, mongo, storage, _ = setup_media
    hero = await _reserve(service, slot="hero", size_bytes=100)
    storage.head_by_key[storage.presign_calls[-1]["key"]] = {
        "ContentLength": 100,
        "ContentType": "image/webp",
        "ETag": '"hero-source"',
    }
    await service.finalize(_owner(), hero["asset_id"])
    mongo.raw.storefront_settings.insert_one(
        {"planner_id": OWNER_ID, "hero_asset_id": hero["asset_id"]}
    )
    await service.attach(_owner(), hero["asset_id"], "hero")

    still_used = await service.release_if_unreferenced(_owner(), hero["asset_id"])
    assert still_used["state"] == "attached"

    mongo.raw.storefront_settings.update_one(
        {"planner_id": OWNER_ID}, {"$set": {"hero_asset_id": None}}
    )
    released = await service.release_if_unreferenced(_owner(), hero["asset_id"])
    assert released["state"] == "ready"
    stored = mongo.raw.storefront_assets.find_one({"_id": ObjectId(hero["asset_id"])})
    assert stored["state"] == "ready"
    assert "attached_at" not in stored
