import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from fastapi import HTTPException

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.api.guest_verification as guest_verification_api  # noqa: E402
import app.api.wedding as wedding_api  # noqa: E402
import app.services.guest_verification_service as guest_verification_module  # noqa: E402
from app.models.rsvp import RSVPModel  # noqa: E402
from app.services.rsvp_service import RSVPService  # noqa: E402
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


def _assert_guest_internal_fields_absent(payload):
    forbidden_fields = {
        "_id",
        "assigned_planner_email",
        "assigned_planner_id",
        "confirmed_by_admin",
        "created_at",
        "email_opt_in_date",
        "group_id",
        "internal_note",
        "must_sit_apart",
        "must_sit_with",
        "password_protection",
        "phone_status",
        "planner_note",
        "seed_scope",
        "seed_source",
        "sms_opt_in_date",
        "table_id",
        "token",
        "total_budget",
        "updated_at",
        "wedding_id",
    }

    def walk(value):
        if isinstance(value, dict):
            assert forbidden_fields.isdisjoint(value)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(payload)


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


def test_get_wedding_privacy_info_rejects_pre_allowlist_cache_payloads(monkeypatch):
    legacy_cached_payload = {
        "id": "wed_legacy_cache",
        "couple_names": "Jordan & Alex",
        "privacy_mode": "public",
        "assigned_planner_email": "planner@example.com",
        "events": [{"event_notes": [{"text": "internal"}]}],
    }
    written_cache_entries = []

    async def fake_get(key):
        return legacy_cached_payload

    async def fake_set(key, value, expire=None):
        written_cache_entries.append(value)

    monkeypatch.setattr(guest_verification_module.cache, "get", fake_get)
    monkeypatch.setattr(guest_verification_module.cache, "set", fake_set)

    service = GuestVerificationService.__new__(GuestVerificationService)
    service.weddings_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(
            return_value={
                "_id": "wed_current",
                "couple_names": "Jordan & Alex",
                "privacy_settings": {"privacy_mode": "private"},
            }
        )
    )

    result = asyncio.run(service.get_wedding_privacy_info("jordan-and-alex"))

    assert result["id"] == "wed_current"
    assert result["privacy_mode"] == "private"
    assert "assigned_planner_email" not in result
    service.weddings_collection.find_one.assert_awaited_once()  # type: ignore[attr-defined]
    assert written_cache_entries == [
        {
            "schema_version": 1,
            "response": result,
        }
    ]


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
            "privacy_settings": {"privacy_mode": "public"},
            "featured_image": "gallery/james-and-mel/hero.jpg",
            "our_story": {"image_url": "our-story/james-and-mel/story.jpg"},
            "wedding_party": [
                {"id": "party_1", "image_url": "wedding-party/james-and-mel/alex.jpg"}
            ],
        }
    )

    assert result["id"] == "wed_serialized"
    assert result["privacy_mode"] == "public"
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


def test_serialize_wedding_response_uses_nested_privacy_mode_as_authoritative():
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.gallery_service = SimpleNamespace(  # type: ignore[assignment]
        build_public_url=lambda key: f"https://media.example.com/{key}"
    )

    result = service._serialize_wedding_response(
        {
            "_id": "wed_privacy_source",
            "privacy_mode": "private",
            "privacy_settings": {"privacy_mode": "public"},
        }
    )

    assert result["privacy_mode"] == "public"


def test_serialize_wedding_response_fails_closed_for_partial_nested_privacy_settings():
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.gallery_service = SimpleNamespace(  # type: ignore[assignment]
        build_public_url=lambda key: f"https://media.example.com/{key}"
    )

    for nested_settings in ({}, {"privacy_mode": "unsupported"}):
        result = service._serialize_wedding_response(
            {
                "_id": "wed_partial_privacy",
                "privacy_mode": "public",
                "privacy_settings": nested_settings,
            }
        )

        assert result["privacy_mode"] == "private"


def test_serialize_wedding_response_preserves_repository_static_media_paths():
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.gallery_service = SimpleNamespace(  # type: ignore[assignment]
        build_public_url=lambda key: f"https://media.example.com/{key}"
    )

    result = service._serialize_wedding_response(
        {
            "_id": "wed_static_media",
            "privacy_settings": {"privacy_mode": "public"},
            "featured_image": "/demo-gallery/sofia-daniel-terrace.webp",
            "our_story": {"image_url": "/demo-gallery/sofia-daniel-terrace.webp"},
            "wedding_party": [
                {
                    "id": "party_1",
                    "image_url": "/demo-gallery/sofia-daniel-ceremony.webp",
                }
            ],
        }
    )

    assert result["featured_image"] == "/demo-gallery/sofia-daniel-terrace.webp"
    assert result["our_story"]["image_url"] == "/demo-gallery/sofia-daniel-terrace.webp"
    assert (
        result["wedding_party"][0]["image_url"]
        == "/demo-gallery/sofia-daniel-ceremony.webp"
    )


def test_serialize_wedding_response_rejects_unapproved_repository_static_media_paths():
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.gallery_service = SimpleNamespace(  # type: ignore[assignment]
        build_public_url=lambda key: f"https://media.example.com/{key}"
    )

    result = service._serialize_wedding_response(
        {
            "_id": "wed_unsafe_static_media",
            "privacy_settings": {"privacy_mode": "public"},
            "featured_image": "/demo-gallery/../api/private",
            "our_story": {"image_url": "/demo-gallery/unapproved.svg"},
            "wedding_party": [
                {
                    "id": "party_1",
                    "image_url": "/demo-gallery/%2e%2e/api/private",
                }
            ],
        }
    )

    assert result["featured_image"] is None
    assert result["our_story"]["image_url"] is None
    assert result["wedding_party"][0]["image_url"] is None


def test_serialize_wedding_response_exposes_only_the_public_page_contract():
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.gallery_service = SimpleNamespace(  # type: ignore[assignment]
        build_public_url=lambda key: f"https://media.example.com/{key}"
    )

    result = service._serialize_wedding_response(
        {
            "_id": "wed_public_contract",
            "slug": "jordan-and-alex",
            "couple_names": "Jordan & Alex",
            "date": "2027-04-03",
            "timezone": "America/Chicago",
            "events": [
                {
                    "type": "ceremony",
                    "custom_type_label": "Garden ceremony",
                    "date": "2027-04-03",
                    "details": {
                        "venue_name": "The Glasshouse",
                        "location": "Chicago, IL",
                        "time": "4:00 PM",
                        "attire": "Garden formal",
                        "timezone": "America/Chicago",
                        "planner_arrival_time": "11:30 AM",
                    },
                    "order_of_events": [
                        {
                            "title": "Private run of show",
                            "notes": [{"text": "Internal planner instruction"}],
                        }
                    ],
                    "event_notes": [{"text": "Hidden couple/planner thread"}],
                    "planner_notes": "Internal event note",
                }
            ],
            "rsvp_config": {
                "greeting": "Join us in celebrating.",
                "help_text": "Use the help button if you need us.",
                "help_button_label": "Get Help",
                "hide_phone_numbers": True,
                "phone_numbers": ["(312) 555-0100"],
                "contact_email": "planner@example.com",
                "deadline": "2027-03-01",
            },
            "registries": [
                {
                    "name": "Home Fund",
                    "url": "https://registry.example.com/home",
                    "color": "bg-stone-700",
                    "internal_id": "registry_internal",
                }
            ],
            "faqs": [
                {
                    "question": "What should I wear?",
                    "answer": "Garden formal attire.",
                    "link_url": "https://example.com/attire",
                    "link_label": "View guide",
                    "planner_note": "Do not publish",
                }
            ],
            "theme_config": {
                "primary_color": "#123456",
                "secondary_color": "#abcdef",
                "accent_color": "#fedcba",
                "background_style": "image",
                "font_style": "elegant",
                "admin_preview_token": "theme-secret",
            },
            "featured_image": "gallery/jordan-and-alex/hero.jpg",
            "our_story": {
                "text": "We met through mutual friends.",
                "image_url": "our-story/jordan-and-alex/story.jpg",
                "image_shape": "circle",
                "draft_notes": "Rewrite before launch",
            },
            "venue": {
                "name": "The Glasshouse",
                "address": "Chicago, IL",
                "vendor_contact_email": "venue@example.com",
            },
            "wedding_party": [
                {
                    "id": "party_1",
                    "name": "Taylor",
                    "role": "maid_of_honor",
                    "side": "bride",
                    "display_order": 0,
                    "image_url": "wedding-party/jordan-and-alex/taylor.jpg",
                    "linked_guest_id": "guest_123",
                    "linked_guest_email": "taylor@example.com",
                }
            ],
            "privacy_settings": {
                "privacy_mode": "public",
                "password_protection": "do-not-return",
            },
            "assigned_planner_id": "planner_123",
            "assigned_planner_email": "planner@example.com",
            "couple_portal_email": "couple@example.com",
            "total_budget": 120000,
            "guest_media": {"upload_token_hash": "do-not-return"},
            "seed_source": "internal-seed-tag",
            "unrecognized_future_field": "must fail closed",
        }
    )

    assert result == {
        "id": "wed_public_contract",
        "slug": "jordan-and-alex",
        "couple_names": "Jordan & Alex",
        "date": "2027-04-03",
        "timezone": "America/Chicago",
        "events": [
            {
                "type": "ceremony",
                "custom_type_label": "Garden ceremony",
                "date": "2027-04-03",
                "details": {
                    "venue_name": "The Glasshouse",
                    "location": "Chicago, IL",
                    "time": "4:00 PM",
                    "attire": "Garden formal",
                    "timezone": "America/Chicago",
                },
            }
        ],
        "rsvp_config": {
            "greeting": "Join us in celebrating.",
            "help_text": "Use the help button if you need us.",
            "help_button_label": "Get Help",
            "hide_phone_numbers": True,
        },
        "registries": [
            {
                "name": "Home Fund",
                "url": "https://registry.example.com/home",
                "color": "bg-stone-700",
            }
        ],
        "faqs": [
            {
                "question": "What should I wear?",
                "answer": "Garden formal attire.",
                "link_url": "https://example.com/attire",
                "link_label": "View guide",
            }
        ],
        "theme_config": {
            "primary_color": "#123456",
            "secondary_color": "#abcdef",
            "accent_color": "#fedcba",
            "background_style": "image",
            "font_style": "elegant",
        },
        "featured_image": "https://media.example.com/gallery/jordan-and-alex/hero.jpg",
        "our_story": {
            "text": "We met through mutual friends.",
            "image_url": "https://media.example.com/our-story/jordan-and-alex/story.jpg",
            "image_shape": "circle",
        },
        "venue": {"name": "The Glasshouse", "address": "Chicago, IL"},
        "wedding_party": [
            {
                "id": "party_1",
                "name": "Taylor",
                "role": "maid_of_honor",
                "side": "bride",
                "display_order": 0,
                "image_url": "https://media.example.com/wedding-party/jordan-and-alex/taylor.jpg",
            }
        ],
        "privacy_mode": "public",
    }


def test_serialize_wedding_response_only_exposes_rsvp_phones_when_explicitly_visible():
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.gallery_service = SimpleNamespace(  # type: ignore[assignment]
        build_public_url=lambda key: f"https://media.example.com/{key}"
    )

    visible = service._serialize_wedding_response(
        {
            "_id": "wed_visible_help",
            "privacy_settings": {"privacy_mode": "public"},
            "rsvp_config": {
                "hide_phone_numbers": False,
                "phone_numbers": [" (312) 555-0100 ", "", 12345],
            },
        }
    )
    ambiguous = service._serialize_wedding_response(
        {
            "_id": "wed_ambiguous_help",
            "privacy_settings": {"privacy_mode": "public"},
            "rsvp_config": {
                "hide_phone_numbers": "false",
                "phone_numbers": ["(312) 555-0199"],
            },
        }
    )

    assert visible["rsvp_config"] == {
        "hide_phone_numbers": False,
        "phone_numbers": ["(312) 555-0100"],
    }
    assert ambiguous["rsvp_config"] == {"hide_phone_numbers": True}


def test_public_privacy_info_uses_the_same_nested_guest_safe_projection(monkeypatch):
    cache_store = {}

    async def fake_get(key):
        return cache_store.get(key)

    async def fake_set(key, value, expire=None):
        cache_store[key] = value

    wedding_doc = {
        "_id": "wed_public_bootstrap",
        "couple_names": "Jordan & Alex",
        "date": "2027-04-03",
        "privacy_settings": {
            "privacy_mode": "public",
            "password_protection": "must-not-return",
        },
        "events": [
            {
                "type": "ceremony",
                "date": "2027-04-03",
                "details": {"time": "4:00 PM", "planner_call_time": "11:00 AM"},
                "event_notes": [{"text": "internal"}],
            }
        ],
        "rsvp_config": {
            "hide_phone_numbers": True,
            "phone_numbers": ["(312) 555-0100"],
            "contact_email": "planner@example.com",
        },
        "wedding_party": [
            {
                "id": "party_1",
                "name": "Taylor",
                "role": "maid_of_honor",
                "side": "bride",
                "linked_guest_email": "taylor@example.com",
            }
        ],
    }

    monkeypatch.setattr(guest_verification_module.cache, "get", fake_get)
    monkeypatch.setattr(guest_verification_module.cache, "set", fake_set)

    service = GuestVerificationService.__new__(GuestVerificationService)
    service.weddings_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(return_value=wedding_doc)
    )

    result = asyncio.run(service.get_wedding_privacy_info("jordan-and-alex"))

    assert result["events"] == [
        {
            "type": "ceremony",
            "date": "2027-04-03",
            "details": {"time": "4:00 PM"},
        }
    ]
    assert result["rsvp_config"] == {"hide_phone_numbers": True}
    assert result["wedding_party"] == [
        {
            "id": "party_1",
            "name": "Taylor",
            "role": "maid_of_honor",
            "side": "bride",
        }
    ]


def test_private_privacy_info_exposes_only_the_authentication_bootstrap(monkeypatch):
    cache_store = {}

    async def fake_get(key):
        return cache_store.get(key)

    async def fake_set(key, value, expire=None):
        cache_store[key] = value

    monkeypatch.setattr(guest_verification_module.cache, "get", fake_get)
    monkeypatch.setattr(guest_verification_module.cache, "set", fake_set)

    service = GuestVerificationService.__new__(GuestVerificationService)
    service.weddings_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(
            return_value={
                "_id": "wed_private_bootstrap",
                "couple_names": "Jordan & Alex",
                "date": "2027-04-03",
                "privacy_settings": {"privacy_mode": "private"},
                "featured_image": "gallery/jordan-and-alex/hero.jpg",
                "theme_config": {"primary_color": "#123456"},
                "events": [
                    {
                        "type": "ceremony",
                        "date": "2027-04-03",
                        "details": {"location": "Private venue address"},
                    }
                ],
                "rsvp_config": {
                    "greeting": "Private greeting",
                    "hide_phone_numbers": False,
                    "phone_numbers": ["(312) 555-0100"],
                },
                "registries": [
                    {"name": "Private registry", "url": "https://example.com"}
                ],
                "faqs": [{"question": "Private FAQ", "answer": "Private answer"}],
                "our_story": {"text": "Private story"},
                "venue": "Private venue",
                "wedding_party": [
                    {
                        "id": "party_1",
                        "name": "Private party member",
                        "role": "best_man",
                        "side": "groom",
                    }
                ],
            }
        )
    )

    result = asyncio.run(service.get_wedding_privacy_info("jordan-and-alex"))

    assert result == {
        "id": "wed_private_bootstrap",
        "couple_names": "Jordan & Alex",
        "privacy_mode": "private",
        "requires_password": False,
        "requires_guest_verification": True,
        "verification_requirements": {
            "otp_enabled": True,
            "supports_phone": True,
            "supports_email": True,
        },
    }


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


def test_guest_serialization_is_an_explicit_public_contract():
    guest_id = ObjectId("507f1f77bcf86cd799439011")
    result = GuestVerificationService._serialize_guest_response(
        {
            "_id": guest_id,
            "wedding_id": "wedding_1",
            "name": "Jordan Guest",
            "phone": "+13125550101",
            "email": "jordan@example.com",
            "plus_one_allowed": True,
            "number_of_plus_ones_allowed": 1,
            "sms_opt_in": True,
            "email_opt_in": False,
            "token": "invite-secret",
            "group_id": "family",
            "table_id": "table_1",
            "must_sit_with": ["guest_2"],
            "internal_note": "planner only",
            "seed_source": "marketing_capture",
        }
    )

    assert result == {
        "id": str(guest_id),
        "name": "Jordan Guest",
        "phone": "+13125550101",
        "email": "jordan@example.com",
        "plus_one_allowed": True,
        "number_of_plus_ones_allowed": 1,
        "sms_opt_in": True,
        "email_opt_in": False,
    }
    _assert_guest_internal_fields_absent(result)


def test_rsvp_and_plus_one_reads_are_wedding_scoped_and_fail_closed():
    rsvp_find_one = AsyncMock(
        return_value={
            "_id": "rsvp_internal",
            "guest_id": "guest_1",
            "wedding_id": "wedding_1",
            "submitted_at": "2027-03-01T12:00:00Z",
            "attending": ["ceremony", {"internal": "bad"}, 42],
            "dietary": "Vegetarian",
            "confirmed_by_admin": True,
            "seed_scope": "capture_workspace",
        }
    )
    plus_one_cursor = SimpleNamespace(
        to_list=AsyncMock(
            return_value=[
                {
                    "_id": "plus_one_internal",
                    "guest_id": "guest_1",
                    "wedding_id": "wedding_1",
                    "name": "Taylor Guest",
                    "phone": "+13125550102",
                    "email": "taylor@example.com",
                    "attending": ["ceremony", {"internal": "bad"}],
                    "dietary": "Nut allergy",
                    "sms_opt_in": False,
                    "email_opt_in": True,
                    "planner_note": "internal",
                    "seed_source": "marketing_capture",
                }
            ]
        )
    )
    plus_one_find = MagicMock(return_value=plus_one_cursor)

    service = GuestVerificationService.__new__(GuestVerificationService)
    service.rsvp_collection = SimpleNamespace(find_one=rsvp_find_one)  # type: ignore[assignment]
    service.plus_ones_collection = SimpleNamespace(find=plus_one_find)  # type: ignore[assignment]

    result = asyncio.run(service._load_rsvp_data("guest_1", "wedding_1"))

    assert result == {
        "has_rsvp": True,
        "submitted_at": "2027-03-01T12:00:00Z",
        "attending": ["ceremony"],
        "dietary": "Vegetarian",
        "plus_ones": [
            {
                "name": "Taylor Guest",
                "phone": "+13125550102",
                "email": "taylor@example.com",
                "attending": ["ceremony"],
                "dietary": "Nut allergy",
                "sms_opt_in": False,
                "email_opt_in": True,
            }
        ],
    }
    assert rsvp_find_one.await_args.args[0] == {
        "guest_id": {"$in": ["guest_1"]},
        "wedding_id": {"$in": ["wedding_1"]},
    }
    assert plus_one_find.call_args.args[0] == {
        "guest_id": {"$in": ["guest_1"]},
        "$or": [
            {"wedding_id": {"$in": ["wedding_1"]}},
            {"wedding_id": {"$exists": False}},
        ],
    }
    _assert_guest_internal_fields_absent(result)


def test_password_otp_token_and_session_paths_never_return_internal_fields():
    guest_id = "507f1f77bcf86cd799439011"
    guest_doc = {
        "id": guest_id,
        "wedding_id": "wedding_1",
        "name": "Jordan Guest",
        "phone": "+13125550101",
        "email": "jordan@example.com",
        "plus_one_allowed": True,
        "number_of_plus_ones_allowed": 1,
        "token": "invite-secret",
        "table_id": "table_1",
        "seed_source": "marketing_capture",
    }
    wedding_internal_fields = {
        "slug": "jordan-and-alex",
        "couple_names": "Jordan & Alex",
        "total_budget": 125000,
        "assigned_planner_email": "planner@example.com",
        "seed_scope": "capture_workspace",
    }

    password_service = _build_privacy_service(
        {
            "_id": "wedding_1",
            **wedding_internal_fields,
            "privacy_settings": {
                "privacy_mode": "password",
                "password_protection": "open-sesame",  # pragma: allowlist secret
            },
        }
    )
    password_result = asyncio.run(
        password_service.verify_wedding_page_access(
            "jordan-and-alex",
            {"password": "open-sesame"},  # pragma: allowlist secret
        )
    )

    otp_service = _build_privacy_service(
        {
            "_id": "wedding_1",
            **wedding_internal_fields,
            "privacy_settings": {"privacy_mode": "private"},
        }
    )
    otp_service.otp_service.verify_otp = AsyncMock(
        return_value={
            "success": True,
            "auth_method": "email_otp",
            "guest": guest_doc,
            "seed_source": "marketing_capture",
        }
    )
    otp_result = asyncio.run(
        otp_service.verify_wedding_page_access(
            "jordan-and-alex",
            {"contact": "jordan@example.com", "otp_code": "123456"},
        )
    )

    token_service = _build_privacy_service(
        {
            "_id": "wedding_1",
            **wedding_internal_fields,
            "privacy_settings": {"privacy_mode": "private"},
        }
    )
    token_service.guest_service = SimpleNamespace(  # type: ignore[assignment]
        get_guest_by_token=AsyncMock(return_value=guest_doc)
    )
    token_service.rsvp_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(return_value=None)
    )
    token_result = asyncio.run(
        token_service.get_rsvp_access_by_token(
            "jordan-and-alex",
            "invite-secret",
        )
    )

    session_service = GuestVerificationService.__new__(GuestVerificationService)
    session_service.wedding_service = SimpleNamespace(  # type: ignore[assignment]
        get_wedding_by_slug=AsyncMock(
            return_value={
                "_id": "wedding_1",
                **wedding_internal_fields,
                "privacy_settings": {"privacy_mode": "private"},
            }
        )
    )
    session_guest_doc = {**guest_doc, "_id": ObjectId(guest_id)}
    session_service.guests_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(return_value=session_guest_doc)
    )
    session_service.rsvp_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(return_value=None)
    )
    session_result = asyncio.run(
        session_service.get_session_access(
            slug="jordan-and-alex",
            wedding_id="wedding_1",
            guest_id=guest_id,
            auth_method="token",
        )
    )

    for result in (password_result, otp_result, token_result, session_result):
        _assert_guest_internal_fields_absent(result)

    expected_guest = {
        "id": guest_id,
        "name": "Jordan Guest",
        "phone": "+13125550101",
        "email": "jordan@example.com",
        "plus_one_allowed": True,
        "number_of_plus_ones_allowed": 1,
    }
    assert otp_result["guest"] == expected_guest
    assert token_result["guest"] == expected_guest
    assert session_result["guest"] == expected_guest


def test_session_access_rejects_a_guest_owned_by_another_wedding():
    guest_id = "507f1f77bcf86cd799439011"
    guest_lookup = AsyncMock(
        return_value={
            "_id": ObjectId(guest_id),
            "wedding_id": "wedding_2",
            "name": "Cross Tenant Guest",
        }
    )
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.wedding_service = SimpleNamespace(  # type: ignore[assignment]
        get_wedding_by_slug=AsyncMock(
            return_value={
                "_id": "wedding_1",
                "slug": "jordan-and-alex",
                "privacy_settings": {"privacy_mode": "private"},
            }
        )
    )
    service.guests_collection = SimpleNamespace(find_one=guest_lookup)  # type: ignore[assignment]

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            service.get_session_access(
                slug="jordan-and-alex",
                wedding_id="wedding_1",
                guest_id=guest_id,
                auth_method="token",
            )
        )

    assert exc_info.value.status_code == 403
    assert guest_lookup.await_args.args[0]["wedding_id"] == {"$in": ["wedding_1"]}


def test_privacy_mutation_requires_manage_wedding_settings_permission(monkeypatch):
    current_user = SimpleNamespace(
        is_root_admin=False,
        is_wedding_planner=False,
        is_team_member=True,
        team_permissions={"manage_wedding_settings": False},
    )
    access_check = AsyncMock(return_value=True)
    privacy_update = AsyncMock(return_value={"message": "should not run"})
    monkeypatch.setattr(
        guest_verification_api,
        "check_wedding_access",
        access_check,
    )
    monkeypatch.setattr(
        guest_verification_api.verification_service,
        "update_wedding_privacy_settings",
        privacy_update,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            guest_verification_api.update_wedding_privacy_settings(
                "wedding_1",
                guest_verification_api.PrivacySettingsUpdate(privacy_mode="private"),
                current_user=current_user,  # type: ignore[arg-type]
            )
        )

    assert exc_info.value.status_code == 403
    assert "manage wedding settings" in str(exc_info.value.detail)
    access_check.assert_not_awaited()
    privacy_update.assert_not_awaited()


def test_new_plus_one_rows_store_the_wedding_scope():
    service = RSVPService.__new__(RSVPService)
    service.rsvp_collection = SimpleNamespace(  # type: ignore[assignment]
        update_one=AsyncMock(return_value=None)
    )
    service.guest_collection = SimpleNamespace(  # type: ignore[assignment]
        update_one=AsyncMock(return_value=None)
    )
    service.plus_one_collection = SimpleNamespace(  # type: ignore[assignment]
        delete_many=AsyncMock(return_value=None),
        insert_many=AsyncMock(return_value=None),
    )
    service._notify_planner_rsvp = AsyncMock(return_value=None)  # type: ignore[method-assign]
    guest_id = ObjectId("507f1f77bcf86cd799439011")

    result = asyncio.run(
        service._submit_rsvp_for_guest_doc(
            {
                "_id": guest_id,
                "wedding_id": "wedding_1",
                "name": "Jordan Guest",
                "plus_one_allowed": True,
                "number_of_plus_ones_allowed": 1,
            },
            RSVPModel(
                attending=["ceremony"],
                plus_ones=[{"name": "Taylor Guest", "attending": ["ceremony"]}],
            ),
        )
    )

    assert result == {"message": "RSVP submitted successfully"}
    inserted_rows = service.plus_one_collection.insert_many.await_args.args[0]  # type: ignore[attr-defined]
    assert inserted_rows[0]["guest_id"] == str(guest_id)
    assert inserted_rows[0]["wedding_id"] == "wedding_1"


def test_update_wedding_admin_invalidates_all_wedding_projections(monkeypatch):
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
        AsyncMock(
            return_value={
                "slug": "old-slug",
                "assigned_planner_id": "planner_1",
                "assigned_planner_email": "planner@example.com",
            }
        ),
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
        wedding_api,
        "invalidate_wedding_projection_caches",
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
    invalidate_mock.assert_awaited_once_with(
        "wedding_1",
        previous_slug="old-slug",
    )


def test_direct_privacy_settings_update_invalidates_all_wedding_projections(
    monkeypatch,
):
    update_result = SimpleNamespace(matched_count=1)
    service = GuestVerificationService.__new__(GuestVerificationService)
    service.weddings_collection = SimpleNamespace(  # type: ignore[assignment]
        find_one=AsyncMock(return_value={"slug": "james-and-mel"}),
        update_one=AsyncMock(return_value=update_result),
    )
    invalidate_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        guest_verification_module,
        "invalidate_wedding_projection_caches",
        invalidate_mock,
        raising=False,
    )

    result = asyncio.run(
        service.update_wedding_privacy_settings(
            "wedding_1",
            {
                "privacy_mode": "public",
                "guest_auth_required": False,
            },
        )
    )

    assert result == {"message": "Privacy settings updated successfully"}
    service.weddings_collection.find_one.assert_awaited_once_with(  # type: ignore[attr-defined]
        {"_id": "wedding_1"}, {"slug": 1}
    )
    invalidate_mock.assert_awaited_once_with(
        "wedding_1",
        previous_slug="james-and-mel",
    )
