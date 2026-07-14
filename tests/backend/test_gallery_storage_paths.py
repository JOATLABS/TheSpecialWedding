import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

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

        class BotoCoreError(Exception):
            pass

        botocore_exceptions.BotoCoreError = BotoCoreError
        botocore_exceptions.ClientError = ClientError
        sys.modules["botocore.exceptions"] = botocore_exceptions


_install_test_stubs()

from app.services.gallery_media_service import GalleryUploadService  # noqa: E402
from app.api import gallery_admin as gallery_admin_api  # noqa: E402
from app.api import gallery_public as gallery_public_api  # noqa: E402
from app.constants.marketing_capture_media import (  # noqa: E402
    MARKETING_CAPTURE_GALLERY_ITEMS,
    allow_local_demo_gallery_fallback,
    gallery_fallback_items_for_wedding,
)
from app.constants.seed_sources import (  # noqa: E402
    MARKETING_CAPTURE_SEED_SCOPE,
    MARKETING_CAPTURE_SEED_SOURCE,
)


def _build_service() -> GalleryUploadService:
    service = GalleryUploadService.__new__(GalleryUploadService)
    service.bucket_name = "test-bucket"
    service.storage = object()
    return service


def _planner_user() -> SimpleNamespace:
    return SimpleNamespace(
        is_root_admin=False,
        is_wedding_planner=True,
        is_team_member=False,
        team_permissions={},
    )


def _team_member(*, manage_gallery: bool) -> SimpleNamespace:
    return SimpleNamespace(
        is_root_admin=False,
        is_wedding_planner=False,
        is_team_member=True,
        team_permissions={"manage_gallery": manage_gallery},
    )


def _marketing_capture_wedding(
    *,
    wedding_id: str = "wedding_marketing_capture_sofia_daniel",
    slug: str = "sofia-and-daniel",
) -> dict[str, str]:
    return {
        "_id": wedding_id,
        "slug": slug,
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }


def test_local_gallery_fallback_accepts_only_the_primary_capture_wedding(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    primary = _marketing_capture_wedding()

    assert allow_local_demo_gallery_fallback(primary) is True
    assert (
        gallery_fallback_items_for_wedding(primary) == MARKETING_CAPTURE_GALLERY_ITEMS
    )


@pytest.mark.parametrize(
    ("wedding_id", "slug"),
    [
        ("wedding_marketing_capture_avery_morgan", "avery-and-morgan"),
        ("wedding_marketing_capture_not_sofia_daniel", "sofia-and-daniel"),
        ("wedding_marketing_capture_sofia_daniel", "not-sofia-and-daniel"),
    ],
)
def test_local_gallery_fallback_rejects_secondary_or_mismatched_wedding_identity(
    monkeypatch,
    wedding_id,
    slug,
):
    monkeypatch.setenv("ENVIRONMENT", "local")
    wedding = _marketing_capture_wedding(wedding_id=wedding_id, slug=slug)

    assert allow_local_demo_gallery_fallback(wedding) is False
    assert gallery_fallback_items_for_wedding(wedding) == []


def test_gallery_fallback_fails_closed_when_environment_is_not_declared(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    primary = _marketing_capture_wedding()

    assert allow_local_demo_gallery_fallback(primary) is False
    assert gallery_fallback_items_for_wedding(primary) == []


def test_planner_scope_prefers_planner_id_and_avoids_email_leakage():
    assert (
        GalleryUploadService.get_planner_scope_from_wedding(
            {
                "assigned_planner_id": "507F1F77BCF86CD799439011",
                "assigned_planner_email": "planner@example.com",
            }
        )
        == "planner-507f1f77bcf86cd799439011"
    )

    email_scope = GalleryUploadService.get_planner_scope_from_wedding(
        {"assigned_planner_email": "planner@example.com"}
    )
    assert email_scope.startswith("planner-")
    assert "@" not in email_scope


def test_parse_wedding_storage_key_supports_legacy_and_planner_scoped_shapes():
    legacy = GalleryUploadService.parse_wedding_storage_key(
        "gallery/jane-john/20260405_photo.jpg"
    )
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
    scoped_prefix = service.build_wedding_storage_prefix(
        "gallery", "jane-john", planner_scope
    )

    files_by_prefix = {
        scoped_prefix: [
            {
                "key": f"{scoped_prefix}20260405_a.jpg",
                "url": "https://cdn.example/scoped-a",
                "size": 1,
            },
        ],
        legacy_prefix: [
            {
                "key": f"{legacy_prefix}20260405_a.jpg",
                "url": "https://cdn.example/legacy-a",
                "size": 1,
            },
            {
                "key": f"{legacy_prefix}20260405_b.jpg",
                "url": "https://cdn.example/legacy-b",
                "size": 1,
            },
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
    scoped_prefix = service.build_wedding_storage_prefix(
        "gallery", "jane-john", planner_scope
    )

    def fake_page(prefix: str, limit: int, cursor: str | None = None):
        if prefix == scoped_prefix:
            return {"items": [], "next_cursor": None, "has_more": False}
        assert prefix == legacy_prefix
        return {
            "items": [
                {
                    "key": f"{legacy_prefix}20260405_a.jpg",
                    "url": "https://cdn.example/legacy-a",
                    "size": 1,
                },
                {
                    "key": f"{legacy_prefix}20260405_b.jpg",
                    "url": "https://cdn.example/legacy-b",
                    "size": 1,
                },
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


def test_marketing_capture_gallery_uses_seeded_fallback_when_storage_is_empty(
    monkeypatch,
):
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "slug": "sofia-and-daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setattr(
        gallery_public_api,
        "wedding_service",
        SimpleNamespace(get_wedding_by_slug=AsyncMock(return_value=wedding)),
    )
    monkeypatch.setattr(
        gallery_public_api,
        "gallery_service",
        SimpleNamespace(
            get_planner_scope_from_wedding=lambda _wedding: "planner-capture",
            list_wedding_files_page=lambda **_kwargs: {
                "items": [],
                "next_cursor": None,
                "has_more": False,
            },
        ),
    )

    page = asyncio.run(
        gallery_public_api._list_gallery_page_for_wedding(
            "sofia-and-daniel",
            limit=2,
            cursor=None,
        )
    )

    assert page == {
        "items": MARKETING_CAPTURE_GALLERY_ITEMS[:2],
        "next_cursor": None,
        "has_more": False,
    }


@pytest.mark.parametrize("seed_scope", [None, "another-demo"])
def test_public_gallery_does_not_bypass_storage_for_wrong_or_missing_seed_scope(
    monkeypatch,
    seed_scope,
):
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "slug": "sofia-and-daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": seed_scope,
    }
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setattr(
        gallery_public_api,
        "wedding_service",
        SimpleNamespace(get_wedding_by_slug=AsyncMock(return_value=wedding)),
    )
    monkeypatch.setattr(
        gallery_public_api,
        "gallery_service",
        SimpleNamespace(
            get_planner_scope_from_wedding=lambda _wedding: "planner-capture",
            list_wedding_files_page=lambda **_kwargs: {
                "items": [],
                "next_cursor": None,
                "has_more": False,
            },
        ),
    )

    page = asyncio.run(
        gallery_public_api._list_gallery_page_for_wedding(
            "sofia-and-daniel",
            limit=2,
            cursor=None,
        )
    )

    assert page == {"items": [], "next_cursor": None, "has_more": False}


def test_marketing_capture_gallery_keys_look_like_real_wedding_media():
    for item in MARKETING_CAPTURE_GALLERY_ITEMS:
        assert item["key"].startswith("gallery/sofia-and-daniel/20270125-")
        assert item["key"].endswith(".webp")
        assert item["url"].endswith(".webp")
        assert item["content_type"] == "image/webp"
        assert item["display_name"]
        assert item["alt"]
        assert (
            item["credit"]
            == "Fictional capture fixture generated for The Special Wedding"
        )
        assert "marketing-capture" not in item["key"]
        assert "test" not in item["key"]


def test_admin_gallery_list_rejects_team_member_without_manage_gallery(monkeypatch):
    wedding_lookup = AsyncMock(return_value={"_id": "wedding-1", "slug": "demo"})
    parse_prefix = Mock(
        return_value={
            "folder": "gallery",
            "wedding_slug": "demo",
        }
    )
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        wedding_lookup,
    )
    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_prefix=parse_prefix,
            get_planner_scope_from_wedding=lambda _wedding: "planner-owner",
            list_wedding_files=lambda **_kwargs: [],
        ),
    )

    with pytest.raises(gallery_admin_api.HTTPException) as exc_info:
        asyncio.run(
            gallery_admin_api.list_gallery_files(
                prefix="gallery/demo/",
                current_user=_team_member(manage_gallery=False),
            )
        )

    assert exc_info.value.status_code == 403
    assert "manage gallery" in exc_info.value.detail
    parse_prefix.assert_not_called()
    wedding_lookup.assert_not_awaited()


def test_admin_gallery_list_allows_team_member_with_manage_gallery(monkeypatch):
    wedding = {"_id": "wedding-1", "slug": "demo"}
    wedding_lookup = AsyncMock(return_value=wedding)
    expected_files = [
        {"key": "gallery/demo/photo.webp", "url": "https://media.example/photo.webp"}
    ]
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        wedding_lookup,
    )
    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_prefix=lambda _prefix: {
                "folder": "gallery",
                "wedding_slug": "demo",
            },
            get_planner_scope_from_wedding=lambda _wedding: "planner-owner",
            list_wedding_files=lambda **_kwargs: expected_files,
        ),
    )

    files = asyncio.run(
        gallery_admin_api.list_gallery_files(
            prefix="gallery/demo/",
            current_user=_team_member(manage_gallery=True),
        )
    )

    assert files == expected_files
    wedding_lookup.assert_awaited_once()


def test_admin_gallery_file_url_rejects_team_member_without_manage_gallery(monkeypatch):
    wedding_lookup = AsyncMock(return_value={"_id": "wedding-1", "slug": "demo"})
    parse_key = Mock(return_value={"wedding_slug": "demo"})
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        wedding_lookup,
    )
    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_key=parse_key,
            get_file_url=lambda _key: {"file_url": "https://signed.example/photo"},
        ),
    )

    with pytest.raises(gallery_admin_api.HTTPException) as exc_info:
        asyncio.run(
            gallery_admin_api.get_file_url(
                key="gallery/demo/photo.webp",
                current_user=_team_member(manage_gallery=False),
            )
        )

    assert exc_info.value.status_code == 403
    assert "manage gallery" in exc_info.value.detail
    parse_key.assert_not_called()
    wedding_lookup.assert_not_awaited()


def test_admin_gallery_file_url_allows_team_member_with_manage_gallery(monkeypatch):
    wedding = {"_id": "wedding-1", "slug": "demo"}
    wedding_lookup = AsyncMock(return_value=wedding)
    expected = {"file_url": "https://signed.example/photo"}
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        wedding_lookup,
    )
    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_key=lambda _key: {"wedding_slug": "demo"},
            get_file_url=lambda _key: expected,
        ),
    )

    result = asyncio.run(
        gallery_admin_api.get_file_url(
            key="gallery/demo/photo.webp",
            current_user=_team_member(manage_gallery=True),
        )
    )

    assert result == expected
    wedding_lookup.assert_awaited_once()


def test_marketing_capture_admin_gallery_uses_seeded_fallback_when_storage_is_empty(
    monkeypatch,
):
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "slug": "sofia-and-daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        AsyncMock(return_value=wedding),
    )
    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_prefix=lambda _prefix: {
                "folder": "gallery",
                "wedding_slug": "sofia-and-daniel",
            },
            get_planner_scope_from_wedding=lambda _wedding: "planner-capture",
            list_wedding_files=lambda **_kwargs: [],
        ),
    )

    files = asyncio.run(
        gallery_admin_api.list_gallery_files(
            prefix="gallery/sofia-and-daniel/",
            current_user=_planner_user(),
        )
    )

    assert files == MARKETING_CAPTURE_GALLERY_ITEMS


@pytest.mark.parametrize("seed_scope", [None, "another-demo"])
def test_admin_gallery_does_not_bypass_storage_for_wrong_or_missing_seed_scope(
    monkeypatch,
    seed_scope,
):
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "slug": "sofia-and-daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": seed_scope,
    }
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        AsyncMock(return_value=wedding),
    )
    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_prefix=lambda _prefix: {
                "folder": "gallery",
                "wedding_slug": "sofia-and-daniel",
            },
            get_planner_scope_from_wedding=lambda _wedding: "planner-capture",
            list_wedding_files=lambda **_kwargs: [],
        ),
    )

    files = asyncio.run(
        gallery_admin_api.list_gallery_files(
            prefix="gallery/sofia-and-daniel/",
            current_user=_planner_user(),
        )
    )

    assert files == []


def test_marketing_capture_admin_gallery_uses_seeded_fallback_when_storage_is_down(
    monkeypatch,
):
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "slug": "sofia-and-daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        AsyncMock(return_value=wedding),
    )

    def unavailable_storage(**_kwargs):
        raise gallery_admin_api.HTTPException(
            status_code=503, detail="storage unavailable"
        )

    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_prefix=lambda _prefix: {
                "folder": "gallery",
                "wedding_slug": "sofia-and-daniel",
            },
            get_planner_scope_from_wedding=lambda _wedding: "planner-capture",
            list_wedding_files=unavailable_storage,
        ),
    )

    files = asyncio.run(
        gallery_admin_api.list_gallery_files(
            prefix="gallery/sofia-and-daniel/",
            current_user=_planner_user(),
        )
    )

    assert files == MARKETING_CAPTURE_GALLERY_ITEMS


@pytest.mark.parametrize("folder", ["our-story", "wedding-party"])
def test_marketing_capture_admin_optional_folders_are_empty_when_storage_is_down(
    monkeypatch,
    folder,
):
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "slug": "sofia-and-daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        AsyncMock(return_value=wedding),
    )

    def unavailable_storage(**_kwargs):
        raise gallery_admin_api.HTTPException(
            status_code=503, detail="storage unavailable"
        )

    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_prefix=lambda _prefix: {
                "folder": folder,
                "wedding_slug": "sofia-and-daniel",
            },
            get_planner_scope_from_wedding=lambda _wedding: "planner-capture",
            list_wedding_files=unavailable_storage,
        ),
    )

    files = asyncio.run(
        gallery_admin_api.list_gallery_files(
            prefix=f"{folder}/sofia-and-daniel/",
            current_user=_planner_user(),
        )
    )

    assert files == []


@pytest.mark.parametrize(
    ("environment", "seed_scope", "folder"),
    [
        ("production", MARKETING_CAPTURE_SEED_SCOPE, "our-story"),
        ("local", "another-demo", "our-story"),
        ("local", MARKETING_CAPTURE_SEED_SCOPE, "private-folder"),
    ],
)
def test_admin_optional_folder_storage_failure_stays_fail_closed_outside_capture_scope(
    monkeypatch,
    environment,
    seed_scope,
    folder,
):
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "slug": "sofia-and-daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": seed_scope,
    }
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        AsyncMock(return_value=wedding),
    )

    def unavailable_storage(**_kwargs):
        raise gallery_admin_api.HTTPException(
            status_code=503, detail="storage unavailable"
        )

    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_prefix=lambda _prefix: {
                "folder": folder,
                "wedding_slug": "sofia-and-daniel",
            },
            get_planner_scope_from_wedding=lambda _wedding: "planner-capture",
            list_wedding_files=unavailable_storage,
        ),
    )

    with pytest.raises(gallery_admin_api.HTTPException) as exc_info:
        asyncio.run(
            gallery_admin_api.list_gallery_files(
                prefix=f"{folder}/sofia-and-daniel/",
                current_user=_planner_user(),
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "storage unavailable"


def test_marketing_capture_admin_gallery_fallback_never_bypasses_wedding_access(
    monkeypatch,
):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        AsyncMock(
            side_effect=gallery_admin_api.HTTPException(
                status_code=403,
                detail="Access denied to this wedding's gallery",
            )
        ),
    )

    def storage_must_not_run(**_kwargs):
        raise AssertionError("storage must not run before wedding access succeeds")

    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_prefix=lambda _prefix: {
                "folder": "our-story",
                "wedding_slug": "sofia-and-daniel",
            },
            get_planner_scope_from_wedding=lambda _wedding: "planner-capture",
            list_wedding_files=storage_must_not_run,
        ),
    )

    with pytest.raises(gallery_admin_api.HTTPException) as exc_info:
        asyncio.run(
            gallery_admin_api.list_gallery_files(
                prefix="our-story/sofia-and-daniel/",
                current_user=_planner_user(),
            )
        )

    assert exc_info.value.status_code == 403


def test_marketing_capture_admin_gallery_does_not_duplicate_fallback_across_folders(
    monkeypatch,
):
    wedding = {
        "_id": "wedding_marketing_capture_sofia_daniel",
        "slug": "sofia-and-daniel",
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setattr(
        gallery_admin_api,
        "get_accessible_wedding_by_slug",
        AsyncMock(return_value=wedding),
    )
    monkeypatch.setattr(
        gallery_admin_api,
        "gallery_service",
        SimpleNamespace(
            parse_wedding_storage_prefix=lambda _prefix: {
                "folder": "our-story",
                "wedding_slug": "sofia-and-daniel",
            },
            get_planner_scope_from_wedding=lambda _wedding: "planner-capture",
            list_wedding_files=lambda **_kwargs: [],
        ),
    )

    files = asyncio.run(
        gallery_admin_api.list_gallery_files(
            prefix="our-story/sofia-and-daniel/",
            current_user=_planner_user(),
        )
    )

    assert files == []
