from fastapi import HTTPException
from bson import ObjectId
from app.core.database import mongo
from app.models.plus_one import PlusOneModel
from datetime import datetime


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
        """
        Add a plus-one with race condition protection.

        Uses "insert then verify" pattern:
        1. Validate guest permissions
        2. Insert the plus-one document
        3. Count total plus-ones AFTER insert
        4. If count exceeds limit, rollback (delete) and return error

        This prevents concurrent requests from both succeeding when only one slot remains.
        """
        guest_collection = mongo.get_guest_collection()
        inserted_id = None

        try:
            # Validate guest_id format
            try:
                guest_id = ObjectId(plus_one_data.guest_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid guest_id format")

            guest_id_str = str(guest_id)

            # Get guest to check permissions
            guest = await guest_collection.find_one({"_id": guest_id})

            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            if not guest.get("plus_one_allowed", False):
                raise HTTPException(status_code=403, detail="Plus-ones not allowed for this guest")

            max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)

            # Quick pre-check (not authoritative due to race conditions)
            current_count = await self.collection.count_documents({"guest_id": guest_id_str})
            if current_count >= max_plus_ones:
                raise HTTPException(
                    status_code=400,
                    detail=f"Maximum number of plus-ones ({max_plus_ones}) already reached"
                )

            # Insert the plus-one document
            doc = plus_one_data.dict()
            doc["guest_id"] = guest_id_str  # Normalize to string
            doc["created_at"] = datetime.utcnow()
            result = await self.collection.insert_one(doc)
            inserted_id = result.inserted_id

            # CRITICAL: Re-count AFTER insert to handle race conditions
            # If two concurrent requests both pass the pre-check, only one should succeed
            final_count = await self.collection.count_documents({"guest_id": guest_id_str})

            if final_count > max_plus_ones:
                # Race condition detected! Another request inserted at the same time.
                # Rollback our insert.
                await self.collection.delete_one({"_id": inserted_id})
                raise HTTPException(
                    status_code=409,  # Conflict
                    detail=f"Maximum number of plus-ones ({max_plus_ones}) reached. Please try again."
                )

            # Update guest if all slots now filled
            if final_count >= max_plus_ones:
                await guest_collection.update_one(
                    {"_id": guest_id},
                    {"$set": {"plus_one_submitted": True, "updated_at": datetime.utcnow()}}
                )

            return {"id": str(inserted_id), "message": "Plus-one added successfully"}

        except HTTPException:
            raise
        except Exception as e:
            # If we inserted but failed somewhere, try to clean up
            if inserted_id:
                try:
                    await self.collection.delete_one({"_id": inserted_id})
                except Exception:
                    pass  # Best effort cleanup
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

    async def get_plus_ones_by_wedding_id(self, wedding_id: str):
        try:
            guest_collection = mongo.get_guest_collection()
            guests = await guest_collection.find({"wedding_id": wedding_id}).to_list(length=None)
            guest_ids = [str(g["_id"]) for g in guests]

            results = await self.collection.find({"guest_id": {"$in": guest_ids}}).to_list(length=None)
            for r in results:
                r["id"] = str(r["_id"])
                r.pop("_id", None)
            return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve plus-ones: {str(e)}")

    async def delete_plus_one(self, plus_one_id: str):
        """
        Delete a plus-one and update guest's submission status.

        Handles guest_id stored as either string or ObjectId for backward compatibility.
        """
        try:
            # Validate plus_one_id format
            try:
                plus_one_obj_id = ObjectId(plus_one_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid plus-one id format")

            # Get plus-one to find guest_id
            plus_one = await self.collection.find_one({"_id": plus_one_obj_id})
            if not plus_one:
                raise HTTPException(status_code=404, detail="Plus-one not found")

            guest_id_raw = plus_one["guest_id"]

            # Normalize guest_id - try to convert to ObjectId for guest lookup
            guest_obj_id = None
            guest_id_str = str(guest_id_raw) if guest_id_raw else None

            if guest_id_str:
                try:
                    guest_obj_id = ObjectId(guest_id_str)
                except Exception:
                    pass  # guest_id might not be valid ObjectId format

            # Delete the plus-one
            await self.collection.delete_one({"_id": plus_one_obj_id})

            # Update guest's plus_one_submitted status if needed
            if guest_id_str:
                guest_collection = mongo.get_guest_collection()

                # Look up guest by ObjectId (guests._id is always ObjectId)
                guest = None
                if guest_obj_id:
                    guest = await guest_collection.find_one({"_id": guest_obj_id})

                if guest:
                    # Count remaining plus-ones (using string guest_id as stored in plus_ones)
                    current_count = await self.collection.count_documents({"guest_id": guest_id_str})
                    max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)

                    # If we now have room for more plus-ones, set submitted to False
                    if current_count < max_plus_ones:
                        await guest_collection.update_one(
                            {"_id": guest_obj_id},
                            {"$set": {"plus_one_submitted": False, "updated_at": datetime.utcnow()}}
                        )

            return {"message": "Plus-one deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete plus-one: {str(e)}")
