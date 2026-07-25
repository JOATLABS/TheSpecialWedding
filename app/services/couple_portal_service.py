"""
Couple Portal Service

Aggregates wedding data for the couple's portal view.
Sprint 3: Adds email digest generation for unread updates, messages, payments.
"""

import asyncio
import html
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from app.core.database import mongo
from app.services.guest_media_service import guest_media_service
from app.utils.messaging_roles import SENDER_ROLE_PLANNER
from app.utils.planner_ownership import resolve_wedding_owner_identity

logger = logging.getLogger(__name__)


class CouplePortalService:
    """Service for couple portal data aggregation."""

    @staticmethod
    def _normalize_attending_events(rsvp: dict[str, Any]) -> list[str]:
        """Return a normalized list of event types a guest is attending."""
        attending = rsvp.get("attending")
        if isinstance(attending, list):
            return [event for event in attending if isinstance(event, str) and event]
        if isinstance(attending, dict):
            return [event for event, is_attending in attending.items() if is_attending]
        return []

    async def get_portal_dashboard(
        self, wedding_id: str, couple_email: str
    ) -> dict[str, Any] | None:
        """
        Get complete portal dashboard data for a couple.
        Aggregates wedding info, guest stats, budget summary, events, and planner info.
        """
        wedding = await mongo.get_weddings_collection().find_one(
            {"_id": wedding_id},
            {
                "couple_names": 1,
                "date": 1,
                "timezone": 1,
                "venue": 1,
                "cultural_style": 1,
                "theme_config": 1,
                "events": 1,
                "registries": 1,
                "faqs": 1,
                "assigned_planner_id": 1,
                "assigned_planner_email": 1,
            },
        )
        if not wedding:
            return None

        owner_identity = await resolve_wedding_owner_identity(wedding)
        planner_email = owner_identity.get("planner_email")
        planner_task = (
            mongo.get_users_collection().find_one(
                {"email": planner_email},
                {
                    "first_name": 1,
                    "last_name": 1,
                    "company_name": 1,
                    "support_phone": 1,
                    "profile_image_url": 1,
                },
            )
            if planner_email
            else asyncio.sleep(0, result=None)
        )

        (
            planner,
            guest_stats,
            budget_summary,
            contract_info,
            shared_forms,
            updates,
            memories_summary,
        ) = await asyncio.gather(
            planner_task,
            self._get_guest_stats(wedding),
            self._get_budget_summary(wedding_id),
            self._get_contract_info(wedding_id, couple_email),
            self._get_shared_forms(wedding_id, couple_email),
            self._get_updates(wedding_id),
            guest_media_service.get_dashboard_summary(wedding_id),
        )
        planner = cast(dict[str, Any] | None, planner)

        dashboard = {
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
            "planner": (
                {
                    "name": (
                        f"{planner.get('first_name', '')} {planner.get('last_name', '')}".strip()
                        if planner
                        else None
                    ),
                    "company": planner.get("company_name") if planner else None,
                    "email": planner_email,
                    "phone": planner.get("support_phone") if planner else None,
                    "profile_image_url": (
                        planner.get("profile_image_url") if planner else None
                    ),
                }
                if planner
                else None
            ),
            "guest_stats": guest_stats,
            "budget_summary": budget_summary,
            "contract": contract_info,
            "forms": shared_forms,
            "updates": updates,
            "memories_summary": memories_summary,
        }

        return dashboard

    async def _get_guest_stats(self, wedding: dict[str, Any]) -> dict[str, Any]:
        """Get aggregated guest statistics in couple-friendly language."""
        try:
            wedding_id = str(wedding.get("_id", ""))
            guests_collection = mongo.db["guests"]
            rsvp_collection = mongo.db["rsvps"]

            guests_task = guests_collection.find(
                {"wedding_id": wedding_id},
                {"_id": 1, "invite_sent": 1},
            ).to_list(length=5000)

            rsvps_task = rsvp_collection.find(
                {
                    "$or": [
                        {"wedding_id": wedding_id},
                        {"wedding_id": wedding.get("_id")},
                    ]
                },
                {
                    "guest_id": 1,
                    "attending": 1,
                },
            ).to_list(length=5000)

            guests, rsvps = await asyncio.gather(guests_task, rsvps_task)

            guest_list_total = len(guests)
            planned_total = max(int(wedding.get("guest_count") or 0), guest_list_total)
            invited = sum(1 for guest in guests if guest.get("invite_sent"))

            confirmed = 0
            declined = 0
            responded_guest_ids: set[str] = set()
            event_counts: dict[str, int] = {}

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
                1
                for guest in guests
                if guest.get("invite_sent")
                and str(guest["_id"]) not in responded_guest_ids
            )
            not_invited = sum(
                1
                for guest in guests
                if not guest.get("invite_sent")
                and str(guest["_id"]) not in responded_guest_ids
            )
            response_rate = (
                min(100.0, round((responded / invited) * 100, 1))
                if invited > 0
                else 0.0
            )

            configured_events = wedding.get("events", []) or []
            ordered_event_types: list[str] = []
            event_dates: dict[str, str] = {}
            event_labels: dict[str, str] = {}
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

    async def _get_budget_summary(self, wedding_id: str) -> dict[str, Any]:
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
            categories_total_budget = sum(
                category.get("budgeted_amount", 0) or 0 for category in categories
            )
            total_budget = (
                wedding_total_budget
                if wedding_total_budget > 0
                else categories_total_budget
            )
            total_spent = sum(
                category.get("actual_spent", 0) or 0 for category in categories
            )

            return {
                "total_budget": total_budget,
                "total_spent": total_spent,
                "remaining": total_budget - total_spent,
            }
        except Exception as e:
            logger.error(f"Error getting budget summary for wedding {wedding_id}: {e}")
            return {"total_budget": 0, "total_spent": 0, "remaining": 0}

    async def _get_contract_payments(self, contract: dict[str, Any]) -> list[dict]:
        """Read the canonical scheduled-payment rows for a client contract."""
        contract_id = str(contract["_id"])
        cursor = (
            mongo.db["scheduled_payments"]
            .find({"contract_id": contract_id})
            .sort("due_date", 1)
        )
        scheduled_payments = await cursor.to_list(length=None)
        source_payments = scheduled_payments or contract.get("payments") or []

        return [
            {
                "id": str(payment.get("id") or payment.get("_id")),
                "name": payment.get("name"),
                "amount": float(payment.get("amount", 0) or 0),
                "currency": payment.get("currency", "usd"),
                "due_date": payment.get("due_date"),
                "status": payment.get("status"),
                "paid_at": payment.get("paid_at"),
            }
            for payment in source_payments
        ]

    @staticmethod
    def _contract_total_amount(contract: dict[str, Any], payments: list[dict]) -> float:
        """Prefer the signed package total, with legacy fallbacks."""
        package_snapshot = contract.get("package_snapshot") or {}
        total_amount = package_snapshot.get("total_amount")
        if total_amount is None:
            total_amount = contract.get("total_amount")
        if total_amount is None:
            total_amount = sum(payment.get("amount", 0) or 0 for payment in payments)
        return float(total_amount or 0)

    async def _get_contract_info(
        self, wedding_id: str, couple_email: str
    ) -> dict | None:
        """Get contract and payment information for the couple."""
        try:
            contract = await mongo.db["contracts"].find_one(
                {"wedding_id": wedding_id, "couple.email": couple_email},
                {
                    "status": 1,
                    "package_name": 1,
                    "package_snapshot": 1,
                    "total_amount": 1,
                    "signed_at": 1,
                    "payments": 1,
                },
            )

            if not contract:
                # Try finding by wedding_id only
                contract = await mongo.db["contracts"].find_one(
                    {"wedding_id": wedding_id},
                    {
                        "status": 1,
                        "package_name": 1,
                        "package_snapshot": 1,
                        "total_amount": 1,
                        "signed_at": 1,
                        "payments": 1,
                    },
                )

            if not contract:
                return None

            payments = await self._get_contract_payments(contract)
            total_amount = self._contract_total_amount(contract, payments)
            paid_amount = sum(
                (p.get("amount", 0) or 0)
                for p in payments
                if p.get("status") == "succeeded"
            )
            package_snapshot = contract.get("package_snapshot") or {}

            return {
                "id": str(contract["_id"]),
                "status": contract.get("status"),
                "package_name": contract.get("package_name")
                or package_snapshot.get("name"),
                "signed_at": (
                    contract.get("signed_at").isoformat()
                    if contract.get("signed_at")
                    else None
                ),
                "payments": payments,
                "summary": {
                    "total_amount": total_amount,
                    "paid_amount": paid_amount,
                    "remaining": total_amount - paid_amount,
                },
            }
        except Exception as e:
            logger.error(f"Error getting contract info for wedding {wedding_id}: {e}")
            return None

    async def _get_shared_forms(self, wedding_id: str, couple_email: str) -> list[dict]:
        """Get forms shared with this couple."""
        try:
            # Collect all shared forms first
            form_list = []
            form_ids = []
            async for form in (
                mongo.db["forms"]
                .find(
                    {
                        "wedding_id": wedding_id,
                        "$or": [
                            {"shared_with_couple": True},
                            {"target_audience": "couple"},
                            {"couple_email": couple_email},
                        ],
                    },
                    {
                        "title": 1,
                        "description": 1,
                        "created_at": 1,
                    },
                )
                .sort("created_at", -1)
            ):
                form_list.append(form)
                form_ids.append(str(form["_id"]))

            # Batch-fetch all submissions for these forms in a single query (fixes N+1)
            submissions_lookup = {}
            if form_ids:
                async for sub in mongo.db["form_submissions"].find(
                    {"form_id": {"$in": form_ids}, "submitted_by": couple_email}
                ):
                    submissions_lookup[sub["form_id"]] = sub

            # Build response
            forms = []
            for form in form_list:
                fid = str(form["_id"])
                submission = submissions_lookup.get(fid)
                forms.append(
                    {
                        "id": fid,
                        "title": form.get("title"),
                        "description": form.get("description"),
                        "status": "submitted" if submission else "pending",
                        "submitted_at": (
                            submission.get("submitted_at").isoformat()
                            if submission and submission.get("submitted_at")
                            else None
                        ),
                        "created_at": (
                            form.get("created_at").isoformat()
                            if form.get("created_at")
                            else None
                        ),
                    }
                )

            return forms
        except Exception as e:
            logger.error(f"Error getting shared forms for wedding {wedding_id}: {e}")
            return []

    async def _get_updates(self, wedding_id: str) -> list[dict]:
        """Get planner updates/milestones for the couple."""
        try:
            updates = []
            async for update in (
                mongo.db["couple_updates"]
                .find(
                    {"wedding_id": wedding_id},
                    {
                        "type": 1,
                        "title": 1,
                        "content": 1,
                        "category": 1,
                        "attachments": 1,
                        "is_milestone": 1,
                        "created_at": 1,
                        "created_by_name": 1,
                    },
                )
                .sort("created_at", -1)
                .limit(50)
            ):
                updates.append(
                    {
                        "id": str(update["_id"]),
                        "type": update.get(
                            "type", "update"
                        ),  # update, milestone, announcement
                        "title": update.get("title"),
                        "content": update.get("content"),
                        "category": update.get(
                            "category"
                        ),  # venue, catering, decor, timeline, etc.
                        "attachments": update.get("attachments", []),
                        "is_milestone": update.get("is_milestone", False),
                        "created_at": (
                            update.get("created_at").isoformat()
                            if update.get("created_at")
                            else None
                        ),
                        "created_by": update.get("created_by_name"),
                    }
                )

            return updates
        except Exception as e:
            logger.error(f"Error getting updates for wedding {wedding_id}: {e}")
            return []

    async def get_contract_for_couple(
        self, wedding_id: str, couple_email: str
    ) -> dict | None:
        """
        Get full contract details for the couple portal.
        Returns payment info, sections, and timestamps — all read-only for the couple.
        Single DB query (no N+1). Access scoped to the couple's wedding.
        """
        try:
            # Find contract scoped to this wedding (same query pattern as _get_contract_info)
            contract = await mongo.db["contracts"].find_one(
                {
                    "wedding_id": wedding_id,
                    "$or": [
                        {"couple.email": couple_email},
                        {
                            "wedding_id": wedding_id
                        },  # fallback for contracts without couple.email
                    ],
                }
            )

            if not contract:
                return None

            payments = await self._get_contract_payments(contract)
            total_amount = self._contract_total_amount(contract, payments)
            paid_amount = sum(
                (p.get("amount", 0) or 0)
                for p in payments
                if p.get("status") == "succeeded"
            )
            package_snapshot = contract.get("package_snapshot") or {}

            # Extract sections (terms, scope, etc.) — safe for couple to read
            sections = []
            for section in contract.get("custom_sections", []):
                sections.append(
                    {
                        "title": section.get("title"),
                        "content": section.get("content"),
                    }
                )

            return {
                "id": str(contract["_id"]),
                "status": contract.get("status"),
                "package_name": contract.get("package_name")
                or package_snapshot.get("name"),
                "couple_name": contract.get("couple", {}).get("name"),
                "couple_email": contract.get("couple", {}).get("email"),
                "signed_at": (
                    contract.get("signed_at").isoformat()
                    if contract.get("signed_at")
                    else None
                ),
                "created_at": (
                    contract.get("created_at").isoformat()
                    if contract.get("created_at")
                    else None
                ),
                "sent_at": (
                    contract.get("sent_at").isoformat()
                    if contract.get("sent_at")
                    else None
                ),
                "viewed_at": (
                    contract.get("viewed_at").isoformat()
                    if contract.get("viewed_at")
                    else None
                ),
                "sections": sections,
                "payments": payments,
                "summary": {
                    "total_amount": total_amount,
                    "paid_amount": paid_amount,
                    "remaining": total_amount - paid_amount,
                },
            }
        except Exception as e:
            logger.error(
                f"Error getting contract details for wedding {wedding_id}: {e}"
            )
            return None

    async def archive_wedding_data(self, wedding_id: str) -> dict[str, Any]:
        """
        Archive all wedding data when a wedding is completed/removed.
        Stores in archived_weddings collection for analytics.
        Preserves couple login but marks as archived.
        """
        try:
            wedding = await mongo.get_weddings_collection().find_one(
                {"_id": wedding_id}
            )
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
                async for fs in mongo.db["form_submissions"].find(
                    {"form_id": {"$in": form_ids}}
                ):
                    fs["_id"] = str(fs["_id"])
                    form_submissions.append(fs)

            updates = []
            async for u in mongo.db["couple_updates"].find({"wedding_id": wedding_id}):
                u["_id"] = str(u["_id"])
                updates.append(u)

            # Build archive document
            wedding["_id"] = str(wedding["_id"])
            owner_identity = await resolve_wedding_owner_identity(wedding)
            planner_email = owner_identity.get("planner_email")
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
                "archived_at": datetime.now(UTC),
                "archived_by": planner_email,
                # Analytics-friendly fields
                "wedding_date": wedding.get("date"),
                "couple_names": wedding.get("couple_names"),
                "planner_email": planner_email,
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
                {
                    "$set": {
                        "wedding_archived": True,
                        "archived_at": datetime.now(UTC),
                    }
                },
            )

            logger.info(
                f"Wedding {wedding_id} archived successfully: {result.inserted_id!s}"
            )

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

    async def generate_couple_digest(
        self, couple_email: str, wedding_id: str, since: datetime
    ) -> dict | None:
        """
        Generate digest data for a couple: unread messages, new updates, upcoming payments.
        Returns None if there's nothing new to report.
        Used by a scheduled task or API trigger to send digest emails.
        """
        try:
            # 1. Unread messages from planner
            unread_messages = await mongo.db["couple_messages"].count_documents(
                {
                    "wedding_id": wedding_id,
                    "sender_role": SENDER_ROLE_PLANNER,
                    "read_by_couple": False,
                }
            )

            # 2. New updates since last digest
            new_updates = []
            async for update in (
                mongo.db["couple_updates"]
                .find(
                    {
                        "wedding_id": wedding_id,
                        "created_at": {"$gte": since},
                    }
                )
                .sort("created_at", -1)
                .limit(5)
            ):
                new_updates.append(
                    {
                        "title": update.get("title"),
                        "content": update.get("content", "")[:150],
                        "created_at": (
                            update.get("created_at").isoformat()
                            if update.get("created_at")
                            else None
                        ),
                    }
                )

            # 3. Upcoming payments (due in next 14 days)
            upcoming_payments = []
            contract = await mongo.db["contracts"].find_one({"wedding_id": wedding_id})
            if contract:
                now = datetime.now(UTC)
                cutoff = now + timedelta(days=14)
                for p in contract.get("payments", []):
                    if p.get("status") not in ("succeeded", "refunded"):
                        due_date_str = p.get("due_date")
                        if due_date_str:
                            try:
                                due_date = (
                                    datetime.fromisoformat(
                                        due_date_str.replace("Z", "+00:00")
                                    )
                                    if isinstance(due_date_str, str)
                                    else due_date_str
                                )
                                if now <= due_date <= cutoff:
                                    upcoming_payments.append(
                                        {
                                            "name": p.get("name"),
                                            "amount": p.get("amount"),
                                            "due_date": due_date_str,
                                        }
                                    )
                            except (ValueError, TypeError):
                                pass

            # 4. Pending forms
            pending_forms_count = 0
            form_ids = []
            async for form in mongo.db["forms"].find(
                {
                    "wedding_id": wedding_id,
                    "$or": [
                        {"shared_with_couple": True},
                        {"target_audience": "couple"},
                        {"couple_email": couple_email},
                    ],
                }
            ):
                form_ids.append(str(form["_id"]))

            if form_ids:
                submitted_ids = set()
                async for sub in mongo.db["form_submissions"].find(
                    {
                        "form_id": {"$in": form_ids},
                        "submitted_by": couple_email,
                    }
                ):
                    submitted_ids.add(sub["form_id"])
                pending_forms_count = len(form_ids) - len(submitted_ids)

            # If nothing to report, return None
            if (
                unread_messages == 0
                and len(new_updates) == 0
                and len(upcoming_payments) == 0
                and pending_forms_count == 0
            ):
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

    async def send_couple_digest_email(self, couple_doc: dict, digest: dict) -> bool:
        """
        Format and send a digest email to a couple.
        Reuses the existing email_service (Resend) — no new email infra.
        """
        try:
            from app.services.email_service_resend import ResendEmailService

            email_service = ResendEmailService()
            from app.core.settings import settings

            frontend_url = (
                getattr(settings, "frontend_url", None)
                or "https://thespecialwedding.io"
            )
            couple_name = couple_doc.get("partner1_name", "")
            if couple_doc.get("partner2_name"):
                couple_name = (
                    f"{couple_doc['partner1_name']} & {couple_doc['partner2_name']}"
                )

            # Build digest sections
            sections_html = ""

            if digest["unread_messages"] > 0:
                safe_unread_count = html.escape(
                    str(digest["unread_messages"]), quote=True
                )
                sections_html += f"""
                <div style="margin-bottom: 20px; padding: 16px; background: #f0f7ff; border-radius: 8px;">
                    <h3 style="color: #1e3a5f; margin: 0 0 8px 0; font-size: 16px;">💬 {safe_unread_count} Unread Message{"s" if digest["unread_messages"] > 1 else ""}</h3>
                    <p style="color: #555; margin: 0; font-size: 14px;">Your planner sent you a message. Check your portal to read it.</p>
                </div>
                """

            if digest["new_updates_count"] > 0:
                updates_list = ""
                for update in digest["new_updates"]:
                    safe_update_title = html.escape(
                        str(update.get("title", "")), quote=True
                    )
                    updates_list += f'<li style="margin-bottom: 8px;"><strong>{safe_update_title}</strong></li>'
                safe_updates_count = html.escape(
                    str(digest["new_updates_count"]), quote=True
                )
                sections_html += f"""
                <div style="margin-bottom: 20px; padding: 16px; background: #f8f6f3; border-radius: 8px;">
                    <h3 style="color: #1e3a5f; margin: 0 0 8px 0; font-size: 16px;">📋 {safe_updates_count} New Update{"s" if digest["new_updates_count"] > 1 else ""}</h3>
                    <ul style="color: #555; font-size: 14px; padding-left: 20px; margin: 0;">{updates_list}</ul>
                </div>
                """

            if len(digest["upcoming_payments"]) > 0:
                payment_list = ""
                for p in digest["upcoming_payments"]:
                    safe_payment_name = html.escape(str(p.get("name", "")), quote=True)
                    safe_due_date = html.escape(str(p.get("due_date", "")), quote=True)
                    payment_list += f'<li style="margin-bottom: 8px;">{safe_payment_name}: ${p["amount"]:,.0f} due {safe_due_date}</li>'
                sections_html += f"""
                <div style="margin-bottom: 20px; padding: 16px; background: #fff8e6; border-radius: 8px;">
                    <h3 style="color: #1e3a5f; margin: 0 0 8px 0; font-size: 16px;">💰 Upcoming Payment{"s" if len(digest["upcoming_payments"]) > 1 else ""}</h3>
                    <ul style="color: #555; font-size: 14px; padding-left: 20px; margin: 0;">{payment_list}</ul>
                </div>
                """

            if digest["pending_forms_count"] > 0:
                safe_pending_forms_count = html.escape(
                    str(digest["pending_forms_count"]), quote=True
                )
                sections_html += f"""
                <div style="margin-bottom: 20px; padding: 16px; background: #f5f0eb; border-radius: 8px;">
                    <h3 style="color: #1e3a5f; margin: 0 0 8px 0; font-size: 16px;">📝 {safe_pending_forms_count} Form{"s" if digest["pending_forms_count"] > 1 else ""} Pending</h3>
                    <p style="color: #555; margin: 0; font-size: 14px;">Your planner has forms waiting for your response.</p>
                </div>
                """

            safe_couple_name = html.escape(couple_name or "there", quote=True)
            safe_dashboard_url = html.escape(
                f"{frontend_url}/couple/dashboard", quote=True
            )

            html_content = f"""
            <div style="font-family: 'Georgia', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #1e3a5f; font-size: 28px; margin-bottom: 8px;">Your Wedding Update</h1>
                    <p style="color: #d4af37; font-size: 16px; letter-spacing: 2px;">THE SPECIAL WEDDING</p>
                </div>

                <p style="color: #333; font-size: 16px; line-height: 1.6;">
                    Hi {safe_couple_name}, here's what's new with your wedding:
                </p>

                {sections_html}

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{safe_dashboard_url}"
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
            logger.error(
                f"Failed to send couple digest email to {couple_doc.get('email')}: {e}"
            )
            return False


couple_portal_service = CouplePortalService()
