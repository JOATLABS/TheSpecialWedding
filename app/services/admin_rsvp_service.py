import csv
import io
from bson import ObjectId
from fastapi import HTTPException
from app.core.database import mongo
from datetime import datetime, timezone
from typing import List, Optional
from app.utils.csv_export import CSVExportUtils


class AdminRSVPService:
    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]

    async def get_all_rsvps(self, wedding_id=None):
        try:
            # Filter by wedding_id if provided
            query = {"wedding_id": wedding_id} if wedding_id else {}
            guests = await self.guest_collection.find(query).to_list(length=None)
            result = []

            if not guests:
                return []

            # Batch fetch RSVPs and PlusOnes to avoid N+1 queries
            guest_ids_obj = [g["_id"] for g in guests]
            guest_ids_str = [str(g["_id"]) for g in guests]

            # 1. Batch fetch RSVPs (check both ObjectId and string formats)
            rsvps_cursor = self.rsvp_collection.find({
                "$or": [
                    {"guest_id": {"$in": guest_ids_obj}},
                    {"guest_id": {"$in": guest_ids_str}}
                ]
            })
            rsvps_list = await rsvps_cursor.to_list(length=None)

            # Map RSVPs by guest_id (normalize to string for lookup)
            rsvps_map = {}
            for rsvp in rsvps_list:
                gid = rsvp.get("guest_id")
                rsvps_map[str(gid)] = rsvp

            # 2. Batch fetch PlusOnes
            plus_ones_cursor = self.plus_one_collection.find({
                "guest_id": {"$in": guest_ids_str}
            })
            plus_ones_list = await plus_ones_cursor.to_list(length=None)

            # Map PlusOnes by guest_id
            plus_ones_map = {p["guest_id"]: p for p in plus_ones_list}

            for guest in guests:
                guest_id = guest["_id"]
                guest_id_str = str(guest_id)
                
                # Look up RSVP from map
                rsvp = rsvps_map.get(guest_id_str)
                
                # Only include guests who have actually RSVP'd
                if rsvp:
                    plus_one = plus_ones_map.get(guest_id_str)
                    
                    # Convert plus_one _id to string if it exists
                    if plus_one and "_id" in plus_one:
                        plus_one["_id"] = str(plus_one["_id"])
                    
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

    def sanitize_csv_field(self, field_value: Optional[str]) -> str:
        """
        Sanitize CSV field to prevent Formula Injection (CSV Injection).
        If the field starts with =, +, -, or @, prepend a single quote.
        """
        if not field_value:
            return ""

        value = str(field_value)
        if value.startswith(("=", "+", "-", "@")):
            return f"'{value}"
        return value

    async def export_rsvps_to_csv(self):
        try:
            guests = await self.get_all_rsvps()

            headers = ["Guest Name", "Phone", "Attending", "Dietary", "Token", "Plus-One Name", "Plus-One Attending", "Plus-One Dietary"]
            rows = []

            for entry in guests:
                plus_one = entry.get("plus_one")
                rows.append([
                    entry["name"],
                    entry.get("phone", ""),
                    ", ".join(entry.get("attending", [])),
                    entry.get("dietary", ""),
                    entry.get("token", ""),
                    plus_one.get("name") if plus_one else "",
                    ", ".join(plus_one.get("attending", [])) if plus_one else "",
                    plus_one.get("dietary") if plus_one else ""
                ]

                sanitized_row = [self.sanitize_csv_field(val) for val in row_data]
                writer.writerow(sanitized_row)

            return CSVExportUtils.generate_csv_content(headers, rows)
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
            valid_events = {"traditional", "white_wedding", "reception", "engagement", "rehearsal"}
            if attending and not all(event in valid_events for event in attending):
                raise HTTPException(status_code=400, detail="Invalid event(s) in attending list")

            # Upsert RSVP
            rsvp_data = {
                "guest_id": guest_id,
                "wedding_id": wedding_id,
                "attending": attending,
                "dietary": dietary,
                "submitted_at": datetime.now(timezone.utc),
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