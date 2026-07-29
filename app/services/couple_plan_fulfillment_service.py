# app/services/couple_plan_fulfillment_service.py
"""Fulfillment for the self-serve Couple Plan — One Wedding purchase.

A couple pays through the live Stripe Payment Link (mode=payment, price id in
env STRIPE_COUPLE_LIFETIME_PRICE_ID). Stripe fires ``checkout.session.completed``
at the existing ``/stripe/webhook`` endpoint; ``StripeService`` routes one-time
payment sessions whose line-item price matches the couple offer here.

Account model (operator ruling 2026-07-28): the couple-plan purchaser uses the
PLANNER dashboard for their own single wedding. They are NOT a couple-portal
user — they ARE the couple, so their workspace has no couple-portal surfaces
at all. Their entitlements come from the internal ``plan_couple`` subscription
plan (see app/constants/billing.py::COUPLE_PLAN_SEED): one wedding, no service
packages, no couple-portal invitations, no team seats.

What fulfillment provisions (idempotently, keyed on the checkout session id):

1. The internal ``plan_couple`` plan document, if it does not exist yet
   (insert-only — an operator-edited plan document is never overwritten).
2. A wedding workspace document (``weddings``) flagged ``self_serve_couple``.
   It has no owner yet; ownership is attached when the buyer claims their
   account. The workspace follows the standard wedding lifecycle: it stays
   active through 90 days after the wedding date and is then removed by the
   existing archival/cleanup path. NOT lifetime access.
3. A ``user_invitations`` row carrying ``invite_data.couple_plan=True`` — the
   exact mechanism admin-invited planners use. The buyer sets a password at
   ``/setup-account/{token}`` (existing page); ``complete_account_setup``
   detects the couple flag, creates the planner-dashboard account as
   immediately ACTIVE (no trial, no pending_payment — they already paid),
   assigns the ``plan_couple`` subscription, and attaches the wedding.
4. A payment audit row in ``payment_records`` under the sentinel
   ``category_id="platform:couple_plan"`` (never a real budget category, so
   wedding budget aggregations — which join through the wedding's own
   budget_categories — can never pick it up).
5. A welcome/claim email through the existing Resend email service. A paying
   couple gets into their workspace with zero manual steps from us.

Edge handling:

- Email already backs an existing planner/user account: we must NOT create a
  second account on the same email (dashboard login is a single
  email/password surface). The paid session is never dropped: we record the
  payment, open a ``couple_plan_fulfillment_issues`` row, notify support, and
  email the customer an acknowledgement.
- A pending invitation already exists for the email (e.g. an admin invite in
  flight): flagged for support the same way — auto-creating a competing
  invitation would race the admin flow.
- Email belongs to an existing couple-portal login (``couple_users``): that is
  a separate auth surface, so provisioning proceeds; the invitation is
  annotated for observability.
- Any infrastructure failure raises, so the webhook marks the event failed and
  Stripe retries; every step here re-enters safely.
"""

import html
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.constants.billing import COUPLE_PLAN_ID, COUPLE_PLAN_SEED
from app.core.database import mongo
from app.core.settings import settings
from app.services.email_service_resend import ResendEmailService
from app.services.wedding_service import WeddingService
from app.utils.couple_identity import normalize_couple_email

logger = logging.getLogger(__name__)

COUPLE_PLAN_PAYMENT_CATEGORY = "platform:couple_plan"
COUPLE_PLAN_PURPOSE = "couple_plan_purchase"
COUPLE_PLAN_INVITED_BY = "system:couple_plan_checkout"
# Paid customers get a longer claim window than admin-sent invites (7 days):
# there is no admin watching to click "resend" for them.
INVITE_TOKEN_TTL_DAYS = 30
# If the buyer left the optional wedding-date field blank (or unparseable), we
# still need a wedding date — the workspace lifecycle (through 90 days after
# the wedding, then removed) hangs off it. Default a year out; support can
# correct it once the couple confirms the real date.
FALLBACK_WEDDING_DATE_DAYS = 365

_WEDDING_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
)


async def ensure_couple_plan(plans_collection) -> None:
    """Insert the internal couple plan document if it is missing.

    Insert-only on purpose: operators may tune the couple plan's caps or
    feature flags through the admin plan editor, and a webhook replay must
    never clobber that. The seed is the starting point, not a sync target.
    """
    existing = await plans_collection.find_one({"_id": COUPLE_PLAN_ID})
    if existing:
        return
    now = datetime.now(UTC)
    plan_doc = {**COUPLE_PLAN_SEED, "created_at": now, "updated_at": now}
    await plans_collection.insert_one(plan_doc)
    logger.info("Seeded internal couple plan document %s", COUPLE_PLAN_ID)


def _extract_custom_field(session: dict[str, Any], *keys: str) -> str | None:
    """Pull a text custom-field value from a checkout session payload."""
    wanted = {k.replace("_", "").lower() for k in keys}
    for field in session.get("custom_fields") or []:
        if not isinstance(field, dict):
            continue
        key = str(field.get("key") or "").replace("_", "").lower()
        if key not in wanted:
            continue
        value = ((field.get("text") or {}).get("value") or "").strip()
        if value:
            return value
    return None


def _parse_wedding_date(raw: str | None) -> str | None:
    """Best-effort parse of a buyer-entered wedding date into YYYY-MM-DD."""
    if not raw:
        return None
    candidate = raw.strip()
    for fmt in _WEDDING_DATE_FORMATS:
        try:
            parsed = datetime.strptime(candidate, fmt)
        except ValueError:
            continue
        if parsed.date() < datetime.now(UTC).date():
            # A past date is almost certainly a typo; fall back rather than
            # provisioning a workspace that the cleanup path would consider
            # already ended.
            return None
        return parsed.strftime("%Y-%m-%d")
    return None


def _support_email_address() -> str:
    return os.getenv("RESEND_TO_EMAIL", "").strip() or "support@thespecialwedding.io"


def _frontend_base_url() -> str:
    frontend_url = (
        getattr(settings, "frontend_url", None) or "https://thespecialwedding.io"
    )
    return str(frontend_url).rstrip("/")


class CouplePlanFulfillmentService:
    """Provision a couple's wedding workspace after a paid checkout session."""

    def __init__(self):
        self.email_service = ResendEmailService()

    # ── collections resolved lazily so tests can monkeypatch module mongo ──
    @property
    def couples_collection(self):
        return mongo.db["couple_users"]

    @property
    def weddings_collection(self):
        return mongo.db["weddings"]

    @property
    def payment_records_collection(self):
        return mongo.db["payment_records"]

    @property
    def issues_collection(self):
        return mongo.db["couple_plan_fulfillment_issues"]

    @property
    def invitations_collection(self):
        return mongo.db["user_invitations"]

    @property
    def plans_collection(self):
        return mongo.db["subscription_plans"]

    @property
    def users_collection(self):
        return mongo.get_users_collection()

    async def fulfill_checkout_session(self, session: dict[str, Any]) -> dict[str, Any]:
        """Idempotent fulfillment entrypoint for a paid couple-plan session."""
        session_id = str(session.get("id") or "")
        if not session_id:
            raise ValueError("Checkout session payload is missing an id")

        customer_details = session.get("customer_details") or {}
        email = normalize_couple_email(
            customer_details.get("email") or session.get("customer_email")
        )
        customer_name = (customer_details.get("name") or "").strip()

        # ── Replay/retry short-circuits ────────────────────────────────
        existing_invitation = await self.invitations_collection.find_one(
            {"stripe_checkout_session_id": session_id}
        )
        if existing_invitation:
            if not existing_invitation.get("welcome_email_sent"):
                # Previous attempt provisioned but the email failed — finish
                # the job on this retry instead of silently succeeding.
                await self._send_welcome_email(existing_invitation)
                await self.invitations_collection.update_one(
                    {"_id": existing_invitation["_id"]},
                    {
                        "$set": {
                            "welcome_email_sent": True,
                            "email_status": "sent",
                            "email_sent_at": datetime.now(UTC),
                        }
                    },
                )
            logger.info(
                "Couple plan session %s already fulfilled (invitation for %s); skipping",
                session_id,
                existing_invitation.get("email"),
            )
            return {
                "status": "already_fulfilled",
                "session_id": session_id,
                "wedding_id": (existing_invitation.get("invite_data") or {}).get(
                    "wedding_id"
                ),
            }

        existing_issue = await self.issues_collection.find_one(
            {"stripe_checkout_session_id": session_id}
        )
        if existing_issue:
            logger.info(
                "Couple plan session %s already flagged for support (%s); skipping",
                session_id,
                existing_issue.get("reason"),
            )
            return {
                "status": "already_flagged_for_support",
                "session_id": session_id,
                "reason": existing_issue.get("reason"),
            }

        if not email:
            # Payment Links always collect an email, so this is pathological —
            # but it is still a PAID session and must never be dropped.
            return await self._flag_for_support(
                session,
                email=None,
                reason="missing_customer_email",
                detail="Paid couple-plan checkout session arrived without a customer email.",
            )

        # ── Edge: email already backs a dashboard account ──────────────
        existing_user = await self.users_collection.find_one({"email": email})
        if existing_user:
            return await self._flag_for_support(
                session,
                email=email,
                reason="email_already_linked_to_account",
                detail=(
                    f"Customer email already backs a {existing_user.get('role')!r} "
                    "dashboard account. Dashboard login is a single email/password "
                    "surface, so a second account on the same email cannot be "
                    "auto-created. Attach the purchase manually."
                ),
                notify_customer=True,
            )

        pending_invitation = await self.invitations_collection.find_one(
            {
                "email": email,
                "status": "pending",
                "expires_at": {"$gt": datetime.now(UTC)},
            }
        )
        if pending_invitation:
            return await self._flag_for_support(
                session,
                email=email,
                reason="pending_invitation_exists",
                detail=(
                    "Customer email already has a pending account invitation "
                    f"(role {pending_invitation.get('role')!r}, invited by "
                    f"{pending_invitation.get('invited_by')!r}). Auto-creating a "
                    "competing couple-plan invitation would race that flow. "
                    "Attach the purchase manually."
                ),
                notify_customer=True,
            )

        # Couple-portal overlap is allowed (separate auth surface) — annotate only.
        portal_couple = await self.couples_collection.find_one({"email": email})
        if portal_couple:
            logger.info(
                "Couple plan buyer %s also has a couple-portal login (wedding %s); "
                "provisioning planner-dashboard account anyway (separate auth surface)",
                email,
                portal_couple.get("wedding_id"),
            )

        # ── Provision ──────────────────────────────────────────────────
        now = datetime.now(UTC)
        await ensure_couple_plan(self.plans_collection)

        partner_names_raw = _extract_custom_field(
            session, "partnernames", "partner_names", "couplenames"
        )
        wedding_date = _parse_wedding_date(
            _extract_custom_field(session, "weddingdate", "wedding_date")
        )
        wedding_date_confirmed = wedding_date is not None
        if wedding_date is None:
            wedding_date = (now + timedelta(days=FALLBACK_WEDDING_DATE_DAYS)).strftime(
                "%Y-%m-%d"
            )

        couple_names = (
            partner_names_raw or customer_name or email.split("@")[0]
        ).strip()
        if len(couple_names) < 3:
            couple_names = f"{couple_names} Wedding".strip()

        partner1_name, partner2_name = self._split_partner_names(
            partner_names_raw or customer_name or email.split("@")[0]
        )

        wedding_id = await self._ensure_wedding(
            session=session,
            session_id=session_id,
            email=email,
            couple_names=couple_names,
            wedding_date=wedding_date,
            wedding_date_confirmed=wedding_date_confirmed,
            now=now,
        )

        invite_token = secrets.token_urlsafe(48)
        invitation_doc = {
            "email": email,
            "role": "wedding_planner",
            "token": invite_token,
            "invite_data": {
                # The couple flag is what complete_account_setup branches on:
                # account lands ACTIVE on plan_couple with the wedding
                # attached — no trial, no pending_payment (they already paid).
                "couple_plan": True,
                "plan_id": COUPLE_PLAN_ID,
                "trial_days": 0,
                "wedding_id": wedding_id,
                "company_name": couple_names,
                "partner1_name": partner1_name,
                "partner2_name": partner2_name,
                "source": "couple_plan_checkout",
                "email_matches_couple_portal": bool(portal_couple),
            },
            "invited_by": COUPLE_PLAN_INVITED_BY,
            "created_at": now,
            "expires_at": now + timedelta(days=INVITE_TOKEN_TTL_DAYS),
            "status": "pending",
            "stripe_customer_id": session.get("customer"),
            "stripe_checkout_session_id": session_id,
            "stripe_payment_intent_id": session.get("payment_intent"),
            "welcome_email_sent": False,
            "email_status": "pending",
            "email_sent_at": None,
            "resend_count": 0,
        }
        insert_result = await self.invitations_collection.insert_one(invitation_doc)
        invitation_doc["_id"] = insert_result.inserted_id

        await self._record_payment(
            session,
            session_id=session_id,
            email=email,
            wedding_id=wedding_id,
            now=now,
        )

        # The welcome email is part of the contract — a paying couple must be
        # able to reach their workspace without any manual step from us. If it
        # fails, raise: the webhook marks the event failed, Stripe retries,
        # and the replay path above resends the email for the existing record.
        await self._send_welcome_email(invitation_doc)
        await self.invitations_collection.update_one(
            {"_id": invitation_doc["_id"]},
            {
                "$set": {
                    "welcome_email_sent": True,
                    "email_status": "sent",
                    "email_sent_at": datetime.now(UTC),
                }
            },
        )

        logger.info(
            "Couple plan fulfilled: session %s -> wedding %s, invitation for %s",
            session_id,
            wedding_id,
            email,
        )
        return {
            "status": "success",
            "session_id": session_id,
            "wedding_id": wedding_id,
            "invitation_id": str(invitation_doc["_id"]),
        }

    # ── provisioning pieces ────────────────────────────────────────────

    @staticmethod
    def _split_partner_names(raw: str) -> tuple[str, str | None]:
        cleaned = (raw or "").strip()
        for separator in (" & ", " and ", " + ", "&", "+"):
            if separator in cleaned:
                first, _, second = cleaned.partition(separator)
                first = first.strip()
                second = second.strip()
                if first and second:
                    return first[:100], second[:100]
        return (cleaned[:100] or "Couple", None)

    async def _ensure_wedding(
        self,
        *,
        session: dict[str, Any],
        session_id: str,
        email: str,
        couple_names: str,
        wedding_date: str,
        wedding_date_confirmed: bool,
        now: datetime,
    ) -> str:
        """Create the wedding workspace, reusing one from a partial retry."""
        existing = await self.weddings_collection.find_one(
            {"stripe_checkout_session_id": session_id}
        )
        if existing:
            return str(existing["_id"])

        base_slug = WeddingService._slugify_couple_names(couple_names)
        slug = base_slug
        if await self.weddings_collection.find_one({"slug": slug}):
            slug = f"{base_slug}-{secrets.token_hex(3)}"

        wedding_doc = {
            "_id": WeddingService._generate_wedding_id(),
            "couple_names": couple_names,
            "date": wedding_date,
            "wedding_date_confirmed": wedding_date_confirmed,
            "slug": slug,
            "events": [],
            "registries": [],
            "faqs": [],
            "status": "active",
            # Self-serve couple workspace. The buyer becomes the planner-side
            # owner when they claim their account (complete_account_setup);
            # until then the workspace has no owner. The flag also keeps the
            # couple lifecycle from treating the missing planner as a blocked
            # owner and marks the workspace for the couple-plan gates.
            "self_serve_couple": True,
            "plan": "couple_one_wedding",
            "assigned_planner_id": None,
            "assigned_planner_email": None,
            "created_by": "couple-plan-checkout",
            "updated_by": email,
            # No couple-portal surfaces on a couple-plan workspace: the
            # purchaser IS the couple and works in the planner dashboard.
            "couple_portal_enabled": False,
            "stripe_checkout_session_id": session_id,
            "stripe_payment_intent_id": session.get("payment_intent"),
            "billed_period": now.strftime("%Y-%m"),
            "meter_pending": False,
            "created_at": now,
        }
        await self.weddings_collection.insert_one(wedding_doc)
        return str(wedding_doc["_id"])

    async def _record_payment(
        self,
        session: dict[str, Any],
        *,
        session_id: str,
        email: str | None,
        wedding_id: str | None,
        now: datetime,
        flagged_for_support: bool = False,
    ) -> None:
        existing = await self.payment_records_collection.find_one(
            {
                "stripe_checkout_session_id": session_id,
                "purpose": COUPLE_PLAN_PURPOSE,
            }
        )
        if existing:
            return

        amount = float(session.get("amount_total") or 0) / 100.0
        await self.payment_records_collection.insert_one(
            {
                # Sentinel category id — intentionally NOT a budget category
                # ObjectId, so wedding budget rollups can never absorb it.
                "category_id": COUPLE_PLAN_PAYMENT_CATEGORY,
                "vendor_name": None,
                "amount": amount,
                "currency": (session.get("currency") or "usd").lower(),
                "payment_method": "card",
                "payment_date": now,
                "description": "Couple Plan — One Wedding (one-time checkout)",
                "receipt_url": None,
                "status": "completed",
                "notes": None,
                "purpose": COUPLE_PLAN_PURPOSE,
                "customer_email": email,
                "wedding_id": wedding_id,
                "flagged_for_support": flagged_for_support,
                "stripe_checkout_session_id": session_id,
                "stripe_payment_intent_id": session.get("payment_intent"),
                "stripe_customer_id": session.get("customer"),
                "created_at": now,
            }
        )

    # ── support path ───────────────────────────────────────────────────

    async def _flag_for_support(
        self,
        session: dict[str, Any],
        *,
        email: str | None,
        reason: str,
        detail: str,
        existing_wedding_id: str | None = None,
        notify_customer: bool = False,
    ) -> dict[str, Any]:
        """Record + escalate a paid session that cannot be auto-provisioned."""
        session_id = str(session.get("id") or "")
        now = datetime.now(UTC)

        await self._record_payment(
            session,
            session_id=session_id,
            email=email,
            wedding_id=existing_wedding_id,
            now=now,
            flagged_for_support=True,
        )

        await self.issues_collection.insert_one(
            {
                "stripe_checkout_session_id": session_id,
                "stripe_payment_intent_id": session.get("payment_intent"),
                "customer_email": email,
                "reason": reason,
                "detail": detail,
                "existing_wedding_id": existing_wedding_id,
                "resolved": False,
                "created_at": now,
            }
        )

        logger.error(
            "Couple plan session %s needs manual fulfillment (%s): %s",
            session_id,
            reason,
            detail,
        )

        support_address = _support_email_address()
        safe_detail = html.escape(detail, quote=True)
        safe_email = html.escape(str(email or "(missing)"), quote=True)
        safe_session = html.escape(session_id, quote=True)
        try:
            await self.email_service.send_email(
                to_email=support_address,
                subject=f"[ACTION REQUIRED] Couple Plan purchase needs manual fulfillment ({reason})",
                html_content=(
                    '<div style="font-family: sans-serif; max-width: 640px;">'
                    "<h2>Paid Couple Plan session could not be auto-provisioned</h2>"
                    f"<p><strong>Reason:</strong> {html.escape(reason, quote=True)}</p>"
                    f"<p><strong>Customer email:</strong> {safe_email}</p>"
                    f"<p><strong>Checkout session:</strong> {safe_session}</p>"
                    f"<p>{safe_detail}</p>"
                    "<p>The payment is recorded in payment_records and the issue is in "
                    "couple_plan_fulfillment_issues. Provision or attach the workspace "
                    "manually, then mark the issue resolved.</p>"
                    "</div>"
                ),
            )
        except Exception as support_err:  # pragma: no cover - defensive
            # The issue row is already persisted; support alert is best-effort.
            logger.error(
                "Failed to send support alert for couple plan session %s: %s",
                session_id,
                support_err,
            )

        if notify_customer and email:
            try:
                await self.email_service.send_email(
                    to_email=email,
                    subject="We received your Couple Plan purchase — The Special Wedding",
                    html_content=(
                        "<div style=\"font-family: 'Georgia', serif; max-width: 600px; "
                        'margin: 0 auto; padding: 40px 20px;">'
                        '<h2 style="color: #1e3a5f;">Thank you — your payment went through</h2>'
                        '<p style="color: #333; font-size: 16px; line-height: 1.6;">'
                        "Your email address is already connected to an account on "
                        "The Special Wedding, so our team is personally connecting your "
                        "new Couple Plan purchase to the right workspace. We'll be in "
                        "touch shortly — no action needed from you.</p>"
                        '<p style="color: #666; font-size: 14px; line-height: 1.6;">'
                        f"Questions in the meantime? Contact us at {html.escape(support_address, quote=True)}.</p>"
                        "</div>"
                    ),
                )
            except Exception as ack_err:  # pragma: no cover - defensive
                logger.error(
                    "Failed to send customer acknowledgement for couple plan session %s: %s",
                    session_id,
                    ack_err,
                )

        return {
            "status": "flagged_for_support",
            "session_id": session_id,
            "reason": reason,
        }

    # ── welcome email ──────────────────────────────────────────────────

    async def _send_welcome_email(self, invitation_doc: dict[str, Any]) -> None:
        """Send the claim email. Raises on failure so Stripe retries."""
        email = invitation_doc["email"]
        invite_token = invitation_doc.get("token")
        if not invite_token:
            # Defensive: token vanished (e.g. setup already completed on a
            # replay) — nothing to send, and setup already succeeded.
            return

        invite_data = invitation_doc.get("invite_data") or {}
        setup_link = f"{_frontend_base_url()}/setup-account/{invite_token}"
        couple_name = invite_data.get("partner1_name") or email.split("@")[0]
        if invite_data.get("partner2_name"):
            couple_name = f"{couple_name} & {invite_data['partner2_name']}"

        safe_couple_name = html.escape(str(couple_name), quote=True)
        safe_setup_link = html.escape(setup_link, quote=True)
        support_address = html.escape(_support_email_address(), quote=True)

        html_content = f"""
        <div style="font-family: 'Georgia', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #1e3a5f; font-size: 28px; margin-bottom: 8px;">Your Wedding Workspace Is Ready</h1>
                <p style="color: #d4af37; font-size: 16px; letter-spacing: 2px;">THE SPECIAL WEDDING</p>
            </div>

            <p style="color: #333; font-size: 16px; line-height: 1.6;">
                Dear {safe_couple_name},
            </p>

            <p style="color: #333; font-size: 16px; line-height: 1.6;">
                Thank you for purchasing the <strong>Couple Plan — One Wedding</strong>.
                Your personal wedding workspace has been created. Set your password
                below to start planning: guests, RSVPs, budget, timeline, and more.
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{safe_setup_link}"
                   style="background-color: #1e3a5f; color: white; padding: 14px 32px;
                          text-decoration: none; border-radius: 6px; font-size: 16px;
                          display: inline-block;">
                    Set Up Your Account
                </a>
            </div>

            <p style="color: #666; font-size: 14px; line-height: 1.6;">
                Your workspace stays active through 90 days after your wedding day,
                then it is closed automatically — you can export your data any time
                before then. This setup link expires in {INVITE_TOKEN_TTL_DAYS} days;
                if it does, contact us at {support_address} and we'll send a fresh one.
            </p>

            <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;" />

            <p style="color: #999; font-size: 12px; text-align: center;">
                Questions? Contact us at {support_address}.
            </p>
        </div>
        """

        result = await self.email_service.send_email(
            to_email=email,
            subject="Your wedding workspace is ready — The Special Wedding",
            html_content=html_content,
        )
        if not isinstance(result, dict) or not result.get("success", False):
            error_detail = (
                (result or {}).get("error") if isinstance(result, dict) else result
            )
            raise RuntimeError(
                f"Welcome email delivery failed for couple plan purchase: {error_detail}"
            )


couple_plan_fulfillment_service = CouplePlanFulfillmentService()
