#!/usr/bin/env python3
"""Guest help SMS inbox lifecycle verification.

This driver exercises the public help form and Twilio inbound webhook against
the real backend + Mongo collections. It exists to catch the exact false
positives that unit tests can miss:

* public help form creates a planner-scoped SMS support ticket
* the planner sees it in ``/admin/sms-tickets?active_only=true``
* another planner cannot see that ticket
* a later Twilio inbound text updates the same ticket instead of creating a
  duplicate thread or routing to ROOT_ADMIN only
* a resolved ticket is reopened when the guest replies
* planner activity notifications are scoped to the owning planner

Usage:

    TESTBED_NON_INTERACTIVE=1 python testbed/verify_guest_help_sms_inbox_lifecycle.py

Optional:

    TESTBED_GUEST_HELP_PHONE=+15551234567

The default phone is a non-real 555 number so local runs do not contact a real
guest. If your Twilio account rejects that number, the public help endpoint
should still create the ticket and record the acknowledgment failure.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness, PlannerSeed

DRIVER_NAME = "verify_guest_help_sms_inbox_lifecycle"

PLANNER_A_EMAIL = "test_planner+guest_help_sms_a@thespecialwedding.io"
PLANNER_A_PASSWORD = "GuestHelpSmsA2026!"  # pragma: allowlist secret
PLANNER_B_EMAIL = "test_planner+guest_help_sms_b@thespecialwedding.io"
PLANNER_B_PASSWORD = "GuestHelpSmsB2026!"  # pragma: allowlist secret

PLAN_ID = os.getenv("GUEST_HELP_SMS_PLAN_ID", "plan_signature")
GUEST_PHONE = os.getenv("TESTBED_GUEST_HELP_PHONE", "+15555550123")
GUEST_NAME = "Testbed SMS Help Guest"
GUEST_RELATIONSHIP = "Friend of the couple"
COUPLE_NAMES = "Guest Help SMS & Inbox"


def _delete_stripe_customers_by_email(h: Harness, email: str) -> int:
    deleted = 0
    for customer in h.stripe.Customer.list(email=email, limit=100).auto_paging_iter():
        try:
            h.stripe.Customer.delete(customer.id)
            h.log.info(f"  ✅ Deleted Stripe customer {customer.id} ({customer.email})")
            deleted += 1
        except h.stripe.error.StripeError as exc:
            h.log.warning(f"  ⚠️ Could not delete Stripe customer {customer.id}: {exc}")
    return deleted


def _drop_driver_state(h: Harness) -> None:
    h.log.info("Dropping guest-help SMS testbed state…")
    planner_emails = [PLANNER_A_EMAIL, PLANNER_B_EMAIL]

    wedding_docs = list(
        h.mongo["weddings"].find(
            {
                "$or": [
                    {"assigned_planner_email": {"$in": planner_emails}},
                    {"created_by": {"$in": planner_emails}},
                    {"couple_names": COUPLE_NAMES},
                ]
            },
            {"_id": 1},
        )
    )
    wedding_ids = [str(doc["_id"]) for doc in wedding_docs]

    ticket_filter: dict[str, Any] = {
        "$or": [
            {"assigned_to": {"$in": planner_emails}},
            {"phone": GUEST_PHONE},
            {"origin": "public_help_form"},
        ]
    }
    if wedding_ids:
        ticket_filter["$or"].append({"wedding_id": {"$in": wedding_ids}})

    ticket_ids = [
        str(doc["_id"])
        for doc in h.mongo["support_tickets"].find(ticket_filter, {"_id": 1})
    ]
    deleted_tickets = h.mongo["support_tickets"].delete_many(ticket_filter)
    if deleted_tickets.deleted_count:
        h.log.info(f"  ✅ support_tickets: removed {deleted_tickets.deleted_count}")

    notification_filter: dict[str, Any] = {
        "$or": [
            {"planner_id": {"$in": planner_emails}},
            {"metadata.ticket_id": {"$in": ticket_ids or ["__none__"]}},
            {"metadata.origin": "public_help_form"},
        ]
    }
    deleted_notifications = h.mongo["planner_notifications"].delete_many(
        notification_filter
    )
    if deleted_notifications.deleted_count:
        h.log.info(
            f"  ✅ planner_notifications: removed {deleted_notifications.deleted_count}"
        )

    deleted_reminders = h.mongo["reminders_sent"].delete_many(
        {
            "$or": [
                {"message_sid": {"$regex": "^SM_testbed_guest_help_"}},
                {"wedding_id": {"$in": wedding_ids or ["__none__"]}},
            ]
        }
    )
    if deleted_reminders.deleted_count:
        h.log.info(f"  ✅ reminders_sent: removed {deleted_reminders.deleted_count}")

    for email in planner_emails:
        _delete_stripe_customers_by_email(h, email)
        h.delete_user_chain(email)


def _seed_planner_pair(h: Harness, admin_token: str) -> tuple[PlannerSeed, PlannerSeed]:
    seed_a = h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_A_EMAIL,
        password=PLANNER_A_PASSWORD,
        plan_id=PLAN_ID,
        first_name="GuestHelp",
        last_name="PlannerA",
        company_name="Guest Help Planner A",
    )
    seed_b = h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_B_EMAIL,
        password=PLANNER_B_PASSWORD,
        plan_id=PLAN_ID,
        first_name="GuestHelp",
        last_name="PlannerB",
        company_name="Guest Help Planner B",
    )
    return seed_a, seed_b


def _create_wedding(h: Harness, planner_token: str) -> tuple[str, str]:
    wedding_id = h.create_wedding(
        planner_token=planner_token,
        couple_names=COUPLE_NAMES,
        date_iso="2027-06-12",
        guest_count=75,
    )
    wedding = h.mongo["weddings"].find_one({"_id": wedding_id}) or h.mongo[
        "weddings"
    ].find_one(
        {"_id": ObjectId(wedding_id) if ObjectId.is_valid(wedding_id) else wedding_id}
    )
    if not wedding:
        raise RuntimeError(f"Could not reload created wedding {wedding_id}")
    slug = wedding.get("slug")
    if not slug:
        raise RuntimeError(f"Created wedding {wedding_id} has no slug")
    return str(wedding.get("_id")), slug


def _post_help_request(h: Harness, slug: str) -> str:
    resp = h.api_post(
        "/guests/help-request",
        json={
            "slug": slug,
            "full_name": GUEST_NAME,
            "phone": GUEST_PHONE,
            "relationship_to_couple": GUEST_RELATIONSHIP,
        },
    )
    if resp.status_code != 200:
        raise RuntimeError(f"help request failed: {resp.status_code} {resp.text}")
    ticket_id = resp.json().get("ticket_id")
    if not ticket_id:
        raise RuntimeError(f"help request response missing ticket_id: {resp.text}")
    return str(ticket_id)


def _assert_ticket_visible_only_to_owner(
    h: Harness,
    *,
    ticket_id: str,
    owner_token: str,
    other_token: str,
    expect_first: bool = False,
) -> None:
    owner_resp = h.api_get(
        "/admin/sms-tickets?active_only=true&page=1&limit=100", token=owner_token
    )
    owner_resp.raise_for_status()
    owner_tickets = owner_resp.json().get("tickets", [])
    owner_ids = {ticket["_id"] for ticket in owner_tickets}
    if ticket_id not in owner_ids:
        raise RuntimeError(
            f"owner inbox did not include active ticket {ticket_id}: {owner_ids}"
        )
    if expect_first and (not owner_tickets or owner_tickets[0]["_id"] != ticket_id):
        ordered_ids = [ticket["_id"] for ticket in owner_tickets[:5]]
        raise RuntimeError(
            f"reopened ticket was not first by latest activity: {ordered_ids}"
        )

    other_resp = h.api_get(
        "/admin/sms-tickets?active_only=true&page=1&limit=100", token=other_token
    )
    other_resp.raise_for_status()
    other_ids = {ticket["_id"] for ticket in other_resp.json().get("tickets", [])}
    if ticket_id in other_ids:
        raise RuntimeError(
            f"cross-planner isolation failed: planner B saw ticket {ticket_id}"
        )


def _notification_count(h: Harness, planner_email: str, ticket_id: str) -> int:
    return h.mongo["planner_notifications"].count_documents(
        {"planner_id": planner_email, "metadata.ticket_id": ticket_id}
    )


def _twilio_signature_headers(h: Harness, path: str, payload: dict[str, str]) -> dict:
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not auth_token:
        return {}

    from twilio.request_validator import RequestValidator

    webhook_base = os.getenv("TWILIO_WEBHOOK_BASE_URL")
    if webhook_base:
        signed_url = webhook_base.rstrip("/") + path
    else:
        configured_base = (
            os.getenv("NEXT_PUBLIC_API_BASE_URL")
            or os.getenv("FRONTEND_URL")
            or h.config.backend_url
        )
        parsed = urlparse(configured_base)
        signed_url = f"{parsed.scheme}://{parsed.netloc}{path}"

    signature = RequestValidator(auth_token).compute_signature(signed_url, payload)
    return {"X-Twilio-Signature": signature}


def _post_twilio_inbound(h: Harness, *, phone: str, body: str, sid: str) -> dict:
    path = "/webhook/twilio/incoming"
    payload = {"From": phone, "Body": body, "MessageSid": sid}
    resp = requests.post(
        f"{h.config.backend_url}{path}",
        data=payload,
        headers=_twilio_signature_headers(h, path, payload),
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Twilio inbound failed: {resp.status_code} {resp.text}")
    return resp.json()


def _post_twilio_status(
    h: Harness,
    *,
    sid: str,
    status: str,
    to_number: str,
    error_code: str = "",
) -> dict:
    path = "/webhook/twilio/status"
    payload = {
        "MessageSid": sid,
        "MessageStatus": status,
        "To": to_number,
    }
    if error_code:
        payload["ErrorCode"] = error_code

    resp = requests.post(
        f"{h.config.backend_url}{path}",
        data=payload,
        headers=_twilio_signature_headers(h, path, payload),
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Twilio status failed: {resp.status_code} {resp.text}")
    return resp.json()


def _assert_invalid_twilio_signature_rejected(h: Harness) -> None:
    if not os.getenv("TWILIO_AUTH_TOKEN"):
        h.log.warning("  ⚠️ Skipping invalid-signature assertion: TWILIO_AUTH_TOKEN is not set")
        return

    path = "/webhook/twilio/incoming"
    payload = {
        "From": GUEST_PHONE,
        "Body": "This forged message should be rejected",
        "MessageSid": "SM_testbed_invalid_signature",
    }
    resp = requests.post(
        f"{h.config.backend_url}{path}",
        data=payload,
        headers={"X-Twilio-Signature": "definitely-invalid"},
        timeout=30,
    )
    if resp.status_code != 401:
        raise RuntimeError(
            f"invalid Twilio signature was not rejected: {resp.status_code} {resp.text}"
        )


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.preflight()
    _drop_driver_state(h)

    admin_token = h.get_admin_token()
    h.phase("GUEST_HELP_SMS_SEED", "Seed two planners and one owner-scoped wedding")
    _seed_a, _seed_b = _seed_planner_pair(h, admin_token)
    token_a = h.login(PLANNER_A_EMAIL, PLANNER_A_PASSWORD)
    token_b = h.login(PLANNER_B_EMAIL, PLANNER_B_PASSWORD)
    wedding_id, slug = _create_wedding(h, token_a)

    h.checkpoint(
        "GUEST_HELP_SMS_P0_SEEDED",
        expectations=[
            f"Planner A: {PLANNER_A_EMAIL}",
            f"Planner B: {PLANNER_B_EMAIL}",
            f"Wedding id {wedding_id} has slug /{slug}",
            "Chrome check: planner A is the only planner assigned to this wedding.",
        ],
    )

    h.phase("GUEST_HELP_SMS_PUBLIC_FORM", "Create public help request")
    ticket_id = _post_help_request(h, slug)
    ticket = h.mongo["support_tickets"].find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise RuntimeError(f"support ticket {ticket_id} missing after help request")
    if ticket.get("assigned_to") != PLANNER_A_EMAIL:
        raise RuntimeError(f"ticket assigned_to drifted: {ticket.get('assigned_to')}")
    if ticket.get("origin") != "public_help_form":
        raise RuntimeError(f"ticket origin missing: {ticket}")
    if _notification_count(h, PLANNER_A_EMAIL, ticket_id) < 1:
        raise RuntimeError("planner A did not receive a public-help notification")
    if _notification_count(h, PLANNER_B_EMAIL, ticket_id) != 0:
        raise RuntimeError("planner B received planner A's help notification")
    _assert_ticket_visible_only_to_owner(
        h,
        ticket_id=ticket_id,
        owner_token=token_a,
        other_token=token_b,
        expect_first=True,
    )

    h.checkpoint(
        "GUEST_HELP_SMS_P1_PUBLIC_HELP_VISIBLE",
        expectations=[
            "Planner A inbox: the SMS support ticket appears under Communications → Inbox.",
            "Planner B inbox: the ticket does not appear.",
            "Planner A notifications: a new guest-message/help notification exists.",
        ],
    )

    h.phase("GUEST_HELP_SMS_REOPEN", "Resolved thread is reopened by guest reply")
    h.mongo["support_tickets"].update_one(
        {"_id": ObjectId(ticket_id)},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": datetime.now(timezone.utc),
                "is_read": True,
            }
        },
    )
    first_reply = "Hello, I cannot RSVP"
    inbound = _post_twilio_inbound(
        h,
        phone=GUEST_PHONE,
        body=first_reply,
        sid="SM_testbed_guest_help_reply_1",
    )
    if inbound.get("action") != "support_ticket_reply":
        raise RuntimeError(f"inbound reply did not update existing ticket: {inbound}")
    refreshed = h.mongo["support_tickets"].find_one({"_id": ObjectId(ticket_id)})
    if not refreshed:
        raise RuntimeError(f"ticket {ticket_id} missing after inbound reply")
    if refreshed.get("status") != "new":
        raise RuntimeError(f"ticket was not reopened: {refreshed.get('status')}")
    if refreshed.get("resolved_at"):
        raise RuntimeError("reopened ticket still has resolved_at set")
    if refreshed.get("is_read") is not False:
        raise RuntimeError("inbound guest reply did not mark ticket unread")
    if not any(
        message.get("message") == first_reply
        for message in refreshed.get("guest_messages", [])
    ):
        raise RuntimeError("inbound guest reply was not stored on guest_messages")
    if (
        h.mongo["support_tickets"].count_documents(
            {"phone": GUEST_PHONE, "source": "sms"}
        )
        != 1
    ):
        raise RuntimeError("inbound guest reply created a duplicate SMS ticket")
    if _notification_count(h, PLANNER_A_EMAIL, ticket_id) < 2:
        raise RuntimeError("planner A did not receive inbound-reply notification")
    if _notification_count(h, PLANNER_B_EMAIL, ticket_id) != 0:
        raise RuntimeError("planner B received planner A's inbound notification")
    _assert_ticket_visible_only_to_owner(
        h, ticket_id=ticket_id, owner_token=token_a, other_token=token_b
    )

    h.checkpoint(
        "GUEST_HELP_SMS_P2_REOPENED",
        expectations=[
            "Planner A inbox: the same ticket is active/unread again and first by latest activity.",
            "Thread detail: the guest's latest SMS is visible as an inbound bubble.",
            "Planner B inbox and notifications still do not show planner A's ticket.",
            "Guest should not receive the generic auto-ack again for this existing thread.",
        ],
    )

    h.phase("GUEST_HELP_SMS_IDEMPOTENCY", "Retry same Twilio MessageSid")
    notification_count_before_duplicate = _notification_count(
        h, PLANNER_A_EMAIL, ticket_id
    )
    duplicate = _post_twilio_inbound(
        h,
        phone=GUEST_PHONE,
        body=first_reply,
        sid="SM_testbed_guest_help_reply_1",
    )
    if duplicate.get("action") != "support_ticket_reply":
        raise RuntimeError(f"duplicate inbound did not resolve to same ticket: {duplicate}")
    after_duplicate = h.mongo["support_tickets"].find_one({"_id": ObjectId(ticket_id)})
    duplicate_messages = [
        message
        for message in after_duplicate.get("guest_messages", [])
        if message.get("message_sid") == "SM_testbed_guest_help_reply_1"
    ]
    if len(duplicate_messages) != 1:
        raise RuntimeError(
            f"duplicate MessageSid appended {len(duplicate_messages)} guest messages"
        )
    if (
        _notification_count(h, PLANNER_A_EMAIL, ticket_id)
        != notification_count_before_duplicate
    ):
        raise RuntimeError("duplicate MessageSid created a duplicate notification")

    help_reply = _post_twilio_inbound(
        h,
        phone=GUEST_PHONE,
        body="HELP",
        sid="SM_testbed_guest_help_keyword_1",
    )
    if help_reply.get("action") != "help_existing_ticket":
        raise RuntimeError(f"HELP did not stay attached to existing ticket: {help_reply}")
    after_help = h.mongo["support_tickets"].find_one({"_id": ObjectId(ticket_id)})
    if not any(
        message.get("message_sid") == "SM_testbed_guest_help_keyword_1"
        for message in after_help.get("guest_messages", [])
    ):
        raise RuntimeError("HELP keyword was not recorded on the existing SMS ticket")
    if (
        h.mongo["support_tickets"].count_documents(
            {"phone": GUEST_PHONE, "source": "sms"}
        )
        != 1
    ):
        raise RuntimeError("HELP keyword created a duplicate SMS ticket")

    h.checkpoint(
        "GUEST_HELP_SMS_P3_IDEMPOTENT_HELP",
        expectations=[
            "Retrying the same inbound MessageSid does not duplicate guest messages.",
            "Retrying the same inbound MessageSid does not duplicate planner notifications.",
            "HELP from the same phone stays attached to the existing planner-scoped ticket.",
        ],
    )

    h.phase("GUEST_HELP_SMS_STATUS_AND_SECURITY", "Status callback and signature rejection")
    status_sid = "SM_testbed_guest_help_status_1"
    h.mongo["reminders_sent"].insert_one(
        {
            "message_sid": status_sid,
            "provider": "twilio",
            "recipient_phone": GUEST_PHONE,
            "guest_id": None,
            "wedding_id": wedding_id,
            "message": "Testbed delivery status fixture",
            "sent_at": datetime.now(timezone.utc),
            "delivery_status": "queued",
            "delivery_events": [],
        }
    )
    status_result = _post_twilio_status(
        h,
        sid=status_sid,
        status="delivered",
        to_number=GUEST_PHONE,
    )
    if status_result.get("status") != "success":
        raise RuntimeError(f"status callback did not update reminder log: {status_result}")
    reminder_log = h.mongo["reminders_sent"].find_one({"message_sid": status_sid})
    if reminder_log.get("delivery_status") != "delivered":
        raise RuntimeError(f"delivery_status was not updated: {reminder_log}")
    if not reminder_log.get("delivery_events"):
        raise RuntimeError("status callback did not append a delivery event")

    _assert_invalid_twilio_signature_rejected(h)

    h.checkpoint(
        "GUEST_HELP_SMS_P4_STATUS_SECURITY",
        expectations=[
            "Twilio status callback updates reminders_sent.delivery_status.",
            "Twilio status callback appends delivery_events.",
            "Forged inbound Twilio signature is rejected when TWILIO_AUTH_TOKEN is configured.",
        ],
    )

    h.banner("PASS — Guest Help SMS Inbox Lifecycle")
    h.log.info(
        "Verified public help form → SMS support ticket → inbound reply → inbox "
        "visibility → notification scoping → idempotent inbound retries → status callbacks."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ {DRIVER_NAME} failed: {exc}\n")
        raise SystemExit(1)
