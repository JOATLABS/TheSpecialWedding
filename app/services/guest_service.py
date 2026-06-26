import logging
import re
from collections import Counter
from datetime import datetime, timezone
from math import ceil
from typing import Any, Optional

from fastapi import HTTPException

from app.core.database import mongo
from app.utils.contact_sanitizer import sanitize_phone
from app.utils.id_utils import normalize_doc_id, to_object_id, to_str_id
from app.utils.rsvp_status import (
    RSVP_FILTER_NOT_INVITED,
    RSVP_FILTER_RESPONDED,
    RSVP_STATUS_CONFIRMED,
    RSVP_STATUS_DECLINED,
    RSVP_STATUS_PENDING,
    get_rsvp_status,
)
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
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]

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
            guest = await self.collection.find_one(
                {"token": token, "wedding_id": wedding_id}
            )
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            normalize_doc_id(guest)
            guest.pop("_id", None)
            return guest
        except Exception as e:
            raise HTTPException(
                status_code=500, detail="Error retrieving guest: {}".format(str(e))
            )

    async def get_guest(self, guest_id: str):
        """Fetch a guest by ObjectId or string id."""
        obj_id = to_object_id(guest_id, "guest_id")
        guest = await self.collection.find_one({"_id": obj_id})
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        normalize_doc_id(guest)
        guest.pop("_id", None)
        return guest

    async def update_guest_timestamps(self, guest_id, created=False):
        """Update guest timestamps"""
        update_data = {"updated_at": datetime.now(timezone.utc)}
        if created:
            update_data["created_at"] = datetime.now(timezone.utc)

        obj_id = to_object_id(guest_id, "guest_id")
        await self.collection.update_one({"_id": obj_id}, {"$set": update_data})

    def _build_guest_match(
        self,
        wedding_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        group_id: Optional[str] = None,
        role: Optional[str] = None,
        phone_issue: Optional[str] = None,
        sms_status: Optional[str] = None,
    ) -> dict[str, Any]:
        match: dict[str, Any] = {"wedding_id": wedding_id}
        and_clauses: list[dict[str, Any]] = []

        if group_id:
            match["group_id"] = group_id
        if role:
            match["role"] = role

        if sms_status == "opted_out":
            match["sms_opt_in"] = False
        elif sms_status == "opted_in":
            match["sms_opt_in"] = True

        if phone_issue == "invalid_or_unreachable":
            match["phone_status"] = {"$in": ["invalid", "landline", "unreachable"]}

        if name:
            and_clauses.append({"name": {"$regex": re.escape(name), "$options": "i"}})
        if email:
            and_clauses.append({"email": {"$regex": re.escape(email), "$options": "i"}})
        if phone:
            sanitized_phone = sanitize_phone(phone) or phone
            and_clauses.append(
                {"phone": {"$regex": re.escape(sanitized_phone), "$options": "i"}}
            )
        if phone_issue == "no_contact":
            and_clauses.append(
                {
                    "$and": [
                        {
                            "$or": [
                                {"phone": {"$exists": False}},
                                {"phone": None},
                                {"phone": ""},
                            ]
                        },
                        {
                            "$or": [
                                {"email": {"$exists": False}},
                                {"email": None},
                                {"email": ""},
                            ]
                        },
                    ]
                }
            )

        if and_clauses:
            match["$and"] = and_clauses

        return match

    def _build_guest_sort(self, sort_field: str, sort_direction: str) -> dict[str, int]:
        sort_direction_value = -1 if sort_direction == "desc" else 1
        sort_key = {
            "name": "name",
            "email": "email",
            "phone": "phone",
            "role": "role",
            "group_id": "group_id",
            "rsvp_status": "rsvp_sort_order",
            "plus_ones": "plus_one_count",
        }.get(sort_field, "name")

        return {
            sort_key: sort_direction_value,
            "name": 1,
            "_id": 1,
        }

    def _rsvp_array_count_expression(self, attending_field: str) -> dict[str, Any]:
        return {
            "$cond": [
                {"$isArray": attending_field},
                {"$size": attending_field},
                -1,
            ]
        }

    def _rsvp_object_true_count_expression(
        self, attending_field: str
    ) -> dict[str, Any]:
        return {
            "$cond": [
                {"$eq": [{"$type": attending_field}, "object"]},
                {
                    "$size": {
                        "$filter": {
                            "input": {"$objectToArray": attending_field},
                            "as": "entry",
                            "cond": {"$toBool": "$$entry.v"},
                        }
                    }
                },
                0,
            ]
        }

    def _rsvp_status_expression(
        self, attending_field: str = "$rsvp_attending"
    ) -> dict[str, Any]:
        array_count = self._rsvp_array_count_expression(attending_field)
        object_true_count = self._rsvp_object_true_count_expression(attending_field)

        return {
            "$switch": {
                "branches": [
                    {
                        "case": {"$gt": [array_count, 0]},
                        "then": RSVP_STATUS_CONFIRMED,
                    },
                    {
                        "case": {"$eq": [array_count, 0]},
                        "then": RSVP_STATUS_DECLINED,
                    },
                    {
                        "case": {"$gt": [object_true_count, 0]},
                        "then": RSVP_STATUS_CONFIRMED,
                    },
                    {
                        "case": {"$eq": [{"$type": attending_field}, "object"]},
                        "then": RSVP_STATUS_DECLINED,
                    },
                ],
                "default": RSVP_STATUS_PENDING,
            }
        }

    async def _build_guest_summary(self, wedding_id: str) -> dict[str, int]:
        guest_docs = await self.collection.find(
            {"wedding_id": wedding_id},
            projection={
                "_id": 1,
                "invite_sent": 1,
                "number_of_plus_ones_allowed": 1,
            },
        ).to_list(length=None)

        if not guest_docs:
            return {
                "totalGuests": 0,
                "invitedGuests": 0,
                "notInvitedGuests": 0,
                "respondedGuests": 0,
                "confirmedGuests": 0,
                "declinedGuests": 0,
                "pendingGuests": 0,
                "totalPlusOneSlots": 0,
                "respondedPlusOnes": 0,
                "pendingPlusOneSlots": 0,
                "submittedPlusOnes": 0,
            }

        guest_ids_obj = [guest["_id"] for guest in guest_docs]
        guest_ids_str = [to_str_id(guest["_id"]) for guest in guest_docs]

        rsvp_docs = await self.rsvp_collection.find(
            {
                "$or": [
                    {"guest_id": {"$in": guest_ids_obj}},
                    {"guest_id": {"$in": guest_ids_str}},
                ]
            },
            projection={"guest_id": 1, "attending": 1},
        ).to_list(length=None)
        rsvp_status_by_guest: dict[str, str] = {}
        for doc in rsvp_docs:
            guest_id_key = str(doc.get("guest_id"))
            if guest_id_key:
                rsvp_status_by_guest[guest_id_key] = get_rsvp_status(doc)
        responded_guest_ids = set(rsvp_status_by_guest.keys())

        plus_one_docs = await self.plus_one_collection.find(
            {"guest_id": {"$in": guest_ids_str}},
            projection={"guest_id": 1},
        ).to_list(length=None)
        plus_one_counts = Counter(
            str(doc.get("guest_id")) for doc in plus_one_docs if doc.get("guest_id")
        )

        total_plus_one_slots = 0
        invited_guests = 0
        responded_guests = 0
        confirmed_guests = 0
        declined_guests = 0
        responded_plus_ones = 0
        pending_guests = 0
        pending_plus_one_slots = 0
        not_invited_guests = 0

        for guest, guest_id in zip(guest_docs, guest_ids_str):
            plus_one_slots = int(guest.get("number_of_plus_ones_allowed") or 0)
            invited = guest.get("invite_sent") is True
            has_rsvp = guest_id in responded_guest_ids

            total_plus_one_slots += plus_one_slots

            # `invited` covers anyone who got an invite, regardless of RSVP.
            # Responding implies they were invited; we count them too.
            if invited or has_rsvp:
                invited_guests += 1

            if has_rsvp:
                responded_guests += 1
                responded_plus_ones += plus_one_counts.get(guest_id, 0)
                status = rsvp_status_by_guest.get(guest_id)
                if status == RSVP_STATUS_CONFIRMED:
                    confirmed_guests += 1
                elif status == RSVP_STATUS_DECLINED:
                    declined_guests += 1
                continue

            if invited:
                pending_guests += 1
                pending_plus_one_slots += plus_one_slots
            else:
                not_invited_guests += 1

        return {
            "totalGuests": len(guest_docs),
            "invitedGuests": invited_guests,
            "notInvitedGuests": not_invited_guests,
            "respondedGuests": responded_guests,
            "confirmedGuests": confirmed_guests,
            "declinedGuests": declined_guests,
            "pendingGuests": pending_guests,
            "totalPlusOneSlots": total_plus_one_slots,
            "respondedPlusOnes": responded_plus_ones,
            "pendingPlusOneSlots": pending_plus_one_slots,
            "submittedPlusOnes": len(plus_one_docs),
        }

    async def _build_guest_filter_options(
        self, wedding_id: str
    ) -> dict[str, list[str]]:
        groups = await self.collection.distinct(
            "group_id",
            {
                "wedding_id": wedding_id,
                "group_id": {"$exists": True, "$nin": [None, ""]},
            },
        )
        roles = await self.collection.distinct(
            "role",
            {"wedding_id": wedding_id, "role": {"$exists": True, "$nin": [None, ""]}},
        )

        return {
            "groups": sorted([group for group in groups if isinstance(group, str)]),
            "roles": sorted([role for role in roles if isinstance(role, str)]),
        }

    async def list_guests_by_wedding(
        self,
        wedding_id: str,
        page: int = 1,
        limit: int = 50,
        fetch_all: bool = False,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        group_id: Optional[str] = None,
        role: Optional[str] = None,
        rsvp_status: str = "all",
        plus_one_status: str = "all",
        phone_issue: str = "all",
        sms_status: str = "all",
        sort_field: str = "name",
        sort_direction: str = "asc",
    ):
        """
        Retrieve guests for a wedding with pagination.

        Args:
            wedding_id: The wedding ID to filter by
            page: Page number (1-indexed), defaults to 1
            limit: Number of guests per page, defaults to 50

        Returns:
            A dict containing:
            - guests: List of guest documents
            - total: Total number of guests for this wedding
            - page: Current page number
            - pages: Total number of pages
            - limit: Guests per page
        """
        try:
            match = self._build_guest_match(
                wedding_id=wedding_id,
                name=name,
                email=email,
                phone=phone,
                group_id=group_id,
                role=role,
                phone_issue=phone_issue if phone_issue != "all" else None,
                sms_status=sms_status if sms_status != "all" else None,
            )

            requires_rsvp_lookup = rsvp_status != "all" or sort_field == "rsvp_status"
            requires_plus_one_lookup = (
                plus_one_status != "all" or sort_field == "plus_ones"
            )

            pipeline: list[dict[str, Any]] = [{"$match": match}]
            add_fields: dict[str, Any] = {}

            if requires_rsvp_lookup:
                pipeline.append(
                    {
                        "$lookup": {
                            "from": "rsvps",
                            "let": {
                                "guest_object_id": "$_id",
                                "guest_id_str": {"$toString": "$_id"},
                            },
                            "pipeline": [
                                {
                                    "$match": {
                                        "$expr": {
                                            "$or": [
                                                {
                                                    "$eq": [
                                                        "$guest_id",
                                                        "$$guest_object_id",
                                                    ]
                                                },
                                                {
                                                    "$eq": [
                                                        "$guest_id",
                                                        "$$guest_id_str",
                                                    ]
                                                },
                                            ]
                                        }
                                    }
                                },
                                {"$project": {"attending": 1}},
                            ],
                            "as": "rsvp_docs",
                        }
                    }
                )
                add_fields["has_rsvp"] = {"$gt": [{"$size": "$rsvp_docs"}, 0]}
                add_fields["rsvp_attending"] = {
                    "$arrayElemAt": ["$rsvp_docs.attending", 0]
                }

            if requires_plus_one_lookup:
                pipeline.append(
                    {
                        "$lookup": {
                            "from": "plus_ones",
                            "let": {"guest_id_str": {"$toString": "$_id"}},
                            "pipeline": [
                                {
                                    "$match": {
                                        "$expr": {
                                            "$eq": ["$guest_id", "$$guest_id_str"]
                                        }
                                    }
                                }
                            ],
                            "as": "plus_one_docs",
                        }
                    }
                )
                add_fields["plus_one_count"] = {"$size": "$plus_one_docs"}

            if add_fields:
                pipeline.append({"$addFields": add_fields})

            if requires_rsvp_lookup:
                pipeline.append(
                    {
                        "$addFields": {
                            "rsvp_status_detail": self._rsvp_status_expression()
                        }
                    }
                )
                pipeline.append(
                    {
                        "$addFields": {
                            "rsvp_sort_order": {
                                "$switch": {
                                    "branches": [
                                        {
                                            "case": {
                                                "$eq": [
                                                    "$rsvp_status_detail",
                                                    RSVP_STATUS_CONFIRMED,
                                                ]
                                            },
                                            "then": 3,
                                        },
                                        {
                                            "case": {
                                                "$eq": [
                                                    "$rsvp_status_detail",
                                                    RSVP_STATUS_DECLINED,
                                                ]
                                            },
                                            "then": 2,
                                        },
                                        {
                                            "case": {"$eq": ["$invite_sent", True]},
                                            "then": 1,
                                        },
                                    ],
                                    "default": 0,
                                }
                            }
                        }
                    }
                )

            post_lookup_clauses: list[dict[str, Any]] = []
            if rsvp_status == RSVP_FILTER_RESPONDED:
                post_lookup_clauses.append({"has_rsvp": True})
            elif rsvp_status == RSVP_STATUS_CONFIRMED:
                post_lookup_clauses.append(
                    {"rsvp_status_detail": RSVP_STATUS_CONFIRMED}
                )
            elif rsvp_status == RSVP_STATUS_DECLINED:
                post_lookup_clauses.append({"rsvp_status_detail": RSVP_STATUS_DECLINED})
            elif rsvp_status == RSVP_STATUS_PENDING:
                post_lookup_clauses.append({"invite_sent": True, "has_rsvp": False})
            elif rsvp_status == RSVP_FILTER_NOT_INVITED:
                post_lookup_clauses.append(
                    {"invite_sent": {"$ne": True}, "has_rsvp": False}
                )

            if plus_one_status == "submitted":
                post_lookup_clauses.append({"plus_one_count": {"$gt": 0}})
            elif plus_one_status == "allowed":
                post_lookup_clauses.append({"plus_one_allowed": True})
            elif plus_one_status == "none":
                post_lookup_clauses.append(
                    {"plus_one_allowed": {"$ne": True}, "plus_one_count": 0}
                )

            if post_lookup_clauses:
                pipeline.append(
                    {
                        "$match": (
                            {"$and": post_lookup_clauses}
                            if len(post_lookup_clauses) > 1
                            else post_lookup_clauses[0]
                        )
                    }
                )

            pipeline.append(
                {"$sort": self._build_guest_sort(sort_field, sort_direction)}
            )

            skip = 0 if fetch_all else (page - 1) * limit
            paginated_items: list[dict[str, Any]] = []
            if not fetch_all:
                paginated_items.extend([{"$skip": skip}, {"$limit": limit}])
            paginated_items.append(
                {
                    "$project": {
                        "rsvp_docs": 0,
                        "plus_one_docs": 0,
                        "has_rsvp": 0,
                        "rsvp_attending": 0,
                        "rsvp_status_detail": 0,
                        "plus_one_count": 0,
                        "rsvp_sort_order": 0,
                    }
                }
            )
            pipeline.append(
                {
                    "$facet": {
                        "items": paginated_items,
                        "totalCount": [{"$count": "count"}],
                    }
                }
            )

            result = await self.collection.aggregate(pipeline).to_list(length=1)
            aggregate_result = result[0] if result else {"items": [], "totalCount": []}
            guests = aggregate_result.get("items", [])
            total = (
                aggregate_result["totalCount"][0]["count"]
                if aggregate_result.get("totalCount")
                else 0
            )
            pages = 1 if fetch_all else (ceil(total / limit) if limit > 0 else 1)

            # Normalize IDs
            for guest in guests:
                normalize_doc_id(guest)
                guest.pop("_id", None)

            summary = await self._build_guest_summary(wedding_id)
            filter_options = await self._build_guest_filter_options(wedding_id)
            response_limit = total if fetch_all else limit

            return {
                "guests": guests,
                "total": total,
                "page": 1 if fetch_all else page,
                "pages": pages,
                "limit": response_limit,
                "summary": summary,
                "filter_options": filter_options,
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error retrieving guests: {str(e)}"
            )

    async def list_all_guests_by_wedding(self, wedding_id: str):
        """
        Retrieve all guests for a wedding without pagination.
        Used for features like seating optimization that need the full guest list.

        Args:
            wedding_id: The wedding ID to filter by

        Returns:
            A list of all guest documents for the wedding
        """
        try:
            guests = await self.collection.find({"wedding_id": wedding_id}).to_list(
                length=None
            )
            for guest in guests:
                normalize_doc_id(guest)
                guest.pop("_id", None)
            return guests
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error retrieving guests: {str(e)}"
            )

    async def update_guest(self, guest_id: str, update_data: dict):
        try:
            # Remove fields that shouldn't be updated
            update_data.pop("_id", None)
            update_data.pop("id", None)
            update_data.pop("token", None)  # Don't allow token changes
            update_data.pop("wedding_id", None)  # Don't allow wedding changes

            # Add timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)

            obj_id = to_object_id(guest_id, "guest_id")
            result = await self.collection.update_one(
                {"_id": obj_id}, {"$set": update_data}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Return updated guest
            updated_guest = await self.collection.find_one({"_id": obj_id})
            normalize_doc_id(updated_guest)
            updated_guest.pop("_id", None)

            # Invalidate AI cache for seating optimization
            if updated_guest.get("wedding_id"):
                await self._invalidate_guest_cache(updated_guest["wedding_id"])

            return updated_guest
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error updating guest: {str(e)}"
            )

    async def delete_guest(self, guest_id: str):
        try:
            # Convert guest_id to ObjectId
            guest_obj_id = to_object_id(guest_id, "guest_id")
            guest_id_str = to_str_id(guest_obj_id)

            # Check if guest exists
            guest = await self.collection.find_one({"_id": guest_obj_id})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            # Get collections for RSVPs and plus-ones
            rsvp_collection = mongo.db["rsvps"]
            plus_one_collection = mongo.db["plus_ones"]

            # Delete associated RSVPs (handle both ObjectId and string formats)
            rsvp_result = await rsvp_collection.delete_many(
                {"$or": [{"guest_id": guest_obj_id}, {"guest_id": guest_id_str}]}
            )

            # Delete associated plus-ones (typically stored with string guest_id)
            plus_one_result = await plus_one_collection.delete_many(
                {"$or": [{"guest_id": guest_obj_id}, {"guest_id": guest_id_str}]}
            )

            # Clean up orphan seating constraint references (T2/T6)
            # Remove this guest's ID from other guests' must_sit_with and must_sit_apart arrays
            wedding_id = guest.get("wedding_id")
            if wedding_id:
                await self.collection.update_many(
                    {
                        "wedding_id": wedding_id,
                        "$or": [
                            {"must_sit_with": guest_id_str},
                            {"must_sit_apart": guest_id_str},
                        ],
                    },
                    {
                        "$pull": {
                            "must_sit_with": guest_id_str,
                            "must_sit_apart": guest_id_str,
                        }
                    },
                )

            # Delete the guest
            guest_result = await self.collection.delete_one({"_id": guest_obj_id})

            # Invalidate AI cache for seating optimization
            if wedding_id:
                await self._invalidate_guest_cache(wedding_id)

            return {
                "message": "Guest and associated data deleted successfully",
                "deleted": {
                    "guest": guest_result.deleted_count,
                    "rsvps": rsvp_result.deleted_count,
                    "plus_ones": plus_one_result.deleted_count,
                },
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error deleting guest: {str(e)}"
            )

    async def get_guest_by_phone_or_name(
        self,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        wedding_id: Optional[str] = None,
    ):
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
                raise HTTPException(
                    status_code=400, detail="Must provide phone or name to search"
                )

            guest = await self.collection.find_one(query)
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            normalize_doc_id(guest)
            guest.pop("_id", None)
            return guest
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail="Error retrieving guest: {}".format(str(e))
            )

    async def create_guest(self, guest_data, wedding_id: str):
        """Create a single guest for a wedding."""
        try:
            # Convert Pydantic model to dict
            data = (
                guest_data.model_dump()
                if hasattr(guest_data, "model_dump")
                else guest_data.dict()
            )

            # Require at least phone or email
            if not data.get("phone") and not data.get("email"):
                raise HTTPException(
                    status_code=400, detail="At least phone or email is required"
                )

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
                "number_of_plus_ones_allowed": data.get(
                    "number_of_plus_ones_allowed", 0
                ),
                "plus_one_submitted": False,
                "sms_opt_in": True,  # Default to opted-in, guest can opt-out later
                "email_opt_in": True,  # Default to opted-in, guest can opt-out later
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            result = await self.collection.insert_one(doc)
            doc["id"] = to_str_id(result.inserted_id)
            doc.pop("_id", None)

            # Invalidate AI cache for seating optimization
            await self._invalidate_guest_cache(wedding_id)

            return doc
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error creating guest: {str(e)}"
            )
