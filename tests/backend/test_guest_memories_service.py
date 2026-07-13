import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_test_stubs() -> None:
    if "aiohttp" not in sys.modules:
        aiohttp_module = types.ModuleType("aiohttp")
        aiohttp_module.ClientSession = object
        aiohttp_module.ClientTimeout = lambda *args, **kwargs: None
        sys.modules["aiohttp"] = aiohttp_module

    if "boto3" not in sys.modules:
        boto3_module = types.ModuleType("boto3")
        boto3_module.client = lambda *args, **kwargs: object()
        sys.modules["boto3"] = boto3_module

    if "botocore" not in sys.modules:
        sys.modules["botocore"] = types.ModuleType("botocore")

    if "botocore.config" not in sys.modules:
        botocore_config = types.ModuleType("botocore.config")

        class Config:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        botocore_config.Config = Config
        sys.modules["botocore.config"] = botocore_config

    if "botocore.exceptions" not in sys.modules:
        botocore_exceptions = types.ModuleType("botocore.exceptions")

        class ClientError(Exception):
            pass

        class BotoCoreError(Exception):
            pass

        botocore_exceptions.BotoCoreError = BotoCoreError
        botocore_exceptions.ClientError = ClientError
        sys.modules["botocore.exceptions"] = botocore_exceptions

    if "fastapi" not in sys.modules:
        fastapi_module = types.ModuleType("fastapi")

        class HTTPException(Exception):
            def __init__(self, status_code: int, detail: str):
                self.status_code = status_code
                self.detail = detail
                super().__init__(detail)

        fastapi_module.HTTPException = HTTPException
        sys.modules["fastapi"] = fastapi_module

    if "app.core.database" not in sys.modules:
        database_module = types.ModuleType("app.core.database")
        database_module.mongo = types.SimpleNamespace(
            get_guest_collection=lambda: object(),
            db={
                "weddings": object(),
                "rsvps": object(),
                "guest_media_assets": object(),
                "guest_media_exports": object(),
            },
        )
        sys.modules["app.core.database"] = database_module

    if "app.core.settings" not in sys.modules:
        settings_module = types.ModuleType("app.core.settings")
        settings_module.settings = types.SimpleNamespace(
            api_base_url=None,
            cors_origins=[],
            environment="test",
            frontend_url="https://app.example.com",
            s3_endpoint_url=None,
            s3_access_key_id=None,
            s3_secret_access_key=None,
            s3_region="auto",
            s3_healthcheck_ttl_seconds=0,
            s3_credentials_configured=False,
            primary_media_bucket_name=None,
            normalized_media_domain=None,
            guest_media_bucket_name=None,
            normalized_guest_media_domain=None,
            ad_media_bucket_name=None,
            normalized_ad_media_domain=None,
            blog_media_bucket_name=None,
            normalized_blog_media_domain=None,
            form_uploads_bucket_name=None,
            normalized_form_uploads_domain=None,
            secret_key="test-secret-key-with-sufficient-length-123456",
        )
        sys.modules["app.core.settings"] = settings_module

    if "app.utils.serializers" not in sys.modules:
        serializers_module = types.ModuleType("app.utils.serializers")
        serializers_module.serialize_mongo_doc = lambda doc: dict(doc)
        sys.modules["app.utils.serializers"] = serializers_module


_install_test_stubs()

import app.services.guest_media_service as guest_media_module  # noqa: E402
from app.constants.seed_sources import (  # noqa: E402
    MARKETING_CAPTURE_SEED_SCOPE,
    MARKETING_CAPTURE_SEED_SOURCE,
)
from app.services.guest_export_service import GuestExportService  # noqa: E402
from app.services.guest_media_service import GuestMediaService  # noqa: E402


def _build_service() -> GuestMediaService:
    return GuestMediaService.__new__(GuestMediaService)


def _build_export_service() -> GuestExportService:
    return GuestExportService.__new__(GuestExportService)


def test_uploaded_object_constraints_accept_matching_reserved_upload():
    service = _build_service()

    reserved_asset = {
        "media_type": "image",
        "mime_type": "image/jpeg",
        "size_bytes": 1024,
    }

    service._validate_uploaded_object_constraints(
        reserved_asset,
        actual_size=1024,
        actual_content_type="image/jpeg",
    )


@pytest.mark.parametrize(
    ("reserved_asset", "actual_size", "actual_content_type", "expected_message"),
    [
        (
            {"media_type": "image", "mime_type": "image/jpeg", "size_bytes": 1024},
            2048,
            "image/jpeg",
            "Uploaded object size does not match the reserved upload",
        ),
        (
            {"media_type": "image", "mime_type": "image/jpeg", "size_bytes": 1024},
            1024,
            "image/png",
            "Uploaded object content type does not match the reserved upload",
        ),
        (
            {
                "media_type": "image",
                "mime_type": "image/jpeg",
                "size_bytes": 30 * 1024 * 1024,
            },
            30 * 1024 * 1024,
            "image/jpeg",
            "Images must be 25 MB or smaller",
        ),
        (
            {"media_type": "video", "mime_type": "video/mp4", "size_bytes": 1024},
            1024,
            "application/octet-stream",
            "Uploaded object uses an unsupported media type",
        ),
    ],
)
def test_uploaded_object_constraints_reject_invalid_finalize_objects(
    reserved_asset,
    actual_size,
    actual_content_type,
    expected_message,
):
    service = _build_service()

    with pytest.raises(ValueError, match=expected_message):
        service._validate_uploaded_object_constraints(
            reserved_asset,
            actual_size=actual_size,
            actual_content_type=actual_content_type,
        )


def test_serialize_asset_uses_authenticated_relative_paths_for_images():
    service = _build_service()

    serialized = service._serialize_asset(
        {
            "_id": "asset-image-1",
            "media_type": "image",
            "event_type": None,
            "upload_status": "uploaded",
            "original_bucket": "guest-memories",
            "original_key": "guest-media/demo/asset.jpg",
            "demo_preview_url": "/demo-gallery/elegant-couple-stairs.svg",
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            "stream_uid": None,
            "stream_playback_base_url": None,
        }
    )

    assert serialized["id"] == "asset-image-1"
    assert serialized["preview_path"] == "/couple/portal/memories/asset-image-1/preview"
    assert serialized["event_type"] == "not_sure"
    assert serialized["download_ready"] is True
    assert "original_bucket" not in serialized
    assert "original_key" not in serialized
    assert "stream_uid" not in serialized
    assert "demo_preview_url" not in serialized
    assert "seed_source" not in serialized
    assert "seed_scope" not in serialized


def test_serialize_asset_uses_authenticated_relative_paths_for_videos():
    service = _build_service()

    serialized = service._serialize_asset(
        {
            "_id": "asset-video-1",
            "media_type": "video",
            "event_type": "reception",
            "upload_status": "uploaded",
            "stream_uid": "video-uid-123",
            "stream_playback_base_url": "https://customer-demo.cloudflarestream.com",
            "stream_token": "should-not-leak",
            "stream_token_expires_at": datetime.now(timezone.utc).isoformat(),
            "original_bucket": "guest-memories",
            "original_key": "guest-media/demo/asset.mp4",
        }
    )

    assert serialized["id"] == "asset-video-1"
    assert serialized["player_path"] == "/couple/portal/memories/asset-video-1/player"
    assert (
        serialized["thumbnail_path"]
        == "/couple/portal/memories/asset-video-1/thumbnail"
    )
    assert serialized["event_type"] == "reception"
    assert "original_bucket" not in serialized
    assert "original_key" not in serialized
    assert "stream_uid" not in serialized
    assert "stream_token" not in serialized
    assert "stream_token_expires_at" not in serialized


def test_marketing_capture_memories_use_public_site_url_and_clean_storage_health():
    service = _build_service()
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "slug": "sofia-and-daniel",
        "couple_names": "Sofia & Daniel",
        "public_site_url": "https://www.thespecialwedding.io/sofia-and-daniel",
    }
    service.storage = SimpleNamespace(
        is_configured=False,
        status="unavailable",
        issue="SignatureDoesNotMatch",
    )
    service._allow_demo_context_without_storage = lambda _wedding: True
    service._get_wedding_by_id = AsyncMock(return_value=wedding)
    service.ensure_guest_media_config = AsyncMock(
        return_value={
            "config": {"last_rotated_at": None},
            "upload_token": "showcase-token",
        }
    )
    service.get_dashboard_summary = AsyncMock(
        return_value={"pending_count": 4, **service._storage_health_payload(wedding)}
    )
    service._event_options = lambda _wedding: []

    settings = asyncio.run(service.get_couple_settings(str(wedding["_id"])))

    assert settings["upload_url"] == (
        "https://www.thespecialwedding.io/sofia-and-daniel/upload/showcase-token"
    )
    assert settings["storage_ready"] is True
    assert settings["storage_status"] == "ready"
    assert settings["storage_issue"] is None


def test_normal_memories_preserve_real_storage_failures():
    service = _build_service()
    service.storage = SimpleNamespace(
        is_configured=False,
        status="unavailable",
        issue="Signer credentials are invalid",
    )
    service._allow_demo_context_without_storage = lambda _wedding: False

    assert service._storage_health_payload({"slug": "real-wedding"}) == {
        "storage_ready": False,
        "storage_status": "unavailable",
        "storage_issue": "Signer credentials are invalid",
    }


@pytest.mark.asyncio
async def test_marketing_capture_preview_uses_allowlisted_local_demo_asset(
    monkeypatch: pytest.MonkeyPatch,
):
    service = _build_service()
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    asset = {
        "_id": "marketing_capture_memory_pending_001",
        "wedding_id": str(wedding["_id"]),
        "media_type": "image",
        "upload_status": "uploaded",
        "original_key": "guest-media/sofia-and-daniel/demo/memory.jpg",
        "demo_preview_url": "/demo-gallery/elegant-couple-stairs.svg",
    }
    service._get_wedding_by_id = AsyncMock(return_value=wedding)
    service.assets = SimpleNamespace(find_one=AsyncMock(return_value=asset))
    service.storage = SimpleNamespace(
        create_presigned_download_url=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("exact demo preview must not call unavailable storage")
        )
    )
    monkeypatch.setattr(guest_media_module.settings, "environment", "test")
    monkeypatch.setattr(
        guest_media_module.settings,
        "frontend_url",
        "http://127.0.0.1:3000",
    )

    preview_url = await service.get_asset_redirect_url(
        str(wedding["_id"]),
        str(asset["_id"]),
        "preview",
    )

    assert preview_url == (
        "http://127.0.0.1:3000/demo-gallery/elegant-couple-stairs.svg"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_preview_url",
    [
        "https://attacker.example/demo.svg",
        "/demo-gallery/../secret.svg",
        "/not-demo-gallery/image.svg",
    ],
)
async def test_marketing_capture_preview_rejects_non_allowlisted_demo_urls(
    monkeypatch: pytest.MonkeyPatch,
    unsafe_preview_url: str,
):
    service = _build_service()
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    asset = {
        "_id": "marketing_capture_memory_pending_001",
        "wedding_id": str(wedding["_id"]),
        "media_type": "image",
        "upload_status": "uploaded",
        "original_key": "guest-media/sofia-and-daniel/demo/memory.jpg",
        "demo_preview_url": unsafe_preview_url,
    }
    service._get_wedding_by_id = AsyncMock(return_value=wedding)
    service.assets = SimpleNamespace(find_one=AsyncMock(return_value=asset))
    service.storage = SimpleNamespace(
        create_presigned_download_url=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("storage remains authoritative")
        )
    )
    monkeypatch.setattr(guest_media_module.settings, "environment", "test")

    with pytest.raises(guest_media_module.HTTPException) as exc_info:
        await service.get_asset_redirect_url(
            str(wedding["_id"]),
            str(asset["_id"]),
            "preview",
        )

    assert exc_info.value.status_code == 503


@pytest.mark.parametrize("seed_scope", [None, "another-demo"])
def test_marketing_capture_storage_bypass_requires_exact_seed_scope(seed_scope):
    service = _build_service()
    guest_media_module.settings.environment = "test"

    assert not service._allow_demo_context_without_storage(
        {
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": seed_scope,
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("seed_scope", [None, "another-demo"])
async def test_marketing_capture_preview_does_not_bypass_storage_for_wrong_scope(
    monkeypatch: pytest.MonkeyPatch,
    seed_scope: str | None,
):
    service = _build_service()
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": seed_scope,
    }
    asset = {
        "_id": "marketing_capture_memory_pending_001",
        "wedding_id": str(wedding["_id"]),
        "media_type": "image",
        "upload_status": "uploaded",
        "original_key": "guest-media/sofia-and-daniel/demo/memory.jpg",
        "demo_preview_url": "/demo-gallery/elegant-couple-stairs.svg",
    }
    service._get_wedding_by_id = AsyncMock(return_value=wedding)
    service.assets = SimpleNamespace(find_one=AsyncMock(return_value=asset))
    service.storage = SimpleNamespace(
        create_presigned_download_url=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("storage remains authoritative")
        )
    )
    monkeypatch.setattr(guest_media_module.settings, "environment", "test")

    with pytest.raises(guest_media_module.HTTPException) as exc_info:
        await service.get_asset_redirect_url(
            str(wedding["_id"]),
            str(asset["_id"]),
            "preview",
        )

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_normal_tenant_preview_preserves_storage_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    service = _build_service()
    wedding = {"_id": "real-wedding", "seed_source": None}
    asset = {
        "_id": "real-memory",
        "wedding_id": "real-wedding",
        "media_type": "image",
        "upload_status": "uploaded",
        "original_key": "guest-media/real-wedding/memory.jpg",
        "demo_preview_url": "/demo-gallery/elegant-couple-stairs.svg",
    }
    service._get_wedding_by_id = AsyncMock(return_value=wedding)
    service.assets = SimpleNamespace(find_one=AsyncMock(return_value=asset))
    service.storage = SimpleNamespace(
        create_presigned_download_url=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("SignatureDoesNotMatch")
        )
    )
    monkeypatch.setattr(guest_media_module.settings, "environment", "test")

    with pytest.raises(guest_media_module.HTTPException) as exc_info:
        await service.get_asset_redirect_url(
            str(wedding["_id"]),
            str(asset["_id"]),
            "preview",
        )

    assert exc_info.value.status_code == 503


def test_build_stream_copy_payload_enforces_private_stream_defaults():
    service = _build_service()

    guest_media_module.settings.frontend_url = "https://portal.example.com"
    guest_media_module.settings.cors_origins = [
        "https://portal.example.com",
        "http://localhost:3000",
        "https://admin.example.com",
    ]

    payload = service._build_stream_copy_payload(
        "https://signed-r2.example.com/object",
        {
            "wedding_id": "wedding-123",
            "original_filename": "toast.mp4",
        },
        "asset-123",
    )

    assert payload["url"] == "https://signed-r2.example.com/object"
    assert payload["requireSignedURLs"] is True
    assert payload["allowedOrigins"] == ["admin.example.com", "portal.example.com"]
    assert payload["meta"] == {
        "asset_id": "asset-123",
        "wedding_id": "wedding-123",
        "filename": "toast.mp4",
    }


def test_get_stream_player_token_reuses_unexpired_cached_token():
    service = _build_service()

    class FakeAssets:
        async def update_one(self, *_args, **_kwargs):
            raise AssertionError(
                "Should not persist a new token when cached token is still valid"
            )

    service.assets = FakeAssets()

    asset = {
        "_id": "asset-video-2",
        "stream_uid": "stream-123",
        "stream_token": "cached-token",
        "stream_token_expires_at": (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).isoformat(),
    }

    token = asyncio.run(service._get_stream_player_token(asset))
    assert token == "cached-token"


def test_poll_stream_ready_marks_error_state_as_failed():
    service = _build_service()
    guest_media_module.settings.frontend_url = "https://app.example.com"
    guest_media_module.settings.cors_origins = []

    class FakeAssets:
        def __init__(self):
            self.calls = []

        async def update_one(self, query, update):
            self.calls.append((query, update))

    fake_assets = FakeAssets()
    service.assets = fake_assets
    call_log = []

    async def fake_stream_request(method, path, payload=None):
        call_log.append((method, path, payload))
        assert path == "/stream-uid-123"
        if method == "POST":
            assert payload["requireSignedURLs"] is True
            assert payload["allowedOrigins"] == ["app.example.com"]
            return {}

        assert method == "GET"
        return {
            "uid": "stream-uid-123",
            "requireSignedURLs": True,
            "allowedOrigins": ["app.example.com"],
            "status": {
                "state": "error",
                "errorReasonCode": "ERR_NON_VIDEO",
                "errorReasonText": "The file was not recognized as a valid video file.",
            },
        }

    service._stream_request = fake_stream_request

    asyncio.run(service._poll_stream_ready_once("asset-video-3", "stream-uid-123"))

    assert [entry[0] for entry in call_log] == ["GET"]
    assert fake_assets.calls
    query, update = fake_assets.calls[-1]
    assert query == {"_id": "asset-video-3"}
    assert update["$set"]["stream_status"] == "failed"
    assert (
        update["$set"]["stream_error"]
        == "The file was not recognized as a valid video file."
    )


def test_generate_guest_memories_sign_pdf_embeds_qr_and_upload_url(monkeypatch):
    export_service = _build_export_service()
    rendered = {}

    class FakeHTML:
        def __init__(self, string: str):
            rendered["html"] = string

        def write_pdf(self) -> bytes:
            return b"%PDF-guest-memories%"

    monkeypatch.setitem(sys.modules, "weasyprint", types.SimpleNamespace(HTML=FakeHTML))

    pdf_bytes = asyncio.run(
        export_service.generate_guest_memories_sign_pdf(
            couple_names="Ada & Kunle",
            upload_url="https://app.example.com/demo/upload/token",
            qr_png_bytes=b"fake-qr-bytes",
            upload_closes_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        )
    )

    assert pdf_bytes == b"%PDF-guest-memories%"
    assert "Ada &amp; Kunle" in rendered["html"]
    assert "https://app.example.com/demo/upload/token" in rendered["html"]
    assert "Uploads close:" in rendered["html"]
    assert "data:image/png;base64," in rendered["html"]
