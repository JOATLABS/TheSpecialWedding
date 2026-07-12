from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.dependencies.auth_extended import ExtendedAuthUser
from app.models.storefront import StorefrontSettingsUpdate
from app.services.storefront_entitlement_service import StorefrontEntitlements
from app.services.storefront_service import (
    StorefrontService,
    normalize_storefront_slug,
)


OWNER_ID = "507f1f77bcf86cd799439011"
SECOND_OWNER_ID = "507f1f77bcf86cd799439012"


class AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        documents = list(self._cursor)
        return documents if length is None else documents[:length]


class AsyncCollection:
    def __init__(self, collection):
        self._collection = collection

    async def find_one(self, *args, **kwargs):
        return self._collection.find_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return AsyncCursor(self._collection.find(*args, **kwargs))

    async def insert_one(self, *args, **kwargs):
        return self._collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._collection.update_one(*args, **kwargs)

    async def create_index(self, *args, **kwargs):
        return self._collection.create_index(*args, **kwargs)


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
        self.raw = mongomock.MongoClient()["storefront_test"]
        self.db = AsyncDatabase(self.raw)

    def get_users_collection(self):
        return self.db["users"]


class FakeEntitlements:
    def __init__(self):
        self.enabled_by_owner = {
            OWNER_ID: True,
            SECOND_OWNER_ID: True,
        }

    def _result(self, owner_id: str) -> StorefrontEntitlements:
        enabled = self.enabled_by_owner.get(owner_id, False)
        return StorefrontEntitlements(
            owner_id=owner_id,
            plan_id="plan_signature" if enabled else "plan_boutique",
            storefront_enabled=enabled,
            custom_domain_enabled=enabled,
        )

    async def resolve_for_owner(self, user_data: dict) -> StorefrontEntitlements:
        return self._result(str(user_data.get("_id") or ""))

    async def resolve_for_planner_id(self, planner_id: str) -> StorefrontEntitlements:
        return self._result(str(planner_id))


@pytest.fixture
def setup_storefront():
    fake_mongo = FakeMongo()
    entitlements = FakeEntitlements()
    service = StorefrontService(fake_mongo, entitlements)
    fake_mongo.raw.users.insert_many(
        [
            {
                "_id": ObjectId(OWNER_ID),
                "role": "wedding_planner",
                "is_active": True,
                "company_name": "Luxe & Light Events",
                "first_name": "Ada",
                "profile_image_url": "https://cdn.example.test/profile.webp",
                "email": "private-account@example.test",
                "support_phone": "+15555550100",
            },
            {
                "_id": ObjectId(SECOND_OWNER_ID),
                "role": "wedding_planner",
                "is_active": True,
                "company_name": "Second Events",
                "first_name": "Grace",
                "email": "second-private@example.test",
            },
        ]
    )
    return service, fake_mongo, entitlements


def _owner(owner_id: str = OWNER_ID) -> ExtendedAuthUser:
    return ExtendedAuthUser(
        email=f"{owner_id}@example.test",
        role="wedding_planner",
        user_data={"_id": ObjectId(owner_id), "role": "wedding_planner"},
    )


def test_slug_normalization_is_ascii_bounded_and_reserved_safe():
    assert normalize_storefront_slug("  Luxe & Lîght Events  ") == "luxe-light-events"
    assert normalize_storefront_slug("A---B___C") == "a-b-c"

    for invalid in ("ab", "a" * 65, "admin", "API", "storefront", "---"):
        with pytest.raises(ValueError):
            normalize_storefront_slug(invalid)


def test_settings_model_forbids_domain_and_arbitrary_image_fields():
    for forbidden_field in (
        "custom_domain",
        "cloudflare_hostname_id",
        "hero_image_url",
        "about_image_url",
    ):
        with pytest.raises(ValidationError):
            StorefrontSettingsUpdate.model_validate(
                {"slug": "luxe-events", forbidden_field: "attacker-controlled"}
            )


@pytest.mark.asyncio
async def test_create_and_edit_round_trip_preserves_explicit_state(setup_storefront):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()

    created = await service.update_settings(
        owner,
        StorefrontSettingsUpdate(
            slug="Luxe & Light Events",
            title="Luxe celebrations",
            description="Calm, considered wedding planning.",
            contact_email="hello@luxe.example",
            contact_phone="+1 555 555 0199",
            theme_color="#7c3aed",
            packages_enabled=True,
            reviews_enabled=False,
        ),
    )

    assert created["slug"] == "luxe-light-events"
    assert created["contact_email"] == "hello@luxe.example"
    assert created["contact_phone"] == "+1 555 555 0199"
    assert created["is_published"] is False
    assert created["published_at"] is None
    assert created["slug_editable"] is True

    edited = await service.update_settings(
        owner,
        StorefrontSettingsUpdate(description="Updated description"),
    )
    assert edited["slug"] == "luxe-light-events"
    assert edited["title"] == "Luxe celebrations"
    assert edited["description"] == "Updated description"
    assert edited["contact_email"] == "hello@luxe.example"
    assert edited["reviews_enabled"] is False

    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored is not None
    assert "custom_domain" not in stored
    assert "hero_image_url" not in stored
    assert stored["planner_id"] == OWNER_ID


@pytest.mark.asyncio
async def test_slug_conflict_and_post_publication_change_are_rejected_atomically(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    first_owner = _owner()
    second_owner = _owner(SECOND_OWNER_ID)

    await service.update_settings(
        first_owner,
        StorefrontSettingsUpdate(slug="luxe-events", title="First"),
    )
    with pytest.raises(HTTPException) as conflict:
        await service.update_settings(
            second_owner,
            StorefrontSettingsUpdate(slug="Luxe Events", title="Second"),
        )
    assert conflict.value.status_code == 409
    assert (
        fake_mongo.raw.storefront_settings.find_one({"planner_id": SECOND_OWNER_ID})
        is None
    )

    published = await service.update_settings(
        first_owner,
        StorefrontSettingsUpdate(is_published=True),
    )
    assert published["published_at"] is not None
    assert published["slug_editable"] is False

    with pytest.raises(HTTPException) as immutable:
        await service.update_settings(
            first_owner,
            StorefrontSettingsUpdate(slug="a-new-address", description="must not land"),
        )
    assert immutable.value.status_code == 409

    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored["slug"] == "luxe-events"
    assert stored.get("description") != "must not land"

    unpublished = await service.update_settings(
        first_owner,
        StorefrontSettingsUpdate(is_published=False),
    )
    assert unpublished["is_published"] is False
    assert unpublished["published_at"] == published["published_at"]
    assert unpublished["slug_editable"] is False


@pytest.mark.asyncio
async def test_draft_preview_is_owner_only_and_public_read_needs_publication(
    setup_storefront,
):
    service, _, _ = setup_storefront
    owner = _owner()
    other_owner = _owner(SECOND_OWNER_ID)
    await service.update_settings(
        owner,
        StorefrontSettingsUpdate(
            slug="luxe-events",
            title="Private draft",
            contact_email="public-contact@luxe.example",
        ),
    )

    preview = await service.get_owner_preview(owner, "luxe-events")
    assert preview["storefront"]["title"] == "Private draft"

    with pytest.raises(HTTPException) as other_preview:
        await service.get_owner_preview(other_owner, "luxe-events")
    assert other_preview.value.status_code == 404

    with pytest.raises(HTTPException) as public_draft:
        await service.get_public_storefront("luxe-events")
    assert public_draft.value.status_code == 404

    with pytest.raises(HTTPException) as object_id_fallback:
        await service.get_public_storefront(OWNER_ID)
    assert object_id_fallback.value.status_code == 404


@pytest.mark.asyncio
async def test_public_projection_filters_packages_reviews_and_private_owner_fields(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()
    await service.update_settings(
        owner,
        StorefrontSettingsUpdate(
            slug="luxe-events",
            title="Published storefront",
            description="Public description",
            contact_email="public-contact@luxe.example",
            contact_phone="+1 555 0100",
            is_published=True,
        ),
    )
    fake_mongo.raw.packages.insert_many(
        [
            {
                "_id": ObjectId(),
                "planner_id": OWNER_ID,
                "status": "active",
                "is_template": False,
                "name": "Full Planning",
                "description": "Start-to-finish support",
                "total_amount": 12500,
                "currency": "USD",
                "services": [
                    {
                        "name": "Vendor sourcing",
                        "description": "Curated shortlists",
                        "internal_cost": 50,
                    }
                ],
                "internal_margin": 0.42,
                "contract_terms": "private",
            },
            {
                "_id": ObjectId(),
                "planner_id": OWNER_ID,
                "status": "draft",
                "is_template": False,
                "name": "Draft package",
                "total_amount": 1,
            },
            {
                "_id": ObjectId(),
                "planner_id": OWNER_ID,
                "status": "active",
                "is_template": True,
                "name": "Template package",
                "total_amount": 1,
            },
            {
                "_id": ObjectId(),
                "planner_id": SECOND_OWNER_ID,
                "status": "active",
                "is_template": False,
                "name": "Another tenant",
                "total_amount": 1,
            },
        ]
    )
    fake_mongo.raw.planner_reviews.insert_many(
        [
            {
                "_id": ObjectId(),
                "planner_id": OWNER_ID,
                "is_published": True,
                "author_name": "A Couple",
                "rating": 5,
                "text": "Wonderful",
                "source": "manual",
                "date": "2026-06-01",
                "author_email": "private-couple@example.test",
            },
            {
                "_id": ObjectId(),
                "planner_id": OWNER_ID,
                "is_published": False,
                "author_name": "Hidden",
                "rating": 1,
                "text": "Hidden",
            },
        ]
    )

    result = await service.get_public_storefront("luxe-events")

    assert result["storefront"]["contact_email"] == "public-contact@luxe.example"
    assert result["storefront"]["contact_phone"] == "+1 555 0100"
    assert "planner_id" not in result["storefront"]
    assert result["planner"] == {
        "company_name": "Luxe & Light Events",
        "first_name": "Ada",
        "profile_image_url": "https://cdn.example.test/profile.webp",
    }
    assert "email" not in result["planner"]
    assert "support_phone" not in result["planner"]

    assert len(result["packages"]) == 1
    package = result["packages"][0]
    assert set(package) == {
        "_id",
        "name",
        "description",
        "total_amount",
        "currency",
        "services",
    }
    assert package["total_amount"] == 12500
    assert package["services"] == [
        {"name": "Vendor sourcing", "description": "Curated shortlists"}
    ]
    assert len(result["reviews"]) == 1
    assert "author_email" not in result["reviews"][0]


@pytest.mark.asyncio
async def test_eligibility_loss_retains_authored_publication_state(setup_storefront):
    service, fake_mongo, entitlements = setup_storefront
    owner = _owner()
    await service.update_settings(
        owner,
        StorefrontSettingsUpdate(
            slug="luxe-events", title="Retained", is_published=True
        ),
    )
    before = deepcopy(
        fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    )

    entitlements.enabled_by_owner[OWNER_ID] = False
    with pytest.raises(HTTPException) as settings_denied:
        await service.get_settings(owner)
    assert settings_denied.value.status_code == 403
    with pytest.raises(HTTPException) as public_denied:
        await service.get_public_storefront("luxe-events")
    assert public_denied.value.status_code == 404

    after = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert after == before
    assert after["is_published"] is True
    assert isinstance(after["published_at"], datetime)


@pytest.mark.asyncio
async def test_access_reports_independent_current_capabilities(setup_storefront):
    service, _, entitlements = setup_storefront
    entitlements.enabled_by_owner[OWNER_ID] = True
    access = await service.get_access(_owner())
    assert access == {
        "plan_id": "plan_signature",
        "storefront_enabled": True,
        "custom_domain_enabled": True,
    }


@pytest.mark.asyncio
async def test_service_rejects_non_owner_roles_even_when_called_without_a_route(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    team_member = ExtendedAuthUser(
        email="team@example.com",
        role="team_member",
        user_data={"_id": ObjectId(OWNER_ID), "role": "team_member"},
    )

    with pytest.raises(HTTPException) as denied:
        await service.update_settings(
            team_member, StorefrontSettingsUpdate(slug="team-bypass")
        )

    assert denied.value.status_code == 403
    assert fake_mongo.raw.storefront_settings.count_documents({}) == 0


@pytest.mark.asyncio
async def test_legacy_settings_are_readable_then_gain_a_persisted_slug_on_edit(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    fake_mongo.raw.storefront_settings.insert_one(
        {
            "planner_id": OWNER_ID,
            "title": "Legacy settings",
            "packages_enabled": True,
            "reviews_enabled": True,
        }
    )

    legacy = await service.get_settings(_owner())
    assert legacy["slug"] == "luxe-light-events"
    assert legacy["created_at"] is None
    assert (
        fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID}).get(
            "slug"
        )
        is None
    )

    edited = await service.update_settings(
        _owner(), StorefrontSettingsUpdate(description="Migrated on explicit save")
    )
    assert edited["slug"] == "luxe-light-events"
    assert edited["created_at"] is not None
    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored["slug"] == "luxe-light-events"


@pytest.mark.asyncio
async def test_unique_index_race_is_translated_to_slug_conflict(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront

    async def duplicate_write(*_args, **_kwargs):
        raise DuplicateKeyError("duplicate slug")

    fake_mongo.db["storefront_settings"].update_one = duplicate_write
    with pytest.raises(HTTPException) as conflict:
        await service.update_settings(
            _owner(), StorefrontSettingsUpdate(slug="race-winner")
        )
    assert conflict.value.status_code == 409
