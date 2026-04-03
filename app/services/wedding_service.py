from fastapi import HTTPException
from app.core.database import mongo
from app.models.wedding import WeddingModel
from app.utils.event_time import normalize_optional_event_time
from app.utils.serializers import serialize_mongo_doc
from app.utils.id_utils import normalize_doc_id
from typing import List, Dict, Any, Union, Optional
from datetime import datetime, timezone
from bson import ObjectId

# import re


class WeddingService:
    def __init__(self):
        self.collection = mongo.db["weddings"]

    def _normalize_event_times(self, wedding_data: Dict[str, Any]) -> Dict[str, Any]:
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
                event_label = str(event.get("type") or f"event {index + 1}").replace("_", " ")
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
                slug = f"{base_slug}-{int(datetime.now(timezone.utc).timestamp())}"
                break

        return slug

    async def create_wedding(self, wedding: Union[WeddingModel, Dict[str, Any]]):
        """Create a new wedding"""
        try:
            if isinstance(wedding, dict):
                wedding_dict = wedding
            else:
                wedding_dict = wedding.model_dump(by_alias=True)

            wedding_dict = self._normalize_event_times(wedding_dict)

            # Normalize _id to string for storage consistency
            if "_id" in wedding_dict and not isinstance(wedding_dict["_id"], str):
                wedding_dict["_id"] = str(wedding_dict["_id"])
            # Track billing period marker
            if "billed_period" not in wedding_dict:
                current_month = datetime.now(timezone.utc).strftime("%Y-%m")
                wedding_dict["billed_period"] = current_month
            wedding_dict.setdefault("meter_pending", False)

            # Check if wedding ID already exists
            existing = await self.collection.find_one({"_id": wedding_dict["_id"]})
            if existing:
                raise HTTPException(status_code=400, detail="Wedding ID already exists")

            # Ensure slug is unique (prevent collisions across planners)
            if "slug" in wedding_dict and wedding_dict["slug"]:
                wedding_dict["slug"] = await self._ensure_unique_slug(
                    wedding_dict["slug"]
                )

            await self.collection.insert_one(wedding_dict)
            return {
                "message": "Wedding created successfully",
                "id": wedding_dict["_id"],
                "slug": wedding_dict.get("slug"),
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error creating wedding: {str(e)}"
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
                status_code=500, detail=f"Error retrieving wedding: {str(e)}"
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
                status_code=500, detail=f"Error retrieving wedding: {str(e)}"
            )

    async def list_weddings(self) -> List[dict]:
        """List all weddings"""
        try:
            weddings = await self.collection.find().to_list(length=None)
            for wedding in weddings:
                normalize_doc_id(wedding)
            return serialize_mongo_doc(weddings)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing weddings: {str(e)}"
            )

    async def list_weddings_for_planner(self, planner_email: str, accessible_ids: Optional[List[str]] = None, page: int = 1, limit: int = 50, search: Optional[str] = None) -> dict:
        """
        List weddings assigned to a specific planner with pagination.

        Args:
            planner_email: Email of the planner
            accessible_ids: Optional list of wedding IDs to filter by (for team members with "assigned" access)
            page: Page number for pagination (default 1)
            limit: Number of items per page (default 50)
            search: Optional search term to filter by wedding name or other fields
        """
        try:
            from math import ceil

            query = {"assigned_planner_email": planner_email}
            # Apply team member wedding scope filter if provided
            if accessible_ids is not None:
                query["_id"] = {"$in": [ObjectId(id) if len(id) == 24 else id for id in accessible_ids]}

            # Add search filter if provided
            if search:
                query["$or"] = [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"couple_name": {"$regex": search, "$options": "i"}},
                    {"venue": {"$regex": search, "$options": "i"}}
                ]

            # Count total matching documents
            total = await self.collection.count_documents(query)

            # Calculate skip and pages
            skip = (page - 1) * limit
            pages = ceil(total / limit) if total > 0 else 1

            weddings = await self.collection.find(query).skip(skip).limit(limit).to_list(length=None)
            for wedding in weddings:
                normalize_doc_id(wedding)

            return {
                "weddings": serialize_mongo_doc(weddings),
                "total": total,
                "page": page,
                "pages": pages,
                "limit": limit
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing weddings for planner: {str(e)}"
            )

    async def list_weddings_with_planner_info(self, page: int = 1, limit: int = 50, search: Optional[str] = None) -> dict:
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
                    {"assigned_planner_email": {"$regex": search, "$options": "i"}}
                ]

            # Count total matching documents
            total = await self.collection.count_documents(query)

            # Calculate skip and pages
            skip = (page - 1) * limit
            pages = ceil(total / limit) if total > 0 else 1

            weddings = await self.collection.find(query).skip(skip).limit(limit).to_list(length=None)
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
                "limit": limit
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing weddings: {str(e)}"
            )

    async def update_wedding(self, wedding_id: str, wedding_data: dict):
        """Update a wedding"""
        try:
            # Remove _id from update data if present
            wedding_data.pop("_id", None)
            wedding_data = self._normalize_event_times(wedding_data)

            result = await self.collection.update_one(
                {"_id": wedding_id}, {"$set": wedding_data}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")

            return {"message": "Wedding updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error updating wedding: {str(e)}"
            )

    async def delete_wedding(self, wedding_id: str):
        """Delete a wedding"""
        try:
            result = await self.collection.delete_one({"_id": wedding_id})

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")

            return {"message": "Wedding deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error deleting wedding: {str(e)}"
            )
