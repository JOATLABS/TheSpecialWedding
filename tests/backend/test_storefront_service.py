from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.constants.storefront import PENDING_ASSET_RECOVERY_FIELDS
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


class FakeDomains:
    def __init__(self):
        self.owner_by_hostname: dict[str, str] = {}
        self.lookups: list[str] = []

    async def resolve_active_hostname(self, hostname: str) -> dict | None:
        self.lookups.append(hostname)
        owner_id = self.owner_by_hostname.get(hostname.lower())
        if not owner_id:
            return None
        return {"planner_id": owner_id, "hostname": hostname.lower()}


class FakeMedia:
    def __init__(self, mongo: FakeMongo):
        self.mongo = mongo
        self.validations: list[dict] = []
        self.attachments: list[tuple[str, str]] = []
        self.releases: list[str] = []
        self.claim_releases: list[str] = []
        self.claim_release_entries: list[tuple[str, tuple[str, ...]]] = []
        self.claim_reconciliations: list[str] = []
        self.pre_promotion_settings: list[dict] = []
        self.recovery_calls = 0
        self._claim_number = 0
        self.fail_asset_attach = False

    async def validate_settings_assets(self, _owner, **asset_fields):
        self.validations.append(dict(asset_fields))
        if "foreign-asset" in asset_fields.values():
            raise HTTPException(status_code=404, detail="Storefront asset not found")
        return dict(asset_fields)

    async def claim_settings_assets(self, _owner, **asset_fields):
        values = await self.validate_settings_assets(_owner, **asset_fields)
        self._claim_number += 1
        claim_id = f"claim-{self._claim_number}"
        claimed_assets = [
            {
                "asset_id": asset_id,
                "slot": "hero" if field_name == "hero_asset_id" else "about",
                "field_name": field_name,
            }
            for field_name, asset_id in values.items()
            if asset_id
        ]
        manifest = {
            "claim_id": claim_id,
            "count": len(values),
            "members": {
                field_name.removesuffix("_asset_id"): asset_id
                for field_name, asset_id in values.items()
            },
        }
        return {
            "owner_id": OWNER_ID,
            "claim_id": claim_id,
            "values": values,
            "claimed_assets": claimed_assets,
            "manifest": manifest,
        }

    async def release_settings_asset_claims(self, _owner, claim):
        self.claim_releases.append(claim["claim_id"])
        self.claim_release_entries.append(
            (
                claim["claim_id"],
                tuple(entry["slot"] for entry in claim["claimed_assets"]),
            )
        )

    async def attach_settings_asset_claims(self, _owner, claim):
        if self.fail_asset_attach:
            raise RuntimeError("forced asset attach failure")
        row = self.mongo.raw.storefront_settings.find_one(
            {
                "planner_id": OWNER_ID,
                "pending_asset_group": claim["manifest"],
            }
        )
        assert row is not None, "asset intent must retain the exact pending token"
        for field_name, asset_id in claim["values"].items():
            slot = field_name.removesuffix("_asset_id")
            assert f"pending_{slot}_asset_id" in row
            assert row[f"pending_{slot}_asset_id"] == asset_id
            assert row[f"pending_{slot}_claim_id"] == claim["claim_id"]
        for entry in claim["claimed_assets"]:
            saved = self.mongo.raw.storefront_settings.find_one(
                {
                    f"pending_{entry['slot']}_asset_id": entry["asset_id"],
                    f"pending_{entry['slot']}_claim_id": claim["claim_id"],
                    "pending_asset_group": claim["manifest"],
                }
            )
            assert saved is not None, "asset claim must attach from exact pending token"
            assert saved.get(entry["field_name"]) != entry["asset_id"]
            self.attachments.append((entry["asset_id"], entry["slot"]))

    async def promote_settings_asset_claims(self, _owner, claim):
        query = {
            "planner_id": OWNER_ID,
            "pending_asset_group": claim["manifest"],
        }
        set_fields = {}
        unset_fields = {}
        for field_name, asset_id in claim["values"].items():
            slot = field_name.removesuffix("_asset_id")
            pending_asset = f"pending_{slot}_asset_id"
            pending_claim = f"pending_{slot}_claim_id"
            query[pending_asset] = asset_id
            query[pending_claim] = claim["claim_id"]
            set_fields[field_name] = asset_id
            unset_fields[pending_asset] = ""
            unset_fields[pending_claim] = ""
        unset_fields["pending_asset_group"] = ""
        before = self.mongo.raw.storefront_settings.find_one(query)
        assert before is not None, "promotion must retain the exact pending token"
        self.pre_promotion_settings.append(deepcopy(before))
        result = self.mongo.raw.storefront_settings.update_one(
            query,
            {"$set": set_fields, "$unset": unset_fields, "$inc": {"revision": 1}},
        )
        assert result.modified_count == 1

    async def reconcile_settings_asset_claims(self, owner, claim):
        self.claim_reconciliations.append(claim["claim_id"])
        row = self.mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
        exact_group = row and row.get("pending_asset_group") == claim["manifest"]
        exact_entries = exact_group and all(
            f"pending_{field_name.removesuffix('_asset_id')}_asset_id" in row
            and row.get(f"pending_{field_name.removesuffix('_asset_id')}_asset_id")
            == asset_id
            and row.get(f"pending_{field_name.removesuffix('_asset_id')}_claim_id")
            == claim["claim_id"]
            for field_name, asset_id in claim["values"].items()
        )
        if exact_entries:
            try:
                await self.attach_settings_asset_claims(owner, claim)
                await self.promote_settings_asset_claims(owner, claim)
                return
            except Exception:
                pass
        unset_fields = {"pending_asset_group": ""}
        for field_name in claim["values"]:
            slot = field_name.removesuffix("_asset_id")
            unset_fields[f"pending_{slot}_asset_id"] = ""
            unset_fields[f"pending_{slot}_claim_id"] = ""
        self.mongo.raw.storefront_settings.update_one(
            {
                "planner_id": OWNER_ID,
                "pending_asset_group": claim["manifest"],
            },
            {"$unset": unset_fields, "$inc": {"revision": 1}},
        )
        await self.release_settings_asset_claims(owner, claim)

    async def recover_pending_settings_assets(self, _owner):
        self.recovery_calls += 1

    async def attach(self, _owner, asset_id: str, slot: str):
        saved = self.mongo.raw.storefront_settings.find_one(
            {f"{slot}_asset_id": asset_id}
        )
        assert saved is not None, "asset attachment must happen after settings persist"
        self.attachments.append((asset_id, slot))
        return {"asset_id": asset_id, "slot": slot, "state": "attached"}

    async def release_if_unreferenced(self, _owner, asset_id: str):
        settings = self.mongo.raw.storefront_settings.find_one(
            {
                "$or": [
                    {"hero_asset_id": asset_id},
                    {"about_asset_id": asset_id},
                ]
            }
        )
        assert settings is None, "old asset release must happen after settings change"
        self.releases.append(asset_id)
        return {"asset_id": asset_id, "state": "ready"}


@pytest.fixture
def setup_storefront():
    fake_mongo = FakeMongo()
    fake_mongo.raw.storefront_settings.create_index("planner_id", unique=True)
    fake_mongo.raw.storefront_settings.create_index(
        "slug",
        unique=True,
        partialFilterExpression={"slug": {"$type": "string"}},
    )
    entitlements = FakeEntitlements()
    domains = FakeDomains()
    media = FakeMedia(fake_mongo)
    service = StorefrontService(
        fake_mongo,
        entitlements,
        domain_service=domains,
        media_service=media,
    )
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
    assert created["slug_persisted"] is True

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
async def test_settings_validates_only_explicit_asset_fields_before_save_then_attaches(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()

    await service.update_settings(
        owner,
        StorefrontSettingsUpdate(slug="asset-events", description="No image edit"),
    )
    assert service._media.validations == []

    saved = await service.update_settings(
        owner,
        StorefrontSettingsUpdate(hero_asset_id="hero-ready-1"),
    )
    assert saved["hero_asset_id"] == "hero-ready-1"
    assert service._media.validations == [{"hero_asset_id": "hero-ready-1"}]
    assert service._media.attachments == [("hero-ready-1", "hero")]
    first_handoff = service._media.pre_promotion_settings[0]
    assert first_handoff.get("hero_asset_id") is None
    assert first_handoff["pending_hero_asset_id"] == "hero-ready-1"
    assert first_handoff["pending_hero_claim_id"] == "claim-1"
    assert first_handoff["pending_asset_group"] == {
        "claim_id": "claim-1",
        "count": 1,
        "members": {"hero": "hero-ready-1"},
    }

    replaced = await service.update_settings(
        owner,
        StorefrontSettingsUpdate(hero_asset_id="hero-ready-2"),
    )
    assert replaced["hero_asset_id"] == "hero-ready-2"
    replacement_handoff = service._media.pre_promotion_settings[1]
    assert replacement_handoff["hero_asset_id"] == "hero-ready-1"
    assert replacement_handoff["pending_hero_asset_id"] == "hero-ready-2"
    assert service._media.releases == ["hero-ready-1"]

    before = deepcopy(
        fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    )
    with pytest.raises(HTTPException) as foreign:
        await service.update_settings(
            owner,
            StorefrontSettingsUpdate(about_asset_id="foreign-asset"),
        )
    assert foreign.value.status_code == 404
    assert (
        fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID}) == before
    )

    fake_mongo.raw.storefront_settings.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "pending_hero_asset_id": "paused-asset",
                "pending_hero_claim_id": "paused-claim",
                "pending_asset_group": {
                    "claim_id": "paused-claim",
                    "count": 1,
                    "members": {"hero": "paused-asset"},
                },
            }
        },
    )
    cleared = await service.update_settings(
        owner,
        StorefrontSettingsUpdate(hero_asset_id=None),
    )
    assert cleared["hero_asset_id"] is None
    assert service._media.validations[-1] == {"hero_asset_id": None}
    assert service._media.attachments == [
        ("hero-ready-1", "hero"),
        ("hero-ready-2", "hero"),
    ]
    assert service._media.releases == ["hero-ready-1", "hero-ready-2"]
    assert service._media.claim_releases == ["paused-claim"]
    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert "pending_hero_asset_id" not in stored
    assert "pending_hero_claim_id" not in stored
    assert "pending_asset_group" not in stored


@pytest.mark.asyncio
async def test_multi_slot_settings_handoff_promotes_together(setup_storefront):
    service, fake_mongo, _ = setup_storefront
    saved = await service.update_settings(
        _owner(),
        StorefrontSettingsUpdate(
            slug="two-images",
            hero_asset_id="hero-ready",
            about_asset_id="about-ready",
        ),
    )

    assert saved["hero_asset_id"] == "hero-ready"
    assert saved["about_asset_id"] == "about-ready"
    pending_snapshot = service._media.pre_promotion_settings[-1]
    assert pending_snapshot.get("hero_asset_id") is None
    assert pending_snapshot.get("about_asset_id") is None
    assert (
        pending_snapshot["pending_hero_claim_id"]
        == pending_snapshot["pending_about_claim_id"]
    )
    assert pending_snapshot["pending_asset_group"] == {
        "claim_id": pending_snapshot["pending_hero_claim_id"],
        "count": 2,
        "members": {"hero": "hero-ready", "about": "about-ready"},
    }
    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert not any(key.startswith("pending_") for key in stored)


@pytest.mark.asyncio
async def test_mixed_clear_and_attach_roll_back_as_one_atomic_intent(setup_storefront):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()
    seeded = await service.update_settings(
        owner,
        StorefrontSettingsUpdate(
            slug="mixed-asset-intent",
            hero_asset_id="hero-existing",
            about_asset_id="about-existing",
        ),
    )
    assert seeded["hero_asset_id"] == "hero-existing"
    assert seeded["about_asset_id"] == "about-existing"
    service._media.fail_asset_attach = True

    with pytest.raises(HTTPException) as failed:
        await service.update_settings(
            owner,
            StorefrontSettingsUpdate(
                hero_asset_id=None,
                about_asset_id="about-replacement",
            ),
        )

    assert failed.value.status_code == 503
    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored["hero_asset_id"] == "hero-existing"
    assert stored["about_asset_id"] == "about-existing"
    assert not any(key.startswith("pending_") for key in stored)


@pytest.mark.asyncio
async def test_new_asset_edit_retires_every_member_of_displaced_pending_group(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    await service.update_settings(
        _owner(), StorefrontSettingsUpdate(slug="retire-old-group")
    )
    fake_mongo.raw.storefront_settings.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "pending_hero_asset_id": "paused-hero",
                "pending_hero_claim_id": "paused-group",
                "pending_about_asset_id": "paused-about",
                "pending_about_claim_id": "paused-group",
                "pending_asset_group": {
                    "claim_id": "paused-group",
                    "count": 2,
                    "members": {
                        "hero": "paused-hero",
                        "about": "paused-about",
                    },
                },
            }
        },
    )

    saved = await service.update_settings(
        _owner(), StorefrontSettingsUpdate(hero_asset_id="replacement-hero")
    )

    assert saved["hero_asset_id"] == "replacement-hero"
    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert not any(key.startswith("pending_") for key in stored)
    assert ("paused-group", ("hero", "about")) in service._media.claim_release_entries


@pytest.mark.asyncio
async def test_successor_asset_edit_clears_stale_manifest_recovery_metadata(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    await service.update_settings(
        _owner(), StorefrontSettingsUpdate(slug="replace-recovery-metadata")
    )
    fake_mongo.raw.storefront_settings.update_one(
        {"planner_id": OWNER_ID},
        {
            "$set": {
                "pending_asset_recovery_status": "quarantined",
                "pending_asset_recovery_error": "invalid_pending_manifest",
                "pending_asset_recovery_attempts": 3,
            }
        },
    )

    saved = await service.update_settings(
        _owner(), StorefrontSettingsUpdate(hero_asset_id="successor-hero")
    )

    assert saved["hero_asset_id"] == "successor-hero"
    pre_promotion = service._media.pre_promotion_settings[-1]
    assert not PENDING_ASSET_RECOVERY_FIELDS.intersection(pre_promotion)


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
async def test_owner_preview_seed_uses_canonical_unfiltered_data_without_persisting_settings(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    fake_mongo.raw.packages.insert_one(
        {
            "_id": ObjectId(),
            "planner_id": OWNER_ID,
            "status": "active",
            "is_template": False,
            "name": "Canonical Full Planning",
            "description": "Backend-owned preview data",
            "total_amount": 9800,
            "currency": "USD",
            "services": [{"name": "Vendor sourcing", "description": None}],
        }
    )
    fake_mongo.raw.planner_reviews.insert_one(
        {
            "_id": ObjectId(),
            "planner_id": OWNER_ID,
            "is_published": True,
            "author_name": "A Couple",
            "rating": 5,
            "text": "Canonical review",
            "source": "manual",
            "date": "2026-07-01",
        }
    )

    preview = await service.get_owner_preview_seed(_owner())

    assert preview["planner"]["company_name"] == "Luxe & Light Events"
    assert preview["packages"][0]["name"] == "Canonical Full Planning"
    assert preview["reviews"][0]["text"] == "Canonical review"
    assert preview["slug"] == "luxe-light-events"
    assert fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID}) is None


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
                    },
                    {
                        "name": "Explicitly included",
                        "description": "Published by explicit intent",
                        "included": True,
                    },
                    {
                        "name": "Explicitly excluded",
                        "description": "Private package exclusion",
                        "included": False,
                    },
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
            {
                "_id": ObjectId(),
                "planner_id": OWNER_ID,
                "status": "active",
                "name": "Missing template marker",
                "total_amount": 1,
            },
            {
                "_id": ObjectId(),
                "planner_id": OWNER_ID,
                "status": "active",
                "is_template": None,
                "name": "Null template marker",
                "total_amount": 1,
            },
            {
                "_id": ObjectId(),
                "planner_id": OWNER_ID,
                "status": "active",
                "is_template": "false",
                "name": "Malformed template marker",
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
        {"name": "Vendor sourcing", "description": "Curated shortlists"},
        {
            "name": "Explicitly included",
            "description": "Published by explicit intent",
        },
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
async def test_public_custom_hostname_requires_active_mapping_and_published_owner_settings(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()
    await service.update_settings(
        owner,
        StorefrontSettingsUpdate(
            slug="events-example",
            title="Published host",
            is_published=True,
        ),
    )

    # A dotted identifier must never silently alias the hyphenated slug.
    with pytest.raises(HTTPException) as inactive:
        await service.get_public_storefront("events.example")
    assert inactive.value.status_code == 404

    service._domains.owner_by_hostname["events.example"] = OWNER_ID
    result = await service.get_public_storefront("EVENTS.EXAMPLE")
    assert result["slug"] == "events-example"

    fake_mongo.raw.storefront_settings.update_one(
        {"planner_id": OWNER_ID}, {"$set": {"is_published": False}}
    )
    with pytest.raises(HTTPException) as unpublished:
        await service.get_public_storefront("events.example")
    assert unpublished.value.status_code == 404


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
    assert legacy["slug_persisted"] is False
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
    assert edited["slug_persisted"] is True
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

    fake_mongo.db["storefront_settings"].insert_one = duplicate_write
    with pytest.raises(HTTPException) as conflict:
        await service.update_settings(
            _owner(), StorefrontSettingsUpdate(slug="race-winner")
        )
    assert conflict.value.status_code == 409


def _pause_first_write_for_task(collection, task_name: str):
    original_update = collection.update_one
    original_insert = collection.insert_one
    paused = asyncio.Event()
    resume = asyncio.Event()
    did_pause = False

    async def maybe_pause():
        nonlocal did_pause
        current = asyncio.current_task()
        if current and current.get_name() == task_name and not did_pause:
            did_pause = True
            paused.set()
            await resume.wait()

    async def interleaved_update(*args, **kwargs):
        await maybe_pause()
        return await original_update(*args, **kwargs)

    async def interleaved_insert(*args, **kwargs):
        await maybe_pause()
        return await original_insert(*args, **kwargs)

    collection.update_one = interleaved_update
    collection.insert_one = interleaved_insert
    return paused, resume


@pytest.mark.asyncio
async def test_stale_slug_change_cannot_land_after_concurrent_publication(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()
    await service.update_settings(
        owner, StorefrontSettingsUpdate(slug="draft-address", title="Draft")
    )
    collection = fake_mongo.db["storefront_settings"]
    paused, resume = _pause_first_write_for_task(collection, "stale-slug-change")

    stale_change = asyncio.create_task(
        service.update_settings(owner, StorefrontSettingsUpdate(slug="must-not-land")),
        name="stale-slug-change",
    )
    await paused.wait()
    await service.update_settings(owner, StorefrontSettingsUpdate(is_published=True))
    resume.set()

    with pytest.raises(HTTPException) as conflict:
        await stale_change
    assert conflict.value.status_code == 409
    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored["slug"] == "draft-address"
    assert stored["is_published"] is True


@pytest.mark.asyncio
async def test_unrelated_stale_edit_does_not_overwrite_concurrent_slug_choice(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()
    await service.update_settings(
        owner, StorefrontSettingsUpdate(slug="first-address", title="Draft")
    )
    collection = fake_mongo.db["storefront_settings"]
    paused, resume = _pause_first_write_for_task(collection, "stale-description")

    stale_description = asyncio.create_task(
        service.update_settings(
            owner, StorefrontSettingsUpdate(description="Keep this edit")
        ),
        name="stale-description",
    )
    await paused.wait()
    await service.update_settings(
        owner, StorefrontSettingsUpdate(slug="chosen-address")
    )
    resume.set()
    result = await stale_description

    assert result["slug"] == "chosen-address"
    assert result["description"] == "Keep this edit"
    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored["slug"] == "chosen-address"


@pytest.mark.asyncio
async def test_asset_claim_is_released_before_a_settings_cas_retry(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()
    await service.update_settings(
        owner, StorefrontSettingsUpdate(slug="claim-retry", title="Draft")
    )
    collection = fake_mongo.db["storefront_settings"]
    paused, resume = _pause_first_write_for_task(collection, "stale-asset-save")

    stale_asset_save = asyncio.create_task(
        service.update_settings(
            owner, StorefrontSettingsUpdate(hero_asset_id="hero-ready-claim")
        ),
        name="stale-asset-save",
    )
    await paused.wait()
    await service.update_settings(
        owner, StorefrontSettingsUpdate(description="Concurrent edit")
    )
    resume.set()
    saved = await stale_asset_save

    assert saved["hero_asset_id"] == "hero-ready-claim"
    assert service._media.claim_releases == ["claim-1"]
    assert service._media.attachments == [("hero-ready-claim", "hero")]
    assert service._media.validations == [
        {"hero_asset_id": "hero-ready-claim"},
        {"hero_asset_id": "hero-ready-claim"},
    ]


@pytest.mark.asyncio
async def test_ambiguous_settings_write_reconciles_claim_against_durable_reference(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()
    await service.update_settings(
        owner, StorefrontSettingsUpdate(slug="claim-reconcile", title="Draft")
    )
    collection = fake_mongo.db["storefront_settings"]
    original_update = collection.update_one
    raised = False

    async def applied_then_transport_failed(*args, **kwargs):
        nonlocal raised
        result = await original_update(*args, **kwargs)
        if not raised and asyncio.current_task().get_name() == "ambiguous-asset-save":
            raised = True
            raise RuntimeError("response lost after durable Mongo write")
        return result

    collection.update_one = applied_then_transport_failed
    ambiguous_save = asyncio.create_task(
        service.update_settings(
            owner, StorefrontSettingsUpdate(hero_asset_id="hero-ambiguous")
        ),
        name="ambiguous-asset-save",
    )

    with pytest.raises(RuntimeError, match="response lost"):
        await ambiguous_save

    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored["hero_asset_id"] == "hero-ambiguous"
    assert service._media.claim_reconciliations == ["claim-1"]
    assert service._media.attachments == [("hero-ambiguous", "hero")]


@pytest.mark.asyncio
async def test_stale_first_save_cannot_overwrite_concurrent_first_publication(
    setup_storefront,
):
    service, fake_mongo, _ = setup_storefront
    owner = _owner()
    collection = fake_mongo.db["storefront_settings"]
    paused, resume = _pause_first_write_for_task(collection, "stale-first-save")

    stale_first_save = asyncio.create_task(
        service.update_settings(
            owner,
            StorefrontSettingsUpdate(
                slug="stale-first-address", description="Must not overwrite"
            ),
        ),
        name="stale-first-save",
    )
    await paused.wait()
    published = await service.update_settings(
        owner,
        StorefrontSettingsUpdate(
            slug="published-first-address",
            title="Published",
            is_published=True,
        ),
    )
    resume.set()

    with pytest.raises(HTTPException) as conflict:
        await stale_first_save
    assert conflict.value.status_code == 409
    stored = fake_mongo.raw.storefront_settings.find_one({"planner_id": OWNER_ID})
    assert stored["slug"] == published["slug"] == "published-first-address"
    assert stored["is_published"] is True
    assert stored["published_at"] is not None
    assert stored.get("description") != "Must not overwrite"
