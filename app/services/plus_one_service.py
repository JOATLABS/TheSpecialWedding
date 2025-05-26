from fastapi import HTTPException
from bson import ObjectId
from app.core.database import mongo
from app.models.plus_one import PlusOneModel

class PlusOneService:
    def __init__(self):
        self.collection = mongo.db["plus_ones"]

    def add_plus_one(self, plus_one_data: PlusOneModel):
        try:
            # Get guest to check limits
            guest_collection = mongo.get_guest_collection()
            guest = guest_collection.find_one({"_id": plus_one_data.guest_id})
            
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            
            if not guest.get("plus_one_allowed", False):
                raise HTTPException(status_code=403, detail="Plus-ones not allowed for this guest")
            
            # Check number limit
            max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)
            current_count = self.collection.count_documents({"guest_id": plus_one_data.guest_id})
            
            if current_count >= max_plus_ones:
                raise HTTPException(status_code=400, detail=f"Maximum number of plus-ones ({max_plus_ones}) already reached")
            
            doc = plus_one_data.dict()
            result = self.collection.insert_one(doc)
            
            # Update guest if all slots filled
            if current_count + 1 >= max_plus_ones:
                guest_collection.update_one(
                    {"_id": plus_one_data.guest_id},
                    {"$set": {"plus_one_submitted": True, "updated_at": mongo.client.server_info()['localTime']}}
                )
            
            return {"id": str(result.inserted_id), "message": "Plus-one added successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add plus-one: {str(e)}")

    def get_plus_ones_by_guest(self, guest_id: str):
        try:
            results = list(self.collection.find({"guest_id": guest_id}))
            for r in results:
                r["id"] = str(r["_id"])
                r.pop("_id", None)
            return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve plus-ones: {str(e)}")

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
                        {"$set": {"plus_one_submitted": False, "updated_at": mongo.client.server_info()['localTime']}}
                    )
            
            return {"message": "Plus-one deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete plus-one: {str(e)}")