"""
Couple Portal Service

Aggregates wedding data for the couple's portal view.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.core.database import mongo
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class CouplePortalService:
    """Service for couple portal data aggregation."""

    async def get_portal_dashboard(self, wedding_id: str, couple_email: str) -> Dict[str, Any]:
        """
        Get complete portal dashboard data for a couple.
        Aggregates wedding info, guest stats, budget summary, events, and planner info.
        """
        # Get wedding
        wedding = await mongo.get_weddings_collection().find_one({"_id": ObjectId(wedding_id)})
        if not wedding:
            return None

        # Get planner info
        planner_email = wedding.get("assigned_planner_email")
        planner = None
        if planner_email:
            planner = await mongo.get_users_collection().find_one({"email": planner_email})

        # Get guest stats (aggregated, not individual)
        guest_stats = await self._get_guest_stats(wedding_id)

        # Get budget summary (totals only, not line items)
        budget_summary = await self._get_budget_summary(wedding_id)

        # Get contract/payment info
        contract_info = await self._get_contract_info(wedding_id, couple_email)

        # Get shared forms
        shared_forms = await self._get_shared_forms(wedding_id, couple_email)

        # Get updates/milestones
        updates = await self._get_updates(wedding_id)

        return {
            "wedding": {
                "id": str(wedding["_id"]),
                "couple_names": wedding.get("couple_names"),
                "date": wedding.get("date"),
                "timezone": wedding.get("timezone", "America/Chicago"),
                "venue": wedding.get("venue"),
                "cultural_style": wedding.get("cultural_style"),
                "theme_config": wedding.get("theme_config"),
                "events": [
                    {
                        "type": e.get("type"),
                        "date": e.get("date"),
                        "details": e.get("details"),
                        "order_of_events": e.get("order_of_events", []),
                        "event_notes": e.get("event_notes", []),
                    }
                    for e in wedding.get("events", [])
                ],
                "registries": wedding.get("registries", []),
                "faqs": wedding.get("faqs", []),
            },
            "planner": {
                "name": f"{planner.get('first_name', '')} {planner.get('last_name', '')}".strip() if planner else None,
                "company": planner.get("company_name") if planner else None,
                "email": planner_email,
                "phone": planner.get("support_phone") if planner else None,
                "profile_image_url": planner.get("profile_image_url") if planner else None,
            } if planner else None,
            "guest_stats": guest_stats,
            "budget_summary": budget_summary,
            "contract": contract_info,
            "forms": shared_forms,
            "updates": updates,
        }

    async def _get_guest_stats(self, wedding_id: str) -> Dict[str, int]:
        """Get aggregated guest statistics (no individual data)."""
        try:
            guests_collection = mongo.db["guests"]

            total = await guests_collection.count_documents({"wedding_id": wedding_id})

            # Get RSVP stats
            rsvp_collection = mongo.db["rsvps"]
            confirmed = await rsvp_collection.count_documents({
                "wedding_id": wedding_id,
                "attending": True
            })
            declined = await rsvp_collection.count_documents({
                "wedding_id": wedding_id,
                "attending": False
            })
            pending = total - confirmed - declined
            if pending < 0:
                pending = 0

            return {
                "total_invited": total,
                "confirmed": confirmed,
                "declined": declined,
                "pending": pending
            }
        except Exception as e:
            logger.error(f"Error getting guest stats for wedding {wedding_id}: {e}")
            return {"total_invited": 0, "confirmed": 0, "declined": 0, "pending": 0}

    async def _get_budget_summary(self, wedding_id: str) -> Dict[str, Any]:
        """Get budget totals (not line items)."""
        try:
            budget_collection = mongo.db["budgets"]
            budget = await budget_collection.find_one({"wedding_id": wedding_id})

            if not budget:
                return {"total_budget": 0, "total_spent": 0, "remaining": 0}

            total_budget = budget.get("total_budget", 0)
            total_spent = 0

            # Sum up spent amounts from categories
            for category in budget.get("categories", []):
                for item in category.get("items", []):
                    if item.get("status") in ("paid", "deposit_paid"):
                        total_spent += item.get("actual_cost", 0) or item.get("estimated_cost", 0)

            return {
                "total_budget": total_budget,
                "total_spent": total_spent,
                "remaining": total_budget - total_spent
            }
        except Exception as e:
            logger.error(f"Error getting budget summary for wedding {wedding_id}: {e}")
            return {"total_budget": 0, "total_spent": 0, "remaining": 0}

    async def _get_contract_info(self, wedding_id: str, couple_email: str) -> Optional[Dict]:
        """Get contract and payment information for the couple."""
        try:
            contract = await mongo.db["contracts"].find_one({
                "wedding_id": wedding_id,
                "couple.email": couple_email
            })

            if not contract:
                # Try finding by wedding_id only
                contract = await mongo.db["contracts"].find_one({"wedding_id": wedding_id})

            if not contract:
                return None

            # Get payments
            payments = []
            for p in contract.get("payments", []):
                payments.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "amount": p.get("amount"),
                    "currency": p.get("currency", "usd"),
                    "due_date": p.get("due_date"),
                    "status": p.get("status"),
                    "paid_at": p.get("paid_at"),
                })

            total_amount = sum(p.get("amount", 0) for p in payments)
            paid_amount = sum(p.get("amount", 0) for p in payments if p.get("status") == "succeeded")

            return {
                "id": str(contract["_id"]),
                "status": contract.get("status"),
                "package_name": contract.get("package_name"),
                "signed_at": contract.get("signed_at").isoformat() if contract.get("signed_at") else None,
                "payments": payments,
                "summary": {
                    "total_amount": total_amount,
                    "paid_amount": paid_amount,
                    "remaining": total_amount - paid_amount
                }
            }
        except Exception as e:
            logger.error(f"Error getting contract info for wedding {wedding_id}: {e}")
            return None

    async def _get_shared_forms(self, wedding_id: str, couple_email: str) -> List[Dict]:
        """Get forms shared with this couple."""
        try:
            # Collect all shared forms first
            form_list = []
            form_ids = []
            async for form in mongo.db["forms"].find({
                "wedding_id": wedding_id,
                "$or": [
                    {"shared_with_couple": True},
                    {"target_audience": "couple"},
                    {"couple_email": couple_email}
                ]
            }).sort("created_at", -1):
                form_list.append(form)
                form_ids.append(str(form["_id"]))

            # Batch-fetch all submissions for these forms in a single query (fixes N+1)
            submissions_lookup = {}
            if form_ids:
                async for sub in mongo.db["form_submissions"].find({
                    "form_id": {"$in": form_ids},
                    "submitted_by": couple_email
                }):
                    submissions_lookup[sub["form_id"]] = sub

            # Build response
            forms = []
            for form in form_list:
                fid = str(form["_id"])
                submission = submissions_lookup.get(fid)
                forms.append({
                    "id": fid,
                    "title": form.get("title"),
                    "description": form.get("description"),
                    "status": "submitted" if submission else "pending",
                    "submitted_at": submission.get("submitted_at").isoformat() if submission and submission.get("submitted_at") else None,
                    "created_at": form.get("created_at").isoformat() if form.get("created_at") else None
                })

            return forms
        except Exception as e:
            logger.error(f"Error getting shared forms for wedding {wedding_id}: {e}")
            return []

    async def _get_updates(self, wedding_id: str) -> List[Dict]:
        """Get planner updates/milestones for the couple."""
        try:
            updates = []
            async for update in mongo.db["couple_updates"].find({
                "wedding_id": wedding_id
            }).sort("created_at", -1).limit(50):
                updates.append({
                    "id": str(update["_id"]),
                    "type": update.get("type", "update"),  # update, milestone, announcement
                    "title": update.get("title"),
                    "content": update.get("content"),
                    "category": update.get("category"),  # venue, catering, decor, timeline, etc.
                    "attachments": update.get("attachments", []),
                    "is_milestone": update.get("is_milestone", False),
                    "created_at": update.get("created_at").isoformat() if update.get("created_at") else None,
                    "created_by": update.get("created_by_name"),
                })

            return updates
        except Exception as e:
            logger.error(f"Error getting updates for wedding {wedding_id}: {e}")
            return []

    async def get_contract_for_couple(self, wedding_id: str, couple_email: str) -> Optional[Dict]:
        """
        Get full contract details for the couple portal.
        Returns payment info, sections, and timestamps — all read-only for the couple.
        Single DB query (no N+1). Access scoped to the couple's wedding.
        """
        try:
            # Find contract scoped to this wedding (same query pattern as _get_contract_info)
            contract = await mongo.db["contracts"].find_one({
                "wedding_id": wedding_id,
                "$or": [
                    {"couple.email": couple_email},
                    {"wedding_id": wedding_id}  # fallback for contracts without couple.email
                ]
            })

            if not contract:
                return None

            # Build payments summary
            payments = []
            for p in contract.get("payments", []):
                payments.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "amount": p.get("amount"),
                    "currency": p.get("currency", "usd"),
                    "due_date": p.get("due_date"),
                    "status": p.get("status"),
                    "paid_at": p.get("paid_at"),
                })

            total_amount = sum(p.get("amount", 0) for p in payments)
            paid_amount = sum(p.get("amount", 0) for p in payments if p.get("status") == "succeeded")

            # Extract sections (terms, scope, etc.) — safe for couple to read
            sections = []
            for section in contract.get("custom_sections", []):
                sections.append({
                    "title": section.get("title"),
                    "content": section.get("content"),
                })

            return {
                "id": str(contract["_id"]),
                "status": contract.get("status"),
                "package_name": contract.get("package_name"),
                "couple_name": contract.get("couple", {}).get("name"),
                "couple_email": contract.get("couple", {}).get("email"),
                "signed_at": contract.get("signed_at").isoformat() if contract.get("signed_at") else None,
                "created_at": contract.get("created_at").isoformat() if contract.get("created_at") else None,
                "sent_at": contract.get("sent_at").isoformat() if contract.get("sent_at") else None,
                "viewed_at": contract.get("viewed_at").isoformat() if contract.get("viewed_at") else None,
                "sections": sections,
                "payments": payments,
                "summary": {
                    "total_amount": total_amount,
                    "paid_amount": paid_amount,
                    "remaining": total_amount - paid_amount,
                }
            }
        except Exception as e:
            logger.error(f"Error getting contract details for wedding {wedding_id}: {e}")
            return None

    async def archive_wedding_data(self, wedding_id: str) -> Dict[str, Any]:
        """
        Archive all wedding data when a wedding is completed/removed.
        Stores in archived_weddings collection for analytics.
        Preserves couple login but marks as archived.
        """
        try:
            wedding = await mongo.get_weddings_collection().find_one({"_id": ObjectId(wedding_id)})
            if not wedding:
                return {"error": "Wedding not found"}

            # Collect all related data
            guests = []
            async for g in mongo.db["guests"].find({"wedding_id": wedding_id}):
                g["_id"] = str(g["_id"])
                guests.append(g)

            rsvps = []
            async for r in mongo.db["rsvps"].find({"wedding_id": wedding_id}):
                r["_id"] = str(r["_id"])
                rsvps.append(r)

            budget = await mongo.db["budgets"].find_one({"wedding_id": wedding_id})
            if budget:
                budget["_id"] = str(budget["_id"])

            contracts = []
            async for c in mongo.db["contracts"].find({"wedding_id": wedding_id}):
                c["_id"] = str(c["_id"])
                contracts.append(c)

            forms = []
            async for f in mongo.db["forms"].find({"wedding_id": wedding_id}):
                f["_id"] = str(f["_id"])
                forms.append(f)

            form_submissions = []
            form_ids = [f["_id"] for f in forms]
            if form_ids:
                async for fs in mongo.db["form_submissions"].find({"form_id": {"$in": form_ids}}):
                    fs["_id"] = str(fs["_id"])
                    form_submissions.append(fs)

            updates = []
            async for u in mongo.db["couple_updates"].find({"wedding_id": wedding_id}):
                u["_id"] = str(u["_id"])
                updates.append(u)

            # Build archive document
            wedding["_id"] = str(wedding["_id"])
            archive_doc = {
                "original_wedding_id": wedding_id,
                "wedding": wedding,
                "guests": guests,
                "guest_count": len(guests),
                "rsvps": rsvps,
                "budget": budget,
                "contracts": contracts,
                "forms": forms,
                "form_submissions": form_submissions,
                "updates": updates,
                "archived_at": datetime.now(timezone.utc),
                "archived_by": wedding.get("assigned_planner_email"),
                # Analytics-friendly fields
                "wedding_date": wedding.get("date"),
                "couple_names": wedding.get("couple_names"),
                "planner_email": wedding.get("assigned_planner_email"),
                "cultural_style": wedding.get("cultural_style"),
                "region": wedding.get("region"),
                "total_budget": budget.get("total_budget") if budget else None,
                "total_guests": len(guests),
                "confirmed_rsvps": len([r for r in rsvps if r.get("attending")]),
            }

            # Insert into archived_weddings collection
            result = await mongo.db["archived_weddings"].insert_one(archive_doc)

            # Mark couple accounts as archived (keep login working but show archived state)
            await mongo.db["couple_users"].update_many(
                {"wedding_id": wedding_id},
                {"$set": {
                    "wedding_archived": True,
                    "archived_at": datetime.now(timezone.utc)
                }}
            )

            logger.info(f"Wedding {wedding_id} archived successfully: {str(result.inserted_id)}")

            return {
                "archive_id": str(result.inserted_id),
                "guests_archived": len(guests),
                "rsvps_archived": len(rsvps),
                "contracts_archived": len(contracts),
                "forms_archived": len(forms),
            }
        except Exception as e:
            logger.error(f"Error archiving wedding {wedding_id}: {e}")
            raise


couple_portal_service = CouplePortalService()
