from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
import threading
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException
from PIL import Image

import app.services.storefront_media_service as storefront_media_module
from app.services.storefront_entitlement_service import StorefrontEntitlements
from app.services.storefront_media_service import (
    MAX_STOREFRONT_ASSET_SIZE_BYTES,
    STOREFRONT_ASSET_OPERATION_LEASE_SECONDS,
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
