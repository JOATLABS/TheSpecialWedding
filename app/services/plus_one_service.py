from fastapi import HTTPException
from bson import ObjectId
from app.core.database import mongo
from app.models.plus_one import PlusOneModel
from datetime import datetime

class PlusOneService:
    def __init__(self):
        self.collection = mongo.db["plus_ones"]

    def add_plus_one(self, plus_one_data: PlusOneModel):
        try:
            # Get guest to check limits
            guest_collection = mongo.get_guest_collection()
            guest_id = ObjectId(plus_one_data.guest_id)
            guest = guest_collection.find_one({"_id": guest_id})
            
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            
            if not guest.get("plus_one_allowed", False):
                raise HTTPException(status_code=403, detail="Plus-ones not allowed for this guest")
            
            # Check number limit
            max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)
            current_count = self.collection.count_documents({"guest_id": str(guest_id)})
            
            if current_count >= max_plus_ones:
                raise HTTPException(status_code=400, detail=f"Maximum number of plus-ones ({max_plus_ones}) already reached")
            
            doc = plus_one_data.dict()
            result = self.collection.insert_one(doc)
            
            # Update guest if all slots filled
            if current_count + 1 >= max_plus_ones:
                guest_collection.update_one(
                    {"_id": guest_id},
                    {"$set": {"plus_one_submitted": True, "updated_at": datetime.utcnow()}}
                )
            
            return {"id": str(result.inserted_id), "message": "Plus-one added successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add plus-one: {str(e)}")

    def get_plus_one(self, plus_one_id: str):
        """Get a single plus-one by ID"""
        try:
            plus_one = self.collection.find_one({"_id": ObjectId(plus_one_id)})
            if plus_one:
                plus_one["id"] = str(plus_one["_id"])
                plus_one.pop("_id", None)
            return plus_one
        except Exception as e:
            return None

    def get_plus_ones_by_guest(self, guest_id: str):
        try:
            results = list(self.collection.find({"guest_id": guest_id}))
            for r in results:
                r["id"] = str(r["_id"])
                r.pop("_id", None)
            return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve plus-ones: {str(e)}")

    def get_bulk_plus_ones_by_wedding(self, wedding_id: str):
        """
        Efficiently fetch all plus-ones for a wedding in a single query.
        Uses MongoDB aggregation pipeline to join guests and plus-ones.
        Returns a dictionary mapping guest_id to their plus-ones array.
        """
        try:
            # Get all guests for this wedding
            guest_collection = mongo.get_guest_collection()
            guests = list(guest_collection.find(
                {"wedding_id": wedding_id},
                {"_id": 1, "name": 1}
            ))

            # Get all guest IDs
            guest_ids = [str(guest["_id"]) for guest in guests]

            # Fetch all plus-ones for these guests in one query
            plus_ones = list(self.collection.find({"guest_id": {"$in": guest_ids}}))

            # Create a mapping of guest_id to plus-ones
            plus_ones_by_guest = {}
            for guest_id in guest_ids:
                plus_ones_by_guest[guest_id] = []

            # Populate the mapping
            for plus_one in plus_ones:
                plus_one["id"] = str(plus_one["_id"])
                plus_one.pop("_id", None)
                guest_id = plus_one["guest_id"]
                if guest_id in plus_ones_by_guest:
                    # Add guest name for frontend convenience
                    guest = next((g for g in guests if str(g["_id"]) == guest_id), None)
                    if guest:
                        plus_one["guest_name"] = guest.get("name", "Unknown Guest")
                    plus_ones_by_guest[guest_id].append(plus_one)

            return {
                "wedding_id": wedding_id,
                "plus_ones_by_guest": plus_ones_by_guest,
                "total_plus_ones": len(plus_ones),
                "guests_with_plus_ones": len([g for g in plus_ones_by_guest.values() if g])
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve bulk plus-ones: {str(e)}")

    def update_plus_one(self, plus_one_id: str, data: dict):
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(plus_one_id)},
                {"$set": data}
            )
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Plus-one not found")
            return {"message": "Plus-one updated successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update plus-one: {str(e)}")

    def delete_plus_one(self, plus_one_id: str):
        try:
            # Get plus-one to find guest_id
            plus_one = self.collection.find_one({"_id": ObjectId(plus_one_id)})
            if not plus_one:
                raise HTTPException(status_code=404, detail="Plus-one not found")
            
            guest_id = plus_one["guest_id"]
            
            # Delete the plus-one
            result = self.collection.delete_one({"_id": ObjectId(plus_one_id)})
            
            # Update guest's plus_one_submitted status if needed
            guest_collection = mongo.get_guest_collection()
            guest = guest_collection.find_one({"_id": guest_id})
            if guest:
                current_count = self.collection.count_documents({"guest_id": guest_id})
                max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)
                
                # If we now have room for more plus-ones, set submitted to False
                if current_count < max_plus_ones:
                    guest_collection.update_one(
                        {"_id": guest_id},
                        {"$set": {"plus_one_submitted": False, "updated_at": datetime.utcnow()}}
                    )
            
            return {"message": "Plus-one deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete plus-one: {str(e)}")