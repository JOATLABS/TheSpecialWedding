#!/usr/bin/env python3
"""
Form Send Recipient Dedup Recovery — Live Verification
======================================================

Exercises the recipient-dedup gate in
``app/services/form_service.py::send_form`` (PR #297 / #299).

Background
----------
Before the fix, *any* prior unsubmitted distribution row for
(form_id, recipient_email) blocked subsequent sends — meaning a
Resend bounce or an expired token left the recipient permanently
un-resendable from the planner UI. The fix tightened the gate so a
prior row only blocks when ALL three are true:

    1. ``submitted_at is None``        — recipient has not replied yet
    2. ``email_sends > 0``             — at least one delivery succeeded
    3. ``token_expires_at > now()``    — the access token is still live

Anything else (failed delivery, expired token, never-attempted) must
fall through so the planner can recover from the bounce.

Strategy
--------
SEED:
    - ``DEDUP_RECOVERY`` planner email is recorded as the form's
      ``created_by`` (idempotent insert via Mongo — the smoke import
      path stays network-free).
    - One generic form is seeded with one required ``name`` field.
    - The Resend email service is monkey-patched on the FormService
      instance so each ``send_form`` call returns deterministic
      ``success=True`` results without actually hitting Resend.

VERIFY (each checkpoint asserts on the live ``send_form`` response
and ENTER-gates so a human can inspect the planner's send page in
Chrome between steps):

    [CHECKPOINT 1/8] Delivered + live distribution rejects duplicate send
    [CHECKPOINT 2/8] First send creates a delivered+live distribution
    [CHECKPOINT 3/8] Failed-send recovery — fresh send goes through
    [CHECKPOINT 4/8] Expired-token recovery — fresh send goes through
    [CHECKPOINT 5/8] Never-attempted recovery — fresh send goes through
    [CHECKPOINT 6/8] Submitted lead unblocks resend
    [CHECKPOINT 7/8] Per-recipient detail shape
    [CHECKPOINT 8/8] skipped_duplicates total matches recipients with status

Pair: cleanup_form_send_dedup_recovery_state.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    DEDUP_RECOVERY,
    banner,
    checkpoint_pause,
    count_documents,
    get_async_mongo,
    insert_one,
    now_utc,
    short_token,
)


FORM_ID_PREFIX = "verify_dedup"
RECIPIENT_EMAIL = "test_recipient+dedup@thespecialwedding.io"


# ---------------------------------------------------------------------------
# Stub email service — deterministic success without hitting Resend.
# We swap this onto the FormService instance for the verifier run only.
# ---------------------------------------------------------------------------


class _StubEmailService:
    """Always-successful stub so the dedup gate is the only variable."""

    def __init__(self) -> None:
        self.configured = True
        self.send_count = 0

    async def send_email(self, **_kwargs: Any) -> Dict[str, Any]:
        self.send_count += 1
        return {"success": True, "email_id": f"stub_msg_{self.send_count}"}


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


async def seed_form() -> str:
    """Insert one form owned by the verifier planner. Idempotent suffix
    via short_token() keeps re-runs from collision but cleanup wipes
    by created_by so stale rows still get reaped."""
    form_id = f"{FORM_ID_PREFIX}_{short_token()}"
    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": "Send Dedup Recovery Verifier",
            "form_type": "general",
            "settings": {
                "title": "Dedup Recovery",
                "description": "Verifier-seeded — send_form recipient dedup gate.",
                "submit_button_text": "Send",
                "success_message": "Thanks!",
                "allow_multiple_submissions": True,
                "collect_email": True,
                "is_public": True,
                "requires_auth": False,
            },
            "fields": [
                {
                    "id": "name",
                    "label": "Your name",
                    "type": "text",
                    "required": True,
                    "order": 1,
                }
            ],
            "created_by": DEDUP_RECOVERY.email,
            "wedding_id": None,
            "is_active": True,
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "submission_count": 0,
            "planner_state": {},
        },
    )
    return form_id


def _make_send_request():
    """Construct the Pydantic SendFormRequest for one recipient."""
    # Imported inside the helper so module-level import stays network-free.
    from app.models.form import EmailDistributionSettings, SendFormRequest

    return SendFormRequest(
        recipient_emails=[RECIPIENT_EMAIL],
        email_settings=EmailDistributionSettings(
            subject="Please complete this form",
            message="Hi — please reply.",
            sender_name="Wedding Planner",
            include_form_link=True,
            send_reminder=False,
            reminder_days=7,
        ),
        wedding_id=None,
    )


async def _call_send(form_service, form_id: str) -> Dict[str, Any]:
    """Invoke FormService.send_form for the seeded planner."""
    return await form_service.send_form(
        form_id,
        _make_send_request(),
        DEDUP_RECOVERY.email,
    )


async def _latest_distribution(form_id: str) -> Dict[str, Any]:
    """Most recent form_distributions row for the verifier recipient."""
    mongo = get_async_mongo()
    coll = mongo.db["form_distributions"]
    cursor = (
        coll.find({"form_id": form_id, "recipient_email": RECIPIENT_EMAIL.lower()})
        .sort("sent_at", -1)
        .limit(1)
    )
    docs = [d async for d in cursor]
    assert docs, "expected at least one distribution row"
    return docs[0]


async def _update_latest_distribution(form_id: str, update: Dict[str, Any]) -> None:
    """Patch the most recent distribution row in Mongo."""
    latest = await _latest_distribution(form_id)
    mongo = get_async_mongo()
    await mongo.db["form_distributions"].update_one(
        {"_id": latest["_id"]}, {"$set": update}
    )


def _assert(cond: bool, msg: str) -> None:
    """Loud, explicit assert helper — prints a CHECKPOINT FAIL marker
    on failure so the log has a single grep-able token."""
    if not cond:
        print(f"  [CHECKPOINT FAIL] {msg}")
        raise AssertionError(msg)
    print(f"    ✓ {msg}")


def _log_checkpoint(idx: int, total: int, label: str) -> None:
    print()
    print(f"[CHECKPOINT {idx}/{total}] {label}")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


TOTAL = 8


async def main() -> None:
    banner("verify_form_send_dedup_recovery — SEED")
    print(f"Planner: {DEDUP_RECOVERY.email}")
    print(f"Recipient: {RECIPIENT_EMAIL}")

    # Local import keeps module-level import network-free for the smoke test.
    from app.services.form_service import FormService

    form_id = await seed_form()
    print(f"Seeded form: {form_id}")
    print(
        f"Distributions before run: "
        f"{await count_documents('form_distributions', {'form_id': form_id})}"
    )

    form_service = FormService()
    stub_email = _StubEmailService()
    # Swap the live Resend service for our stub so the dedup gate
    # is the only variable in this run.
    form_service.email_service = stub_email

    banner("VERIFY")

    # ------------------------------------------------------------------
    # CHECKPOINT 1: First send creates a delivered+live distribution.
    # ------------------------------------------------------------------
    _log_checkpoint(1, TOTAL, "First send creates a delivered+live distribution")
    response_1 = await _call_send(form_service, form_id)
    recipients_1 = response_1.get("recipients", [])
    _assert(len(recipients_1) == 1, "response carries one recipients[] entry")
    _assert(
        recipients_1[0]["email"] == RECIPIENT_EMAIL.lower(),
        "recipients[0].email matches normalized recipient",
    )
    _assert(recipients_1[0]["status"] == "sent", "recipients[0].status == 'sent'")
    _assert(response_1.get("sent") == 1, "aggregate sent=1")
    _assert(
        response_1.get("skipped_duplicates", 0) == 0,
        "aggregate skipped_duplicates=0 on first send",
    )
    latest = await _latest_distribution(form_id)
    _assert(
        int(latest.get("email_sends") or 0) == 1,
        "new distribution row records email_sends=1",
    )
    _assert(
        int(latest.get("email_send_failures") or 0) == 0,
        "new distribution row records email_send_failures=0",
    )
    checkpoint_pause(
        "Open the planner's send page in Chrome",
        [
            f"Login as {DEDUP_RECOVERY.email}.",
            f"Open /admin/forms/{form_id}/distributions.",
            f"Confirm one row exists for {RECIPIENT_EMAIL} with status=sent.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 2: Duplicate send to delivered+live blocks (positive case).
    # ------------------------------------------------------------------
    _log_checkpoint(
        2, TOTAL, "Duplicate send to delivered+live distribution is skipped"
    )
    response_2 = await _call_send(form_service, form_id)
    recipients_2 = response_2.get("recipients", [])
    _assert(len(recipients_2) == 1, "duplicate response still carries one entry")
    _assert(
        recipients_2[0]["status"] == "skipped_duplicate",
        "recipients[0].status == 'skipped_duplicate'",
    )
    _assert(
        response_2.get("skipped_duplicates") == 1,
        "skipped_duplicates aggregate increments to 1",
    )
    _assert(response_2.get("sent") == 0, "no new send recorded (sent=0)")
    # No new distribution row should have been created.
    rows_after_dup = await count_documents(
        "form_distributions",
        {"form_id": form_id, "recipient_email": RECIPIENT_EMAIL.lower()},
    )
    _assert(rows_after_dup == 1, "no new distribution row created on dedup-skip")
    checkpoint_pause(
        "Verify dedup behavior in Chrome",
        [
            "Click 'Send' again on the same recipient in the planner UI.",
            "Confirm a 'skipped_duplicate' indication is shown (no new row).",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 3: Failed-send recovery (false-negative under old code).
    # Flip the row to look like a Resend bounce: email_sends=0, failures=1.
    # ------------------------------------------------------------------
    _log_checkpoint(3, TOTAL, "Failed-send recovery — fresh send goes through")
    await _update_latest_distribution(
        form_id,
        {"email_sends": 0, "email_send_failures": 1, "status": "failed"},
    )
    response_3 = await _call_send(form_service, form_id)
    recipients_3 = response_3.get("recipients", [])
    _assert(
        recipients_3[0]["status"] == "sent",
        "failed-send row does NOT block — recipients[0].status=='sent'",
    )
    _assert(response_3.get("sent") == 1, "aggregate sent=1 after failed-send recovery")
    _assert(
        response_3.get("skipped_duplicates", 0) == 0,
        "skipped_duplicates=0 after failed-send recovery",
    )
    checkpoint_pause(
        "Inspect the new distribution row in Chrome",
        [
            "Refresh the planner's distribution table.",
            f"Confirm a fresh 'sent' row appeared for {RECIPIENT_EMAIL}.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 4: Expired-token recovery.
    # Backdate token_expires_at on the most recent row.
    # ------------------------------------------------------------------
    _log_checkpoint(4, TOTAL, "Expired-token recovery — fresh send goes through")
    yesterday = now_utc() - timedelta(days=1)
    await _update_latest_distribution(
        form_id,
        {"token_expires_at": yesterday},
    )
    response_4 = await _call_send(form_service, form_id)
    recipients_4 = response_4.get("recipients", [])
    _assert(
        recipients_4[0]["status"] == "sent",
        "expired-token row does NOT block — recipients[0].status=='sent'",
    )
    _assert(
        response_4.get("sent") == 1, "aggregate sent=1 after expired-token recovery"
    )
    checkpoint_pause(
        "Verify expired-token recovery in Chrome",
        [
            "Refresh the distribution table.",
            "Confirm a brand-new row was issued (latest token unexpired).",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 5: Never-attempted distribution recovery.
    # Simulate a row that was inserted but the email_sends counter never
    # got bumped (no email_sends or email_send_failures field at all).
    # ------------------------------------------------------------------
    _log_checkpoint(5, TOTAL, "Never-attempted recovery — fresh send goes through")
    # Insert a distribution by hand with NO email_sends / failures fields.
    naked_dist_id = f"{form_id}_naked_{short_token()}"
    await insert_one(
        "form_distributions",
        {
            "_id": naked_dist_id,
            "form_id": form_id,
            "recipient_email": RECIPIENT_EMAIL.lower(),
            "sent_at": now_utc(),
            "status": "sending",
            "access_token_hash": "stub",
            "token_expires_at": now_utc() + timedelta(days=14),
            "send_reminder": False,
            "reminder_days": 7,
            "reminder_sent_at": None,
            "reminder_count": 0,
            # NB: deliberately no email_sends / email_send_failures keys.
        },
    )
    # Drop any prior delivered+live rows so this naked row is what
    # send_form's find_one() returns.
    mongo = get_async_mongo()
    await mongo.db["form_distributions"].delete_many(
        {
            "form_id": form_id,
            "recipient_email": RECIPIENT_EMAIL.lower(),
            "_id": {"$ne": naked_dist_id},
        }
    )
    response_5 = await _call_send(form_service, form_id)
    recipients_5 = response_5.get("recipients", [])
    _assert(
        recipients_5[0]["status"] == "sent",
        "never-attempted row does NOT block (email_sends defaults to 0)",
    )
    checkpoint_pause(
        "Verify never-attempted recovery in Chrome",
        [
            "Confirm planner can resend after a queue-stuck distribution.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 6: Submitted lead unblocks resend (positive — planner
    # may want to re-collect from the same person, e.g. updated info).
    # ------------------------------------------------------------------
    _log_checkpoint(6, TOTAL, "Submitted distribution unblocks a resend")
    await _update_latest_distribution(
        form_id,
        {
            "submitted_at": now_utc(),
            "email_sends": 1,
            "email_send_failures": 0,
            "token_expires_at": now_utc() + timedelta(days=14),
        },
    )
    response_6 = await _call_send(form_service, form_id)
    recipients_6 = response_6.get("recipients", [])
    _assert(
        recipients_6[0]["status"] == "sent",
        "submitted distribution does NOT block re-send",
    )
    _assert(
        response_6.get("skipped_duplicates", 0) == 0,
        "submitted recipient is not counted as a skipped duplicate",
    )
    checkpoint_pause(
        "Verify resend after submission in Chrome",
        [
            "Confirm planner can collect a fresh response from the same recipient.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 7: Per-recipient detail shape — every entry in
    # recipients[] carries the documented {email, distribution_id,
    # status, error} schema.
    # ------------------------------------------------------------------
    _log_checkpoint(7, TOTAL, "Per-recipient detail shape")
    for entry in response_6.get("recipients", []):
        _assert("email" in entry, "entry has 'email' key")
        _assert("distribution_id" in entry, "entry has 'distribution_id' key")
        _assert("status" in entry, "entry has 'status' key")
        _assert("error" in entry, "entry has 'error' key")
    print("  Sample recipients[] entry:")
    print(f"    {response_6['recipients'][0]}")

    # ------------------------------------------------------------------
    # CHECKPOINT 8: skipped_count totals match recipients with
    # status='skipped_duplicate'. Reuse response_2 — it's the only
    # response where the gate fired. Also re-verify the always-zero
    # case on response_3 / response_6.
    # ------------------------------------------------------------------
    _log_checkpoint(
        8, TOTAL, "skipped_duplicates aggregate matches per-recipient counts"
    )
    for resp_label, resp in (
        ("first send", response_1),
        ("duplicate send", response_2),
        ("failed-send recovery", response_3),
        ("expired-token recovery", response_4),
        ("never-attempted recovery", response_5),
        ("submitted resend", response_6),
    ):
        recipients = resp.get("recipients", [])
        per_count = sum(1 for r in recipients if r.get("status") == "skipped_duplicate")
        agg_count = int(resp.get("skipped_duplicates") or 0)
        _assert(
            per_count == agg_count,
            f"{resp_label}: skipped_duplicates aggregate ({agg_count}) "
            f"matches per-recipient count ({per_count})",
        )

    print()
    print(f"All 8 checkpoints passed. Total stub-email sends: {stub_email.send_count}")
    print("  ↳ run cleanup: python testbed/cleanup_form_send_dedup_recovery_state.py")


if __name__ == "__main__":
    asyncio.run(main())
