from fastapi import HTTPException
from app.core.database import mongo
from datetime import datetime

class GuestService:
    def __init__(self):
        self.collection = mongo.get_guest_collection()

    async def get_guest_by_token(self, token: str, wedding_id: str):
        try:
            guest = await self.collection.find_one({"token": token, "wedding_id": wedding_id})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            guest["id"] = str(guest["_id"])
            guest.pop("_id", None)
            return guest
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error retrieving guest: {}".format(str(e)))
    
    async def update_guest_timestamps(self, guest_id, created=False):
        """Update guest timestamps"""
        update_data = {"updated_at": datetime.utcnow()}
        if created:
            update_data["created_at"] = datetime.utcnow()
        
        await self.collection.update_one(
            {"_id": guest_id},
            {"$set": update_data}
        )

    def list_guests_by_wedding(self, wedding_id: str):
        try:
            guests = list(self.collection.find({"wedding_id": wedding_id}))
            for guest in guests:
                guest["id"] = str(guest["_id"])
                guest.pop("_id", None)
            return guests
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving guests: {str(e)}")
    
    async def update_guest(self, guest_id: str, update_data: dict):
        try:
            from bson import ObjectId
            
            # Remove fields that shouldn't be updated
            update_data.pop("_id", None)
            update_data.pop("id", None)
            update_data.pop("token", None)  # Don't allow token changes
            update_data.pop("wedding_id", None)  # Don't allow wedding changes
            
            # Add timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            result = await self.collection.update_one(
                {"_id": ObjectId(guest_id)},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Guest not found")
                
            # Return updated guest
            updated_guest = await self.collection.find_one({"_id": ObjectId(guest_id)})
            updated_guest["id"] = str(updated_guest["_id"])
            updated_guest.pop("_id", None)
            
            return updated_guest
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating guest: {str(e)}")
    
    async def delete_guest(self, guest_id: str):
        try:
            from bson import ObjectId
            
            # Convert guest_id to ObjectId
            guest_obj_id = ObjectId(guest_id)
            guest_id_str = str(guest_obj_id)
            
            # Check if guest exists
            guest = await self.collection.find_one({"_id": guest_obj_id})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            
            # Get collections for RSVPs and plus-ones
            rsvp_collection = mongo.db["rsvps"]
            plus_one_collection = mongo.db["plus_ones"]
            
            # Delete associated RSVPs (handle both ObjectId and string formats)
            rsvp_result = await rsvp_collection.delete_many({
                "$or": [
                    {"guest_id": guest_obj_id},
                    {"guest_id": guest_id_str}
                ]
            })
            
            # Delete associated plus-ones (typically stored with string guest_id)
            plus_one_result = await plus_one_collection.delete_many({
                "$or": [
                    {"guest_id": guest_obj_id},
                    {"guest_id": guest_id_str}
                ]
            })
            
            # Delete the guest
            guest_result = await self.collection.delete_one({"_id": guest_obj_id})
            
            return {
                "message": "Guest and associated data deleted successfully",
                "deleted": {
                    "guest": guest_result.deleted_count,
                    "rsvps": rsvp_result.deleted_count,
                    "plus_ones": plus_one_result.deleted_count
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting guest: {str(e)}")

    from typing import Optional

    async def get_guest_by_phone_or_name(self, phone: Optional[str] = None, name: Optional[str] = None):
        try:
            query = {}
            if phone:
                query["phone"] = phone
            if name:
                query["name"] = name
            if not query:
                raise HTTPException(status_code=400, detail="Must provide phone or name to search")

            guest = await self.collection.find_one(query)
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            guest["id"] = str(guest["_id"])
            guest.pop("_id", None)
            return guest
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error retrieving guest: {}".format(str(e)))





# from fastapi import HTTPException
# from app.core.database import mongo
# from app.models.guest import PlusOneModel
# from typing import List, Dict, Any

# class GuestService:
#     def __init__(self):
#         self.collection = mongo.get_guest_collection()

#     def get_guest_by_token(self, token: str):
#         try:
#             guest = await self.collection.find_one({"token": token})
#             if not guest:
#                 raise HTTPException(status_code=404, detail="Guest not found")
#             guest["id"] = str(guest["_id"])
#             guest.pop("_id", None)
#             return guest
#         except Exception as e:
#             raise HTTPException(status_code=500, detail="Error retrieving guest: {}".format(str(e)))

#     def get_guest_by_phone_or_name(self, phone: str = None, name: str = None):
#         try:
#             query = {}
#             if phone:
#                 query["phone"] = phone
#             if name:
#                 query["name"] = name
#             if not query:
#                 raise HTTPException(status_code=400, detail="Must provide phone or name to search")

#             guest = await self.collection.find_one(query)
#             if not guest:
#                 raise HTTPException(status_code=404, detail="Guest not found")
#             guest["id"] = str(guest["_id"])
#             guest.pop("_id", None)
#             return guest
#         except Exception as e:
#             raise HTTPException(status_code=500, detail="Error retrieving guest: {}".format(str(e)))

#     def add_plus_one(self, token: str, plus_one: PlusOneModel):
#         """
#         Add a plus-one guest to the main guest's invitation
#         """
#         try:
#             # Get the guest
#             guest = await self.collection.find_one({"token": token})
#             if not guest:
#                 raise HTTPException(status_code=404, detail="Guest not found")

#             # Check if plus ones are allowed
#             if not guest.get("allow_plus_ones", False):
#                 raise HTTPException(status_code=403, detail="This guest is not allowed to add plus ones")

#             # Check if the guest has reached their plus-one limit
#             current_plus_ones = guest.get("plus_ones", [])
#             max_plus_ones = guest.get("number_of_allowed_plus_ones", 0)

#             if len(current_plus_ones) >= max_plus_ones:
#                 raise HTTPException(
#                     status_code=400,
#                     detail=f"Maximum number of plus ones ({max_plus_ones}) reached"
#                 )

#             # Convert plus_one to dict
#             plus_one_data = plus_one.model_dump()

#             # Add the plus-one
#             result = await self.collection.update_one(
#                 {"token": token},
#                 {"$push": {"plus_ones": plus_one_data}}
#             )

#             if result.modified_count == 0:
#                 raise HTTPException(status_code=500, detail="Failed to add plus one")

#             # Return the updated guest
#             updated_guest = await self.collection.find_one({"token": token})
#             updated_guest["id"] = str(updated_guest["_id"])
#             updated_guest.pop("_id", None)

#             return updated_guest

#         except HTTPException:
#             raise
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Error adding plus one: {str(e)}")

#     def remove_plus_one(self, token: str, plus_one_index: int):
#         """
#         Remove a plus-one guest from the main guest's invitation
#         """
#         try:
#             # Get the guest
#             guest = await self.collection.find_one({"token": token})
#             if not guest:
#                 raise HTTPException(status_code=404, detail="Guest not found")

#             # Check if the plus-one exists
#             plus_ones = guest.get("plus_ones", [])
#             if plus_one_index < 0 or plus_one_index >= len(plus_ones):
#                 raise HTTPException(status_code=404, detail="Plus one not found")

#             # Create the update filter
#             # Use MongoDB array notation to remove specific index
#             update_filter = {f"plus_ones.{plus_one_index}": 1}

#             # Remove the plus-one
#             result = await self.collection.update_one(
#                 {"token": token},
#                 {"$unset": update_filter}
#             )

#             if result.modified_count == 0:
#                 raise HTTPException(status_code=500, detail="Failed to remove plus one")

#             # Remove null elements from the array
#             await self.collection.update_one(
#                 {"token": token},
#                 {"$pull": {"plus_ones": None}}
#             )

#             # Return the updated guest
#             updated_guest = await self.collection.find_one({"token": token})
#             updated_guest["id"] = str(updated_guest["_id"])
#             updated_guest.pop("_id", None)

#             return updated_guest

#         except HTTPException:
#             raise
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Error removing plus one: {str(e)}")

#     def update_plus_one(self, token: str, plus_one_index: int, updated_plus_one: PlusOneModel):
#         """
#         Update a plus-one guest's information
#         """
#         try:
#             # Get the guest
#             guest = await self.collection.find_one({"token": token})
#             if not guest:
#                 raise HTTPException(status_code=404, detail="Guest not found")

#             # Check if the plus-one exists
#             plus_ones = guest.get("plus_ones", [])
#             if plus_one_index < 0 or plus_one_index >= len(plus_ones):
#                 raise HTTPException(status_code=404, detail="Plus one not found")

#             # Convert plus_one to dict
#             plus_one_data = updated_plus_one.model_dump()

#             # Create the update filter
#             update_filter = {f"plus_ones.{plus_one_index}": plus_one_data}

#             # Update the plus-one
#             result = await self.collection.update_one(
#                 {"token": token},
#                 {"$set": update_filter}
#             )

#             if result.modified_count == 0:
#                 raise HTTPException(status_code=500, detail="Failed to update plus one")

#             # Return the updated guest
#             updated_guest = await self.collection.find_one({"token": token})
#             updated_guest["id"] = str(updated_guest["_id"])
#             updated_guest.pop("_id", None)

#             return updated_guest

#         except HTTPException:
#             raise
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Error updating plus one: {str(e)}")