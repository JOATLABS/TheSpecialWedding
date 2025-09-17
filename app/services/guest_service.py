from fastapi import HTTPException
from app.core.database import mongo
from datetime import datetime
from bson import ObjectId
from typing import Optional, Any, Dict

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

    def create_guest(self, guest_data: dict):
        try:
            from app.utils.token_generator import generate_token

            # Validate required fields
            name = guest_data.get("name", "").strip()
            wedding_id = guest_data.get("wedding_id")

            if not name or len(name) < 2:
                raise HTTPException(status_code=400, detail="Name is required and must be at least 2 characters")

            if not wedding_id:
                raise HTTPException(status_code=400, detail="Wedding ID is required")

            # Validate contact info - require at least phone or email
            phone = guest_data.get("phone", "").strip() if guest_data.get("phone") else None
            email = guest_data.get("email", "").strip() if guest_data.get("email") else None

            if not phone and not email:
                raise HTTPException(status_code=400, detail="At least phone or email is required")

            # Generate unique token
            token = generate_token()

            # Set default values
            role = guest_data.get("role", "guest")
            plus_one_allowed = guest_data.get("plus_one_allowed", False)
            number_of_plus_ones_allowed = int(guest_data.get("number_of_plus_ones_allowed", 0)) if guest_data.get("number_of_plus_ones_allowed") else 0
            group_id = guest_data.get("group_id")

            # Ensure logical consistency
            if not plus_one_allowed:
                number_of_plus_ones_allowed = 0

            # Create guest document
            doc = {
                "wedding_id": wedding_id,
                "name": name,
                "token": token,
                "phone": phone,
                "email": email,
                "role": role,
                "group_id": group_id,
                "plus_one_allowed": plus_one_allowed,
                "number_of_plus_ones_allowed": number_of_plus_ones_allowed,
                "plus_one_submitted": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # Insert guest
            result = self.collection.insert_one(doc)

            # Return created guest
            created_guest = self.collection.find_one({"_id": result.inserted_id})
            created_guest["id"] = str(created_guest["_id"])
            created_guest.pop("_id", None)

            return created_guest
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating guest: {str(e)}")

    def list_guests_by_wedding(self, wedding_id: str):
        try:
            guests = list(self.collection.find({"wedding_id": wedding_id}))
            for guest in guests:
                guest["id"] = str(guest["_id"])
                guest.pop("_id", None)
            return guests
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving guests: {str(e)}")
    
    def update_guest(self, guest_id: str, update_data: dict):
        try:
            # Remove fields that shouldn't be updated
            update_data.pop("_id", None)
            update_data.pop("id", None)
            update_data.pop("token", None)  # Don't allow token changes
            update_data.pop("wedding_id", None)  # Don't allow wedding changes
            
            # Add timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            result = self.collection.update_one(
                {"_id": ObjectId(guest_id)},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Guest not found")
                
            # Return updated guest
            updated_guest = self.collection.find_one({"_id": ObjectId(guest_id)})
            updated_guest["id"] = str(updated_guest["_id"])
            updated_guest.pop("_id", None)
            
            return updated_guest
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating guest: {str(e)}")
    
    def delete_guest(self, guest_id: str):
        try:
            # Convert guest_id to ObjectId
            guest_obj_id = ObjectId(guest_id)
            guest_id_str = str(guest_obj_id)

            # Check if guest exists
            guest = self.collection.find_one({"_id": guest_obj_id})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Get all collections that might contain guest data
            rsvp_collection = mongo.db["rsvps"]
            plus_one_collection = mongo.db["plus_ones"]
            checkin_collection = mongo.db["checkins"]
            otp_codes_collection = mongo.db["otp_codes"]
            otp_audit_collection = mongo.db["otp_audit_log"]
            access_logs_collection = mongo.db["access_logs"]
            form_responses_collection = mongo.db["form_responses"]
            reminders_sent_collection = mongo.db["reminders_sent"]

            # Delete associated RSVPs (handle both ObjectId and string formats)
            rsvp_result = rsvp_collection.delete_many({
                "$or": [
                    {"guest_id": guest_obj_id},
                    {"guest_id": guest_id_str}
                ]
            })

            # Delete associated plus-ones (typically stored with string guest_id)
            plus_one_result = plus_one_collection.delete_many({
                "$or": [
                    {"guest_id": guest_obj_id},
                    {"guest_id": guest_id_str}
                ]
            })

            # Delete check-in records
            checkin_result = checkin_collection.delete_many({
                "$or": [
                    {"guest_id": guest_obj_id},
                    {"guest_id": guest_id_str}
                ]
            })

            # Delete OTP codes
            otp_codes_result = otp_codes_collection.delete_many({
                "$or": [
                    {"guest_id": guest_obj_id},
                    {"guest_id": guest_id_str}
                ]
            })

            # Anonymize OTP audit logs (preserve for security compliance)
            otp_audit_result = otp_audit_collection.update_many(
                {
                    "$or": [
                        {"guest_id": guest_obj_id},
                        {"guest_id": guest_id_str}
                    ]
                },
                {
                    "$set": {
                        "guest_id": "DELETED_GUEST",
                        "guest_deleted": True,
                        "deleted_at": datetime.utcnow()
                    }
                }
            )

            # Anonymize access logs (preserve for security compliance)
            access_logs_result = access_logs_collection.update_many(
                {
                    "$or": [
                        {"guest_id": guest_obj_id},
                        {"guest_id": guest_id_str}
                    ]
                },
                {
                    "$set": {
                        "guest_id": "DELETED_GUEST",
                        "guest_deleted": True,
                        "deleted_at": datetime.utcnow()
                    }
                }
            )

            # Delete form responses (operational data)
            form_responses_result = form_responses_collection.delete_many({
                "$or": [
                    {"guest_id": guest_obj_id},
                    {"guest_id": guest_id_str}
                ]
            })

            # Anonymize reminder logs (preserve for analytics/billing)
            reminders_result = reminders_sent_collection.update_many(
                {
                    "$or": [
                        {"guest_id": guest_obj_id},
                        {"guest_id": guest_id_str}
                    ]
                },
                {
                    "$set": {
                        "guest_id": "DELETED_GUEST",
                        "guest_deleted": True,
                        "deleted_at": datetime.utcnow()
                    }
                }
            )

            # Delete the guest
            guest_result = self.collection.delete_one({"_id": guest_obj_id})

            return {
                "message": "Guest and associated data processed successfully",
                "deleted": {
                    "guest": guest_result.deleted_count,
                    "rsvps": rsvp_result.deleted_count,
                    "plus_ones": plus_one_result.deleted_count,
                    "checkins": checkin_result.deleted_count,
                    "otp_codes": otp_codes_result.deleted_count,
                    "form_responses": form_responses_result.deleted_count
                },
                "anonymized": {
                    "otp_audit_logs": otp_audit_result.modified_count,
                    "access_logs": access_logs_result.modified_count,
                    "reminder_logs": reminders_result.modified_count
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting guest: {str(e)}")

    def get_guest_by_phone_or_name(self, phone: Optional[str] = None, name: Optional[str] = None, wedding_id: Optional[str] = None):
        """Get guest by phone or name, with required wedding_id for security isolation"""
        try:
            # Security: wedding_id should be required for multi-tenant isolation
            if not wedding_id:
                raise HTTPException(status_code=400, detail="Wedding ID is required for security isolation")

            query = {"wedding_id": wedding_id}
            if phone:
                query["phone"] = phone
            if name:
                query["name"] = name
            if not (phone or name):
                raise HTTPException(status_code=400, detail="Must provide phone or name to search")

            guest = self.collection.find_one(query)
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            guest["id"] = str(guest["_id"])
            guest.pop("_id", None)
            return guest
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error retrieving guest: {}".format(str(e)))

    def get_guest(self, guest_id: str, wedding_id: Optional[str] = None):
        """Get guest by ID. If wedding_id provided, ensures guest belongs to that wedding."""
        try:
            query: Dict[str, Any] = {"_id": ObjectId(guest_id)}

            # If wedding_id provided, add it for isolation
            if wedding_id:
                query["wedding_id"] = wedding_id

            guest = self.collection.find_one(query)
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            guest["id"] = str(guest["_id"])
            guest.pop("_id", None)
            return guest
        except HTTPException:
            raise
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