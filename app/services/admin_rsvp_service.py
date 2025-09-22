import csv
import io
from bson import ObjectId
from fastapi import HTTPException
from app.core.database import mongo

class AdminRSVPService:
    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]

    def get_all_rsvps(self, wedding_id=None):
        try:
            # Filter by wedding_id if provided
            query = {"wedding_id": wedding_id} if wedding_id else {}
            guests = list(self.guest_collection.find(query))

            if not guests:
                return []

            # Get all guest IDs for bulk queries
            guest_ids = [guest["_id"] for guest in guests]
            guest_id_strs = [str(gid) for gid in guest_ids]

            # Bulk fetch all RSVPs in ONE query instead of N queries
            rsvps_query = {
                "$or": [
                    {"guest_id": {"$in": guest_ids}},      # Old format: ObjectId
                    {"guest_id": {"$in": guest_id_strs}}   # New format: string
                ]
            }
            all_rsvps = list(self.rsvp_collection.find(rsvps_query))

            # Bulk fetch all plus-ones in ONE query instead of N queries
            all_plus_ones = list(self.plus_one_collection.find({"guest_id": {"$in": guest_id_strs}}))

            # Create lookup dictionaries for O(1) access
            rsvps_by_guest = {}
            for rsvp in all_rsvps:
                guest_id = rsvp.get("guest_id")
                # Handle both ObjectId and string formats
                key = str(guest_id) if guest_id else None
                if key:
                    rsvps_by_guest[key] = rsvp

            plus_ones_by_guest = {}
            for plus_one in all_plus_ones:
                guest_id = plus_one.get("guest_id")
                if guest_id:
                    plus_ones_by_guest[str(guest_id)] = plus_one

            # Build result with O(n) complexity instead of O(n²)
            result = []
            for guest in guests:
                guest_id_str = str(guest["_id"])

                # Look up RSVP in dictionary (O(1))
                rsvp = rsvps_by_guest.get(guest_id_str)

                # Only include guests who have actually RSVP'd
                if rsvp:
                    # Look up plus-one in dictionary (O(1))
                    plus_one = plus_ones_by_guest.get(guest_id_str)

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

    def export_rsvps_to_csv(self):
        try:
            guests = self.get_all_rsvps()
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
    
    def get_rsvp_by_guest_id(self, guest_id: str):
        try:
            guest = self.guest_collection.find_one({"_id": ObjectId(guest_id)})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Look for RSVP with either ObjectId or string guest_id for backwards compatibility
            rsvp = self.rsvp_collection.find_one({
                "$or": [
                    {"guest_id": ObjectId(guest_id)},  # Old format: ObjectId
                    {"guest_id": guest_id}             # New format: string
                ]
            })
            plus_one = self.plus_one_collection.find_one({"guest_id": guest_id})
            
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
    
    def update_rsvp(self, guest_id: str, rsvp_data: dict):
        try:
            guest = self.guest_collection.find_one({"_id": ObjectId(guest_id)})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Update RSVP - handle both old ObjectId and new string format
            self.rsvp_collection.update_one(
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
    
    def delete_rsvp(self, guest_id: str):
        try:
            guest = self.guest_collection.find_one({"_id": ObjectId(guest_id)})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Delete RSVP - handle both old ObjectId and new string format
            self.rsvp_collection.delete_one({
                "$or": [
                    {"guest_id": ObjectId(guest_id)},  # Old format
                    {"guest_id": guest_id}             # New format
                ]
            })

            return {"message": "RSVP deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete RSVP: {str(e)}")