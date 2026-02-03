from fastapi import HTTPException
from app.core.database import mongo
from datetime import datetime, timezone
from typing import Optional
import logging
from app.utils.token_generator import generate_token

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_ai_cache_service = None


def _get_ai_cache_service():
    """Get AI cache service lazily to avoid circular imports."""
    global _ai_cache_service
    if _ai_cache_service is None:
        from app.services.ai_cache_service import ai_cache_service
        _ai_cache_service = ai_cache_service
    return _ai_cache_service


class GuestService:
    def __init__(self):
        self.collection = mongo.get_guest_collection()

    async def _invalidate_guest_cache(self, wedding_id: str):
        """Invalidate AI cache when guest data changes (affects seating optimization)."""
        try:
            cache_service = _get_ai_cache_service()
            # Invalidate all seating-related caches
            for feature in ["seating_small", "seating_medium", "seating_large"]:
                await cache_service.invalidate_by_feature(feature, wedding_id)
            logger.debug(f"Invalidated seating cache for wedding {wedding_id}")
        except Exception as e:
            # Cache invalidation failures should not break main operations
            logger.warning(f"Failed to invalidate guest cache: {str(e)}")

    async def get_guest_by_token(self, token: str, wedding_id: str):
        try:
            guest = await self.collection.find_one({"token": token, "wedding_id": wedding_id})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            guest["id"] = str(guest["_id"])
            guest.pop("_id", None)
            return guest
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error retrieving guest: {}".format(str(e)))

    async def get_guest(self, guest_id: str):
        """Fetch a guest by ObjectId or string id."""
        from bson import ObjectId
        try:
            obj_id = ObjectId(guest_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid guest id")

        guest = await self.collection.find_one({"_id": obj_id})
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        guest["id"] = str(guest["_id"])
        guest.pop("_id", None)
        return guest
    
    async def update_guest_timestamps(self, guest_id, created=False):
        """Update guest timestamps"""
        update_data = {"updated_at": datetime.now(timezone.utc)}
        if created:
            update_data["created_at"] = datetime.now(timezone.utc)
        
        await self.collection.update_one(
            {"_id": guest_id},
            {"$set": update_data}
        )

    async def list_guests_by_wedding(self, wedding_id: str):
        try:
            guests = await self.collection.find({"wedding_id": wedding_id}).to_list(length=None)
            for guest in guests:
                guest["id"] = str(guest["_id"])
                guest.pop("_id", None)
            return guests
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving guests: {str(e)}")
    
    async def update_guest(self, guest_id: str, update_data: dict):
        try:
            from bson import ObjectId
            
            # Remove fields that shouldn't be updated
            update_data.pop("_id", None)
            update_data.pop("id", None)
            update_data.pop("token", None)  # Don't allow token changes
            update_data.pop("wedding_id", None)  # Don't allow wedding changes
            
            # Add timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await self.collection.update_one(
                {"_id": ObjectId(guest_id)},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Return updated guest
            updated_guest = await self.collection.find_one({"_id": ObjectId(guest_id)})
            updated_guest["id"] = str(updated_guest["_id"])
            updated_guest.pop("_id", None)

            # Invalidate AI cache for seating optimization
            if updated_guest.get("wedding_id"):
                await self._invalidate_guest_cache(updated_guest["wedding_id"])

            return updated_guest
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating guest: {str(e)}")
    
    async def delete_guest(self, guest_id: str):
        try:
            from bson import ObjectId
            
            # Convert guest_id to ObjectId
            guest_obj_id = ObjectId(guest_id)
            guest_id_str = str(guest_obj_id)
            
            # Check if guest exists
            guest = await self.collection.find_one({"_id": guest_obj_id})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            
            # Get collections for RSVPs and plus-ones
            rsvp_collection = mongo.db["rsvps"]
            plus_one_collection = mongo.db["plus_ones"]
            
            # Delete associated RSVPs (handle both ObjectId and string formats)
            rsvp_result = await rsvp_collection.delete_many({
                "$or": [
                    {"guest_id": guest_obj_id},
                    {"guest_id": guest_id_str}
                ]
            })
            
            # Delete associated plus-ones (typically stored with string guest_id)
            plus_one_result = await plus_one_collection.delete_many({
                "$or": [
                    {"guest_id": guest_obj_id},
                    {"guest_id": guest_id_str}
                ]
            })
            
            # Delete the guest
            guest_result = await self.collection.delete_one({"_id": guest_obj_id})

            # Invalidate AI cache for seating optimization
            wedding_id = guest.get("wedding_id")
            if wedding_id:
                await self._invalidate_guest_cache(wedding_id)

            return {
                "message": "Guest and associated data deleted successfully",
                "deleted": {
                    "guest": guest_result.deleted_count,
                    "rsvps": rsvp_result.deleted_count,
                    "plus_ones": plus_one_result.deleted_count
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting guest: {str(e)}")

    async def get_guest_by_phone_or_name(self, phone: Optional[str] = None, name: Optional[str] = None, wedding_id: Optional[str] = None):
        """
        Search for a guest by phone or name, optionally filtered by wedding_id.

        Args:
            phone: Guest phone number
            name: Guest name
            wedding_id: Wedding ID to filter results (REQUIRED for security)

        Security: Always provide wedding_id to prevent cross-wedding data access
        """
        try:
            query = {}

            # SECURITY: Always filter by wedding_id to prevent cross-wedding access
            if wedding_id:
                query["wedding_id"] = wedding_id

            if phone:
                query["phone"] = phone
            if name:
                query["name"] = name

            if not phone and not name:
                raise HTTPException(status_code=400, detail="Must provide phone or name to search")

            guest = await self.collection.find_one(query)
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            guest["id"] = str(guest["_id"])
            guest.pop("_id", None)
            return guest
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error retrieving guest: {}".format(str(e)))

    async def create_guest(self, guest_data, wedding_id: str):
        """Create a single guest for a wedding."""
        try:
            # Convert Pydantic model to dict
            data = guest_data.model_dump() if hasattr(guest_data, 'model_dump') else guest_data.dict()

            # Require at least phone or email
            if not data.get("phone") and not data.get("email"):
                raise HTTPException(status_code=400, detail="At least phone or email is required")

            # Generate unique token
            token = generate_token()

            # Ensure logical consistency for plus-ones
            if not data.get("plus_one_allowed", False):
                data["number_of_plus_ones_allowed"] = 0

            doc = {
                "wedding_id": wedding_id,
                "name": data["name"].strip(),
                "token": token,
                "phone": data.get("phone", "").strip() if data.get("phone") else None,
                "email": data.get("email", "").strip() if data.get("email") else None,
                "role": data.get("role", "guest"),
                "group_id": data.get("group_id"),
                "plus_one_allowed": data.get("plus_one_allowed", False),
                "number_of_plus_ones_allowed": data.get("number_of_plus_ones_allowed", 0),
                "plus_one_submitted": False,
                "sms_opt_in": True,  # Default to opted-in, guest can opt-out later
                "email_opt_in": True,  # Default to opted-in, guest can opt-out later
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            result = await self.collection.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            doc.pop("_id", None)

            # Invalidate AI cache for seating optimization
            await self._invalidate_guest_cache(wedding_id)

            return doc
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating guest: {str(e)}")
        
    
