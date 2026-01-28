import csv
import io
from bson import ObjectId
from fastapi import HTTPException
from app.core.database import mongo
from datetime import datetime
from typing import List, Optional

class AdminRSVPService:
    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]

    async def get_all_rsvps(self, wedding_id=None):
        try:
            # Filter by wedding_id if provided
            query = {"wedding_id": wedding_id} if wedding_id else {}

            # Optimized: Async fetch
            cursor = self.guest_collection.find(query)
            guests = await cursor.to_list(length=None)

            if not guests:
                return []

            # Collect guest IDs for batch querying
            guest_ids_obj = [g["_id"] for g in guests]
            guest_ids_str = [str(g["_id"]) for g in guests]

            # Batch fetch RSVPs (handle both ObjectId and string formats)
            rsvp_cursor = self.rsvp_collection.find({
                "guest_id": {"$in": guest_ids_obj + guest_ids_str}
            })
            rsvps_list = await rsvp_cursor.to_list(length=None)

            # Index RSVPs by guest_id (normalized to string)
            rsvp_map = {}
            for r in rsvps_list:
                gid = str(r.get("guest_id"))
                rsvp_map[gid] = r

            # Batch fetch Plus Ones
            plus_one_cursor = self.plus_one_collection.find({
                "guest_id": {"$in": guest_ids_str}
            })
            plus_ones_list = await plus_one_cursor.to_list(length=None)

            # Index Plus Ones by guest_id
            plus_one_map = {}
            for p in plus_ones_list:
                gid = str(p.get("guest_id"))
                if "_id" in p:
                    p["_id"] = str(p["_id"])
                plus_one_map[gid] = p

            result = []
            for guest in guests:
                guest_id = guest["_id"]
                guest_id_str = str(guest_id)
                
                # O(1) Lookup
                rsvp = rsvp_map.get(guest_id_str)
                
                # Only include guests who have actually RSVP'd
                if rsvp:
                    plus_one = plus_one_map.get(guest_id_str)
                    
                    result.append({
                        "guest_id": guest_id_str,
                        "name": guest.get("name"),
                        "phone": guest.get("phone"),
                        "token": guest.get("token"),
                        "attending": rsvp.get("attending", []),
                        "dietary": rsvp.get("dietary"),
                        "submitted_at": rsvp.get("submitted_at").isoformat() if rsvp.get("submitted_at") else None,
                        "plus_one": plus_one
                    })

            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve RSVPs: {str(e)}")

    async def export_rsvps_to_csv(self):
        try:
            guests = await self.get_all_rsvps()
            output = io.StringIO()
            writer = csv.writer(output)

            writer.writerow(["Guest Name", "Phone", "Attending", "Dietary", "Token", "Plus-One Name", "Plus-One Attending", "Plus-One Dietary"])

            for entry in guests:
                plus_one = entry.get("plus_one")
                writer.writerow([
                    entry["name"],
                    entry.get("phone", ""),
                    ", ".join(entry.get("attending", [])),
                    entry.get("dietary", ""),
                    entry.get("token", ""),
                    plus_one.get("name") if plus_one else "",
                    ", ".join(plus_one.get("attending", [])) if plus_one else "",
                    plus_one.get("dietary") if plus_one else ""
                ])

            output.seek(0)
            return output.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to export RSVPs: {str(e)}")
    
    async def get_rsvp_by_guest_id(self, guest_id: str):
        try:
            guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Look for RSVP with either ObjectId or string guest_id for backwards compatibility
            rsvp = await self.rsvp_collection.find_one({
                "$or": [
                    {"guest_id": ObjectId(guest_id)},  # Old format: ObjectId
                    {"guest_id": guest_id}             # New format: string
                ]
            })
            plus_one = await self.plus_one_collection.find_one({"guest_id": guest_id})
            
            # Convert plus_one _id to string if it exists
            if plus_one and "_id" in plus_one:
                plus_one["_id"] = str(plus_one["_id"])

            return {
                "guest_id": str(guest["_id"]),
                "name": guest.get("name"),
                "phone": guest.get("phone"),
                "token": guest.get("token"),
                "attending": rsvp.get("attending") if rsvp else [],
                "dietary": rsvp.get("dietary") if rsvp else None,
                "plus_one": plus_one
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve RSVP: {str(e)}")
    
    async def update_rsvp(self, guest_id: str, rsvp_data: dict):
        try:
            guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Update RSVP - handle both old ObjectId and new string format
            await self.rsvp_collection.update_one(
                {
                    "$or": [
                        {"guest_id": ObjectId(guest_id)},  # Old format
                        {"guest_id": guest_id}             # New format
                    ]
                },
                {"$set": rsvp_data}
            )

            return {"message": "RSVP updated successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update RSVP: {str(e)}")
    
    async def delete_rsvp(self, guest_id: str):
        try:
            guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Delete RSVP - handle both old ObjectId and new string format
            await self.rsvp_collection.delete_one({
                "$or": [
                    {"guest_id": ObjectId(guest_id)},  # Old format
                    {"guest_id": guest_id}             # New format
                ]
            })

            return {"message": "RSVP deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete RSVP: {str(e)}")

    async def admin_create_or_update_rsvp(
        self,
        guest_id: str,
        wedding_id: str,
        attending: List[str],
        dietary: Optional[str] = None,
        confirmed_by_admin: bool = True
    ):
        """Admin endpoint to create or update an RSVP manually (e.g., phone confirmation)."""
        try:
            # Verify guest exists
            guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Validate attending events
            valid_events = {"traditional", "white_wedding", "reception"}
            if attending and not all(event in valid_events for event in attending):
                raise HTTPException(status_code=400, detail="Invalid event(s) in attending list")

            # Upsert RSVP
            rsvp_data = {
                "guest_id": guest_id,
                "wedding_id": wedding_id,
                "attending": attending,
                "dietary": dietary,
                "submitted_at": datetime.utcnow(),
                "confirmed_by_admin": confirmed_by_admin
            }

            result = await self.rsvp_collection.update_one(
                {
                    "$or": [
                        {"guest_id": ObjectId(guest_id)},
                        {"guest_id": guest_id}
                    ]
                },
                {"$set": rsvp_data},
                upsert=True
            )

            action = "created" if result.upserted_id else "updated"
            return {
                "message": f"RSVP {action} successfully",
                "guest_id": guest_id,
                "attending": attending,
                "dietary": dietary,
                "confirmed_by_admin": confirmed_by_admin
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update RSVP: {str(e)}")
