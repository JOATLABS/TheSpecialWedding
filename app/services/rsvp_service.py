from fastapi import HTTPException
from app.core.database import mongo
from app.models.rsvp import RSVPModel
from app.models.plus_one import PlusOneModel
from bson import ObjectId
from datetime import datetime

class RSVPService:
    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]

    def submit_rsvp(self, token: str, rsvp_data: RSVPModel):
        try:
            guest = self.guest_collection.find_one({"token": token})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            guest_id = ObjectId(guest["_id"])
            guest_id_str = str(guest_id)
            wedding_id_str = str(guest.get("wedding_id", ""))

            self.rsvp_collection.update_one(
                {"guest_id": guest_id_str},
                {"$set": {
                    "guest_id": guest_id_str,
                    "wedding_id": wedding_id_str,
                    "attending": rsvp_data.attending,
                    "dietary": rsvp_data.dietary,
                    "submitted_at": datetime.utcnow()
                }},
                upsert=True
            )

            update_data = {
                "phone": rsvp_data.phone, 
                "updated_at": datetime.utcnow()
            }
            
            # Handle SMS opt-in
            if hasattr(rsvp_data, 'sms_opt_in'):
                update_data["sms_opt_in"] = rsvp_data.sms_opt_in
                if rsvp_data.sms_opt_in:
                    update_data["sms_opt_in_date"] = datetime.utcnow()
            
            self.guest_collection.update_one(
                {"_id": guest_id},
                {"$set": update_data}
            )

            if rsvp_data.plus_ones and len(rsvp_data.plus_ones) > 0:
                if not guest.get("plus_one_allowed", False):
                    raise HTTPException(status_code=403, detail="Plus-ones not allowed for this guest")

                # Check number of plus-ones allowed
                max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)
                if max_plus_ones == 0:
                    raise HTTPException(status_code=403, detail="No plus-ones allowed for this guest")
                
                # Count existing plus-ones
                existing_count = self.plus_one_collection.count_documents({"guest_id": str(guest_id)})
                new_plus_ones_count = len(rsvp_data.plus_ones)

                if existing_count + new_plus_ones_count > max_plus_ones:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot add {new_plus_ones_count} plus-ones. Maximum allowed: {max_plus_ones}, already have: {existing_count}"
                    )

                # Insert all new plus-ones
                plus_ones_to_insert = []
                for plus_one_data in rsvp_data.plus_ones:
                    plus_one = PlusOneModel(
                        guest_id=str(guest_id),
                        name=plus_one_data.name,
                        phone=plus_one_data.phone,
                        attending=plus_one_data.attending,
                        dietary=plus_one_data.dietary
                    )
                    plus_ones_to_insert.append(plus_one.dict())

                if plus_ones_to_insert:
                    self.plus_one_collection.insert_many(plus_ones_to_insert)
                
                # Update guest to mark plus_one_submitted as True only if all slots are filled
                if existing_count + new_plus_ones_count >= max_plus_ones:
                    self.guest_collection.update_one(
                        {"_id": guest_id},
                        {"$set": {"plus_one_submitted": True}}
                    )

            return {"message": "RSVP submitted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error submitting RSVP: {}".format(str(e)))
