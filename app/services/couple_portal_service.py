"""
Couple Portal Service

Aggregates wedding data for the couple's portal view.
Sprint 3: Adds email digest generation for unread updates, messages, payments.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from app.core.database import mongo
from app.services.guest_media_service import guest_media_service
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class CouplePortalService:
    """Service for couple portal data aggregation."""

    @staticmethod
    def _normalize_attending_events(rsvp: Dict[str, Any]) -> List[str]:
        """Return a normalized list of event types a guest is attending."""
        attending = rsvp.get("attending")
        if isinstance(attending, list):
            return [event for event in attending if isinstance(event, str) and event]
        if isinstance(attending, dict):
            return [event for event, is_attending in attending.items() if is_attending]
        return []

    async def get_portal_dashboard(self, wedding_id: str, couple_email: str) -> Dict[str, Any]:
        """
        Get complete portal dashboard data for a couple.
        Aggregates wedding info, guest stats, budget summary, events, and planner info.
        """
        # Get wedding
        wedding = await mongo.get_weddings_collection().find_one({"_id": wedding_id})
        if not wedding:
            return None

        # Get planner info
        planner_email = wedding.get("assigned_planner_email")
        planner = None
        if planner_email:
            planner = await mongo.get_users_collection().find_one({"email": planner_email})

        # Get guest stats (aggregated, not individual)
        guest_stats = await self._get_guest_stats(wedding)

        # Get budget summary (totals only, not line items)
        budget_summary = await self._get_budget_summary(wedding_id)

        # Get contract/payment info
        contract_info = await self._get_contract_info(wedding_id, couple_email)

        # Get shared forms
        shared_forms = await self._get_shared_forms(wedding_id, couple_email)

        # Get updates/milestones
        updates = await self._get_updates(wedding_id)

        # Get guest memories summary
        memories_summary = await guest_media_service.get_dashboard_summary(wedding_id)

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
            "memories_summary": memories_summary,
        }

    async def _get_guest_stats(self, wedding: Dict[str, Any]) -> Dict[str, Any]:
        """Get aggregated guest statistics in couple-friendly language."""
        try:
            wedding_id = str(wedding.get("_id", ""))
            guests_collection = mongo.db["guests"]
            rsvp_collection = mongo.db["rsvps"]

            guests = await guests_collection.find(
                {"wedding_id": wedding_id},
                {"_id": 1, "invite_sent": 1},
            ).to_list(length=5000)

            guest_list_total = len(guests)
            planned_total = max(int(wedding.get("guest_count") or 0), guest_list_total)
            invited = sum(1 for guest in guests if guest.get("invite_sent"))

            rsvps = await rsvp_collection.find({
                "$or": [
                    {"wedding_id": wedding_id},
                    {"wedding_id": wedding.get("_id")},
                ]
            }).to_list(length=5000)

            confirmed = 0
            declined = 0
            responded_guest_ids: set[str] = set()
            event_counts: Dict[str, int] = {}

            for rsvp in rsvps:
                guest_id = str(rsvp.get("guest_id", ""))
                if guest_id:
                    responded_guest_ids.add(guest_id)

                attending_events = self._normalize_attending_events(rsvp)
                if attending_events:
                    confirmed += 1
                    for event_type in attending_events:
                        event_counts[event_type] = event_counts.get(event_type, 0) + 1
                else:
                    declined += 1

            responded = len(responded_guest_ids)
            pending = sum(
                1 for guest in guests
                if guest.get("invite_sent") and str(guest["_id"]) not in responded_guest_ids
            )
            not_invited = sum(
                1 for guest in guests
                if not guest.get("invite_sent") and str(guest["_id"]) not in responded_guest_ids
            )
            response_rate = min(100.0, round((responded / invited) * 100, 1)) if invited > 0 else 0.0

            configured_events = wedding.get("events", []) or []
            ordered_event_types: List[str] = []
            event_dates: Dict[str, str] = {}
            event_labels: Dict[str, str] = {}
            for event in configured_events:
                event_type = event.get("type")
                if event_type and event_type not in ordered_event_types:
                    ordered_event_types.append(event_type)
                    if event.get("date"):
                        event_dates[event_type] = event.get("date")
                    if event.get("custom_type_label"):
                        event_labels[event_type] = event.get("custom_type_label")

            for event_type in event_counts:
                if event_type not in ordered_event_types:
                    ordered_event_types.append(event_type)

            event_breakdown = [
                {
                    "event_type": event_type,
                    "custom_type_label": event_labels.get(event_type),
                    "date": event_dates.get(event_type),
                    "attending": event_counts.get(event_type, 0),
                }
                for event_type in ordered_event_types
            ]

            return {
                "planned_total": planned_total,
                "guest_list_total": guest_list_total,
                "invited": invited,
                "responded": responded,
                "confirmed": confirmed,
                "declined": declined,
                "pending": pending,
                "not_invited": not_invited,
                "response_rate": response_rate,
                "event_breakdown": event_breakdown,
            }
        except Exception as e:
            wedding_id = str(wedding.get("_id", "unknown"))
            logger.error(f"Error getting guest stats for wedding {wedding_id}: {e}")
            return {
                "planned_total": 0,
                "guest_list_total": 0,
                "invited": 0,
                "responded": 0,
                "confirmed": 0,
                "declined": 0,
                "pending": 0,
                "not_invited": 0,
                "response_rate": 0.0,
                "event_breakdown": [],
            }

    async def _get_budget_summary(self, wedding_id: str) -> Dict[str, Any]:
        """Get budget totals using the same sources as the planner budget surface."""
        try:
            wedding = await mongo.db["weddings"].find_one(
                {"_id": wedding_id},
                {"total_budget": 1},
            )
            categories_cursor = mongo.db["budget_categories"].find(
                {"wedding_id": wedding_id},
                {"budgeted_amount": 1, "actual_spent": 1},
            )
            categories = await categories_cursor.to_list(length=500)

            wedding_total_budget = wedding.get("total_budget", 0) if wedding else 0
            categories_total_budget = sum(category.get("budgeted_amount", 0) or 0 for category in categories)
            total_budget = wedding_total_budget if wedding_total_budget > 0 else categories_total_budget
            total_spent = sum(category.get("actual_spent", 0) or 0 for category in categories)

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
            wedding = await mongo.get_weddings_collection().find_one({"_id": wedding_id})
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


    # =========================================================================
    # SPRINT 3: EMAIL DIGEST
    # =========================================================================

    async def generate_couple_digest(self, couple_email: str, wedding_id: str, since: datetime) -> Optional[Dict]:
        """
        Generate digest data for a couple: unread messages, new updates, upcoming payments.
        Returns None if there's nothing new to report.
        Used by a scheduled task or API trigger to send digest emails.
        """
        try:
            # 1. Unread messages from planner
            unread_messages = await mongo.db["couple_messages"].count_documents({
                "wedding_id": wedding_id,
                "sender_role": "planner",
                "read_by_couple": False,
            })

            # 2. New updates since last digest
            new_updates = []
            async for update in mongo.db["couple_updates"].find({
                "wedding_id": wedding_id,
                "created_at": {"$gte": since},
            }).sort("created_at", -1).limit(5):
                new_updates.append({
                    "title": update.get("title"),
                    "content": update.get("content", "")[:150],
                    "created_at": update.get("created_at").isoformat() if update.get("created_at") else None,
                })

            # 3. Upcoming payments (due in next 14 days)
            upcoming_payments = []
            contract = await mongo.db["contracts"].find_one({"wedding_id": wedding_id})
            if contract:
                now = datetime.now(timezone.utc)
                cutoff = now + timedelta(days=14)
                for p in contract.get("payments", []):
                    if p.get("status") not in ("succeeded", "refunded"):
                        due_date_str = p.get("due_date")
                        if due_date_str:
                            try:
                                due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00")) if isinstance(due_date_str, str) else due_date_str
                                if now <= due_date <= cutoff:
                                    upcoming_payments.append({
                                        "name": p.get("name"),
                                        "amount": p.get("amount"),
                                        "due_date": due_date_str,
                                    })
                            except (ValueError, TypeError):
                                pass

            # 4. Pending forms
            pending_forms_count = 0
            form_ids = []
            async for form in mongo.db["forms"].find({
                "wedding_id": wedding_id,
                "$or": [
                    {"shared_with_couple": True},
                    {"target_audience": "couple"},
                    {"couple_email": couple_email},
                ]
            }):
                form_ids.append(str(form["_id"]))

            if form_ids:
                submitted_ids = set()
                async for sub in mongo.db["form_submissions"].find({
                    "form_id": {"$in": form_ids},
                    "submitted_by": couple_email,
                }):
                    submitted_ids.add(sub["form_id"])
                pending_forms_count = len(form_ids) - len(submitted_ids)

            # If nothing to report, return None
            if unread_messages == 0 and len(new_updates) == 0 and len(upcoming_payments) == 0 and pending_forms_count == 0:
                return None

            return {
                "unread_messages": unread_messages,
                "new_updates": new_updates,
                "new_updates_count": len(new_updates),
                "upcoming_payments": upcoming_payments,
                "pending_forms_count": pending_forms_count,
            }
        except Exception as e:
            logger.error(f"Error generating couple digest for {couple_email}: {e}")
            return None

    async def send_couple_digest_email(self, couple_doc: dict, digest: Dict) -> bool:
        """
        Format and send a digest email to a couple.
        Reuses the existing email_service (Resend) — no new email infra.
        """
        try:
            from app.services.email_service_resend import ResendEmailService
            email_service = ResendEmailService()
            from app.core.settings import settings

            frontend_url = getattr(settings, 'frontend_url', None) or "https://thespecialwedding.io"
            couple_name = couple_doc.get("partner1_name", "")
            if couple_doc.get("partner2_name"):
                couple_name = f"{couple_doc['partner1_name']} & {couple_doc['partner2_name']}"

            # Build digest sections
            sections_html = ""

            if digest["unread_messages"] > 0:
                sections_html += f"""
                <div style="margin-bottom: 20px; padding: 16px; background: #f0f7ff; border-radius: 8px;">
                    <h3 style="color: #1e3a5f; margin: 0 0 8px 0; font-size: 16px;">💬 {digest['unread_messages']} Unread Message{'s' if digest['unread_messages'] > 1 else ''}</h3>
                    <p style="color: #555; margin: 0; font-size: 14px;">Your planner sent you a message. Check your portal to read it.</p>
                </div>
                """

            if digest["new_updates_count"] > 0:
                updates_list = ""
                for update in digest["new_updates"]:
                    updates_list += f'<li style="margin-bottom: 8px;"><strong>{update["title"]}</strong></li>'
                sections_html += f"""
                <div style="margin-bottom: 20px; padding: 16px; background: #f8f6f3; border-radius: 8px;">
                    <h3 style="color: #1e3a5f; margin: 0 0 8px 0; font-size: 16px;">📋 {digest['new_updates_count']} New Update{'s' if digest['new_updates_count'] > 1 else ''}</h3>
                    <ul style="color: #555; font-size: 14px; padding-left: 20px; margin: 0;">{updates_list}</ul>
                </div>
                """

            if len(digest["upcoming_payments"]) > 0:
                payment_list = ""
                for p in digest["upcoming_payments"]:
                    payment_list += f'<li style="margin-bottom: 8px;">{p["name"]}: ${p["amount"]:,.0f} due {p["due_date"]}</li>'
                sections_html += f"""
                <div style="margin-bottom: 20px; padding: 16px; background: #fff8e6; border-radius: 8px;">
                    <h3 style="color: #1e3a5f; margin: 0 0 8px 0; font-size: 16px;">💰 Upcoming Payment{'s' if len(digest['upcoming_payments']) > 1 else ''}</h3>
                    <ul style="color: #555; font-size: 14px; padding-left: 20px; margin: 0;">{payment_list}</ul>
                </div>
                """

            if digest["pending_forms_count"] > 0:
                sections_html += f"""
                <div style="margin-bottom: 20px; padding: 16px; background: #f5f0eb; border-radius: 8px;">
                    <h3 style="color: #1e3a5f; margin: 0 0 8px 0; font-size: 16px;">📝 {digest['pending_forms_count']} Form{'s' if digest['pending_forms_count'] > 1 else ''} Pending</h3>
                    <p style="color: #555; margin: 0; font-size: 14px;">Your planner has forms waiting for your response.</p>
                </div>
                """

            html_content = f"""
            <div style="font-family: 'Georgia', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #1e3a5f; font-size: 28px; margin-bottom: 8px;">Your Wedding Update</h1>
                    <p style="color: #d4af37; font-size: 16px; letter-spacing: 2px;">THE SPECIAL WEDDING</p>
                </div>

                <p style="color: #333; font-size: 16px; line-height: 1.6;">
                    Hi {couple_name or 'there'}, here's what's new with your wedding:
                </p>

                {sections_html}

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{frontend_url}/couple/dashboard"
                       style="background-color: #1e3a5f; color: white; padding: 14px 32px;
                              text-decoration: none; border-radius: 6px; font-size: 16px;
                              display: inline-block;">
                        View Your Portal
                    </a>
                </div>

                <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;" />

                <p style="color: #999; font-size: 12px; text-align: center;">
                    This is a summary digest from The Special Wedding portal.
                </p>
            </div>
            """

            await email_service.send_email(
                to_email=couple_doc["email"],
                subject=f"Wedding Portal Update — {couple_name or 'Your Wedding'}",
                html_content=html_content,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send couple digest email to {couple_doc.get('email')}: {e}")
            return False


couple_portal_service = CouplePortalService()
