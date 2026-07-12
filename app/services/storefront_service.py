"""Canonical planner storefront settings and public projection service."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any
import unicodedata

from fastapi import HTTPException, status
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.constants.roles import is_wedding_planner_role
from app.constants.storefront import RESERVED_STOREFRONT_SLUGS
from app.core.database import mongo
from app.models.storefront import (
    PublicPackage,
    PublicPlanner,
    PublicReview,
    PublicStorefrontResponse,
    PublicStorefrontSettings,
    StorefrontAccessResponse,
    StorefrontSettingsResponse,
    StorefrontSettingsUpdate,
)
from app.services.storefront_entitlement_service import (
    StorefrontEntitlementResolutionError,
    StorefrontEntitlementService,
    storefront_entitlement_service,
)
from app.utils.planner_ownership import normalize_planner_id, normalize_query_id


DEFAULT_THEME_COLOR = "#0f172a"
logger = logging.getLogger(__name__)


def normalize_storefront_slug(value: str) -> str:
    """Return a stable lowercase ASCII slug or reject an unsafe identifier."""

    if not isinstance(value, str):
        raise ValueError("Storefront slug must be text")
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    normalized = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not 3 <= len(normalized) <= 64:
        raise ValueError("Storefront slug must be between 3 and 64 characters")
    if normalized in RESERVED_STOREFRONT_SLUGS:
        raise ValueError("This storefront slug is reserved")
    return normalized


class StorefrontService:
    """Own planner-scoped settings and allowlisted public storefront reads."""

    def __init__(
        self,
        mongo_client: Any | None = None,
        entitlement_service: StorefrontEntitlementService | None = None,
        *,
        domain_service: Any | None = None,
        media_service: Any | None = None,
    ):
        self._mongo = mongo_client or mongo
        self._entitlements = entitlement_service or storefront_entitlement_service
        if domain_service is None:
            from app.services.storefront_domain_service import (
                storefront_domain_service,
            )

            domain_service = storefront_domain_service
        self._domains = domain_service
        if media_service is None:
            from app.services.storefront_media_service import storefront_media_service

            media_service = storefront_media_service
        self._media = media_service

    @staticmethod
    def _owner_data(owner: Any) -> dict:
        if isinstance(owner, dict):
            return owner
        user_data = dict(getattr(owner, "user_data", None) or {})
        role = getattr(owner, "role", None)
        if role:
            user_data["role"] = role
        return user_data

    @classmethod
    def _owner_id(cls, owner: Any) -> str:
        user_data = cls._owner_data(owner)
        owner_id = normalize_planner_id(user_data.get("_id"))
        if not owner_id or not is_wedding_planner_role(user_data.get("role")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Planner-owner access required",
            )
        return owner_id

    async def _resolve_owner_entitlements(self, owner: Any):
        user_data = self._owner_data(owner)
        self._owner_id(user_data)
        try:
            return await self._entitlements.resolve_for_owner(user_data)
        except StorefrontEntitlementResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront eligibility is temporarily unavailable",
            ) from exc

    async def _require_storefront(self, owner: Any):
        entitlements = await self._resolve_owner_entitlements(owner)
        if not entitlements.storefront_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "message": "Planner Storefront is not included in the current plan",
                    "feature": "planner_storefront",
                    "upgrade_required": True,
                },
            )
        return entitlements

    async def get_access(self, owner: Any) -> dict:
        entitlements = await self._resolve_owner_entitlements(owner)
        return StorefrontAccessResponse(
            plan_id=entitlements.plan_id,
            storefront_enabled=entitlements.storefront_enabled,
            custom_domain_enabled=entitlements.custom_domain_enabled,
        ).model_dump()

    async def get_settings(self, owner: Any) -> dict | None:
        owner_id = self._owner_id(owner)
        await self._require_storefront(owner)
        await self._media.recover_pending_settings_assets(owner)
        settings = await self._mongo.db["storefront_settings"].find_one(
            {"planner_id": owner_id}
        )
        if not settings:
            return None
        if not settings.get("slug"):
            settings = dict(settings)
            settings["slug"] = await self._default_slug(owner_id, settings.get("title"))
            settings["_slug_persisted"] = False
        return self._serialize_settings(settings)

    async def update_settings(
        self, owner: Any, payload: StorefrontSettingsUpdate
    ) -> dict:
        owner_id = self._owner_id(owner)
        await self._require_storefront(owner)
        collection = self._mongo.db["storefront_settings"]
        # Finish or roll back any durable handoff left by a crashed request
        # before accepting another edit. Public serializers never project the
        # pending fields, so the previous stable image remains visible until
        # this recovery promotes an exactly fenced claim.
        await self._media.recover_pending_settings_assets(owner)
        requested_changes = payload.model_dump(exclude_unset=True)
        explicit_asset_changes = {
            field: requested_changes[field]
            for field in ("hero_asset_id", "about_asset_id")
            if field in requested_changes
        }
        for field_name in explicit_asset_changes:
            requested_changes.pop(field_name, None)
        requested_slug = requested_changes.pop("slug", None)
        slug_was_explicit = requested_slug is not None
        normalized_requested_slug: str | None = None
        if slug_was_explicit:
            try:
                normalized_requested_slug = normalize_storefront_slug(requested_slug)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(exc),
                ) from exc

        # Nullable authored fields intentionally clear when explicitly sent as
        # null. Optional booleans/theme/slug use null to mean "leave unchanged".
        for optional_control in (
            "packages_enabled",
            "reviews_enabled",
            "is_published",
            "theme_color",
        ):
            if requested_changes.get(optional_control) is None:
                requested_changes.pop(optional_control, None)

        # Retry a stale compare-and-set against the latest row. This keeps
        # publication and slug locking atomic while allowing unrelated edits to
        # merge without re-sending an old slug snapshot.
        for attempt in range(3):
            current = await collection.find_one({"planner_id": owner_id})
            now = datetime.now(timezone.utc)

            if normalized_requested_slug is not None:
                slug = normalized_requested_slug
            elif current and current.get("slug"):
                slug = current["slug"]
            else:
                slug = await self._default_slug(
                    owner_id,
                    requested_changes.get("title") or (current or {}).get("title"),
                )

            was_ever_published = bool(
                current
                and (current.get("published_at") or current.get("is_published") is True)
            )
            if (
                current
                and was_ever_published
                and current.get("slug")
                and slug_was_explicit
                and slug != current["slug"]
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The storefront slug cannot change after first publication; "
                        "a redirect lifecycle is required to preserve existing links"
                    ),
                )

            duplicate = await collection.find_one(
                {"slug": slug, "planner_id": {"$ne": owner_id}}, {"_id": 1}
            )
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This storefront slug is already in use",
                )

            asset_claim: dict | None = None
            attempt_changes = dict(requested_changes)
            pending_unsets: dict[str, str] = {}
            displaced_pending_claims: dict[str, list[dict[str, str]]] = {}
            if explicit_asset_changes:
                asset_claim = await self._media.claim_settings_assets(
                    owner, **explicit_asset_changes
                )
                validated_assets = asset_claim.get("values")
                if not isinstance(validated_assets, dict):
                    raise RuntimeError(
                        "Storefront media service returned an invalid claim receipt"
                    )
                claim_id = asset_claim.get("claim_id")
                if not isinstance(claim_id, str):
                    raise RuntimeError(
                        "Storefront media service returned an invalid claim receipt"
                    )
                for field_name, asset_id in validated_assets.items():
                    slot = field_name.removesuffix("_asset_id")
                    pending_asset_field = f"pending_{slot}_asset_id"
                    pending_claim_field = f"pending_{slot}_claim_id"
                    if asset_id is None:
                        # Explicit clear is immediately authoritative, but it
                        # also fences a paused promoter by removing its token.
                        attempt_changes[field_name] = None
                        pending_unsets[pending_asset_field] = ""
                        pending_unsets[pending_claim_field] = ""
                    else:
                        # New bytes are never made public by the settings CAS.
                        # Only the post-attach promotion may replace stable.
                        attempt_changes[pending_asset_field] = asset_id
                        attempt_changes[pending_claim_field] = claim_id

            if current:
                for field_name in explicit_asset_changes:
                    slot = field_name.removesuffix("_asset_id")
                    pending_asset_field = f"pending_{slot}_asset_id"
                    pending_claim_field = f"pending_{slot}_claim_id"
                    previous_asset_id = current.get(pending_asset_field)
                    previous_claim_id = current.get(pending_claim_field)
                    next_asset_id = attempt_changes.get(pending_asset_field)
                    next_claim_id = attempt_changes.get(pending_claim_field)
                    if (
                        isinstance(previous_asset_id, str)
                        and isinstance(previous_claim_id, str)
                        and (previous_asset_id, previous_claim_id)
                        != (next_asset_id, next_claim_id)
                    ):
                        displaced_pending_claims.setdefault(
                            previous_claim_id, []
                        ).append(
                            {
                                "asset_id": previous_asset_id,
                                "slot": slot,
                                "field_name": field_name,
                            }
                        )

            update: dict[str, Any] = {
                "planner_id": owner_id,
                "updated_at": now,
                **attempt_changes,
            }
            if slug_was_explicit or not current or not current.get("slug"):
                update["slug"] = slug

            if current and not current.get("created_at"):
                update["created_at"] = now
            if not current:
                update.update(
                    {
                        "slug": slug,
                        "created_at": now,
                        "title": attempt_changes.get("title"),
                        "description": attempt_changes.get("description"),
                        "contact_email": attempt_changes.get("contact_email"),
                        "contact_phone": attempt_changes.get("contact_phone"),
                        "hero_asset_id": attempt_changes.get("hero_asset_id"),
                        "about_asset_id": attempt_changes.get("about_asset_id"),
                        "theme_color": attempt_changes.get("theme_color")
                        or DEFAULT_THEME_COLOR,
                        "packages_enabled": attempt_changes.get(
                            "packages_enabled", True
                        ),
                        "reviews_enabled": attempt_changes.get("reviews_enabled", True),
                        "is_published": attempt_changes.get("is_published", False),
                        "published_at": None,
                    }
                )

            requested_publication = attempt_changes.get("is_published")
            if requested_publication is True and not (
                current and current.get("published_at")
            ):
                update["published_at"] = now
            elif (
                current
                and current.get("is_published") is True
                and not current.get("published_at")
            ):
                update["published_at"] = current.get("updated_at") or now

            if current:
                write_filter: dict[str, Any] = {
                    "_id": current["_id"],
                    "planner_id": owner_id,
                }
                if "revision" in current:
                    write_filter["revision"] = current.get("revision")
                else:
                    write_filter["revision"] = {"$exists": False}

            try:
                if current:
                    write_operation: dict[str, Any] = {
                        "$set": update,
                        "$inc": {"revision": 1},
                    }
                    if pending_unsets:
                        write_operation["$unset"] = pending_unsets
                    result = await collection.update_one(
                        write_filter,
                        write_operation,
                        upsert=False,
                    )
                    write_succeeded = bool(getattr(result, "modified_count", 0))
                else:
                    # Creation must be insert-only. An upsert filtered only by
                    # planner_id could match and overwrite a row inserted by a
                    # concurrent first save after this request's read.
                    result = await collection.insert_one({**update, "revision": 1})
                    write_succeeded = bool(getattr(result, "inserted_id", None))
            except DuplicateKeyError as exc:
                if asset_claim:
                    await self._media.release_settings_asset_claims(owner, asset_claim)
                if attempt < 2:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This storefront slug is already in use",
                ) from exc
            except Exception:
                if asset_claim:
                    # A driver/network exception may be raised after Mongo has
                    # applied the write. Reconcile against the canonical row;
                    # blindly releasing here could re-open the cleanup race.
                    await self._media.reconcile_settings_asset_claims(
                        owner, asset_claim
                    )
                raise

            if not write_succeeded:
                if asset_claim:
                    await self._media.release_settings_asset_claims(owner, asset_claim)
                continue

            for (
                displaced_claim_id,
                displaced_entries,
            ) in displaced_pending_claims.items():
                try:
                    await self._media.release_settings_asset_claims(
                        owner,
                        {
                            "owner_id": owner_id,
                            "claim_id": displaced_claim_id,
                            "claimed_assets": displaced_entries,
                            "values": {},
                        },
                    )
                except Exception:
                    # The settings token is already fenced out. Keep the save
                    # authoritative and retain the lifecycle receipt for a
                    # later cleanup/recovery pass.
                    logger.exception(
                        "Failed to release displaced storefront pending claim %s",
                        displaced_claim_id,
                    )

            try:
                saved = await collection.find_one({"planner_id": owner_id})
            except Exception:
                if asset_claim:
                    await self._media.reconcile_settings_asset_claims(
                        owner, asset_claim
                    )
                raise
            if not saved:
                if asset_claim:
                    await self._media.reconcile_settings_asset_claims(
                        owner, asset_claim
                    )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storefront settings could not be read after saving",
                )
            if asset_claim:
                try:
                    await self._media.attach_settings_asset_claims(owner, asset_claim)
                    await self._media.promote_settings_asset_claims(owner, asset_claim)
                except Exception:
                    # Reconcile the exact pending token. It may complete a
                    # committed write or release a losing claim, but can never
                    # promote over a newer settings revision/token.
                    await self._media.reconcile_settings_asset_claims(
                        owner, asset_claim
                    )
            saved = await collection.find_one({"planner_id": owner_id})
            if not saved:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storefront settings could not be read after saving",
                )
            expected_assets = asset_claim.get("values", {}) if asset_claim else {}
            if any(
                saved.get(field_name) != asset_id
                for field_name, asset_id in expected_assets.items()
            ):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storefront image update is pending recovery; retry later",
                )
            replaced_asset_ids = [
                current.get(field_name)
                for field_name, asset_id in expected_assets.items()
                if current
                and current.get(field_name)
                and current.get(field_name) != asset_id
            ]
            for replaced_asset_id in replaced_asset_ids:
                try:
                    await self._media.release_if_unreferenced(owner, replaced_asset_id)
                except Exception:
                    # The old image is no longer publicly referenced. Keep a
                    # repairable lifecycle receipt rather than failing an
                    # already-durable settings edit.
                    logger.exception(
                        "Failed to release replaced storefront asset %s",
                        replaced_asset_id,
                    )
            return self._serialize_settings(saved)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Storefront settings changed concurrently; reload and retry",
        )

    async def _default_slug(self, owner_id: str, title: str | None) -> str:
        owner = await self._mongo.get_users_collection().find_one(
            {"_id": normalize_query_id(owner_id)}, {"company_name": 1}
        )
        source = (
            (owner or {}).get("company_name") or title or f"planner-{owner_id[-8:]}"
        )
        try:
            candidate = normalize_storefront_slug(source)
        except ValueError:
            candidate = f"planner-{owner_id[-8:].lower()}"
        collection = self._mongo.db["storefront_settings"]
        if not await collection.find_one({"slug": candidate}, {"_id": 1}):
            return candidate
        suffixed = f"{candidate[:55].rstrip('-')}-{owner_id[-8:].lower()}"
        return normalize_storefront_slug(suffixed)

    async def get_owner_preview(self, owner: Any, slug: str) -> dict:
        owner_id = self._owner_id(owner)
        await self._require_storefront(owner)
        normalized = self._normalize_lookup_slug(slug)
        settings = await self._mongo.db["storefront_settings"].find_one(
            {"planner_id": owner_id, "slug": normalized}
        )
        if not settings:
            self._raise_not_found()
        return await self._build_public_dto(settings)

    async def get_public_storefront(self, identifier: str) -> dict:
        context = await self.resolve_public_context(identifier)
        return await self._build_public_dto(context["settings"])

    async def resolve_public_context(self, identifier: str) -> dict:
        """Resolve the canonical published owner context used by every public action."""

        if isinstance(identifier, str) and "." in identifier:
            mapping = await self._domains.resolve_active_hostname(identifier)
            if not mapping:
                self._raise_not_found()
            mapped_owner_id = normalize_planner_id(mapping.get("planner_id"))
            if not mapped_owner_id:
                self._raise_not_found()
            settings = await self._mongo.db["storefront_settings"].find_one(
                {
                    "planner_id": mapped_owner_id,
                    "slug": {"$type": "string"},
                    "is_published": True,
                }
            )
        else:
            slug = self._normalize_lookup_slug(identifier)
            settings = await self._mongo.db["storefront_settings"].find_one(
                {"slug": slug, "is_published": True}
            )
        if not settings:
            self._raise_not_found()

        owner_id = normalize_planner_id(settings.get("planner_id"))
        if not owner_id:
            self._raise_not_found()
        try:
            entitlements = await self._entitlements.resolve_for_planner_id(owner_id)
        except StorefrontEntitlementResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront eligibility is temporarily unavailable",
            ) from exc
        if not entitlements.storefront_enabled:
            self._raise_not_found()
        return {"owner_id": owner_id, "slug": settings["slug"], "settings": settings}

    @staticmethod
    def _normalize_lookup_slug(value: str) -> str:
        try:
            return normalize_storefront_slug(value)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Storefront not found",
            ) from exc

    @staticmethod
    def _raise_not_found() -> None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Storefront not found",
        )

    @staticmethod
    def _serialize_settings(settings: dict) -> dict:
        model = StorefrontSettingsResponse(
            slug=settings["slug"],
            title=settings.get("title"),
            description=settings.get("description"),
            contact_email=settings.get("contact_email"),
            contact_phone=settings.get("contact_phone"),
            hero_asset_id=settings.get("hero_asset_id"),
            about_asset_id=settings.get("about_asset_id"),
            theme_color=settings.get("theme_color") or DEFAULT_THEME_COLOR,
            packages_enabled=settings.get("packages_enabled", True),
            reviews_enabled=settings.get("reviews_enabled", True),
            is_published=settings.get("is_published") is True,
            published_at=settings.get("published_at"),
            created_at=settings.get("created_at"),
            updated_at=settings.get("updated_at"),
            revision=settings.get("revision", 0),
            slug_editable=not bool(
                settings.get("published_at") or settings.get("is_published") is True
            ),
            slug_persisted=settings.get("_slug_persisted", True),
        )
        return model.model_dump()

    async def _asset_url(self, owner_id: str, asset_id: str | None) -> str | None:
        if not asset_id:
            return None
        asset = await self._mongo.db["storefront_assets"].find_one(
            {
                "_id": normalize_query_id(asset_id),
                "owner_id": owner_id,
                # ``attaching`` is a validated final object protected from
                # cleanup while post-write lifecycle bookkeeping reconciles.
                "state": {"$in": ["ready", "attaching", "attached"]},
            },
            {"cdn_url": 1},
        )
        return asset.get("cdn_url") if asset else None

    async def _build_public_dto(self, settings: dict) -> dict:
        owner_id = normalize_planner_id(settings.get("planner_id"))
        if not owner_id:
            self._raise_not_found()
        planner = await self._mongo.get_users_collection().find_one(
            {"_id": normalize_query_id(owner_id)},
            {"company_name": 1, "first_name": 1, "profile_image_url": 1},
        )
        if not planner:
            self._raise_not_found()

        public_settings = PublicStorefrontSettings(
            title=settings.get("title"),
            description=settings.get("description"),
            contact_email=settings.get("contact_email"),
            contact_phone=settings.get("contact_phone"),
            hero_image_url=await self._asset_url(
                owner_id, settings.get("hero_asset_id")
            ),
            about_image_url=await self._asset_url(
                owner_id, settings.get("about_asset_id")
            ),
            theme_color=settings.get("theme_color") or DEFAULT_THEME_COLOR,
            packages_enabled=settings.get("packages_enabled", True),
            reviews_enabled=settings.get("reviews_enabled", True),
        )

        packages: list[dict] = []
        if public_settings.packages_enabled:
            package_cursor = self._mongo.db["packages"].find(
                {
                    "planner_id": owner_id,
                    "status": "active",
                    "is_template": False,
                },
                {
                    "_id": 1,
                    "name": 1,
                    "description": 1,
                    "total_amount": 1,
                    "currency": 1,
                    "services.name": 1,
                    "services.description": 1,
                },
            )
            for package in await package_cursor.to_list(length=50):
                services = [
                    {
                        "name": service.get("name"),
                        "description": service.get("description"),
                    }
                    for service in package.get("services", [])
                    if isinstance(service, dict) and service.get("name")
                ]
                try:
                    public_package = PublicPackage.model_validate(
                        {
                            "_id": str(package.get("_id")),
                            "name": package.get("name"),
                            "description": package.get("description"),
                            "total_amount": package.get("total_amount"),
                            "currency": package.get("currency") or "USD",
                            "services": services,
                        }
                    )
                except ValidationError:
                    continue
                packages.append(public_package.model_dump(by_alias=True))

        reviews: list[dict] = []
        if public_settings.reviews_enabled:
            review_cursor = self._mongo.db["planner_reviews"].find(
                {"planner_id": owner_id, "is_published": True},
                {
                    "_id": 1,
                    "author_name": 1,
                    "rating": 1,
                    "text": 1,
                    "source": 1,
                    "date": 1,
                },
            )
            for review in await review_cursor.to_list(length=20):
                public_review = PublicReview(
                    _id=str(review.get("_id")),
                    author_name=review.get("author_name"),
                    rating=review.get("rating"),
                    text=review.get("text"),
                    source=review.get("source"),
                    date=review.get("date"),
                )
                reviews.append(public_review.model_dump(by_alias=True))

        response = PublicStorefrontResponse(
            slug=settings["slug"],
            storefront=public_settings,
            planner=PublicPlanner(
                company_name=planner.get("company_name"),
                first_name=planner.get("first_name"),
                profile_image_url=planner.get("profile_image_url"),
            ),
            packages=packages,
            reviews=reviews,
        )
        return response.model_dump(by_alias=True)


storefront_service = StorefrontService()
