from fastapi import HTTPException
from bson import ObjectId
from app.core.database import mongo

class ChecklistService:
    def __init__(self):
        self.collection = mongo.db["wedding_checklists"]

    async def get_checklist(self, wedding_id: str):
        try:
            items = await self.collection.find({"wedding_id": wedding_id}).to_list(length=None)
            for item in items:
                item["id"] = str(item["_id"])
            return items
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve checklist: {str(e)}")

    async def update_checklist_item(self, wedding_id: str, item_id: str, completed: bool):
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(item_id), "wedding_id": wedding_id},
                {"$set": {"completed": completed}}
            )
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Checklist item not found")
            return {"message": "Checklist item updated successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update checklist item: {str(e)}")
