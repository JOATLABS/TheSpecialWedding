"""
Planner Ad Interaction Service

Phase 3: Planner-facing flows for interacting with sponsored vendor cards
in the advertising campaign platform.

Two primary flows:
  1. Add to Directory — copies vendor info from an active campaign into
     the planner's vendor_profiles collection, records attribution.
  2. Request Quote — planner sends a quote request email to the vendor,
     creates a lead, and optionally auto-adds vendor to directory.

Both flows operate on the NEW campaign-centric platform (ad_campaigns),
NOT the old sponsored_vendors system.
"""

import html
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.models.advertising_campaign import CampaignStatus

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ObjectId _id to string for JSON serialization."""
    if doc and "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc


def _to_oid(val: str, field: str = "ID") -> ObjectId:
    """Validate and convert string to ObjectId."""
    if not val:
        raise HTTPException(status_code=400, detail=f"Missing {field}")
    try:
        return ObjectId(val)
    except InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid {field} format")


class PlannerAdInteractionService:
    """
    Service for planner interactions with advertising campaign cards.

    Reads:  ad_campaigns, ad_creatives, vendor_profiles
    Writes: vendor_profiles, ad_leads, ad_events
    """

    def __init__(
        self,
        db,
        email_service=None,
        billing_service=None,
        fraud_detection_service=None,
        auction_service=None,
    ):
        self.db = db
        self.campaigns = db["ad_campaigns"]
        self.creatives = db["ad_creatives"]
        self.ad_events = db["ad_events"]
        self.ad_leads = db["ad_leads"]
        self.vendor_profiles = db["vendor_profiles"]
        self.email_service = email_service
        self.billing_service = billing_service
        self.fraud_detection_service = fraud_detection_service
        self.auction_service = auction_service

    # ─── Event Deduplication ──────────────────────────────────────────

    # Window in seconds — same planner + campaign + event_type within this
    # window is considered a duplicate and silently skipped.
    DEDUP_WINDOW_SECONDS = 300  # 5 minutes

    async def _is_duplicate_event(
        self,
        event_type: str,
        campaign_id: str,
        planner_id: str,
    ) -> bool:
        """
        Check if an identical event was already recorded within the dedup window.

        Uses an index on (event_type, campaign_id, planner_id, created_at)
        for efficient lookback.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self.DEDUP_WINDOW_SECONDS
        )
        existing = await self.ad_events.find_one(
            {
                "event_type": event_type,
                "campaign_id": campaign_id,
                "planner_id": planner_id,
                "created_at": {"$gte": cutoff},
            }
        )
        return existing is not None

    async def record_event_deduplicated(
        self,
        event_type: str,
        campaign_id: str,
        planner_id: str,
        event_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Record an ad event with deduplication. Returns the event doc if created,
        or None if it was a duplicate.

        Uses a two-layer approach:
          1. Fast pre-check (non-blocking, optimistic)
          2. Insert with DuplicateKeyError guard for race safety
             (requires compound unique index on dedup fields — see database_indexes.py)
        """
        # Layer 1: fast pre-check (avoids unnecessary insert attempts)
        if await self._is_duplicate_event(event_type, campaign_id, planner_id):
            logger.debug(
                f"Dedup: skipping {event_type} for campaign={campaign_id} planner={planner_id}"
            )
            return None

        now = datetime.now(timezone.utc)
        event = {
            "event_type": event_type,
            "campaign_id": campaign_id,
            "planner_id": planner_id,
            **event_data,
            "created_at": now,
            "updated_at": now,
        }

        # Layer 2: race-safe insert — if two concurrent requests both pass Layer 1,
        # the unique partial index catches the second one
        try:
            await self.ad_events.insert_one(event)
        except DuplicateKeyError:
            logger.debug(
                f"Dedup (race-safe): duplicate {event_type} for campaign={campaign_id} planner={planner_id}"
            )
            return None

        return event

    # ─── Shared: Resolve Campaign + Creative ─────────────────────────

    async def _get_active_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Load a campaign and verify it is active/servable."""
        oid = _to_oid(campaign_id, "campaign_id")
        campaign = await self.campaigns.find_one({"_id": oid})
        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.get("status") != CampaignStatus.ACTIVE.value:
            raise HTTPException(
                status_code=400,
                detail="Campaign is not active",
            )
        return campaign

    async def _get_primary_creative(
        self, campaign: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Load the primary creative for a campaign."""
        cid = campaign.get("primary_creative_id")
        if not cid:
            return None
        try:
            creative = await self.creatives.find_one({"_id": ObjectId(cid)})
        except InvalidId:
            return None
        return creative

    # ─── 3.3  Add to Directory ───────────────────────────────────────

    async def add_to_directory(
        self,
        campaign_id: str,
        planner_email: str,
        planner_id: Optional[str] = None,
        click_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Copy vendor info from an active campaign into the planner's
        vendor_profiles collection.

        Args:
          campaign_id: The campaign to add from.
          planner_email: Planner's email (used as created_by on vendor_profiles).
          planner_id: Planner's user ID for directory scoping and attribution.
          click_id: Optional attribution click ID.

        Steps:
          1. Verify campaign is active
          2. Create VendorProfile tagged with source: 'sponsored_ad'
             (uses insert with DuplicateKeyError guard for race-safety)
          3. Record ad_lead (lead_type: add_to_directory)
          4. Record ad_event (event_type: vendor_added_to_directory)
          5. Increment campaign lead_count

        Returns the newly created vendor profile document.
        """
        campaign = await self._get_active_campaign(campaign_id)
        vendor_id = campaign.get("vendor_id")
        vendor_email = campaign.get("vendor_email", "")
        vendor_name = campaign.get("vendor_name", "")

        now = datetime.now(timezone.utc)
        generated_click_id = click_id or str(uuid.uuid4())

        # ── 1. Create vendor profile (race-safe via unique index guard) ──
        creative = await self._get_primary_creative(campaign)

        vendor_profile = {
            "created_by": planner_email,
            "business_name": vendor_name,
            "contact_name": None,
            "email": vendor_email,
            "phone": None,
            "website": None,
            "address": None,
            "city": None,
            "state": None,
            "country": None,
            "postal_code": None,
            "service_category": campaign.get("vendor_category"),
            "service_subcategories": [],
            "service_description": creative.get("description") if creative else None,
            "internal_notes": f"Added from advertising campaign: {campaign.get('campaign_name', '')}",
            "internal_rating": None,
            "is_preferred": False,
            "tags": ["sponsored_ad"],
            "portfolio_urls": [],
            "logo_url": campaign.get("vendor_logo_url"),
            "typical_price_min": None,
            "typical_price_max": None,
            "currency": "USD",
            "pricing_notes": None,
            "max_events_per_day": None,
            "lead_time_days": None,
            "service_radius_miles": None,
            "travel_fee_notes": None,
            "business_license": None,
            "insurance_info": None,
            "tax_id": None,
            "weddings_count": 0,
            "total_revenue": 0.0,
            "last_used_at": None,
            "is_active": True,
            # ── Attribution fields (new for campaign platform) ──
            "source": "sponsored_ad",
            "source_campaign_id": campaign_id,
            "source_vendor_id": vendor_id,
            "source_creative_id": str(creative["_id"]) if creative else None,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = await self.vendor_profiles.insert_one(vendor_profile)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=409,
                detail="Vendor already in your directory from this campaign",
            )

        # Also catch the non-race-condition duplicate (pre-check for better UX
        # when unique index is not yet created — belt + suspenders)
        existing = await self.vendor_profiles.find_one(
            {
                "created_by": planner_email,
                "source_campaign_id": campaign_id,
                "_id": {"$ne": result.inserted_id},
            }
        )
        if existing:
            # Unlikely but clean up the duplicate we just inserted
            await self.vendor_profiles.delete_one({"_id": result.inserted_id})
            raise HTTPException(
                status_code=409,
                detail="Vendor already in your directory from this campaign",
            )

        vendor_profile["_id"] = str(result.inserted_id)

        # ── 2. Create ad_lead ──
        lead = {
            "campaign_id": campaign_id,
            "vendor_id": vendor_id,
            "planner_id": planner_email,
            "wedding_id": None,
            "lead_type": "add_to_directory",
            "status": "converted",  # already completed
            "click_id": generated_click_id,
            "placement": "vendor_rail",
            "message": None,
            "quote_amount": None,
            "responded_at": None,
            "converted_at": now,
            "vendor_profile_id": vendor_profile["_id"],
            "metadata": {
                "campaign_name": campaign.get("campaign_name"),
                "vendor_name": vendor_name,
            },
            "created_at": now,
            "updated_at": now,
        }
        lead_result = await self.ad_leads.insert_one(lead)
        lead["_id"] = str(lead_result.inserted_id)

        # ── 3. Record ad_event ──
        event = {
            "event_type": "vendor_added_to_directory",
            "campaign_id": campaign_id,
            "creative_id": str(creative["_id"]) if creative else None,
            "vendor_id": vendor_id,
            "placement": "vendor_rail",
            "planner_id": planner_email,
            "click_id": generated_click_id,
            "session_id": None,
            "wedding_id": None,
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }
        await self.ad_events.insert_one(event)

        # ── 3b. Fraud detection (non-blocking) ──
        if self.fraud_detection_service:
            try:
                await self.fraud_detection_service.check_click_event(
                    planner_id=planner_email,
                    campaign_id=campaign_id,
                    creative_id=str(creative["_id"]) if creative else None,
                )
            except Exception as e:
                logger.error(f"Fraud detection check failed: {e}")

        # ── 4. Increment campaign counters ──
        await self.campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {
                "$inc": {"lead_count": 1, "conversion_count": 1},
                "$set": {"updated_at": now},
            },
        )

        # ── 5. CPL billing ──
        billing_result = None
        if self.billing_service:
            try:
                billing_result = await self.billing_service.charge_for_lead(
                    campaign=campaign,
                    lead_id=lead["_id"],
                    lead_type="add_to_directory",
                    planner_id=planner_email,
                    click_id=generated_click_id,
                )
            except Exception as e:
                logger.error(f"CPL billing failed for add_to_directory lead: {e}")

        # ── 6. Push notification to vendor ──
        try:
            from app.services.vendor_notification_service import (
                VendorNotificationService,
            )

            vns = VendorNotificationService()
            await vns.notify_vendor_new_lead(
                vendor_email=campaign.get("vendor_email", ""),
                planner_name=planner_email,
                lead_type="add_to_directory",
                campaign_name=campaign.get("campaign_name", ""),
            )
        except Exception as e:
            logger.warning(
                f"Failed to push-notify vendor on add_to_directory lead: {e}"
            )

        logger.info(
            f"Planner {planner_email} added vendor {vendor_name} "
            f"to directory from campaign {campaign_id}"
        )

        return {
            "vendor_profile": vendor_profile,
            "lead_id": lead["_id"],
            "status": "added_to_directory",
            "billing": billing_result,
        }

    # ─── 3.4  Request Quote ──────────────────────────────────────────

    async def request_quote(
        self,
        campaign_id: str,
        planner_email: str,
        planner_name: str,
        planner_id: Optional[str] = None,
        wedding_id: Optional[str] = None,
        message: str = "",
        wedding_context: Optional[Dict[str, Any]] = None,
        click_id: Optional[str] = None,
        auto_add_to_directory: bool = True,
    ) -> Dict[str, Any]:
        """
        Planner sends a quote request to the advertising vendor.

        Steps:
          1. Verify campaign is active
          2. Create ad_lead (lead_type: quote_request)
          3. Record ad_event (event_type: lead_created)
          4. Increment campaign lead_count
          5. Send email to vendor
          6. Optionally auto-add vendor to planner's directory

        wedding_context is optional enrichment data:
          {date, location, guest_count, venue, budget_range}
        """
        campaign = await self._get_active_campaign(campaign_id)
        vendor_id = campaign.get("vendor_id")
        vendor_email = campaign.get("vendor_email", "")
        vendor_name = campaign.get("vendor_name", "")

        if not message.strip():
            raise HTTPException(
                status_code=400,
                detail="Quote request message cannot be empty",
            )

        now = datetime.now(timezone.utc)
        generated_click_id = click_id or str(uuid.uuid4())
        creative = await self._get_primary_creative(campaign)

        # ── 1. Create ad_lead ──
        lead = {
            "campaign_id": campaign_id,
            "vendor_id": vendor_id,
            "planner_id": planner_email,
            "wedding_id": wedding_id,
            "lead_type": "quote_request",
            "status": "pending",
            "click_id": generated_click_id,
            "placement": "vendor_rail",
            "message": message,
            "quote_amount": None,
            "responded_at": None,
            "converted_at": None,
            "metadata": {
                "campaign_name": campaign.get("campaign_name"),
                "vendor_name": vendor_name,
                "planner_name": planner_name,
                "wedding_context": wedding_context or {},
            },
            "created_at": now,
            "updated_at": now,
        }
        lead_result = await self.ad_leads.insert_one(lead)
        lead["_id"] = str(lead_result.inserted_id)

        # ── 2. Record ad_event ──
        event = {
            "event_type": "lead_created",
            "campaign_id": campaign_id,
            "creative_id": str(creative["_id"]) if creative else None,
            "vendor_id": vendor_id,
            "placement": "vendor_rail",
            "planner_id": planner_email,
            "click_id": generated_click_id,
            "session_id": None,
            "wedding_id": wedding_id,
            "metadata": {"lead_type": "quote_request"},
            "created_at": now,
            "updated_at": now,
        }
        await self.ad_events.insert_one(event)

        # ── 2b. Fraud detection (non-blocking) ──
        if self.fraud_detection_service:
            try:
                await self.fraud_detection_service.check_click_event(
                    planner_id=planner_email,
                    campaign_id=campaign_id,
                    creative_id=str(creative["_id"]) if creative else None,
                )
            except Exception as e:
                logger.error(f"Fraud detection check failed: {e}")

        # ── 3. Increment campaign counters ──
        await self.campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {
                "$inc": {"lead_count": 1},
                "$set": {"updated_at": now},
            },
        )

        # ── 3b. CPL billing ──
        billing_result = None
        if self.billing_service:
            try:
                billing_result = await self.billing_service.charge_for_lead(
                    campaign=campaign,
                    lead_id=lead["_id"],
                    lead_type="quote_request",
                    planner_id=planner_email,
                    click_id=generated_click_id,
                )
            except Exception as e:
                logger.error(f"CPL billing failed for quote_request lead: {e}")

        # ── 4. Send email to vendor ──
        email_sent = False
        if self.email_service and vendor_email:
            try:
                subject = f"Quote Request from {planner_name} — The Special Wedding"
                html_content = self._build_quote_email_html(
                    planner_name=planner_name,
                    planner_email=planner_email,
                    vendor_name=vendor_name,
                    campaign_name=campaign.get("campaign_name", ""),
                    message=message,
                    wedding_context=wedding_context,
                )
                await self.email_service.send_email(
                    to_email=vendor_email,
                    subject=subject,
                    html_content=html_content,
                    from_name=f"{planner_name} via The Special Wedding",
                    reply_to=planner_email,
                    email_type="ad_quote_request",
                )
                email_sent = True
                logger.info(f"Quote request email sent to {vendor_email}")
            except Exception as e:
                logger.error(f"Failed to send quote request email: {e}")

        # ── 4b. Push notification to vendor ──
        try:
            from app.services.vendor_notification_service import (
                VendorNotificationService,
            )

            vns = VendorNotificationService()
            await vns.notify_vendor_new_lead(
                vendor_email=vendor_email,
                planner_name=planner_name,
                lead_type="quote_request",
                campaign_name=campaign.get("campaign_name", ""),
            )
        except Exception as e:
            logger.warning(f"Failed to push-notify vendor on quote_request lead: {e}")

        # ── 5. Auto-add vendor to directory if not already present ──
        directory_entry = None
        if auto_add_to_directory:
            existing = await self.vendor_profiles.find_one(
                {
                    "created_by": planner_email,
                    "source_campaign_id": campaign_id,
                }
            )
            if not existing:
                directory_entry = await self._create_directory_entry(
                    campaign=campaign,
                    creative=creative,
                    planner_email=planner_email,
                    now=now,
                    planner_id=planner_id,
                )
                # Back-fill vendor_profile_id on the lead for full attribution
                if directory_entry:
                    await self.ad_leads.update_one(
                        {"_id": ObjectId(lead["_id"])},
                        {"$set": {"vendor_profile_id": directory_entry["_id"]}},
                    )

        logger.info(
            f"Planner {planner_email} sent quote request to {vendor_name} "
            f"for campaign {campaign_id}"
        )

        return {
            "lead_id": lead["_id"],
            "status": "quote_requested",
            "email_sent": email_sent,
            "auto_added_to_directory": directory_entry is not None,
            "vendor_profile_id": (
                directory_entry.get("_id") if directory_entry else None
            ),
            "billing": billing_result,
        }

    async def _create_directory_entry(
        self,
        campaign: Dict[str, Any],
        creative: Optional[Dict[str, Any]],
        planner_email: str,
        now: datetime,
        planner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a slim vendor profile entry (shared between flows)."""
        campaign_id = (
            str(campaign["_id"])
            if isinstance(campaign.get("_id"), ObjectId)
            else campaign.get("_id", "")
        )

        vendor_profile = {
            "created_by": planner_email,
            "business_name": campaign.get("vendor_name", ""),
            "contact_name": None,
            "email": campaign.get("vendor_email", ""),
            "phone": None,
            "website": None,
            "address": None,
            "city": None,
            "state": None,
            "country": None,
            "postal_code": None,
            "service_category": campaign.get("vendor_category"),
            "service_subcategories": [],
            "service_description": creative.get("description") if creative else None,
            "internal_notes": f"Auto-added from quote request — campaign: {campaign.get('campaign_name', '')}",
            "internal_rating": None,
            "is_preferred": False,
            "tags": ["sponsored_ad", "auto_added"],
            "portfolio_urls": [],
            "logo_url": campaign.get("vendor_logo_url"),
            "typical_price_min": None,
            "typical_price_max": None,
            "currency": "USD",
            "pricing_notes": None,
            "max_events_per_day": None,
            "lead_time_days": None,
            "service_radius_miles": None,
            "travel_fee_notes": None,
            "business_license": None,
            "insurance_info": None,
            "tax_id": None,
            "weddings_count": 0,
            "total_revenue": 0.0,
            "last_used_at": None,
            "is_active": True,
            "source": "sponsored_ad",
            "source_campaign_id": campaign_id,
            "source_vendor_id": campaign.get("vendor_id"),
            "source_creative_id": str(creative["_id"]) if creative else None,
            "created_at": now,
            "updated_at": now,
        }
        result = await self.vendor_profiles.insert_one(vendor_profile)
        vendor_profile["_id"] = str(result.inserted_id)
        return vendor_profile

    def _build_quote_email_html(
        self,
        planner_name: str,
        planner_email: str,
        vendor_name: str,
        campaign_name: str,
        message: str,
        wedding_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the HTML email body for a quote request.

        All user-supplied strings are HTML-escaped to prevent injection.
        """
        # Escape all user-supplied content
        esc = html.escape
        ctx = wedding_context or {}
        wedding_details = ""
        if ctx:
            parts = []
            if ctx.get("date"):
                parts.append(f"<strong>Date:</strong> {esc(str(ctx['date']))}")
            if ctx.get("location"):
                parts.append(f"<strong>Location:</strong> {esc(str(ctx['location']))}")
            if ctx.get("guest_count"):
                parts.append(
                    f"<strong>Guest Count:</strong> {esc(str(ctx['guest_count']))}"
                )
            if ctx.get("venue"):
                parts.append(f"<strong>Venue:</strong> {esc(str(ctx['venue']))}")
            if ctx.get("budget_range"):
                parts.append(
                    f"<strong>Budget Range:</strong> {esc(str(ctx['budget_range']))}"
                )
            if parts:
                wedding_details = (
                    '<div style="background:#f8fafc;border:1px solid #e5e7eb;'
                    'border-radius:8px;padding:16px;margin:16px 0;">'
                    '<h3 style="margin:0 0 8px;color:#1D3557;">Wedding Details</h3>'
                    + "<br>".join(parts)
                    + "</div>"
                )

        return f"""
        <div style="font-family:'Inter',sans-serif;max-width:600px;margin:0 auto;">
            <div style="background:linear-gradient(135deg,#1D3557,#457B9D);padding:24px;
                        border-radius:12px 12px 0 0;color:white;">
                <h1 style="margin:0;font-size:20px;">New Quote Request</h1>
                <p style="margin:4px 0 0;opacity:0.8;">via The Special Wedding</p>
            </div>
            <div style="padding:24px;border:1px solid #e5e7eb;border-top:none;
                        border-radius:0 0 12px 12px;">
                <p>Hi {esc(vendor_name)},</p>
                <p><strong>{esc(planner_name)}</strong> ({esc(planner_email)}) has requested a
                quote through your advertising campaign
                <em>&ldquo;{esc(campaign_name)}&rdquo;</em>.</p>

                <div style="background:#f0fdf4;border:1px solid #bbf7d0;
                            border-radius:8px;padding:16px;margin:16px 0;">
                    <h3 style="margin:0 0 8px;color:#166534;">Message</h3>
                    <p style="margin:0;white-space:pre-wrap;">{esc(message)}</p>
                </div>

                {wedding_details}

                <p>Reply directly to this email to respond to the planner, or
                   visit your <a href="https://vendor.thespecialwedding.io/portal/ads/leads">
                   Vendor Portal</a> to manage your leads.</p>

                <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
                <p style="font-size:12px;color:#9ca3af;">
                    This email was sent because your campaign is active on
                    The Special Wedding advertising platform.
                </p>
            </div>
        </div>
        """

    # ─── Planner Ad Serving (delegates to VendorCampaignService) ─────

    async def get_sponsored_cards(
        self,
        planner_email: str,
        planner_id: Optional[str] = None,
        planner_location: Optional[str] = None,
        categories: Optional[List[str]] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Get sponsored vendor cards for the planner rail.

        Filters out:
        - Vendors the planner has already added to their directory
        - Vendors the planner has hidden (planner_ad_preferences)
        - Suppressed categories (planner_ad_preferences)
        Respects reduced_frequency setting (max 1 card if enabled).
        """
        now = datetime.now(timezone.utc)

        # ── Load planner ad preferences ──
        hidden_vendor_ids = []
        suppressed_categories = []
        reduced_frequency = False
        if planner_id:
            prefs = await self.db["planner_ad_preferences"].find_one(
                {"planner_id": planner_id}
            )
            if prefs:
                hidden_vendor_ids = prefs.get("hidden_vendor_ids", [])
                suppressed_categories = prefs.get("suppressed_categories", [])
                reduced_frequency = prefs.get("reduced_frequency", False)

        # Override limit if planner has reduced frequency enabled
        if reduced_frequency:
            limit = 1

        # ── Get campaigns the planner already interacted with ──
        already_added_campaign_ids = []
        async for profile in self.vendor_profiles.find(
            {"created_by": planner_email, "source": "sponsored_ad"},
            {"source_campaign_id": 1},
        ):
            cid = profile.get("source_campaign_id")
            if cid:
                already_added_campaign_ids.append(cid)

        # ── Query active, servable campaigns ──
        query: Dict[str, Any] = {
            "status": CampaignStatus.ACTIVE.value,
            "primary_creative_id": {"$ne": None},
            "$and": [
                {
                    "$or": [
                        {"start_date": {"$lte": now}},
                        {"start_date": {"$in": [None]}},
                        {"start_date": {"$exists": False}},
                    ]
                },
                {
                    "$or": [
                        {"end_date": {"$gte": now}},
                        {"end_date": {"$in": [None]}},
                        {"end_date": {"$exists": False}},
                    ]
                },
            ],
        }

        if already_added_campaign_ids:
            query["_id"] = {
                "$nin": [
                    ObjectId(c)
                    for c in already_added_campaign_ids
                    if ObjectId.is_valid(c)
                ]
            }

        # Filter out hidden vendors
        if hidden_vendor_ids:
            query["vendor_id"] = {"$nin": hidden_vendor_ids}

        # Filter out suppressed categories
        if suppressed_categories:
            query["vendor_category"] = {"$nin": suppressed_categories}

        if categories:
            # Merge with existing vendor_category filter if suppressed_categories set
            if "vendor_category" in query:
                query["vendor_category"] = {
                    "$in": [c for c in categories if c not in suppressed_categories],
                }
            else:
                query["vendor_category"] = {"$in": categories}

        if planner_location:
            # Nest inside existing $and to avoid overwriting date checks
            query["$and"].append(
                {
                    "$or": [
                        {"target_regions": {"$size": 0}},
                        {
                            "target_regions": {
                                "$regex": planner_location,
                                "$options": "i",
                            }
                        },
                    ]
                }
            )

        # Fetch eligible campaigns, dedup by vendor_id
        seen_vendors = set()
        eligible_campaigns = []
        async for campaign in (
            self.campaigns.find(query).sort("quality_score", -1).limit(limit * 5)
        ):
            vid = campaign.get("vendor_id")
            if vid in seen_vendors:
                continue
            seen_vendors.add(vid)
            eligible_campaigns.append(campaign)

        # ── Auction-based ranking (if auction service available) ──
        if self.auction_service and eligible_campaigns:
            try:
                auction_results = await self.auction_service.run_auction(
                    eligible_campaigns=eligible_campaigns,
                    max_winners=limit,
                )

                results = []
                for winner in auction_results:
                    campaign = winner["campaign"]
                    creative = await self._get_primary_creative(campaign)
                    card = {
                        "campaign_id": str(campaign["_id"]),
                        "vendor_id": campaign.get("vendor_id"),
                        "vendor_name": campaign.get("vendor_name"),
                        "vendor_category": campaign.get("vendor_category"),
                        "vendor_service_area": campaign.get("vendor_service_area"),
                        "vendor_logo_url": campaign.get("vendor_logo_url"),
                        "quality_score": campaign.get("quality_score", 50),
                        # Auction metadata (not exposed to planner UI, used for billing/analytics)
                        "adrank": winner["adrank"],
                        "position": winner["position"],
                        "effective_cost": winner["effective_cost"],
                        "estimated_action_rate": winner["estimated_action_rate"],
                        "creative": (
                            {
                                "creative_id": (
                                    str(creative["_id"]) if creative else None
                                ),
                                "headline": (
                                    creative.get("headline") if creative else None
                                ),
                                "description": (
                                    creative.get("description") if creative else None
                                ),
                                "image_url": (
                                    creative.get("image_url") if creative else None
                                ),
                                "offer": creative.get("offer") if creative else None,
                                "call_to_action": (
                                    creative.get("call_to_action", "View Portfolio")
                                    if creative
                                    else "View Portfolio"
                                ),
                            }
                            if creative
                            else None
                        ),
                        "in_directory": False,
                        "targeting_reason": self._build_targeting_reason(
                            campaign, planner_location
                        ),
                    }
                    results.append(card)

                return results

            except Exception as e:
                logger.error(
                    f"Auction engine failed, falling back to quality_score sort: {e}"
                )
                # Fall through to legacy quality_score ranking below

        # ── Legacy fallback: quality_score sort (no auction service) ──
        results = []
        for campaign in eligible_campaigns[:limit]:
            creative = await self._get_primary_creative(campaign)
            card = {
                "campaign_id": str(campaign["_id"]),
                "vendor_id": campaign.get("vendor_id"),
                "vendor_name": campaign.get("vendor_name"),
                "vendor_category": campaign.get("vendor_category"),
                "vendor_service_area": campaign.get("vendor_service_area"),
                "vendor_logo_url": campaign.get("vendor_logo_url"),
                "quality_score": campaign.get("quality_score", 50),
                "creative": (
                    {
                        "creative_id": str(creative["_id"]) if creative else None,
                        "headline": creative.get("headline") if creative else None,
                        "description": (
                            creative.get("description") if creative else None
                        ),
                        "image_url": creative.get("image_url") if creative else None,
                        "offer": creative.get("offer") if creative else None,
                        "call_to_action": (
                            creative.get("call_to_action", "View Portfolio")
                            if creative
                            else "View Portfolio"
                        ),
                    }
                    if creative
                    else None
                ),
                "in_directory": False,
                "targeting_reason": self._build_targeting_reason(
                    campaign, planner_location
                ),
            }
            results.append(card)

        return results

    @staticmethod
    def _build_targeting_reason(
        campaign: Dict[str, Any], planner_location: Optional[str] = None
    ) -> str:
        """
        Build an FTC-compliant targeting disclosure string explaining
        why this sponsored content is being shown to the planner.

        Per FTC native advertising guidelines, sponsored content must
        clearly disclose its commercial nature and targeting rationale.
        """
        reasons = []

        # Location match
        target_regions = campaign.get("target_regions", [])
        if planner_location and target_regions:
            reasons.append(f"your location ({planner_location})")
        elif target_regions:
            reasons.append("your area")

        # Category match
        category = campaign.get("vendor_category", "")
        if category:
            label = category.replace("_", " ").title()
            reasons.append(f"your interest in {label} services")

        # Goal-based
        goal = campaign.get("campaign_goal", "")
        if goal == "quote_requests":
            reasons.append("vendors seeking quotes")
        elif goal == "profile_visits":
            reasons.append("vendor discovery")

        if reasons:
            return f"Based on {', '.join(reasons)}"
        return "Sponsored recommendation for your wedding"

    # ─── Check Directory Status ──────────────────────────────────────

    async def check_directory_status(
        self,
        campaign_id: str,
        planner_email: str,
    ) -> Dict[str, Any]:
        """Check if a planner already has this campaign's vendor in their directory."""
        existing = await self.vendor_profiles.find_one(
            {
                "created_by": planner_email,
                "source_campaign_id": campaign_id,
            }
        )
        return {
            "campaign_id": campaign_id,
            "in_directory": existing is not None,
            "vendor_profile_id": str(existing["_id"]) if existing else None,
        }
