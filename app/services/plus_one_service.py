from fastapi import HTTPException
from bson import ObjectId
from app.core.database import mongo
from app.models.plus_one import PlusOneModel
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class PlusOneService:
    def __init__(self):
        self.collection = mongo.db["plus_ones"]

    async def get_plus_one(self, plus_one_id: str):
        """Fetch a plus-one by id."""
        try:
            obj_id = ObjectId(plus_one_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid plus-one id")

        plus_one = await self.collection.find_one({"_id": obj_id})
        if not plus_one:
            raise HTTPException(status_code=404, detail="Plus-one not found")

        plus_one["id"] = str(plus_one["_id"])
        plus_one.pop("_id", None)
        return plus_one

    async def add_plus_one(self, plus_one_data: PlusOneModel):
        try:
            guest_collection = mongo.get_guest_collection()
            guest_id = ObjectId(plus_one_data.guest_id)
            guest_id_str = str(guest_id)

            # Get guest to check permissions
            guest = await guest_collection.find_one({"_id": guest_id})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            if not guest.get("plus_one_allowed", False):
                raise HTTPException(status_code=403, detail="Plus-ones not allowed for this guest")

            max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)

            # Use insert-then-verify pattern to prevent race condition
            # This is atomic: insert first, then check count, rollback if over limit
            doc = plus_one_data.dict()
            doc["guest_id"] = guest_id_str  # Ensure consistent string type
            result = await self.collection.insert_one(doc)
            inserted_id = result.inserted_id

            # Verify we haven't exceeded the limit (atomic count after insert)
            current_count = await self.collection.count_documents({"guest_id": guest_id_str})

            if current_count > max_plus_ones:
                # Race condition detected - rollback the insert
                await self.collection.delete_one({"_id": inserted_id})
                raise HTTPException(
                    status_code=400,
                    detail=f"Maximum number of plus-ones ({max_plus_ones}) already reached"
                )

            # Update guest if all slots filled
            if current_count >= max_plus_ones:
                await guest_collection.update_one(
                    {"_id": guest_id},
                    {"$set": {"plus_one_submitted": True, "updated_at": datetime.now(timezone.utc)}}
                )

            return {"id": str(inserted_id), "message": "Plus-one added successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add plus-one: {str(e)}")

    async def get_plus_ones_by_guest(self, guest_id: str):
        try:
            results = await self.collection.find({"guest_id": guest_id}).to_list(length=None)
            for r in results:
                r["id"] = str(r["_id"])
                r.pop("_id", None)
            return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve plus-ones: {str(e)}")

    async def get_plus_ones_by_wedding_id(self, wedding_id: str):
        try:
            # 1. Get all guest IDs for this wedding
            guest_collection = mongo.get_guest_collection()
            guests = await guest_collection.find(
                {"wedding_id": wedding_id},
                projection={"_id": 1}
            ).to_list(length=None)

            if not guests:
                return []

            # Convert ObjectIds to strings (plus_ones store guest_id as string)
            guest_ids = [str(g["_id"]) for g in guests]

            # 2. Find plus-ones for these guests
            results = await self.collection.find(
                {"guest_id": {"$in": guest_ids}}
            ).to_list(length=None)

            for r in results:
                r["id"] = str(r["_id"])
                r.pop("_id", None)

            return results
        except Exception as e:
            logger.error(f"Error fetching plus-ones for wedding {wedding_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve plus-ones for wedding: {str(e)}")

    async def update_plus_one(self, plus_one_id: str, data: dict):
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(plus_one_id)},
                {"$set": data}
            )
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Plus-one not found")
            return {"message": "Plus-one updated successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update plus-one: {str(e)}")

    async def delete_plus_one(self, plus_one_id: str):
        try:
            # Get plus-one to find guest_id
            plus_one = await self.collection.find_one({"_id": ObjectId(plus_one_id)})
            if not plus_one:
                raise HTTPException(status_code=404, detail="Plus-one not found")

            # guest_id is stored as string in plus_ones collection
            guest_id_str = str(plus_one["guest_id"])

            # Delete the plus-one
            await self.collection.delete_one({"_id": ObjectId(plus_one_id)})

            # Update guest's plus_one_submitted status if needed
            guest_collection = mongo.get_guest_collection()

            # Convert to ObjectId for guest collection lookup (guests use ObjectId for _id)
            try:
                guest_object_id = ObjectId(guest_id_str)
            except Exception:
                return {"message": "Plus-one deleted successfully"}

            guest = await guest_collection.find_one({"_id": guest_object_id})
            if guest:
                # Count using string format (plus_ones store guest_id as string)
                current_count = await self.collection.count_documents({"guest_id": guest_id_str})
                max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)

                # If we now have room for more plus-ones, set submitted to False
                if current_count < max_plus_ones:
                    await guest_collection.update_one(
                        {"_id": guest_object_id},
                        {"$set": {"plus_one_submitted": False, "updated_at": datetime.now(timezone.utc)}}
                    )

            return {"message": "Plus-one deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete plus-one: {str(e)}")
