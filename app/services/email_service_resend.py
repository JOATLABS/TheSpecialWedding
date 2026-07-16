# app/services/email_service_resend.py

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import resend

from app.constants.storefront_domain import (
    STOREFRONT_DOMAIN_INSTRUCTIONS_EMAIL_TYPE,
)
from app.core.database import mongo
from app.utils.rsvp_links import build_guest_otp_url
from app.utils.contact_sanitizer import sanitize_email, validate_email_format
from app.utils.wedding_event_types import (
    attending_matches_reminder_event,
    is_all_wedding_events,
    normalize_reminder_event_type,
)

logger = logging.getLogger(__name__)


def _masked_instruction_recipient(email: str) -> str:
    """Keep storefront DNS-contact audit data useful without retaining an address."""

    local, separator, domain = email.strip().casefold().rpartition("@")
    if not separator or not local or not domain:
        return "masked recipient"
    labels = domain.split(".")
    domain_name = labels[0]
    domain_suffix = ".".join(labels[1:])
    local_hint = f"{local[0]}***"
    domain_hint = f"{domain_name[0]}***" if domain_name else "***"
    return f"{local_hint}@{domain_hint}{'.' + domain_suffix if domain_suffix else ''}"


class ResendEmailService:
    def __init__(self):
        # Initialize Resend with API key
        api_key = os.getenv("RESEND_API_KEY")
        if api_key:
            resend.api_key = api_key
            self.configured = True
        else:
            logger.warning(
                "Resend email service not configured. RESEND_API_KEY required."
            )
            self.configured = False

        # Database collections
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.email_log_collection = mongo.db["email_logs"]
        self.wedding_collection = mongo.db["weddings"]

    def _generate_reply_to_address(
        self, wedding_slug: str, guest_id: Optional[str] = None
    ) -> str:
        """
        Generate a routable reply-to address that encodes thread context.

        Format: reply+{wedding_slug}@thespecialwedding.io
        With guest: reply+{wedding_slug}--{guest_id}@thespecialwedding.io

        When a recipient replies, Resend's inbound webhook delivers the reply
        and we decode this address to link it back to the correct wedding/guest.
        """
        inbound_domain = os.getenv("RESEND_INBOUND_DOMAIN", "thespecialwedding.io")
        if guest_id:
            return f"reply+{wedding_slug}--{guest_id}@{inbound_domain}"
        return f"reply+{wedding_slug}@{inbound_domain}"

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        reply_to: Optional[str] = None,
        wedding_id: Optional[str] = None,
        email_type: Optional[str] = None,
        wedding_slug: Optional[str] = None,
        guest_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a single email using Resend"""
        is_storefront_domain_instruction = (
            email_type == STOREFRONT_DOMAIN_INSTRUCTIONS_EMAIL_TYPE
        )
        if not self.configured:
            return {"success": False, "error": "Email service not configured"}

        # Sanitize email address — strip whitespace, lowercase
        original_email = to_email
        sanitized = sanitize_email(to_email)
        if not sanitized or not validate_email_format(sanitized):
            return {
                "success": False,
                "error": (
                    "Invalid recipient email"
                    if is_storefront_domain_instruction
                    else f"Invalid recipient email: {original_email!r}"
                ),
            }

        try:
            # Use provided from_email or default
            if not from_email:
                from_email = os.getenv(
                    "RESEND_FROM_EMAIL", "noreply@thespecialwedding.io"
                )

            # Format from address
            if from_name:
                from_address = f"{from_name} <{from_email}>"
            else:
                from_address = from_email

            # Prepare email parameters
            params: Dict[str, Any] = {
                "from": from_address,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            # Auto-generate reply-to address for inbound email support
            if not reply_to and wedding_slug:
                reply_to = self._generate_reply_to_address(wedding_slug, guest_id)

            # Add optional parameters
            if reply_to:
                params["reply_to"] = reply_to

            if attachments:
                params["attachments"] = attachments

            # Send email
            send_args: tuple[Any, ...] = (cast(Any, params),)
            if idempotency_key:
                send_args = (
                    cast(Any, params),
                    cast(
                        Any,
                        {"idempotency_key": idempotency_key},
                    ),
                )
            email_response = await asyncio.to_thread(
                resend.Emails.send,
                *send_args,
            )
            provider_message_id = (
                email_response.get("id")
                if isinstance(email_response, dict)
                else getattr(email_response, "id", None)
            )
            if not isinstance(provider_message_id, str) or not provider_message_id:
                provider_message_id = None

            # Generate thread_id for linking inbound replies
            thread_id = f"wedding-{wedding_slug}" if wedding_slug else None

            # Log the email
            log_entry = {
                "subject": subject,
                "from_email": from_email,
                "from_name": from_name,
                "wedding_id": wedding_id,
                "wedding_slug": wedding_slug,
                "guest_id": guest_id,
                "thread_id": thread_id,
                "reply_to": reply_to,
                "email_type": email_type,
                "idempotency_key": idempotency_key,
                "sent_at": datetime.now(timezone.utc),
                "status": "success",
                "resend_id": provider_message_id,
                "provider": "resend",
            }
            if is_storefront_domain_instruction:
                # Resend necessarily receives the destination to deliver the
                # message. Our application audit trail retains only the same
                # masked hint shown to the planner, never the address itself.
                log_entry["recipient_hint"] = _masked_instruction_recipient(sanitized)
            else:
                log_entry["to"] = to_email
            try:
                await self.email_log_collection.insert_one(log_entry)
            except Exception:
                if not is_storefront_domain_instruction:
                    raise
                # Provider acceptance is authoritative for this delivery. A
                # best-effort application audit write must not turn an accepted
                # idempotent send into a retryable delivery failure.
                logger.warning(
                    "Storefront DNS instruction email was accepted, but its "
                    "masked audit receipt could not be persisted"
                )

            if is_storefront_domain_instruction:
                logger.info("Storefront DNS instruction email accepted by Resend")
                return {
                    "success": True,
                    "id": provider_message_id,
                    "message_id": provider_message_id,
                }
            logger.info(
                f"Email sent successfully to {to_email}, ID: {provider_message_id}"
            )
            return {"success": True, "id": provider_message_id}

        except Exception as e:
            if is_storefront_domain_instruction:
                # Provider exceptions may include request data. Do not put the
                # DNS contact address or raw provider error in application logs.
                logger.error("Storefront DNS instruction email delivery failed")
            else:
                logger.error(f"Failed to send email to {to_email}: {str(e)}")

            # Log the failure
            log_entry = {
                "subject": subject,
                "from_email": from_email,
                "from_name": from_name,
                "wedding_id": wedding_id,
                "email_type": email_type,
                "idempotency_key": idempotency_key,
                "sent_at": datetime.now(timezone.utc),
                "status": "failed",
                "provider": "resend",
            }
            if is_storefront_domain_instruction:
                log_entry.update(
                    {
                        "recipient_hint": _masked_instruction_recipient(sanitized),
                        "error_code": "provider_delivery_failed",
                    }
                )
                try:
                    await self.email_log_collection.insert_one(log_entry)
                except Exception:
                    logger.warning(
                        "Storefront DNS instruction failure audit receipt could "
                        "not be persisted"
                    )
            else:
                log_entry.update({"to": to_email, "error": str(e)})
                await self.email_log_collection.insert_one(log_entry)

            return {
                "success": False,
                "error": (
                    "Email provider delivery failed"
                    if is_storefront_domain_instruction
                    else str(e)
                ),
                # A network/provider exception can happen after Resend accepted
                # the request. Callers with a stable provider key may safely
                # retry inside Resend's idempotency window.
                "delivery_unknown": bool(idempotency_key),
            }

    async def send_rsvp_invitations(
        self,
        wedding_slug: str,
        custom_html: Optional[str] = None,
        custom_subject: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send RSVP invitation emails to guests with email addresses"""
        # Get wedding details
        wedding = await self.wedding_collection.find_one({"slug": wedding_slug})
        if not wedding:
            return {"sent": 0, "failed": 0, "error": "Wedding not found"}

        # Get custom from_email or use wedding-specific or default
        from_email = wedding.get("reminder_from_email") or os.getenv(
            "RESEND_FROM_EMAIL", "noreply@thespecialwedding.io"
        )
        from_name = wedding.get("couple_names", "TheSpecialWedding")

        # Default subject if not provided
        if not custom_subject:
            custom_subject = f"You're Invited - {from_name}"

        base_url = os.getenv("FRONTEND_URL")
        if not base_url:
            logger.warning(
                "FRONTEND_URL environment variable is not set - falling back to production RSVP links"
            )
            base_url = "https://thespecialwedding.io"
        sent = 0
        failed = 0
        skipped_no_email = 0
        skipped_no_token = 0
        skipped_opted_out = 0
        unreachable_guests = []

        # Get all guests with email addresses
        guests = self.guest_collection.find({"wedding_id": wedding["_id"]})

        async for guest in guests:
            email = guest.get("email")
            if not email:
                skipped_no_email += 1
                # Track guests with no contact info at all
                if not guest.get("phone"):
                    unreachable_guests.append(
                        {
                            "name": guest.get("name", "Unknown"),
                            "guest_id": str(guest.get("_id")),
                        }
                    )
                continue

            token = guest.get("token")
            if not token:
                skipped_no_token += 1
                continue

            # Check email opt-in (block if explicitly opted out)
            email_opt_in = guest.get("email_opt_in", None)
            if email_opt_in is False:
                skipped_opted_out += 1
                continue

            # Generate RSVP URL
            rsvp_url = build_guest_otp_url(base_url, wedding_slug, token)

            # Use custom HTML or generate default
            if custom_html:
                # Replace placeholders in custom HTML
                html_content = custom_html.replace("{name}", guest.get("name", "Guest"))
                html_content = html_content.replace(
                    "{guest_name}", guest.get("name", "Guest")
                )
                html_content = html_content.replace("{url}", rsvp_url)
                html_content = html_content.replace("{rsvp_url}", rsvp_url)
                html_content = html_content.replace("{couple_names}", from_name)
                html_content = html_content.replace(
                    "{wedding_date}", wedding.get("date", "")
                )
            else:
                # Generate default invitation HTML
                html_content = self._generate_default_invitation_html(
                    guest_name=guest.get("name", "Guest"),
                    couple_names=from_name,
                    wedding_date=wedding.get("date", ""),
                    rsvp_url=rsvp_url,
                    plus_ones=guest.get("plus_ones", []),
                )
            # Send email (with reply-to encoding for inbound support)
            result = await self.send_email(
                to_email=email,
                subject=custom_subject,
                html_content=html_content,
                from_email=from_email,
                from_name=from_name,
                attachments=attachments,
                wedding_id=str(wedding["_id"]),
                email_type="rsvp_invitation",
                wedding_slug=wedding_slug,
                guest_id=str(guest["_id"]),
            )

            if result["success"]:
                sent += 1
                # Mark guest as having received an invite if not already set
                if not guest.get("invite_sent"):
                    await self.guest_collection.update_one(
                        {"_id": guest["_id"]},
                        {
                            "$set": {
                                "invite_sent": True,
                                "invite_sent_date": datetime.now(timezone.utc),
                            }
                        },
                    )
                    logger.info(
                        f"Set invite_sent=True for guest {guest.get('name', 'Unknown')}"
                    )
            else:
                failed += 1

            # Add delay to respect Resend rate limit (2 requests per second)
            await asyncio.sleep(0.6)  # Sleep for 600ms to stay well under rate limit

        return {
            "sent": sent,
            "failed": failed,
            "skipped_no_email": skipped_no_email,
            "skipped_no_token": skipped_no_token,
            "skipped_opted_out": skipped_opted_out,
            "unreachable_guests": unreachable_guests if unreachable_guests else None,
        }

    async def send_reminders(
        self,
        wedding_slug: str,
        event_type: str,
        custom_html: Optional[str] = None,
        custom_subject: Optional[str] = None,
        target_group: str = "all",
    ) -> Dict[str, Any]:
        """Send reminder emails to guests who have RSVP'd"""
        try:
            event_type = normalize_reminder_event_type(event_type)
        except ValueError as exc:
            return {"sent": 0, "failed": 0, "error": str(exc)}
        if target_group not in {"guests", "plus-ones", "all"}:
            return {"sent": 0, "failed": 0, "error": "Invalid target group"}

        # Get wedding details
        wedding = await self.wedding_collection.find_one({"slug": wedding_slug})
        if not wedding:
            return {"sent": 0, "failed": 0, "error": "Wedding not found"}

        # Get event details
        event = None
        if not is_all_wedding_events(event_type):
            event = next(
                (e for e in wedding.get("events", []) if e["type"] == event_type),
                None,
            )
        if not event and not is_all_wedding_events(event_type):
            return {"sent": 0, "failed": 0, "error": "Event not found"}
        event_name = (
            "All Events"
            if is_all_wedding_events(event_type)
            else event_type.replace("_", " ").title()
        )
        event_date = (
            wedding.get("date", "")
            if is_all_wedding_events(event_type)
            else event.get("date", "")
        )
        event_details = event.get("details", {}) if event else {}

        # Get custom from_email or use wedding-specific or default
        from_email = wedding.get("reminder_from_email") or os.getenv(
            "RESEND_FROM_EMAIL", "noreply@thespecialwedding.io"
        )
        from_name = wedding.get("couple_names", "TheSpecialWedding")

        # Default subject if not provided
        if not custom_subject:
            custom_subject = f"Reminder: {event_name}"
            if event_date:
                custom_subject = f"{custom_subject} - {event_date}"

        sent = 0
        failed = 0
        skipped_no_email = 0
        skipped_opted_out = 0

        wedding_guests = []
        guest_id_values = []
        guest_id_strings = []
        async for guest in self.guest_collection.find({"wedding_id": wedding["_id"]}):
            wedding_guests.append(guest)
            guest_id = guest.get("_id")
            if guest_id is None:
                continue
            for value in (guest_id, str(guest_id)):
                if value not in guest_id_values:
                    guest_id_values.append(value)
            guest_id_string = str(guest_id)
            if guest_id_string not in guest_id_strings:
                guest_id_strings.append(guest_id_string)

        rsvp_lookup = {}
        if guest_id_values:
            async for rsvp in self.rsvp_collection.find(
                {"guest_id": {"$in": guest_id_values}}
            ):
                if attending_matches_reminder_event(
                    rsvp.get("attending", []), event_type
                ):
                    rsvp_lookup[str(rsvp["guest_id"])] = rsvp

        # Get guests based on target group
        if target_group in ["guests", "all"]:
            for guest in wedding_guests:
                # Check if guest has RSVP'd for this event
                rsvp = rsvp_lookup.get(str(guest["_id"]))
                if not rsvp:
                    continue

                email = guest.get("email")
                if not email:
                    skipped_no_email += 1
                    continue

                # Check email opt-in
                if guest.get("email_opt_in") is False:
                    skipped_opted_out += 1
                    continue

                # Use custom HTML or generate default
                if custom_html:
                    # Replace placeholders
                    html_content = custom_html.replace(
                        "{name}", guest.get("name", "Guest")
                    )
                    html_content = html_content.replace(
                        "{guest_name}", guest.get("name", "Guest")
                    )
                    html_content = html_content.replace("{event_type}", event_name)
                    html_content = html_content.replace("{event_date}", event_date)
                    html_content = html_content.replace(
                        "{venue_name}", event_details.get("venue_name", "")
                    )
                    html_content = html_content.replace(
                        "{location}", event_details.get("location", "")
                    )
                    html_content = html_content.replace(
                        "{time}", event_details.get("time", "")
                    )
                    html_content = html_content.replace("{couple_names}", from_name)
                else:
                    # Generate default reminder HTML
                    html_content = self._generate_default_reminder_html(
                        guest_name=guest.get("name", "Guest"),
                        event_type=event_type,
                        event_date=event_date,
                        event_details=event_details,
                        couple_names=from_name,
                        plus_ones=guest.get("plus_ones", []),
                    )
                # Send email (with reply-to encoding for inbound support)
                result = await self.send_email(
                    to_email=email,
                    subject=custom_subject,
                    html_content=html_content,
                    from_email=from_email,
                    from_name=from_name,
                    wedding_id=str(wedding["_id"]),
                    email_type="reminder",
                    wedding_slug=wedding_slug,
                    guest_id=str(guest["_id"]),
                )

                if result["success"]:
                    sent += 1
                else:
                    failed += 1

                # Add delay to respect Resend rate limit (2 requests per second)
                await asyncio.sleep(
                    0.6
                )  # Sleep for 600ms to stay well under rate limit

        # Send reminders to plus-ones
        if target_group in ["plus-ones", "all"]:
            plus_one_collection = mongo.db["plus_ones"]

            plus_ones = await plus_one_collection.find(
                {"guest_id": {"$in": guest_id_strings}}
            ).to_list(length=None)

            for plus_one in plus_ones:
                # Check if plus-one is attending this event
                if not attending_matches_reminder_event(
                    plus_one.get("attending", []), event_type
                ):
                    continue

                email = plus_one.get("email")
                if not email:
                    continue

                # Check email opt-in (must be explicitly True)
                if plus_one.get("email_opt_in") is not True:
                    continue

                # Generate email content
                if custom_html:
                    html_content = custom_html.replace(
                        "{name}", plus_one.get("name", "Guest")
                    )
                    html_content = html_content.replace(
                        "{guest_name}", plus_one.get("name", "Guest")
                    )
                    html_content = html_content.replace("{event_type}", event_name)
                    html_content = html_content.replace("{event_date}", event_date)
                    html_content = html_content.replace(
                        "{venue_name}", event_details.get("venue_name", "")
                    )
                    html_content = html_content.replace(
                        "{location}", event_details.get("location", "")
                    )
                    html_content = html_content.replace(
                        "{time}", event_details.get("time", "")
                    )
                    html_content = html_content.replace("{couple_names}", from_name)
                else:
                    html_content = self._generate_default_reminder_html(
                        guest_name=plus_one.get("name", "Guest"),
                        event_type=event_type,
                        event_date=event_date,
                        event_details=event_details,
                        couple_names=from_name,
                        plus_ones=[],
                    )

                result = await self.send_email(
                    to_email=email,
                    subject=custom_subject,
                    html_content=html_content,
                    from_email=from_email,
                    from_name=from_name,
                    wedding_id=str(wedding["_id"]),
                    email_type="reminder",
                )

                if result.get("success"):
                    sent += 1
                else:
                    failed += 1

                await asyncio.sleep(0.6)

        return {
            "sent": sent,
            "failed": failed,
            "skipped_no_email": skipped_no_email,
            "skipped_opted_out": skipped_opted_out,
        }

    async def get_email_logs(
        self, wedding_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """Get email logs, optionally filtered by wedding"""
        query = {}
        if wedding_id:
            query["wedding_id"] = wedding_id

        cursor = (
            self.email_log_collection.find(query, {"_id": 0})
            .sort("sent_at", -1)
            .limit(limit)
        )

        logs = await cursor.to_list(length=limit)
        return logs

    async def get_email_logs_for_weddings(
        self, wedding_ids: List[str], limit: int = 100
    ) -> List[Dict]:
        """Get email logs for multiple weddings (for planners)"""
        if not wedding_ids:
            return []

        cursor = (
            self.email_log_collection.find(
                {"wedding_id": {"$in": wedding_ids}}, {"_id": 0}
            )
            .sort("sent_at", -1)
            .limit(limit)
        )

        logs = await cursor.to_list(length=limit)
        return logs

    def _generate_default_invitation_html(
        self,
        guest_name: str,
        couple_names: str,
        wedding_date: str,
        rsvp_url: str,
        plus_ones: Optional[List[Any]] = None,
    ) -> str:
        """Generate default RSVP invitation HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 32px; font-weight: 300; letter-spacing: 2px; }}
                .header p {{ margin: 10px 0 0; font-size: 18px; opacity: 0.9; }}
                .content {{ background: #ffffff; padding: 40px 30px; }}
                .content p {{ margin: 15px 0; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; transition: background-color 0.3s; }}
                .button:hover {{ background-color: #b6736d; }}
                .details {{ background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 25px 0; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; }}
                .footer p {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{couple_names}</h1>
                    <p>Request the honor of your presence</p>
                </div>
                <div class="content">
                    <p>Dear {guest_name},</p>
                    <p>We would be delighted to have you join us as we celebrate our special day!</p>

                    <div class="details">
                        <p style="margin: 0;"><strong>Save the Date:</strong> {wedding_date}</p>
                        {self._generate_plus_ones_section(plus_ones)}
                    </div>

                    <p>Please let us know if you'll be able to attend by clicking the button below:</p>

                    <div class="button-container">
                        <a href="{rsvp_url}" class="button">RSVP NOW</a>
                    </div>

                    <p style="text-align: center; color: #666; font-size: 14px;">
                        If you're receiving this email and would like to receive SMS reminders,<br>
                        you can add your phone number when you RSVP.
                    </p>

                    <p style="text-align: center; color: #666; font-size: 14px;">
                        Need help with your invitation? Reply <strong>HELP</strong> to a wedding text message,
                        or use the <strong>Get Help</strong> button on the wedding website so the planner can text you.
                    </p>

                    <p>We look forward to celebrating with you!</p>

                    <p>With love,<br>{couple_names}</p>
                </div>
                <div class="footer">
                    <p>If the button doesn't work, copy and paste this link:</p>
                    <p style="word-break: break-all; color: #c8847e;">{rsvp_url}</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; TheSpecialWedding</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _generate_plus_ones_section(self, plus_ones: Optional[List[Any]] = None) -> str:
        """Generate HTML section for plus-ones information"""
        if not plus_ones:
            return ""

        plus_ones_html = (
            "<br><p style='margin: 10px 0 0;'><strong>Your Plus-Ones:</strong></p>"
        )
        for plus_one in plus_ones:
            plus_one_name = plus_one.get("name", "Plus One")
            attending_events = plus_one.get("attending", [])
            if attending_events:
                events_text = ", ".join(
                    [event.replace("_", " ").title() for event in attending_events]
                )
                plus_ones_html += f"<p style='margin: 5px 0; font-size: 14px;'>• {plus_one_name} - {events_text}</p>"
            else:
                plus_ones_html += (
                    f"<p style='margin: 5px 0; font-size: 14px;'>• {plus_one_name}</p>"
                )

        return plus_ones_html

    def _generate_default_reminder_html(
        self,
        guest_name: str,
        event_type: str,
        event_date: str,
        event_details: dict,
        couple_names: str,
        plus_ones: Optional[List[Any]] = None,
    ) -> str:
        """Generate default reminder HTML"""
        event_title = (
            "All Events"
            if is_all_wedding_events(event_type)
            else event_type.replace("_", " ").title()
        )
        venue_name = event_details.get("venue_name", "Venue details coming soon")
        location = event_details.get("location", "")
        time = event_details.get("time", "")
        attire = event_details.get("attire", "")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 2px; }}
                .header p {{ margin: 10px 0 0; font-size: 18px; opacity: 0.9; }}
                .content {{ background: #ffffff; padding: 40px 30px; }}
                .event-card {{ background: #f8f9fa; border-left: 4px solid #c8847e; padding: 25px; margin: 25px 0; border-radius: 0 8px 8px 0; }}
                .event-card h2 {{ margin: 0 0 20px 0; color: #1e3a5f; }}
                .event-detail {{ margin: 12px 0; display: flex; align-items: flex-start; }}
                .event-detail strong {{ min-width: 100px; color: #555; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Event Reminder</h1>
                    <p>{event_title}</p>
                </div>
                <div class="content">
                    <p>Dear {guest_name},</p>
                    <p>This is a friendly reminder about the upcoming {
            event_title
        }. We're looking forward to celebrating with you!</p>

                    <div class="event-card">
                        <h2>Event Details</h2>
                        <div class="event-detail">
                            <strong>Date:</strong>
                            <span>{event_date}</span>
                        </div>
                        {
            f'''<div class="event-detail">
                            <strong>Time:</strong>
                            <span>{time}</span>
                        </div>'''
            if time
            else ""
        }
                        <div class="event-detail">
                            <strong>Venue:</strong>
                            <span>{venue_name}</span>
                        </div>
                        {
            f'''<div class="event-detail">
                            <strong>Location:</strong>
                            <span>{location}</span>
                        </div>'''
            if location
            else ""
        }
                        {
            f'''<div class="event-detail">
                            <strong>Dress Code:</strong>
                            <span>{attire}</span>
                        </div>'''
            if attire
            else ""
        }
                        {self._generate_plus_ones_section(plus_ones)}
                    </div>

                    <p>We can't wait to see you there!</p>

                    <p>With love,<br>{couple_names}</p>
                </div>
                <div class="footer">
                    <p>If you have any questions, please don't hesitate to reach out.</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; TheSpecialWedding</p>
                </div>
            </div>
        </body>
        </html>
        """

    async def send_subscription_cancelled_email(self, user: dict) -> bool:
        """Send subscription cancellation confirmation email to user.

        Args:
            user: User document with keys: email, full_name or company_name

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if not self.configured:
                logger.warning(
                    "Email service not configured — skipping subscription cancellation email"
                )
                return False

            email = user.get("email")
            if not email:
                logger.error(
                    f"User {user.get('_id')} has no email address — skipping cancellation email"
                )
                return False

            # Use full_name or company_name
            user_name = user.get("full_name") or user.get("company_name", "Planner")

            html_content = self._generate_subscription_cancelled_email_html(
                user_name=user_name
            )

            subject = "Your Special Wedding subscription has been cancelled"

            from_email = os.getenv("RESEND_BILLING_EMAIL") or os.getenv(
                "RESEND_FROM_EMAIL", "noreply@thespecialwedding.io"
            )
            from_name = "The Special Wedding"

            result = await self.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                from_email=from_email,
                from_name=from_name,
                email_type="subscription_cancelled",
            )

            return result.get("success", False)

        except Exception as e:
            logger.error(
                f"Error sending subscription cancellation email to {user.get('email', 'unknown')}: {str(e)}"
            )
            return False

    async def send_planner_cancelled_couple_notification(
        self, couple: dict, planner: dict, wedding: dict
    ) -> bool:
        """Send notification to couple when their planner's account is cancelled.

        Args:
            couple: Couple/user document with keys: email, name
            planner: Planner document with keys: company_name, email
            wedding: Wedding document with keys: title or couple_names

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if not self.configured:
                logger.warning(
                    "Email service not configured — skipping couple cancellation notification"
                )
                return False

            email = couple.get("email")
            if not email:
                logger.error(
                    f"Couple {couple.get('_id')} has no email address — skipping notification"
                )
                return False

            couple_name = couple.get("name", "Couple")
            planner_company = planner.get("company_name", "Your wedding planner")
            wedding_title = wedding.get("title") or wedding.get(
                "couple_names", "Your wedding"
            )

            html_content = self._generate_planner_cancelled_couple_notification_html(
                couple_name=couple_name,
                planner_company=planner_company,
                wedding_title=wedding_title,
            )

            subject = "Important update about your wedding planning service"

            from_email = os.getenv("RESEND_BILLING_EMAIL") or os.getenv(
                "RESEND_FROM_EMAIL", "noreply@thespecialwedding.io"
            )
            from_name = "The Special Wedding"

            result = await self.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                from_email=from_email,
                from_name=from_name,
                email_type="planner_cancelled_couple_notification",
            )

            return result.get("success", False)

        except Exception as e:
            logger.error(
                f"Error sending couple cancellation notification to {couple.get('email', 'unknown')}: {str(e)}"
            )
            return False

    def _generate_subscription_cancelled_email_html(self, user_name: str) -> str:
        """Generate subscription cancellation confirmation email HTML"""
        frontend_url = os.getenv("FRONTEND_URL", "https://thespecialwedding.io")
        resubscribe_url = f"{frontend_url}/admin/planner/billing"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 2px; }}
                .content {{ background: #ffffff; padding: 40px 30px; }}
                .content p {{ margin: 15px 0; }}
                .info-box {{ background: #f0f4f8; border-left: 4px solid #c8847e; padding: 25px; margin: 25px 0; border-radius: 0 8px 8px 0; }}
                .button-container {{ text-align: center; margin: 35px 0; }}
                .button {{ display: inline-block; padding: 16px 40px; background-color: #c8847e; color: white; text-decoration: none; border-radius: 30px; font-weight: 500; letter-spacing: 1px; transition: background-color 0.3s; }}
                .button:hover {{ background-color: #b6736d; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; }}
                .footer p {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Subscription Cancelled</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>We've processed your subscription cancellation request. Your Special Wedding subscription is now inactive.</p>

                    <div class="info-box">
                        <p style="margin: 0;"><strong>What happens next:</strong></p>
                        <ul style="margin: 10px 0; padding-left: 20px;">
                            <li>Your wedding planning data will be preserved for 30 days</li>
                            <li>You can reactivate your subscription at any time</li>
                            <li>Access to your wedding details will be restored immediately upon resubscription</li>
                        </ul>
                    </div>

                    <p>If you'd like to reactivate your subscription, you can do so anytime:</p>

                    <div class="button-container">
                        <a href="{resubscribe_url}" class="button">RESUBSCRIBE NOW</a>
                    </div>

                    <p>We'll miss you! If you have any feedback about your experience with The Special Wedding, we'd love to hear from you. Feel free to reach out to our support team.</p>

                    <p>Thank you for being part of The Special Wedding community.</p>
                </div>
                <div class="footer">
                    <p>Have questions? Contact us at support@thespecialwedding.io</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; The Special Wedding. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _generate_planner_cancelled_couple_notification_html(
        self, couple_name: str, planner_company: str, wedding_title: str
    ) -> str:
        """Generate couple notification when planner's account is cancelled"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1e3a5f, #2c5282); color: white; padding: 40px 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 2px; }}
                .header p {{ margin: 10px 0 0; font-size: 16px; opacity: 0.9; }}
                .content {{ background: #ffffff; padding: 40px 30px; }}
                .content p {{ margin: 15px 0; }}
                .alert-box {{ background: #fff4e6; border-left: 4px solid #ff9800; padding: 25px; margin: 25px 0; border-radius: 0 8px 8px 0; }}
                .highlight {{ color: #1e3a5f; font-weight: 600; }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; background: #f8f9fa; }}
                .footer p {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Service Update</h1>
                    <p>Important information about your wedding planning</p>
                </div>
                <div class="content">
                    <p>Hello {couple_name},</p>

                    <div class="alert-box">
                        <p style="margin-top: 0;"><strong>Your wedding planner's account is no longer active</strong></p>
                        <p style="margin-bottom: 0;">The Special Wedding account for <span class="highlight">{planner_company}</span> has been cancelled.</p>
                    </div>

                    <p><strong>What this means for your wedding:</strong></p>
                    <ul style="margin: 15px 0; padding-left: 20px;">
                        <li>Your wedding details and planning information for <span class="highlight">{wedding_title}</span> remain preserved on The Special Wedding</li>
                        <li>Any scheduled payments or recurring charges have been paused</li>
                        <li>Your couple portal access is currently paused while your planner's account is inactive</li>
                    </ul>

                    <p><strong>Next Steps:</strong></p>
                    <p>We recommend reaching out to {planner_company} directly to discuss the transition of your wedding planning services. If your planner reactivates their account, access to your portal can be restored. If you need assistance or have questions, our support team is here to help.</p>

                    <p>Your wedding details remain safely preserved by The Special Wedding even while portal access is paused.</p>
                </div>
                <div class="footer">
                    <p>Questions? Contact support@thespecialwedding.io</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p>&copy; The Special Wedding. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
