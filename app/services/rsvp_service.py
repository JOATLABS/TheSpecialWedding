import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException

from app.core.database import mongo
from app.models.rsvp import RSVPModel
from app.services.activity_log_service import activity_log_service
from app.utils.rsvp_storage import DEPRECATED_RSVP_FIELDS_UNSET

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

            return await self._submit_rsvp_for_guest_doc(guest, rsvp_data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error submitting RSVP: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail="Error submitting RSVP: {}".format(str(e))
            )

    async def submit_rsvp_for_guest(self, guest_id: str, rsvp_data: RSVPModel):
        try:
            if not ObjectId.is_valid(guest_id):
                raise HTTPException(status_code=400, detail="Invalid guest ID")

            guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            return await self._submit_rsvp_for_guest_doc(guest, rsvp_data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Error submitting RSVP for guest {guest_id}: {str(e)}", exc_info=True
            )
            raise HTTPException(
                status_code=500, detail="Error submitting RSVP: {}".format(str(e))
            )

    async def _submit_rsvp_for_guest_doc(self, guest: dict, rsvp_data: RSVPModel):
        guest_id = ObjectId(guest["_id"])
        guest_id_str = str(guest_id)
        wedding_id_str = str(guest.get("wedding_id", ""))

        logger.info(
            f"RSVP for guest: {guest.get('name', 'Unknown')} "
            f"(id={guest_id_str}), wedding_id={wedding_id_str}, attending={rsvp_data.attending}"
        )

        await self.rsvp_collection.update_one(
            {"guest_id": guest_id_str},
            {
                "$set": {
                    "guest_id": guest_id_str,
                    "wedding_id": wedding_id_str,
                    "attending": rsvp_data.attending,
                    "dietary": rsvp_data.dietary,
                    "submitted_at": datetime.now(timezone.utc),
                },
                "$unset": DEPRECATED_RSVP_FIELDS_UNSET,
            },
            upsert=True,
        )

        update_data: dict[str, object] = {
            "phone": rsvp_data.phone,
            "updated_at": datetime.now(timezone.utc),
        }

        if hasattr(rsvp_data, "sms_opt_in"):
            update_data["sms_opt_in"] = rsvp_data.sms_opt_in
            if rsvp_data.sms_opt_in:
                update_data["sms_opt_in_date"] = datetime.now(timezone.utc)
            elif rsvp_data.sms_opt_in is False:
                update_data["sms_opt_out_date"] = datetime.now(timezone.utc)

        if hasattr(rsvp_data, "email_opt_in"):
            update_data["email_opt_in"] = rsvp_data.email_opt_in
            if rsvp_data.email_opt_in:
                update_data["email_opt_in_date"] = datetime.now(timezone.utc)
            elif rsvp_data.email_opt_in is False:
                update_data["email_opt_out_date"] = datetime.now(timezone.utc)

        await self.guest_collection.update_one({"_id": guest_id}, {"$set": update_data})

        await self.plus_one_collection.delete_many({"guest_id": guest_id_str})

        if rsvp_data.plus_ones and len(rsvp_data.plus_ones) > 0:
            if not guest.get("plus_one_allowed", False):
                raise HTTPException(
                    status_code=403, detail="Plus-ones not allowed for this guest"
                )

            max_plus_ones = guest.get("number_of_plus_ones_allowed", 0)
            if max_plus_ones == 0:
                raise HTTPException(
                    status_code=403, detail="No plus-ones allowed for this guest"
                )

            new_plus_ones_count = len(rsvp_data.plus_ones)
            if new_plus_ones_count > max_plus_ones:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot add {new_plus_ones_count} plus-one(s). Maximum allowed: {max_plus_ones}",
                )

            now = datetime.now(timezone.utc)
            plus_ones_to_insert = []
            for plus_one_data in rsvp_data.plus_ones:
                plus_one_doc: dict[str, object] = {
                    "guest_id": guest_id_str,
                    "name": plus_one_data.name,
                    "phone": plus_one_data.phone,
                    "email": plus_one_data.email,
                    "attending": plus_one_data.attending,
                    "dietary": plus_one_data.dietary,
                    "sms_opt_in": plus_one_data.sms_opt_in,
                    "email_opt_in": plus_one_data.email_opt_in,
                    "created_at": now,
                    "updated_at": now,
                }

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

            if new_plus_ones_count > 0:
                await self.guest_collection.update_one(
                    {"_id": guest_id}, {"$set": {"plus_one_submitted": True}}
                )
        else:
            await self.guest_collection.update_one(
                {"_id": guest_id}, {"$set": {"plus_one_submitted": False}}
            )

        await self._notify_planner_rsvp(
            wedding_id=wedding_id_str,
            guest_name=guest.get("name", "A guest"),
            status="confirmed" if rsvp_data.attending else "declined",
            guest_count=1 + len(rsvp_data.plus_ones) if rsvp_data.plus_ones else 1,
            guest_id=guest_id_str,
        )

        logger.info(
            f"RSVP submitted successfully for guest {guest_id_str} to wedding {wedding_id_str}"
        )
        return {"message": "RSVP submitted successfully"}

    async def _notify_planner_rsvp(
        self,
        wedding_id: str,
        guest_name: str,
        status: str,
        guest_count: int = 1,
        guest_id: str | None = None,
    ):
        """Notify the planner about an RSVP update"""
        try:
            logger.info(
                f"Looking up wedding for RSVP notification: wedding_id={wedding_id}"
            )

            # Get wedding to find planner
            # Note: wedding _id is stored as string, so this query should work
            wedding = await self.wedding_collection.find_one({"_id": wedding_id})
            if not wedding:
                logger.warning(
                    f"Wedding {wedding_id} not found for RSVP notification. "
                    f"This may indicate a mismatch between guest.wedding_id and wedding._id"
                )
                return

            planner_email = wedding.get("assigned_planner_email")
            couple_names = wedding.get("couple_names", "Unknown")

            if not planner_email:
                logger.debug(
                    f"No planner assigned to wedding {wedding_id} ({couple_names})"
                )
                return

            logger.info(
                f"Sending RSVP notification: planner={planner_email}, wedding={couple_names}, guest={guest_name}, status={status}, count={guest_count}"
            )

            # Import here to avoid circular imports
            from app.services.planner_notification_service import (
                planner_notification_service,
            )

            await planner_notification_service.notify_rsvp_update(
                planner_id=planner_email,
                wedding_id=wedding_id,
                guest_name=guest_name,
                status=status,
                guest_count=guest_count,
                guest_id=guest_id,
            )
            logger.info(
                f"RSVP notification sent successfully to {planner_email} for wedding {wedding_id}"
            )

            # Log activity for planner dashboard
            await activity_log_service.log_rsvp_received(
                wedding_id=wedding_id,
                guest_name=guest_name,
                response=status,
                planner_email=planner_email,
                plus_ones=guest_count - 1 if guest_count > 1 else 0,
                metadata={"guest_id": guest_id, "couple_names": couple_names},
            )

            # Broadcast SSE data-change so planner UI updates in real time
            from app.services.sse_manager import sse_manager

            await sse_manager.broadcast_data_change(
                planner_email,
                "rsvp",
                "created",
                wedding_id=wedding_id,
                record_id=guest_id,
            )

        except Exception as e:
            # Don't fail the RSVP submission if notification fails
            logger.error(
                f"Failed to send RSVP notification for wedding {wedding_id}: {str(e)}",
                exc_info=True,
            )
