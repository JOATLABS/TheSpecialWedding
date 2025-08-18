from fastapi import HTTPException
from app.core.database import mongo
from app.models.wedding import WeddingModel
from typing import List

class WeddingService:
    def __init__(self):
        self.collection = mongo.db["weddings"]
    
    def create_wedding(self, wedding_data: dict):
        """Create a new wedding"""
        try:
            # Handle both WeddingModel instances and raw dicts
            if hasattr(wedding_data, 'dict'):
                wedding_dict = wedding_data.dict(by_alias=True)
            else:
                wedding_dict = wedding_data
            
            # Check if wedding ID already exists
            existing = self.collection.find_one({"_id": wedding_dict["_id"]})
            if existing:
                raise HTTPException(status_code=400, detail="Wedding ID already exists")
            
            result = self.collection.insert_one(wedding_dict)
            return {"message": "Wedding created successfully", "id": wedding_dict["_id"]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating wedding: {str(e)}")
    
    def get_wedding(self, wedding_id: str):
        """Get a wedding by ID"""
        try:
            wedding = self.collection.find_one({"_id": wedding_id})
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")
            return wedding
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving wedding: {str(e)}")
    
    def get_wedding_by_slug(self, slug: str):
        """Get a wedding by slug"""
        try:
            wedding = self.collection.find_one({"slug": slug})
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")
            return wedding
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving wedding: {str(e)}")
    
    def list_weddings(self) -> List[dict]:
        """List all weddings"""
        try:
            weddings = list(self.collection.find())
            return weddings
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing weddings: {str(e)}")
    
    def list_weddings_for_planner(self, planner_email: str) -> List[dict]:
        """List weddings assigned to a specific planner"""
        try:
            weddings = list(self.collection.find({"assigned_planner_email": planner_email}))
            return weddings
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing weddings for planner: {str(e)}")
    
    def update_wedding(self, wedding_id: str, wedding_data: dict):
        """Update a wedding"""
        try:
            # Remove _id from update data if present
            wedding_data.pop("_id", None)
            
            result = self.collection.update_one(
                {"_id": wedding_id},
                {"$set": wedding_data}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")
            
            return {"message": "Wedding updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating wedding: {str(e)}")
    
    def delete_wedding(self, wedding_id: str):
        """Delete a wedding"""
        try:
            result = self.collection.delete_one({"_id": wedding_id})
            
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")
            
            return {"message": "Wedding deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting wedding: {str(e)}")