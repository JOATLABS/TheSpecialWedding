from fastapi import HTTPException
from app.core.database import mongo

class GuestService:
    def __init__(self):
        self.collection = mongo.get_guest_collection()

    def get_guest_by_token(self, token: str):
        try:
            guest = self.collection.find_one({"token": token})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            guest["id"] = str(guest["_id"])
            guest.pop("_id", None)
            return guest
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error retrieving guest: {}".format(str(e)))

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