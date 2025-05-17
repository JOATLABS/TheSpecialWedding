from fastapi import HTTPException
from bson import ObjectId
from app.core.database import mongo
from app.models.plus_one import PlusOneModel

class PlusOneService:
    def __init__(self):
        self.collection = mongo.db["plus_ones"]

    def add_plus_one(self, plus_one_data: PlusOneModel):
        try:
            doc = plus_one_data.dict()
            result = self.collection.insert_one(doc)
            return {"id": str(result.inserted_id), "message": "Plus-one added successfully"}
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
            result = self.collection.delete_one({"_id": ObjectId(plus_one_id)})
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Plus-one not found")
            return {"message": "Plus-one deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete plus-one: {str(e)}")