import csv
import io
from fastapi import HTTPException
from app.core.database import mongo

class AdminRSVPService:
    def __init__(self):
        self.collection = mongo.get_guest_collection()

    def get_all_rsvps(self):
        try:
            guests = list(self.collection.find({"rsvp": {"$ne": None}}))
            for guest in guests:
                guest["id"] = str(guest["_id"])
                guest.pop("_id", None)
            return guests
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve RSVPs: {str(e)}")

    def export_rsvps_to_csv(self):
        try:
            guests = self.get_all_rsvps()
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(["Name", "Phone", "Attending", "Dietary", "Token"])

            for guest in guests:
                attending = ", ".join(guest["rsvp"].get("attending", []))
                dietary = guest["rsvp"].get("dietary", "")
                phone = guest.get("phone", "")
                writer.writerow([guest["name"], phone, attending, dietary, guest["token"]])

            output.seek(0)
            return output.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to export RSVPs: {str(e)}")