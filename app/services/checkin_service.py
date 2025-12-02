# app/services/checkin_service.py


from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId
from app.core.database import mongo

class CheckInService:
    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.checkin_collection = mongo.db["checkins"]

    async def check_in_guest(self, token: str, admin_email: str):
        guest = await self.guest_collection.find_one({"token": token})
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        guest_id = str(guest["_id"])

        if await self.checkin_collection.find_one({"guest_id": guest_id}):
            raise HTTPException(status_code=409, detail="Guest already checked in")

        await self.checkin_collection.insert_one({
            "guest_id": guest_id,
            "checked_in_at": datetime.utcnow(),
            "method": "manual",
            "by": admin_email
        })

        return {"message": "Guest checked in successfully"}

    async def check_in_status(self, token: str):
        guest = await self.guest_collection.find_one({"token": token})
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        guest_id = str(guest["_id"])
        record = await self.checkin_collection.find_one({"guest_id": guest_id})

        return {
            "checked_in": bool(record),
            "checked_in_at": record.get("checked_in_at") if record else None,
            "by": record.get("by") if record else None
        }