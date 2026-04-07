"""
Ad Billing Service — CPL (Cost Per Lead) Billing

Handles billing for the advertising campaign platform:
  1. Determines if a lead is billable (free tier bypass)
  2. Creates AdLeadCharge records for every lead (free or paid)
  3. For paid leads: creates Stripe invoice items + updates budget consumed
  4. Budget enforcement: pauses campaigns that hit their budget cap
  5. Vendor-level and campaign-level free tier management

Security: Only root admin can grant free tier status (per vendor or per campaign).
All campaigns track data identically regardless of billing — only Stripe charges differ.

Collections:
  - ad_lead_charges: Individual charge per lead event
  - vendor_free_tier: Vendor-level free tier overrides
  - ad_campaigns: Budget fields (budget_consumed, is_free_tier)
  - vendor_ad_billing: Period-level aggregated billing
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

logger = logging.getLogger(__name__)


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    if doc and "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc


class AdBillingService:
    """
    CPL billing service for the advertising campaign platform.

    Free tier rules (checked in order):
      1. Vendor-level: vendor_free_tier record with is_free=True and not expired
      2. Campaign-level: campaign.is_free_tier == True
      3. Default: campaign is paid, charge CPL rates

    When free tier applies, AdLeadCharge is still created (charge_amount=0,
    charge_status="free") so the data pipeline works identically.
    """

    # ── Default CPL pricing (used when campaign doesn't specify) ──
    DEFAULT_CPL_QUOTE_REQUEST = 10.00  # USD per quote request lead
    DEFAULT_CPL_DIRECTORY_ADD = 3.00  # USD per directory add lead

    def __init__(self, db, stripe_service=None):
        self.db = db
        self.campaigns = db["ad_campaigns"]
        self.lead_charges = db["ad_lead_charges"]
        self.vendor_free_tier = db["vendor_free_tier"]
        self.billing = db["vendor_ad_billing"]
        self.stripe_service = stripe_service

    # ─── Free Tier Check ──────────────────────────────────────────

    async def is_campaign_free(self, campaign: Dict[str, Any]) -> bool:
        """
        Check if a campaign should be billed at $0.

        Priority:
          1. campaign.is_free_tier (campaign-level override)
          2. vendor_free_tier record (vendor-level override)
          3. False (paid campaign)
        """
        # Campaign-level check
        if campaign.get("is_free_tier", False):
            return True

        # Vendor-level check
        vendor_id = campaign.get("vendor_id")
        if vendor_id:
            vendor_override = await self.vendor_free_tier.find_one(
                {
                    "vendor_id": vendor_id,
                    "is_free": True,
                }
            )
            if vendor_override:
                # Check expiry
                expires = vendor_override.get("expires_at")
                if expires is None or expires > datetime.now(timezone.utc):
                    return True

        return False

    # ─── CPL Charge on Lead ───────────────────────────────────────

    async def charge_for_lead(
        self,
        campaign: Dict[str, Any],
        lead_id: str,
        lead_type: str,
        planner_id: Optional[str] = None,
        click_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a CPL charge when a lead is created.

        Called by PlannerAdInteractionService after creating an ad_lead.
        Creates an AdLeadCharge record and, for paid campaigns, charges
        via Stripe and updates budget_consumed.

        Args:
            campaign: Full campaign document from MongoDB
            lead_id: The ad_lead _id (string)
            lead_type: "quote_request" or "add_to_directory"
            planner_id: Planner email for attribution
            click_id: Click attribution ID

        Returns:
            Dict with charge details (charge_id, amount, is_free, budget_status)
        """
        now = datetime.now(timezone.utc)
        campaign_id = str(campaign["_id"])
        vendor_id = campaign.get("vendor_id", "")

        # Determine if free
        is_free = await self.is_campaign_free(campaign)

        # Determine charge amount
        if is_free:
            charge_amount = 0.0
        elif lead_type == "quote_request":
            charge_amount = campaign.get(
                "cpl_quote_request", self.DEFAULT_CPL_QUOTE_REQUEST
            )
        elif lead_type == "add_to_directory":
            charge_amount = campaign.get(
                "cpl_directory_add", self.DEFAULT_CPL_DIRECTORY_ADD
            )
        else:
            charge_amount = 0.0

        # Create charge record (always — free or paid)
        charge = {
            "lead_id": lead_id,
            "campaign_id": campaign_id,
            "vendor_id": vendor_id,
            "lead_type": lead_type,
            "charge_amount": charge_amount,
            "currency": "USD",
            "is_free_tier": is_free,
            "stripe_invoice_item_id": None,
            "stripe_customer_id": None,
            "charge_status": "free" if is_free else "pending",
            "planner_id": planner_id,
            "click_id": click_id,
            "created_at": now,
            "updated_at": now,
        }

        result = await self.lead_charges.insert_one(charge)
        charge_id = str(result.inserted_id)

        # For paid campaigns: charge via Stripe + update budget
        budget_status = "ok"
        if not is_free and charge_amount > 0:
            # Update budget_consumed on campaign
            await self.campaigns.update_one(
                {"_id": campaign["_id"]},
                {
                    "$inc": {"budget_consumed": charge_amount},
                    "$set": {"updated_at": now},
                },
            )

            # Reload campaign to check budget
            updated_campaign = await self.campaigns.find_one({"_id": campaign["_id"]})
            if updated_campaign:
                budget_status = await self._check_budget_enforcement(updated_campaign)

            # Create Stripe invoice item (async, non-blocking)
            stripe_item_id = await self._create_stripe_invoice_item(
                vendor_id=vendor_id,
                campaign_id=campaign_id,
                lead_id=lead_id,
                lead_type=lead_type,
                charge_amount=charge_amount,
                charge_id=charge_id,
            )

            if stripe_item_id:
                await self.lead_charges.update_one(
                    {"_id": result.inserted_id},
                    {
                        "$set": {
                            "stripe_invoice_item_id": stripe_item_id,
                            "charge_status": "charged",
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )

        # Update period billing record
        await self._update_period_billing(
            vendor_id=vendor_id,
            campaign_id=campaign_id,
            lead_type=lead_type,
            charge_amount=charge_amount,
            is_free=is_free,
            now=now,
        )

        logger.info(
            f"CPL charge: campaign={campaign_id} lead={lead_id} "
            f"type={lead_type} amount=${charge_amount:.2f} "
            f"free={is_free} budget_status={budget_status}"
        )

        return {
            "charge_id": charge_id,
            "charge_amount": charge_amount,
            "is_free_tier": is_free,
            "charge_status": "free" if is_free else "charged",
            "budget_status": budget_status,
        }

    # ─── Budget Enforcement ───────────────────────────────────────

    async def _check_budget_enforcement(self, campaign: Dict[str, Any]) -> str:
        """
        Check if campaign has hit its budget cap and auto-pause if so.

        Returns: "ok" | "warning" | "paused"
        """
        total_budget = campaign.get("total_budget", 0)
        budget_consumed = campaign.get("budget_consumed", 0)

        # No budget cap = unlimited
        if total_budget <= 0:
            return "ok"

        usage_pct = budget_consumed / total_budget

        # 100% consumed — auto-pause
        if budget_consumed >= total_budget:
            if campaign.get("status") == "active":
                await self.campaigns.update_one(
                    {"_id": campaign["_id"]},
                    {
                        "$set": {
                            "status": "paused",
                            "metadata.paused_reason": "budget_exhausted",
                            "metadata.paused_at": datetime.now(
                                timezone.utc
                            ).isoformat(),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )
                logger.warning(
                    f"Campaign {campaign['_id']} auto-paused: "
                    f"budget ${budget_consumed:.2f} >= cap ${total_budget:.2f}"
                )

                # Notify vendor (in-portal + email + push)
                try:
                    from app.services.vendor_notification_service import (
                        VendorNotificationService,
                    )

                    vns = VendorNotificationService()
                    await vns.notify_vendor_budget_exhausted(
                        vendor_email=campaign.get("vendor_email", ""),
                        campaign_name=campaign.get(
                            "campaign_name", str(campaign["_id"])
                        ),
                        budget_consumed=budget_consumed,
                        total_budget=total_budget,
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify vendor on budget exhaustion: {e}")

            return "paused"

        # 80% consumed — warning
        if usage_pct >= 0.8:
            return "warning"

        return "ok"

    # ─── Stripe Invoice Item Creation ─────────────────────────────

    async def _create_stripe_invoice_item(
        self,
        vendor_id: str,
        campaign_id: str,
        lead_id: str,
        lead_type: str,
        charge_amount: float,
        charge_id: str,
    ) -> Optional[str]:
        """
        Create a Stripe invoice item for a CPL charge.

        Uses the vendor's Stripe customer ID. If no Stripe customer exists
        for this vendor, logs a warning and skips (billing will be reconciled
        manually or when the vendor connects Stripe).

        Returns: stripe_invoice_item_id or None
        """
        if not self.stripe_service:
            logger.debug("No Stripe service configured — skipping invoice item")
            return None

        try:
            # Look up vendor's Stripe customer ID
            stripe_customers = self.db["stripe_customers"]
            customer_doc = await stripe_customers.find_one({"user_id": vendor_id})

            if not customer_doc or not customer_doc.get("stripe_customer_id"):
                logger.warning(
                    f"No Stripe customer for vendor {vendor_id} — "
                    f"CPL charge ${charge_amount:.2f} recorded but not invoiced"
                )
                return None

            stripe_customer_id = customer_doc["stripe_customer_id"]

            # Update the charge record with customer ID
            await self.lead_charges.update_one(
                {"_id": ObjectId(charge_id)},
                {"$set": {"stripe_customer_id": stripe_customer_id}},
            )

            # Create Stripe invoice item
            import stripe

            lead_label = (
                "Quote Request" if lead_type == "quote_request" else "Directory Add"
            )
            invoice_item = stripe.InvoiceItem.create(
                customer=stripe_customer_id,
                amount=int(charge_amount * 100),  # Stripe uses cents
                currency="usd",
                description=f"CPL: {lead_label} — Campaign {campaign_id[:8]}",
                metadata={
                    "charge_id": charge_id,
                    "lead_id": lead_id,
                    "campaign_id": campaign_id,
                    "lead_type": lead_type,
                    "platform": "thespecialwedding_ads",
                },
            )
            logger.info(
                f"Stripe invoice item created: {invoice_item.id} "
                f"for ${charge_amount:.2f} ({lead_type})"
            )
            return invoice_item.id

        except Exception as e:
            logger.error(f"Failed to create Stripe invoice item: {e}")
            return None

    # ─── Period Billing Aggregation ───────────────────────────────

    async def _update_period_billing(
        self,
        vendor_id: str,
        campaign_id: str,
        lead_type: str,
        charge_amount: float,
        is_free: bool,
        now: datetime,
    ):
        """
        Upsert the vendor_ad_billing period record.

        Groups charges by (vendor_id, campaign_id, month). Updated on every
        lead event so the billing summary is always current.
        """
        # Period = first day of current month to first day of next month
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            period_end = period_start.replace(year=now.year + 1, month=1)
        else:
            period_end = period_start.replace(month=now.month + 1)

        lead_inc_field = (
            "quote_request_leads"
            if lead_type == "quote_request"
            else "directory_add_leads"
        )

        await self.billing.update_one(
            {
                "vendor_id": vendor_id,
                "campaign_id": campaign_id,
                "billing_period_start": period_start,
            },
            {
                "$inc": {
                    "leads": 1,
                    lead_inc_field: 1,
                    "total_spend": charge_amount,
                },
                "$set": {
                    "billing_period_end": period_end,
                    "is_free_tier": is_free,
                    "payment_status": "free" if is_free else "pending",
                    "currency": "USD",
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "vendor_id": vendor_id,
                    "campaign_id": campaign_id,
                    "billing_period_start": period_start,
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0,
                    "created_at": now,
                },
            },
            upsert=True,
        )

    # ─── Vendor Free Tier Management (Root Admin Only) ────────────

    async def set_vendor_free_tier(
        self,
        vendor_id: str,
        is_free: bool,
        reason: str = "",
        granted_by: str = "",
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Set or remove vendor-level free tier. Root admin only.

        When enabled, ALL campaigns from this vendor are free.
        """
        now = datetime.now(timezone.utc)

        # Look up vendor info
        users = self.db["users"]
        vendor = await users.find_one({"_id": ObjectId(vendor_id)})
        vendor_email = vendor.get("email", "") if vendor else ""
        vendor_name = vendor.get("company_name", vendor_email) if vendor else ""

        await self.vendor_free_tier.update_one(
            {"vendor_id": vendor_id},
            {
                "$set": {
                    "vendor_id": vendor_id,
                    "vendor_email": vendor_email,
                    "vendor_name": vendor_name,
                    "is_free": is_free,
                    "reason": reason,
                    "granted_by": granted_by,
                    "expires_at": expires_at,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

        logger.info(
            f"Vendor free tier {'enabled' if is_free else 'disabled'} "
            f"for {vendor_id} by {granted_by}: {reason}"
        )

        doc = await self.vendor_free_tier.find_one({"vendor_id": vendor_id})
        return _serialize(doc) if doc else {"vendor_id": vendor_id, "is_free": is_free}

    async def set_campaign_free_tier(
        self,
        campaign_id: str,
        is_free: bool,
        admin_email: str = "",
    ) -> Dict[str, Any]:
        """
        Toggle free tier on a single campaign. Root admin only.
        """
        now = datetime.now(timezone.utc)
        oid = ObjectId(campaign_id)

        campaign = await self.campaigns.find_one({"_id": oid})
        if not campaign:
            return {"error": "Campaign not found"}

        await self.campaigns.update_one(
            {"_id": oid},
            {
                "$set": {
                    "is_free_tier": is_free,
                    "metadata.free_tier_set_by": admin_email,
                    "metadata.free_tier_set_at": now.isoformat(),
                    "updated_at": now,
                },
            },
        )

        logger.info(
            f"Campaign {campaign_id} free tier {'enabled' if is_free else 'disabled'} "
            f"by {admin_email}"
        )

        updated = await self.campaigns.find_one({"_id": oid})
        return _serialize(updated) if updated else {}

    # ─── Query Methods ────────────────────────────────────────────

    async def get_vendor_free_tier_status(
        self, vendor_id: str
    ) -> Optional[Dict[str, Any]]:
        """Check if a vendor has free tier enabled."""
        doc = await self.vendor_free_tier.find_one({"vendor_id": vendor_id})
        if not doc:
            return None
        return _serialize(doc)

    async def get_lead_charges(
        self,
        campaign_id: Optional[str] = None,
        vendor_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List lead charges with optional filters."""
        query: Dict[str, Any] = {}
        if campaign_id:
            query["campaign_id"] = campaign_id
        if vendor_id:
            query["vendor_id"] = vendor_id

        cursor = (
            self.lead_charges.find(query).sort("created_at", -1).skip(skip).limit(limit)
        )
        return [_serialize(doc) async for doc in cursor]

    async def get_campaign_billing_summary(self, campaign_id: str) -> Dict[str, Any]:
        """Get billing summary for a specific campaign."""
        pipeline = [
            {"$match": {"campaign_id": campaign_id}},
            {
                "$group": {
                    "_id": None,
                    "total_charges": {"$sum": "$charge_amount"},
                    "total_leads": {"$sum": 1},
                    "quote_requests": {
                        "$sum": {
                            "$cond": [{"$eq": ["$lead_type", "quote_request"]}, 1, 0]
                        }
                    },
                    "directory_adds": {
                        "$sum": {
                            "$cond": [{"$eq": ["$lead_type", "add_to_directory"]}, 1, 0]
                        }
                    },
                    "free_leads": {"$sum": {"$cond": ["$is_free_tier", 1, 0]}},
                    "paid_leads": {"$sum": {"$cond": ["$is_free_tier", 0, 1]}},
                }
            },
        ]
        results = await self.lead_charges.aggregate(pipeline).to_list(1)
        if results:
            summary = results[0]
            summary.pop("_id", None)
            return summary
        return {
            "total_charges": 0,
            "total_leads": 0,
            "quote_requests": 0,
            "directory_adds": 0,
            "free_leads": 0,
            "paid_leads": 0,
        }

    async def list_all_free_tier_vendors(self) -> List[Dict[str, Any]]:
        """List all vendors with free tier enabled."""
        cursor = self.vendor_free_tier.find({"is_free": True}).sort("created_at", -1)
        results = []
        async for doc in cursor:
            # Check expiry
            expires = doc.get("expires_at")
            if expires and expires <= datetime.now(timezone.utc):
                continue
            results.append(_serialize(doc))
        return results

    # ─── Stripe Invoice Finalization (called by cron) ─────────────

    async def finalize_monthly_invoices(self) -> Dict[str, Any]:
        """
        Finalize pending Stripe invoices for all vendors with charges.

        Called by monthly billing cron job. Groups pending invoice items
        by customer and creates a finalized invoice for each.

        Returns: summary of invoices created
        """
        if not self.stripe_service:
            return {"status": "skipped", "reason": "no_stripe_service"}

        import stripe

        # Find all billing periods with status "pending" and non-zero spend
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        pending_billing = self.billing.find(
            {
                "payment_status": "pending",
                "total_spend": {"$gt": 0},
                "billing_period_start": {
                    "$lt": period_start
                },  # Only finalize past periods
            }
        )

        invoices_created = 0
        errors = []

        async for bill in pending_billing:
            try:
                # Get Stripe customer
                stripe_customers = self.db["stripe_customers"]
                customer_doc = await stripe_customers.find_one(
                    {"user_id": bill["vendor_id"]}
                )
                if not customer_doc:
                    continue

                customer_id = customer_doc["stripe_customer_id"]

                # Create and finalize invoice
                invoice = stripe.Invoice.create(
                    customer=customer_id,
                    auto_advance=True,
                    collection_method="charge_automatically",
                    description=(
                        f"The Special Wedding - Ad Billing "
                        f"{bill['billing_period_start'].strftime('%B %Y')}"
                    ),
                    metadata={
                        "vendor_id": bill["vendor_id"],
                        "campaign_id": bill["campaign_id"],
                        "platform": "thespecialwedding_ads",
                    },
                )

                # Finalize
                stripe.Invoice.finalize_invoice(invoice.id)

                # Update billing record
                await self.billing.update_one(
                    {"_id": bill["_id"]},
                    {
                        "$set": {
                            "payment_status": "invoiced",
                            "stripe_invoice_id": invoice.id,
                            "stripe_customer_id": customer_id,
                            "updated_at": now,
                        }
                    },
                )

                invoices_created += 1
                logger.info(
                    f"Invoice {invoice.id} created for vendor {bill['vendor_id']}"
                )

            except Exception as e:
                errors.append({"vendor_id": bill.get("vendor_id"), "error": str(e)})
                logger.error(f"Invoice creation failed: {e}")

        return {
            "status": "completed",
            "invoices_created": invoices_created,
            "errors": errors,
        }
