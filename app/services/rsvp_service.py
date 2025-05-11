from app.core.database import mongo
from app.models.rsvp import RSVPModel
from fastapi import HTTPException

class RSVPService:
    def __init__(self):
        self.guests_collection = mongo.get_guest_collection()
    
    def submit_rsvp(self, token: str, rsvp: RSVPModel):
        """
        Submit RSVP for a guest using their invitation token
        """
        # Find the guest by token
        guest = self.guests_collection.find_one({"token": token})
        
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")
        
        # Update the guest's RSVP information
        rsvp_data = rsvp.model_dump()
        
        result = self.guests_collection.update_one(
            {"token": token},
            {"$set": {"rsvp": rsvp_data}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update RSVP")
        
        # Return the updated guest document
        updated_guest = self.guests_collection.find_one({"token": token})
        if not updated_guest:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated guest")
        
        # Convert ObjectId to string for JSON serialization
        updated_guest["_id"] = str(updated_guest["_id"])
        
        return updated_guest