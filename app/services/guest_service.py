from fastapi import HTTPException
from app.core.database import mongo
from datetime import datetime

class GuestService:
    def __init__(self):
        self.collection = mongo.get_guest_collection()

    def get_guest_by_token(self, token: str, wedding_id: str):
        try:
            guest = self.collection.find_one({"token": token, "wedding_id": wedding_id})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            guest["id"] = str(guest["_id"])
            guest.pop("_id", None)
            return guest
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error retrieving guest: {}".format(str(e)))
    
    def update_guest_timestamps(self, guest_id, created=False):
        """Update guest timestamps"""
        update_data = {"updated_at": datetime.utcnow()}
        if created:
            update_data["created_at"] = datetime.utcnow()
        
        self.collection.update_one(
            {"_id": guest_id},
            {"$set": update_data}
        )

    def get_guest_by_phone_or_name(self, phone: str = None, name: str = None):
        try:
            query = {}
            if phone:
                query["phone"] = phone
            if name:
                query["name"] = name
            if not query:
                raise HTTPException(status_code=400, detail="Must provide phone or name to search")

            guest = self.collection.find_one(query)
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
#             guest = self.collection.find_one({"token": token})
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

#             guest = self.collection.find_one(query)
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
#             guest = self.collection.find_one({"token": token})
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
#             result = self.collection.update_one(
#                 {"token": token},
#                 {"$push": {"plus_ones": plus_one_data}}
#             )

#             if result.modified_count == 0:
#                 raise HTTPException(status_code=500, detail="Failed to add plus one")

#             # Return the updated guest
#             updated_guest = self.collection.find_one({"token": token})
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
#             guest = self.collection.find_one({"token": token})
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
#             result = self.collection.update_one(
#                 {"token": token},
#                 {"$unset": update_filter}
#             )

#             if result.modified_count == 0:
#                 raise HTTPException(status_code=500, detail="Failed to remove plus one")

#             # Remove null elements from the array
#             self.collection.update_one(
#                 {"token": token},
#                 {"$pull": {"plus_ones": None}}
#             )

#             # Return the updated guest
#             updated_guest = self.collection.find_one({"token": token})
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
#             guest = self.collection.find_one({"token": token})
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
#             result = self.collection.update_one(
#                 {"token": token},
#                 {"$set": update_filter}
#             )

#             if result.modified_count == 0:
#                 raise HTTPException(status_code=500, detail="Failed to update plus one")

#             # Return the updated guest
#             updated_guest = self.collection.find_one({"token": token})
#             updated_guest["id"] = str(updated_guest["_id"])
#             updated_guest.pop("_id", None)

#             return updated_guest

#         except HTTPException:
#             raise
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Error updating plus one: {str(e)}")