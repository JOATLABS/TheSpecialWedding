from fastapi import HTTPException
from app.core.database import mongo
from app.models.rsvp import RSVPModel
from app.models.plus_one import PlusOneModel
from bson import ObjectId

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

            self.rsvp_collection.update_one(
                {"guest_id": guest_id},
                {"$set": {
                    "guest_id": guest_id,
                    "attending": rsvp_data.attending,
                    "dietary": rsvp_data.dietary,
                    "submitted_at": mongo.client.server_info()['localTime']
                }},
                upsert=True
            )

            update_data = {"phone": rsvp_data.phone, "updated_at": mongo.client.server_info()['localTime']}
            self.guest_collection.update_one(
                {"_id": guest_id},
                {"$set": update_data}
            )

            if rsvp_data.plus_one:
                if not guest.get("plus_one_allowed", False):
                    raise HTTPException(status_code=403, detail="Plus-one not allowed for this guest")

                # Check number of plus-ones allowed
                max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)
                if max_plus_ones == 0:
                    raise HTTPException(status_code=403, detail="No plus-ones allowed for this guest")
                
                # Count existing plus-ones
                existing_count = self.plus_one_collection.count_documents({"guest_id": guest_id})
                if existing_count >= max_plus_ones:
                    raise HTTPException(status_code=400, detail=f"Maximum number of plus-ones ({max_plus_ones}) already reached")

                plus_one = PlusOneModel(
                    guest_id=ObjectId(guest_id),
                    name=rsvp_data.plus_one.name,
                    phone=rsvp_data.plus_one.phone,
                    attending=rsvp_data.plus_one.attending,
                    dietary=rsvp_data.plus_one.dietary
                )
                self.plus_one_collection.insert_one(plus_one.dict())
                
                # Update guest to mark plus_one_submitted as True only if all slots are filled
                if existing_count + 1 >= max_plus_ones:
                    self.guest_collection.update_one(
                        {"_id": guest_id},
                        {"$set": {"plus_one_submitted": True}}
                    )

            return {"message": "RSVP submitted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error submitting RSVP: {}".format(str(e)))
