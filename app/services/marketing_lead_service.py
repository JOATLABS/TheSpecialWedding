"""Lead-capture service for the public template-download surface (Phase C).

The public marketing page (/resources/templates) lets visitors download
any catalog form template as a PDF in exchange for their email. Each
download writes a row to the ``marketing_leads`` Mongo collection (with
optional UTM provenance) and dispatches a confirmation email containing
the PDF as an attachment plus a discreet trial CTA.

Lean by design
- One module, one collection, one public endpoint.
- Idempotent on (email, template_id) — repeat submits resend the email
  but do not create duplicate leads. This is the right semantic for a
  marketing form: the lead is the *person*, not the click.
- Email payload reuses the Phase B PDF cache (lru_cache in
  form_template_pdf_service) so the marketing surface serves N
  recipients with a single render per template per process lifetime.
- No new dependencies — Resend (email) and WeasyPrint (PDF) are
  already part of the stack.

Validation against official sources
- Resend attachment shape: ``{"filename": str, "content": base64-str}``
  per https://resend.com/docs/api-reference/emails/send-email
  ("content … buffer or Base64 string"; "max 40MB per email after
  Base64 encoding"). The 9 catalog PDFs come in well under 200 KB
  each so we are far below the cap.
- Pydantic v2 EmailStr / Field validators per
  https://pydantic.dev/docs/validation/latest/concepts/validators/
  (used by the request model in app.api.forms).
"""

from __future__ import annotations

import base64
import html
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.database import mongo
from app.services.email_service_resend import ResendEmailService
from app.services.form_template_catalog import FORM_TEMPLATES
from app.services.form_template_pdf_service import render_form_template_pdf

logger = logging.getLogger(__name__)


_BRAND_NAME = "The Special Wedding"
_TRIAL_LINK = "https://thespecialwedding.io/saas?utm_source=template_download"

# Sentinel template_id for the homepage "starter pack" lead magnet —
# ships all 9 catalog PDFs in a single email. Stored on the lead row
# under template_id="starter_pack" so analytics can distinguish bundle
# downloads from per-template ones.
STARTER_PACK_TEMPLATE_ID = "starter_pack"


def _resolve_template(template_id: str) -> Optional[Dict[str, Any]]:
    for tpl in FORM_TEMPLATES:
        if tpl.get("id") == template_id:
            return tpl
    return None


def _starter_pack_descriptor() -> Dict[str, Any]:
    """Metadata for the starter-pack 'pseudo-template' used by the
    homepage email-gated band. Not part of FORM_TEMPLATES because it
    isn't a real template — it's a bundle of all 9."""
    return {
        "id": STARTER_PACK_TEMPLATE_ID,
        "name": "Free Wedding Planner Starter Pack",
        "description": (
            "9 production-ready templates — couple intake, vendor "
            "intake, wedding-party RSVP, and more — to kick off your "
            "next wedding."
        ),
    }


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _truncate(value: Optional[str], cap: int) -> Optional[str]:
    """Bound stored UTM strings so a user can't write a 1 MB attribution
    blob. Returns None on falsy input."""
    if not value:
        return None
    trimmed = str(value).strip()
    if not trimmed:
        return None
    return trimmed[:cap]


def _confirmation_html(template: Dict[str, Any], recipient_name: Optional[str]) -> str:
    """Discreet, branded confirmation email with one trial CTA.

    Kept short on purpose — the PDF attachment is the value; the
    email is the delivery vehicle plus a soft brand touch."""
    raw_name = (recipient_name or "").strip() or "there"
    raw_template_name = template.get("name") or template.get("id") or "your template"
    raw_description = template.get("description") or ""

    # Lead-capture form takes recipient_name from a public POST and the
    # catalog metadata is admin-authored — both sources can carry HTML
    # by accident or by design, so escape every interpolated string
    # before splicing it into the email body.
    safe_name = html.escape(raw_name)
    template_name = html.escape(str(raw_template_name))
    description = html.escape(str(raw_description))

    return f"""\
<!DOCTYPE html>
<html lang="en">
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; color: #1f1f1f; max-width: 560px; margin: 0 auto; padding: 24px;">
  <p style="font-size: 16px; line-height: 1.5;">Hi {safe_name},</p>

  <p style="font-size: 16px; line-height: 1.5;">
    Your <strong>{template_name}</strong> is attached as a PDF — print
    it, fill it by hand, or use it as the brief for your next planning
    conversation.
  </p>

  <p style="font-size: 14px; line-height: 1.5; color: #555;">{description}</p>

  <hr style="border: none; border-top: 1px solid #eee; margin: 28px 0;" />

  <p style="font-size: 14px; line-height: 1.5; color: #555;">
    Want to <em>actually use</em> this with your couples — link
    distribution, response tracking, reminders, the works?
    <a href="{_TRIAL_LINK}" style="color: #6b5d4f; font-weight: 600;">
      Start a free trial of {_BRAND_NAME}
    </a>
    — every template you've downloaded loads automatically into your
    workspace.
  </p>

  <p style="font-size: 12px; line-height: 1.5; color: #9a8f82; margin-top: 32px;">
    {_BRAND_NAME} · thespecialwedding.io
  </p>
</body>
</html>
"""


class MarketingLeadService:
    """Captures public template-download leads and dispatches confirmation."""

    def __init__(self) -> None:
        self.leads = mongo.db["marketing_leads"]
        self.email_service = ResendEmailService()

    async def capture_template_download(
        self,
        *,
        email: str,
        template_id: str,
        recipient_name: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Idempotently record a lead and send the template PDF by email.

        Returns ``{status, email_dispatched, lead_id}`` where ``status``
        is ``"created"`` for first-time leads and ``"resent"`` for
        repeat downloads of the same template by the same email.

        When ``template_id == STARTER_PACK_TEMPLATE_ID`` the email
        contains all 9 catalog PDFs as attachments (homepage
        lead-magnet path); the lead row stores
        ``template_id="starter_pack"`` for analytics.
        """
        normalized_email = _normalize_email(email)
        if not normalized_email:
            raise ValueError("email is required")

        if template_id == STARTER_PACK_TEMPLATE_ID:
            template = _starter_pack_descriptor()
        else:
            template = _resolve_template(template_id)
            if template is None:
                raise KeyError(template_id)

        now = datetime.now(timezone.utc)

        # Lookup existing lead for this (email, template) pair so we can
        # report whether this is a fresh capture or a re-send.
        existing = await self.leads.find_one(
            {"email": normalized_email, "template_id": template_id}
        )

        if existing is None:
            lead_doc = {
                "email": normalized_email,
                "template_id": template_id,
                "template_name": template.get("name"),
                "recipient_name": _truncate(recipient_name, 120),
                "utm_source": _truncate(utm_source, 60),
                "utm_medium": _truncate(utm_medium, 60),
                "utm_campaign": _truncate(utm_campaign, 120),
                "ip_address": _truncate(ip_address, 45),
                "user_agent": _truncate(user_agent, 300),
                "first_downloaded_at": now,
                "last_downloaded_at": now,
                "download_count": 1,
                "email_sends": 0,
                "email_send_failures": 0,
            }
            insert_result = await self.leads.insert_one(lead_doc)
            lead_id = str(insert_result.inserted_id)
            status = "created"
        else:
            await self.leads.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "last_downloaded_at": now,
                        # Late-arriving UTM data should not overwrite the
                        # original attribution but we DO record it on
                        # the lead doc as a list of follow-ups.
                    },
                    "$inc": {"download_count": 1},
                    "$push": {
                        "subsequent_utm": {
                            "at": now,
                            "utm_source": _truncate(utm_source, 60),
                            "utm_medium": _truncate(utm_medium, 60),
                            "utm_campaign": _truncate(utm_campaign, 120),
                        }
                    },
                },
            )
            lead_id = str(existing["_id"])
            status = "resent"

        # Render PDF(s) (cached process-side via Phase B's lru_cache) and
        # ship as Resend attachment(s). We don't block the lead capture
        # on email-send success — a deliverability blip should still
        # leave the lead row for follow-up.
        email_dispatched = False
        try:
            if template_id == STARTER_PACK_TEMPLATE_ID:
                # 9 catalog PDFs in one email. Each PDF ≈ a few hundred
                # KB, total well under Resend's 40 MB after-base64 cap
                # (https://resend.com/docs/api-reference/emails/send-email).
                attachments = [
                    {
                        "filename": f"{tpl['id']}.pdf",
                        "content": base64.b64encode(
                            render_form_template_pdf(tpl["id"])
                        ).decode("utf-8"),
                    }
                    for tpl in FORM_TEMPLATES
                ]
                email_type = "marketing_starter_pack_download"
            else:
                pdf_bytes = render_form_template_pdf(template_id)
                attachments = [
                    {
                        "filename": f"{template_id}.pdf",
                        # Resend expects a buffer or base64 string;
                        # codebase's ICS-attachment path uses base64.
                        "content": base64.b64encode(pdf_bytes).decode("utf-8"),
                    }
                ]
                email_type = "marketing_template_download"
            html = _confirmation_html(template, recipient_name)
            send_result = await self.email_service.send_email(
                to_email=normalized_email,
                subject=(f"Your {template.get('name') or 'wedding planner template'}"),
                html_content=html,
                from_name=_BRAND_NAME,
                attachments=attachments,
                email_type=email_type,
            )
            email_dispatched = bool(send_result.get("success"))
            inc = {"email_sends": 1} if email_dispatched else {"email_send_failures": 1}
            await self.leads.update_one(
                {"_id": existing["_id"] if existing else insert_result.inserted_id},
                {"$inc": inc, "$set": {"last_email_attempt_at": now}},
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Marketing template download email failed for %s / %s: %s",
                normalized_email,
                template_id,
                exc,
            )
            await self.leads.update_one(
                {"_id": existing["_id"] if existing else insert_result.inserted_id},
                {
                    "$inc": {"email_send_failures": 1},
                    "$set": {"last_email_attempt_at": now},
                },
            )

        return {
            "status": status,
            "email_dispatched": email_dispatched,
            "lead_id": lead_id,
        }


__all__ = ["MarketingLeadService"]
