import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.api.wedding as wedding_api  # noqa: E402
import app.services.guest_verification_service as guest_verification_module  # noqa: E402
from app.services.guest_verification_service import GuestVerificationService  # noqa: E402


def _build_privacy_service(
    wedding_doc,
):
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.wedding_service = SimpleNamespace(  # type: ignore[assignment]
        get_wedding_by_slug=AsyncMock(return_value=wedding_doc)
    )
    service.otp_service = SimpleNamespace(verify_otp=AsyncMock())  # type: ignore[assignment]
    service._acquire_attempt_lock = AsyncMock(return_value="lock-token")
    service._release_attempt_lock = AsyncMock(return_value=None)
    service._check_rate_limit = AsyncMock(return_value=True)
    service._reset_failed_attempts = AsyncMock(return_value=None)
    service._record_failed_attempt = AsyncMock(return_value=None)
    service._log_security_event = AsyncMock(return_value=None)
    return service


def test_get_wedding_privacy_info_returns_fresh_mode_after_invalidation(monkeypatch):
    cache_store = {}

    async def fake_get(key):
        return cache_store.get(key)

    async def fake_set(key, value, expire=None):
        cache_store[key] = value

    async def fake_delete(key):
        cache_store.pop(key, None)

    find_one = AsyncMock(
        side_effect=[
            {
                "_id": "wed_1",
                "couple_names": "James and Mel",
                "privacy_settings": {"privacy_mode": "private"},
            },
            {
                "_id": "wed_1",
                "couple_names": "James and Mel",
                "privacy_settings": {"privacy_mode": "public"},
            },
        ]
    )

    monkeypatch.setattr(guest_verification_module.cache, "get", fake_get)
    monkeypatch.setattr(guest_verification_module.cache, "set", fake_set)
    monkeypatch.setattr(guest_verification_module.cache, "delete", fake_delete)

    service = GuestVerificationService.__new__(GuestVerificationService)
    service.weddings_collection = SimpleNamespace(find_one=find_one)  # type: ignore[assignment]

    first = asyncio.run(service.get_wedding_privacy_info("james-and-mel"))
    assert first["privacy_mode"] == "private"

    asyncio.run(service.invalidate_wedding_privacy_info("james-and-mel"))

    second = asyncio.run(service.get_wedding_privacy_info("james-and-mel"))
    assert second["privacy_mode"] == "public"


def test_get_wedding_privacy_info_normalizes_guest_media_urls(monkeypatch):
    cache_store = {}

    async def fake_get(key):
        return cache_store.get(key)

    async def fake_set(key, value, expire=None):
        cache_store[key] = value

    wedding_doc = {
        "_id": "wed_media",
        "couple_names": "James and Mel",
        "privacy_settings": {"privacy_mode": "public"},
        "featured_image": "gallery/james-and-mel/hero.jpg",
        "our_story": {
            "text": "It all started with a coffee date.",
            "image_url": "our-story/james-and-mel/story.jpg",
        },
        "wedding_party": [
            {
                "id": "party_1",
                "name": "Alex",
                "image_url": "wedding-party/james-and-mel/alex.jpg",
            },
            {"id": "party_2", "name": "Chris", "image_url": ""},
            {
                "id": "party_3",
                "name": "Sam",
                "image_url": "https://cdn.example.com/custom.jpg",
            },
        ],
    }

    monkeypatch.setattr(guest_verification_module.cache, "get", fake_get)
    monkeypatch.setattr(guest_verification_module.cache, "set", fake_set)

    service = GuestVerificationService.__new__(GuestVerificationService)
    service.weddings_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(return_value=wedding_doc)
    )
    service.gallery_service = SimpleNamespace(  # type: ignore[assignment]
        build_public_url=lambda key: f"https://media.example.com/{key}"
    )

    result = asyncio.run(service.get_wedding_privacy_info("james-and-mel"))

    assert (
        result["featured_image"]
        == "https://media.example.com/gallery/james-and-mel/hero.jpg"
    )
    assert (
        result["our_story"]["image_url"]
        == "https://media.example.com/our-story/james-and-mel/story.jpg"
    )
    assert (
        result["wedding_party"][0]["image_url"]
        == "https://media.example.com/wedding-party/james-and-mel/alex.jpg"
    )
    assert result["wedding_party"][1]["image_url"] == ""
    assert (
        result["wedding_party"][2]["image_url"] == "https://cdn.example.com/custom.jpg"
    )


def test_serialize_wedding_response_normalizes_guest_media_urls():
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.gallery_service = SimpleNamespace(  # type: ignore[assignment]
        build_public_url=lambda key: f"https://media.example.com/{key}"
    )

    result = service._serialize_wedding_response(
        {
            "_id": "wed_serialized",
            "featured_image": "gallery/james-and-mel/hero.jpg",
            "our_story": {"image_url": "our-story/james-and-mel/story.jpg"},
            "wedding_party": [
                {"id": "party_1", "image_url": "wedding-party/james-and-mel/alex.jpg"}
            ],
        }
    )

    assert result["id"] == "wed_serialized"
    assert (
        result["featured_image"]
        == "https://media.example.com/gallery/james-and-mel/hero.jpg"
    )
    assert (
        result["our_story"]["image_url"]
        == "https://media.example.com/our-story/james-and-mel/story.jpg"
    )
    assert (
        result["wedding_party"][0]["image_url"]
        == "https://media.example.com/wedding-party/james-and-mel/alex.jpg"
    )


def test_verify_wedding_page_access_honors_public_password_and_private_modes():
    public_service = _build_privacy_service(
        {
            "_id": "wed_public",
            "slug": "james-and-mel",
            "privacy_settings": {"privacy_mode": "public"},
        }
    )
    public_result = asyncio.run(
        public_service.verify_wedding_page_access("james-and-mel", {})
    )
    assert public_result["access"] is True
    assert public_result["auth_method"] == "public"

    password_service = _build_privacy_service(
        {
            "_id": "wed_password",
            "slug": "james-and-mel",
            "privacy_settings": {
                "privacy_mode": "password",
                "password_protection": "open-sesame",  # pragma: allowlist secret
            },
        }
    )
    password_result = asyncio.run(
        password_service.verify_wedding_page_access(
            "james-and-mel",
            {"password": "open-sesame"},  # pragma: allowlist secret
        )
    )
    assert password_result["access"] is True
    assert password_result["auth_method"] == "password"

    private_service = _build_privacy_service(
        {
            "_id": "wed_private",
            "slug": "james-and-mel",
            "privacy_settings": {"privacy_mode": "private"},
        }
    )
    private_result = asyncio.run(
        private_service.verify_wedding_page_access(
            "james-and-mel", {"email": "guest@example.com"}
        )
    )
    assert private_result["access"] is False
    assert private_result["otp_required"] is True
    assert private_result["contact"] == "guest@example.com"


def test_private_guest_otp_request_accepts_pydantic_none_values():
    email_service = _build_privacy_service(
        {
            "_id": "wed_private",
            "slug": "james-and-mel",
            "privacy_settings": {"privacy_mode": "private"},
        }
    )
    email_result = asyncio.run(
        email_service.verify_wedding_page_access(
            "james-and-mel",
            {
                "token": None,
                "phone": None,
                "email": " guest@example.com ",
                "contact": None,
                "otp_code": None,
            },
        )
    )
    assert email_result["otp_required"] is True
    assert email_result["contact"] == "guest@example.com"
    assert email_result["contact_type"] == "email"

    phone_service = _build_privacy_service(
        {
            "_id": "wed_private",
            "slug": "james-and-mel",
            "privacy_settings": {"privacy_mode": "private"},
        }
    )
    phone_result = asyncio.run(
        phone_service.verify_wedding_page_access(
            "james-and-mel",
            {
                "token": None,
                "phone": " (555) 123-4567 ",
                "email": None,
                "contact": None,
                "otp_code": None,
            },
        )
    )
    assert phone_result["otp_required"] is True
    assert phone_result["contact"] == "(555) 123-4567"
    assert phone_result["contact_type"] == "phone"


def test_update_wedding_admin_invalidates_old_and_new_privacy_slugs(monkeypatch):
    current_user = SimpleNamespace(
        is_team_member=False,
        parent_planner_id=None,
        team_owner_email=None,
        user_data={"_id": "planner_1"},
        email="planner@example.com",
        is_root_admin=False,
    )

    monkeypatch.setattr(wedding_api, "enforce_team_permission", lambda *_args: None)
    monkeypatch.setattr(
        wedding_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        wedding_api.wedding_service,
        "get_wedding",
        AsyncMock(return_value={"slug": "old-slug"}),
    )
    monkeypatch.setattr(
        wedding_api.wedding_service,
        "update_wedding",
        AsyncMock(return_value={"message": "Wedding updated successfully"}),
    )
    monkeypatch.setattr(
        wedding_api,
        "_sync_couple_owner_mirrors",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        wedding_api.sse_manager,
        "broadcast_data_change",
        AsyncMock(return_value=None),
    )

    invalidate_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        wedding_api.guest_verification_service,
        "invalidate_wedding_privacy_info",
        invalidate_mock,
    )

    result = asyncio.run(
        wedding_api.update_wedding_admin(
            "wedding_1",
            {
                "slug": "new-slug",
                "privacy_settings": {"privacy_mode": "public"},
            },
            current_user=current_user,  # type: ignore[arg-type]
        )
    )

    assert result == {"message": "Wedding updated successfully"}
    assert invalidate_mock.await_args_list[0].args == ("old-slug",)
    assert invalidate_mock.await_args_list[1].args == ("new-slug",)
