import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
            frontend_url="https://app.example.com",
            secret_key="test-secret-key-with-sufficient-length-123456",
        )
        sys.modules["app.core.settings"] = settings_module

    if "app.utils.serializers" not in sys.modules:
        serializers_module = types.ModuleType("app.utils.serializers")
        serializers_module.serialize_mongo_doc = lambda doc: dict(doc)
        sys.modules["app.utils.serializers"] = serializers_module


_install_test_stubs()

import app.services.guest_media_service as guest_media_module  # noqa: E402
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
