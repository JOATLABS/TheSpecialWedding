import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.core.database import mongo
from app.models.wedding import WeddingCreateModel, WeddingModel
from app.utils.event_time import normalize_optional_event_time
from app.utils.id_utils import normalize_doc_id
from app.utils.planner_ownership import (
    build_wedding_owner_query,
    combine_mongo_filters,
    normalize_query_id,
    resolve_planner_identity,
)
from app.utils.serializers import serialize_mongo_doc


class WeddingService:
    def __init__(self):
        self.collection = mongo.db["weddings"]

    @staticmethod
    def _generate_wedding_id() -> str:
        return f"wedding_{uuid4().hex[:12]}"

    @staticmethod
    def _slugify_couple_names(couple_names: str) -> str:
        slug = re.sub(r"[^a-z0-9\s]", "", couple_names.lower())
        slug = re.sub(r"\s+", "-", slug).strip("-")
        return slug[:50] or "wedding"

    def _normalize_event_times(self, wedding_data: dict[str, Any]) -> dict[str, Any]:
        events = wedding_data.get("events")
        if not isinstance(events, list):
            return wedding_data

        for index, event in enumerate(events):
            if not isinstance(event, dict):
                continue

            details = event.get("details")
            if not isinstance(details, dict) or "time" not in details:
                continue

            try:
                details["time"] = normalize_optional_event_time(details.get("time"))
            except ValueError as exc:
                event_label = str(event.get("type") or f"event {index + 1}").replace(
                    "_", " "
                )
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid time for {event_label}: {exc}",
                )

        return wedding_data

    async def _ensure_unique_slug(self, base_slug: str) -> str:
        """Ensure slug is unique by appending a number suffix if needed"""
        slug = base_slug
        counter = 1

        while True:
            existing = await self.collection.find_one({"slug": slug})
            if not existing:
                return slug
            # Append or increment counter
            counter += 1
            slug = f"{base_slug}-{counter}"
            # Safety limit to prevent infinite loops
            if counter > 100:
                # Use timestamp as fallback
                slug = f"{base_slug}-{int(datetime.now(UTC).timestamp())}"
                break

        return slug

    async def create_wedding(
        self, wedding: WeddingCreateModel | WeddingModel | dict[str, Any]
    ):
        """Create a new wedding"""
        try:
            if isinstance(wedding, dict):
                wedding_dict = wedding
            else:
                wedding_dict = wedding.model_dump(by_alias=True)

            wedding_dict = self._normalize_event_times(wedding_dict)

            if wedding_dict.get("assigned_planner_id") or wedding_dict.get(
                "assigned_planner_email"
            ):
                owner_identity = await resolve_planner_identity(
                    wedding_dict.get("assigned_planner_id"),
                    wedding_dict.get("assigned_planner_email"),
                )
                if owner_identity.get("planner_id"):
                    wedding_dict["assigned_planner_id"] = owner_identity["planner_id"]
                if owner_identity.get("planner_email"):
                    wedding_dict["assigned_planner_email"] = owner_identity[
                        "planner_email"
                    ]

            # Normalize _id to string for storage consistency while treating null
            # payload aliases as missing so we can generate a real identifier.
            wedding_id = wedding_dict.get("_id")
            if wedding_id in (None, ""):
                wedding_dict["_id"] = self._generate_wedding_id()
            elif not isinstance(wedding_id, str):
                wedding_dict["_id"] = str(wedding_id)
            if not wedding_dict.get("slug"):
                wedding_dict["slug"] = self._slugify_couple_names(
                    str(wedding_dict.get("couple_names") or "")
                )
            if not wedding_dict.get("created_at"):
                wedding_dict["created_at"] = datetime.now(UTC)
            # Track billing period marker
            if "billed_period" not in wedding_dict:
                current_month = datetime.now(UTC).strftime("%Y-%m")
                wedding_dict["billed_period"] = current_month
            wedding_dict.setdefault("meter_pending", False)

            # Check if wedding ID already exists
            existing = await self.collection.find_one({"_id": wedding_dict["_id"]})
            if existing:
                raise HTTPException(status_code=400, detail="Wedding ID already exists")

            # Ensure slug is unique (prevent collisions across planners)
            if wedding_dict.get("slug"):
                wedding_dict["slug"] = await self._ensure_unique_slug(
                    wedding_dict["slug"]
                )

            await self.collection.insert_one(wedding_dict)
            try:
                from app.services.aurinko_contacts_sync_service import (
                    aurinko_contacts_sync_service,
                )

                await aurinko_contacts_sync_service.mirror_couple_to_aurinko(
                    str(wedding_dict["_id"])
                )
            except Exception:
                pass
            return {
                "message": "Wedding created successfully",
                "id": wedding_dict["_id"],
                "slug": wedding_dict.get("slug"),
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error creating wedding: {e!s}"
            )

    async def get_wedding(self, wedding_id: str):
        """Get a wedding by ID"""
        try:
            wedding = await self.collection.find_one({"_id": wedding_id})
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")
            normalize_doc_id(wedding)
            return serialize_mongo_doc(wedding)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error retrieving wedding: {e!s}"
            )

    async def get_wedding_by_slug(self, slug: str):
        """Get a wedding by slug"""
        try:
            wedding = await self.collection.find_one({"slug": slug})
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")
            normalize_doc_id(wedding)
            return serialize_mongo_doc(wedding)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error retrieving wedding: {e!s}"
            )

    async def list_weddings(self) -> list[dict]:
        """List all weddings"""
        try:
            weddings = await self.collection.find().to_list(length=None)
            for wedding in weddings:
                normalize_doc_id(wedding)
            return serialize_mongo_doc(weddings)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing weddings: {e!s}"
            )

    async def list_weddings_for_planner(
        self,
        planner_id: str | None,
        planner_email: str | None,
        accessible_ids: list[str] | None = None,
        page: int = 1,
        limit: int = 50,
        search: str | None = None,
    ) -> dict:
        """
        List weddings assigned to a specific planner with pagination.

        Args:
            planner_id: Canonical planner user ID
            planner_email: Planner email mirror for legacy compatibility
            accessible_ids: Optional list of wedding IDs to filter by (for team members with "assigned" access)
            page: Page number for pagination (default 1)
            limit: Number of items per page (default 50)
            search: Optional search term to filter by wedding name or other fields
        """
        try:
            from math import ceil

            owner_query = build_wedding_owner_query(planner_id, planner_email)
            if not owner_query:
                return {
                    "weddings": [],
                    "total": 0,
                    "page": page,
                    "pages": 1,
                    "limit": limit,
                }

            filters: list[dict[str, Any]] = [owner_query]
            if accessible_ids is not None:
                filters.append(
                    {"_id": {"$in": [normalize_query_id(id) for id in accessible_ids]}}
                )

            if search:
                filters.append(
                    {
                        "$or": [
                            {"name": {"$regex": search, "$options": "i"}},
                            {"couple_name": {"$regex": search, "$options": "i"}},
                            {"venue": {"$regex": search, "$options": "i"}},
                        ]
                    }
                )

            query = combine_mongo_filters(*filters)

            # Count total matching documents
            total = await self.collection.count_documents(query)

            # Calculate skip and pages
            skip = (page - 1) * limit
            pages = ceil(total / limit) if total > 0 else 1

            weddings = (
                await self.collection.find(query)
                .skip(skip)
                .limit(limit)
                .to_list(length=None)
            )
            for wedding in weddings:
                normalize_doc_id(wedding)

            return {
                "weddings": serialize_mongo_doc(weddings),
                "total": total,
                "page": page,
                "pages": pages,
                "limit": limit,
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing weddings for planner: {e!s}"
            )

    async def list_weddings_with_planner_info(
        self, page: int = 1, limit: int = 50, search: str | None = None
    ) -> dict:
        """List all weddings with enhanced planner information for admin interface and pagination"""
        try:
            from math import ceil

            query = {}

            # Add search filter if provided
            if search:
                query["$or"] = [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"couple_name": {"$regex": search, "$options": "i"}},
                    {"venue": {"$regex": search, "$options": "i"}},
                    {"assigned_planner_email": {"$regex": search, "$options": "i"}},
                ]

            # Count total matching documents
            total = await self.collection.count_documents(query)

            # Calculate skip and pages
            skip = (page - 1) * limit
            pages = ceil(total / limit) if total > 0 else 1

            weddings = (
                await self.collection.find(query)
                .skip(skip)
                .limit(limit)
                .to_list(length=None)
            )
            for wedding in weddings:
                normalize_doc_id(wedding)
            serialized_weddings = serialize_mongo_doc(weddings)
            # Ensure all expected fields exist
            for wedding in serialized_weddings:
                if "assigned_planner_email" not in wedding:
                    wedding["assigned_planner_email"] = None
                if "assigned_planner_id" not in wedding:
                    wedding["assigned_planner_id"] = None
                if "status" not in wedding:
                    wedding["status"] = "active"
                if "venue" not in wedding:
                    wedding["venue"] = None
                if "guest_count" not in wedding:
                    wedding["guest_count"] = 0
                if "events" not in wedding:
                    wedding["events"] = []

            return {
                "weddings": serialized_weddings,
                "total": total,
                "page": page,
                "pages": pages,
                "limit": limit,
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing weddings: {e!s}"
            )

    async def update_wedding(self, wedding_id: str, wedding_data: dict):
        """Update a wedding"""
        try:
            # Remove _id from update data if present
            wedding_data.pop("_id", None)
            wedding_data = self._normalize_event_times(wedding_data)

            if wedding_data.get("assigned_planner_id") or wedding_data.get(
                "assigned_planner_email"
            ):
                owner_identity = await resolve_planner_identity(
                    wedding_data.get("assigned_planner_id"),
                    wedding_data.get("assigned_planner_email"),
                )
                if owner_identity.get("planner_id"):
                    wedding_data["assigned_planner_id"] = owner_identity["planner_id"]
                if owner_identity.get("planner_email"):
                    wedding_data["assigned_planner_email"] = owner_identity[
                        "planner_email"
                    ]

            result = await self.collection.update_one(
                {"_id": wedding_id}, {"$set": wedding_data}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")

            try:
                from app.services.aurinko_contacts_sync_service import (
                    aurinko_contacts_sync_service,
                )

                await aurinko_contacts_sync_service.mirror_couple_to_aurinko(wedding_id)
            except Exception:
                pass

            return {"message": "Wedding updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error updating wedding: {e!s}"
            )

    async def delete_wedding(self, wedding_id: str):
        """Delete a wedding"""
        try:
            try:
                from app.services.aurinko_contacts_sync_service import (
                    aurinko_contacts_sync_service,
                )

                await aurinko_contacts_sync_service.unmirror_source(
                    source_type="wedding",
                    source_id=wedding_id,
                )
            except Exception:
                pass
            result = await self.collection.delete_one({"_id": wedding_id})

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")

            return {"message": "Wedding deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error deleting wedding: {e!s}"
            )
