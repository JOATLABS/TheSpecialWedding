import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_test_stubs() -> None:
    if "boto3" not in sys.modules:
        boto3_module = types.ModuleType("boto3")
        boto3_module.client = lambda *args, **kwargs: object()
        sys.modules["boto3"] = boto3_module

    if "qrcode" not in sys.modules:
        qrcode_module = types.ModuleType("qrcode")
        qrcode_module.make = lambda *args, **kwargs: object()
        sys.modules["qrcode"] = qrcode_module

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


_install_test_stubs()

from app.services.gallery_upload_service import GalleryUploadService


def _build_service() -> GalleryUploadService:
    service = GalleryUploadService.__new__(GalleryUploadService)
    service.bucket_name = "test-bucket"
    service.s3 = object()
    return service


def test_planner_scope_prefers_planner_id_and_avoids_email_leakage():
    assert GalleryUploadService.get_planner_scope_from_wedding(
        {"assigned_planner_id": "507F1F77BCF86CD799439011", "assigned_planner_email": "planner@example.com"}
    ) == "planner-507f1f77bcf86cd799439011"

    email_scope = GalleryUploadService.get_planner_scope_from_wedding(
        {"assigned_planner_email": "planner@example.com"}
    )
    assert email_scope.startswith("planner-")
    assert "@" not in email_scope


def test_parse_wedding_storage_key_supports_legacy_and_planner_scoped_shapes():
    legacy = GalleryUploadService.parse_wedding_storage_key("gallery/jane-john/20260405_photo.jpg")
    scoped = GalleryUploadService.parse_wedding_storage_key(
        "gallery/planner-507f1f77bcf86cd799439011/jane-john/20260405_photo.jpg"
    )

    assert legacy == {
        "folder": "gallery",
        "planner_scope": None,
        "wedding_slug": "jane-john",
        "remainder": "20260405_photo.jpg",
    }
    assert scoped == {
        "folder": "gallery",
        "planner_scope": "planner-507f1f77bcf86cd799439011",
        "wedding_slug": "jane-john",
        "remainder": "20260405_photo.jpg",
    }


def test_list_wedding_files_deduplicates_legacy_copy_after_scoped_migration():
    service = _build_service()
    planner_scope = "planner-507f1f77bcf86cd799439011"
    legacy_prefix = service.build_wedding_storage_prefix("gallery", "jane-john")
    scoped_prefix = service.build_wedding_storage_prefix("gallery", "jane-john", planner_scope)

    files_by_prefix = {
        scoped_prefix: [
            {"key": f"{scoped_prefix}20260405_a.jpg", "url": "https://cdn.example/scoped-a", "size": 1},
        ],
        legacy_prefix: [
            {"key": f"{legacy_prefix}20260405_a.jpg", "url": "https://cdn.example/legacy-a", "size": 1},
            {"key": f"{legacy_prefix}20260405_b.jpg", "url": "https://cdn.example/legacy-b", "size": 1},
        ],
    }

    service.list_uploaded_files = lambda prefix: files_by_prefix[prefix]

    merged = service.list_wedding_files("gallery", "jane-john", planner_scope)

    assert [entry["key"] for entry in merged] == [
        f"{legacy_prefix}20260405_b.jpg",
        f"{scoped_prefix}20260405_a.jpg",
    ]


def test_list_wedding_files_page_falls_back_to_legacy_when_scoped_prefix_is_empty():
    service = _build_service()
    planner_scope = "planner-507f1f77bcf86cd799439011"
    legacy_prefix = service.build_wedding_storage_prefix("gallery", "jane-john")
    scoped_prefix = service.build_wedding_storage_prefix("gallery", "jane-john", planner_scope)

    def fake_page(prefix: str, limit: int, cursor: str | None = None):
        if prefix == scoped_prefix:
            return {"items": [], "next_cursor": None, "has_more": False}
        assert prefix == legacy_prefix
        return {
            "items": [
                {"key": f"{legacy_prefix}20260405_a.jpg", "url": "https://cdn.example/legacy-a", "size": 1},
                {"key": f"{legacy_prefix}20260405_b.jpg", "url": "https://cdn.example/legacy-b", "size": 1},
            ],
            "next_cursor": "legacy-token",
            "has_more": True,
        }

    service.list_uploaded_files_page = fake_page

    page = service.list_wedding_files_page(
        folder="gallery",
        wedding_slug="jane-john",
        planner_scope=planner_scope,
        limit=2,
        cursor=None,
    )

    assert [entry["key"] for entry in page["items"]] == [
        f"{legacy_prefix}20260405_a.jpg",
        f"{legacy_prefix}20260405_b.jpg",
    ]
    assert page["next_cursor"] == "legacy::legacy-token"
    assert page["has_more"] is True
