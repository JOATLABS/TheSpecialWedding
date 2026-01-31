from fastapi import HTTPException
from app.core.database import mongo
from app.models.rsvp import RSVPModel
from bson import ObjectId
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RSVPService:
    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]
        self.wedding_collection = mongo.db["weddings"]

    async def submit_rsvp(self, token: str, rsvp_data: RSVPModel):
        try:
            logger.info(f"Processing RSVP submission for token: {token[:8]}...")

            guest = await self.guest_collection.find_one({"token": token})
            if not guest:
                logger.warning(f"Guest not found for token: {token[:8]}...")
                raise HTTPException(status_code=404, detail="Guest not found")

            guest_id = ObjectId(guest["_id"])
            guest_id_str = str(guest_id)
            wedding_id_str = str(guest.get("wedding_id", ""))

            logger.info(f"RSVP for guest: {guest.get('name', 'Unknown')} (id={guest_id_str}), "
                       f"wedding_id={wedding_id_str}, attending={rsvp_data.attending}")

            await self.rsvp_collection.update_one(
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

            update_data: dict[str, object] = {
                "phone": rsvp_data.phone,
                "updated_at": datetime.utcnow()
            }

            # Handle SMS opt-in
            if hasattr(rsvp_data, 'sms_opt_in'):
                update_data["sms_opt_in"] = rsvp_data.sms_opt_in
                if rsvp_data.sms_opt_in:
                    update_data["sms_opt_in_date"] = datetime.utcnow()
                elif rsvp_data.sms_opt_in is False:
                    update_data["sms_opt_out_date"] = datetime.utcnow()

            # Handle Email opt-in
            if hasattr(rsvp_data, 'email_opt_in'):
                update_data["email_opt_in"] = rsvp_data.email_opt_in
                if rsvp_data.email_opt_in:
                    update_data["email_opt_in_date"] = datetime.utcnow()
                elif rsvp_data.email_opt_in is False:
                    update_data["email_opt_out_date"] = datetime.utcnow()

            await self.guest_collection.update_one(
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
                existing_count = await self.plus_one_collection.count_documents({"guest_id": str(guest_id)})
                new_plus_ones_count = len(rsvp_data.plus_ones)

                if existing_count + new_plus_ones_count > max_plus_ones:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot add {new_plus_ones_count} plus-ones. Maximum allowed: {max_plus_ones}, already have: {existing_count}"
                    )

                # Insert all new plus-ones
                plus_ones_to_insert = []
                for plus_one_data in rsvp_data.plus_ones:
                    now = datetime.utcnow()
                    plus_one_doc: dict[str, object] = {
                        "guest_id": str(guest_id),
                        "name": plus_one_data.name,
                        "phone": plus_one_data.phone,
                        "email": plus_one_data.email,
                        "attending": plus_one_data.attending,
                        "dietary": plus_one_data.dietary,
                        "sms_opt_in": plus_one_data.sms_opt_in,
                        "email_opt_in": plus_one_data.email_opt_in,
                    }

                    # Add opt-in timestamps
                    if plus_one_data.sms_opt_in is True:
                        plus_one_doc["sms_opt_in_date"] = now
                    elif plus_one_data.sms_opt_in is False:
                        plus_one_doc["sms_opt_out_date"] = now

                    if plus_one_data.email_opt_in is True:
                        plus_one_doc["email_opt_in_date"] = now
                    elif plus_one_data.email_opt_in is False:
                        plus_one_doc["email_opt_out_date"] = now

                    plus_ones_to_insert.append(plus_one_doc)

                if plus_ones_to_insert:
                    await self.plus_one_collection.insert_many(plus_ones_to_insert)

                # Update guest to mark plus_one_submitted as True if at least one plus-one is submitted
                if new_plus_ones_count > 0:
                    await self.guest_collection.update_one(
                        {"_id": guest_id},
                        {"$set": {"plus_one_submitted": True}}
                    )

            # Notify planner about the RSVP update
            await self._notify_planner_rsvp(
                wedding_id=wedding_id_str,
                guest_name=guest.get("name", "A guest"),
                status="confirmed" if rsvp_data.attending else "declined",
                guest_count=1 + len(rsvp_data.plus_ones) if rsvp_data.plus_ones else 1,
                guest_id=guest_id_str
            )

            logger.info(f"RSVP submitted successfully for guest {guest_id_str} to wedding {wedding_id_str}")
            return {"message": "RSVP submitted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error submitting RSVP: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error submitting RSVP: {}".format(str(e)))

    async def _notify_planner_rsvp(
        self,
        wedding_id: str,
        guest_name: str,
        status: str,
        guest_count: int = 1,
        guest_id: str | None = None
    ):
        """Notify the planner about an RSVP update"""
        try:
            logger.info(f"Looking up wedding for RSVP notification: wedding_id={wedding_id}")

            # Get wedding to find planner
            # Note: wedding _id is stored as string, so this query should work
            wedding = await self.wedding_collection.find_one({"_id": wedding_id})
            if not wedding:
                logger.warning(f"Wedding {wedding_id} not found for RSVP notification. "
                             f"This may indicate a mismatch between guest.wedding_id and wedding._id")
                return

            planner_email = wedding.get("assigned_planner_email")
            couple_names = wedding.get("couple_names", "Unknown")

            if not planner_email:
                logger.debug(f"No planner assigned to wedding {wedding_id} ({couple_names})")
                return

            logger.info(f"Sending RSVP notification: planner={planner_email}, wedding={couple_names}, "
                       f"guest={guest_name}, status={status}, count={guest_count}")

            # Import here to avoid circular imports
            from app.services.planner_notification_service import planner_notification_service

            await planner_notification_service.notify_rsvp_update(
                planner_id=planner_email,
                wedding_id=wedding_id,
                guest_name=guest_name,
                status=status,
                guest_count=guest_count,
                guest_id=guest_id
            )
            logger.info(f"RSVP notification sent successfully to {planner_email} for wedding {wedding_id}")

        except Exception as e:
            # Don't fail the RSVP submission if notification fails
            logger.error(f"Failed to send RSVP notification for wedding {wedding_id}: {str(e)}", exc_info=True)
