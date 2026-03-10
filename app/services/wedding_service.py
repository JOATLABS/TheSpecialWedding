from fastapi import HTTPException
from app.core.database import mongo
from app.models.wedding import WeddingModel
from app.utils.serializers import serialize_mongo_doc
from typing import List, Dict, Any, Union
from datetime import datetime, timezone

# import re


class WeddingService:
    def __init__(self):
        self.collection = mongo.db["weddings"]

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
            return serialize_mongo_doc(weddings)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing weddings: {str(e)}"
            )

    async def list_weddings_for_planner(self, planner_email: str) -> List[dict]:
        """List weddings assigned to a specific planner"""
        try:
            weddings = await self.collection.find(
                {"assigned_planner_email": planner_email}
            ).to_list(length=None)
            # Convert ObjectId to string for JSON serialization
            for wedding in weddings:
                wedding["id"] = str(wedding["_id"])
                wedding["_id"] = str(wedding["_id"])
            return weddings
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing weddings for planner: {str(e)}"
            )

    async def list_weddings_with_planner_info(self) -> List[dict]:
        """List all weddings with enhanced planner information for admin interface"""
        try:
            weddings = await self.collection.find().to_list(length=None)
            # Convert ObjectId to string and add admin-specific fields
            for wedding in weddings:
                wedding["id"] = str(wedding["_id"])
                wedding["_id"] = str(wedding["_id"])
                # Ensure all expected fields exist
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

            return weddings
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing weddings: {str(e)}"
            )

    async def update_wedding(self, wedding_id: str, wedding_data: dict):
        """Update a wedding"""
        try:
            # Remove _id from update data if present
            wedding_data.pop("_id", None)

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
