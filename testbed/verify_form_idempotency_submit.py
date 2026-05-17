#!/usr/bin/env python3
"""
Form Submit Idempotency Key — Live Verification
================================================

Exercises the ``idempotency_key`` contract on
``POST /public/forms/{form_id}/submit``
(``SubmitFormRequest.idempotency_key`` validated 8-128 URL-safe chars
via ``app/models/form.py:validate_idempotency_key``).

Background
----------
The frontend stamps a stable per-form-fill UUID into every submit
request. A network blip + client retry must not produce a duplicate
``form_responses`` row. The server therefore looks up
``(form_id, idempotency_key)`` before inserting; on hit it returns
the original response payload with an extra
``duplicate_of_idempotent_request: True`` flag. Distinct keys still
produce distinct rows, and the key is form-scoped so the same value
on a different form is a separate write.

Strategy
--------
SEED:
    - ``IDEMPOTENCY`` planner email is recorded as ``created_by`` on
      two seeded forms (idempotent insert via Mongo — the smoke
      import path stays network-free).
    - Form A is anonymous-access, ``allow_multiple_submissions=True``.
    - Form B is anonymous-access too (used for the cross-form-scope
      check in CHECKPOINT 7).
    - Form C is tokenized (one distribution per recipient) so
      CHECKPOINT 8 can prove the per-distribution single-submission
      gate still wins over a fresh idempotency key, and
      CHECKPOINT 9 can prove the 410 expired-token gate still wins.

VERIFY (each checkpoint asserts on the live ``submit_form_response``
response and ENTER-gates so the user can inspect Chrome between
phases):

    [CHECKPOINT 1/9] First submit with key → row inserted, no flag
    [CHECKPOINT 2/9] Repeat with same key → SAME response, flag=True,
                     no second row
    [CHECKPOINT 3/9] Distinct keys → two rows
    [CHECKPOINT 4/9] Missing key → legacy path still works (third row)
    [CHECKPOINT 5/9] Malformed key (too short) → 422, no new row
    [CHECKPOINT 6/9] Malformed key (illegal chars) → 422, no new row
    [CHECKPOINT 7/9] Same key on a DIFFERENT form_id → separate row
    [CHECKPOINT 8/9] Tokenized 409 single-submission gate beats key
    [CHECKPOINT 9/9] Tokenized 410 expired-token gate beats key

Pair: cleanup_form_idempotency_submit_state.py
"""

from __future__ import annotations

import asyncio
import hmac
import os
import sys
import uuid
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from typing import Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    IDEMPOTENCY,
    banner,
    checkpoint_pause,
    count_documents,
    get_async_mongo,
    insert_one,
    now_utc,
    short_token,
)


FORM_ID_PREFIX = "verify_idempo"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _hash_token(secret: str, raw: str) -> str:
    return hmac.new(secret.encode(), raw.encode(), sha256).hexdigest()


async def _seed_anon_form(suffix: str) -> str:
    """Insert one anonymous-access form (no token gate). Idempotent
    via short_token() suffix; cleanup wipes by created_by."""
    form_id = f"{FORM_ID_PREFIX}_{suffix}_{short_token()}"
    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": f"Idempotency Verifier — {suffix}",
            "form_type": "general",
            "settings": {
                "title": "Quick Reply",
                "description": "Verifier-seeded — submit idempotency_key path.",
                "submit_button_text": "Send",
                "success_message": "Thanks!",
                "allow_multiple_submissions": True,
                "collect_email": False,
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
            "created_by": IDEMPOTENCY.email,
            "wedding_id": None,
            "is_active": True,
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "submission_count": 0,
            "planner_state": {},
        },
    )
    return form_id


async def _seed_tokenized_distribution(
    form_id: str,
    recipient: str,
    *,
    expires_in_days: int = 14,
) -> Tuple[str, str]:
    """Insert one distribution row + return (dist_id, raw_token).

    The raw token is hashed with the same scheme the live server
    uses (HMAC-SHA256 over SECRET_KEY) so the submit path can verify
    it without ever round-tripping through ``send_form``.
    """
    secret = os.environ.get("SECRET_KEY") or "test-secret"
    dist_id = f"{form_id}_dist_{short_token()}"
    raw_token = f"verify_idempo_tok_{short_token()}"
    expires_at = now_utc() + timedelta(days=expires_in_days)
    await insert_one(
        "form_distributions",
        {
            "_id": dist_id,
            "form_id": form_id,
            "recipient_email": recipient,
            "sent_at": now_utc(),
            "status": "sent",
            "access_token_hash": _hash_token(secret, raw_token),
            "token_expires_at": expires_at,
            "send_reminder": False,
            "reminder_days": 7,
            "reminder_sent_at": None,
            "reminder_count": 0,
            "email_sends": 1,
            "email_send_failures": 0,
        },
    )
    return dist_id, raw_token


async def _expire_distribution(dist_id: str) -> None:
    """Backdate token_expires_at so the 410 gate fires."""
    mongo = get_async_mongo()
    await mongo.db["form_distributions"].update_one(
        {"_id": dist_id},
        {"$set": {"token_expires_at": now_utc() - timedelta(days=1)}},
    )


# ---------------------------------------------------------------------------
# Logging / assertion helpers
# ---------------------------------------------------------------------------


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  [CHECKPOINT FAIL] {msg}")
        raise AssertionError(msg)
    print(f"    ✓ {msg}")


def _log_checkpoint(idx: int, total: int, label: str) -> None:
    print()
    print(f"[CHECKPOINT {idx}/{total}] {label}")


def _new_key() -> str:
    """Fresh URL-safe idempotency key (UUIDv4, 36 chars w/ hyphens)."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


TOTAL = 9


async def main() -> None:
    banner("verify_form_idempotency_submit — SEED")
    print(f"Planner: {IDEMPOTENCY.email}")

    # Local imports keep module-level import network-free for the
    # smoke test in tests/backend/test_testbed_drivers_smoke.py.
    from fastapi import HTTPException
    from pydantic import ValidationError

    from app.models.form import SubmitFormRequest
    from app.services.form_service import FormService

    form_a = await _seed_anon_form("a")
    form_b = await _seed_anon_form("b")
    form_c = await _seed_anon_form("c_tok")  # will host tokenized distributions
    form_d = await _seed_anon_form("d_tok")  # for the 410 expired-token gate
    print(f"Seeded form A (anon):     {form_a}")
    print(f"Seeded form B (anon):     {form_b}")
    print(f"Seeded form C (tokenized):{form_c}")
    print(f"Seeded form D (tokenized):{form_d}")

    dist_c, token_c = await _seed_tokenized_distribution(form_c, "guest_c@example.com")
    print(f"  ↳ form C distribution: {dist_c}  (token live)")
    dist_d, token_d = await _seed_tokenized_distribution(form_d, "guest_d@example.com")
    print(f"  ↳ form D distribution: {dist_d}  (will be expired below)")

    form_service = FormService()

    banner("VERIFY")

    # ------------------------------------------------------------------
    # CHECKPOINT 1: First submit with key → row inserted, NO flag.
    # ------------------------------------------------------------------
    _log_checkpoint(1, TOTAL, "First submit with key creates one row")
    key_1 = _new_key()
    request_1 = SubmitFormRequest(responses={"name": "Alex"}, idempotency_key=key_1)
    response_1 = await form_service.submit_form_response(form_a, request_1)
    _assert("id" in response_1, "response carries an id")
    _assert("message" in response_1, "response carries a message")
    _assert("redirect_url" in response_1, "response carries redirect_url field")
    _assert(
        "duplicate_of_idempotent_request" not in response_1,
        "first submit has NO duplicate_of_idempotent_request flag",
    )
    rows_1 = await count_documents("form_responses", {"form_id": form_a})
    _assert(rows_1 == 1, "exactly one form_responses row exists for form A")
    persisted = (
        await get_async_mongo().db["form_responses"].find_one({"_id": response_1["id"]})
    )
    _assert(
        persisted is not None and persisted.get("idempotency_key") == key_1,
        "idempotency_key persisted on the form_responses row",
    )
    checkpoint_pause(
        "First submit with idempotency key",
        [
            f"Open https://app.thespecialwedding.io/forms/{form_a} in a private window.",
            "Submit name='Alex'. Network panel shows the request body carries an idempotency_key.",
            "Expect a thank-you screen.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 2: Repeat with same key → SAME response, flag=True,
    # NO second row.
    # ------------------------------------------------------------------
    _log_checkpoint(2, TOTAL, "Repeat with same key returns original response")
    request_2 = SubmitFormRequest(responses={"name": "Alex"}, idempotency_key=key_1)
    response_2 = await form_service.submit_form_response(form_a, request_2)
    _assert(response_2["id"] == response_1["id"], "id matches the first submit")
    _assert(response_2["message"] == response_1["message"], "message matches")
    _assert(
        response_2.get("redirect_url") == response_1.get("redirect_url"),
        "redirect_url matches",
    )
    _assert(
        response_2.get("duplicate_of_idempotent_request") is True,
        "second submit carries duplicate_of_idempotent_request: True",
    )
    rows_2 = await count_documents("form_responses", {"form_id": form_a})
    _assert(rows_2 == 1, "still exactly one form_responses row for form A")
    checkpoint_pause(
        "Replay with same idempotency key",
        [
            "Replay the request from DevTools (same body, same key).",
            "Expect the SAME response payload — id matches, no new row in Mongo.",
            "Planner: open /admin/forms — submission_count for form A still == 1.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 3: Distinct key → second row inserted.
    # ------------------------------------------------------------------
    _log_checkpoint(3, TOTAL, "Distinct keys yield two rows")
    key_3 = _new_key()
    response_3 = await form_service.submit_form_response(
        form_a,
        SubmitFormRequest(responses={"name": "Bea"}, idempotency_key=key_3),
    )
    _assert(response_3["id"] != response_1["id"], "fresh response id")
    _assert(
        "duplicate_of_idempotent_request" not in response_3,
        "fresh submit has NO duplicate flag",
    )
    rows_3 = await count_documents("form_responses", {"form_id": form_a})
    _assert(rows_3 == 2, "two distinct rows now exist for form A")
    checkpoint_pause(
        "Fresh key → fresh row",
        [
            "Submit again with a fresh idempotency key (browser-generated).",
            "Expect a new thank-you and a new row in the responses table.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 4: Missing key → legacy path still works.
    # ------------------------------------------------------------------
    _log_checkpoint(4, TOTAL, "Missing key still inserts a row")
    response_4 = await form_service.submit_form_response(
        form_a,
        SubmitFormRequest(responses={"name": "Cleo"}),
    )
    _assert("id" in response_4, "legacy submit carries id")
    _assert(
        "duplicate_of_idempotent_request" not in response_4,
        "legacy submit has NO duplicate flag",
    )
    rows_4 = await count_documents("form_responses", {"form_id": form_a})
    _assert(rows_4 == 3, "three rows now exist for form A")
    checkpoint_pause(
        "Missing key — legacy path",
        [
            "Strip idempotency_key from the request body in DevTools.",
            "Resubmit. Expect a new row — legacy path is preserved.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 5: Malformed key (too short) → 422, no new row.
    # Pydantic raises ValidationError at the request-model boundary,
    # which FastAPI surfaces as 422. We validate at the model layer
    # here since the route is the same wrapper.
    # ------------------------------------------------------------------
    _log_checkpoint(5, TOTAL, "Malformed key (too short) is rejected")
    raised = False
    try:
        SubmitFormRequest(responses={"name": "Dee"}, idempotency_key="abc")
    except ValidationError as exc:
        raised = True
        _assert(
            "idempotency_key" in str(exc),
            "ValidationError mentions idempotency_key",
        )
    _assert(raised, "Pydantic raises (FastAPI surfaces as 422)")
    rows_5 = await count_documents("form_responses", {"form_id": form_a})
    _assert(rows_5 == 3, "still three rows — no row created on malformed key")
    checkpoint_pause(
        "Malformed key (too short) rejected",
        [
            "Send a request with idempotency_key='abc' via DevTools / curl.",
            "Expect HTTP 422 with a Pydantic validation error mentioning idempotency_key.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 6: Malformed key (illegal chars) → 422, no new row.
    # ------------------------------------------------------------------
    _log_checkpoint(6, TOTAL, "Malformed key (illegal chars) is rejected")
    raised = False
    try:
        SubmitFormRequest(
            responses={"name": "Dee"},
            idempotency_key="bad key with space",
        )
    except ValidationError as exc:
        raised = True
        _assert(
            "idempotency_key" in str(exc),
            "ValidationError mentions idempotency_key",
        )
    _assert(raised, "Pydantic raises on illegal chars")
    rows_6 = await count_documents("form_responses", {"form_id": form_a})
    _assert(rows_6 == 3, "still three rows — no row on illegal-char key")
    checkpoint_pause(
        "Malformed key (illegal chars) rejected",
        [
            "Send a request with idempotency_key='bad key with space'.",
            "Expect HTTP 422.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 7: Form-scoped — same key on form B creates a new row.
    # ------------------------------------------------------------------
    _log_checkpoint(7, TOTAL, "Same key on a different form is a separate row")
    response_7 = await form_service.submit_form_response(
        form_b,
        SubmitFormRequest(responses={"name": "Eli"}, idempotency_key=key_1),
    )
    _assert(response_7["id"] != response_1["id"], "form B response has its own id")
    _assert(
        "duplicate_of_idempotent_request" not in response_7,
        "cross-form re-use is NOT a duplicate",
    )
    rows_b = await count_documents("form_responses", {"form_id": form_b})
    _assert(rows_b == 1, "form B has its own row, not a cross-form collision")
    rows_a = await count_documents("form_responses", {"form_id": form_a})
    _assert(rows_a == 3, "form A row count unchanged after the form-B submit")
    checkpoint_pause(
        "Form-scoped idempotency",
        [
            f"Open /forms/{form_b} in a fresh window.",
            f"Submit with the SAME idempotency key {key_1}.",
            "Expect a fresh thank-you and a new row scoped to form B.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 8: Tokenized 409 single-submission gate still wins,
    # even when the second submit uses a fresh idempotency key.
    # ------------------------------------------------------------------
    _log_checkpoint(8, TOTAL, "Tokenized 409 beats a fresh idempotency key")
    first_tok_key = _new_key()
    response_tok_1 = await form_service.submit_form_response(
        form_c,
        SubmitFormRequest(
            responses={"name": "Tok-First"},
            distribution_id=dist_c,
            access_token=token_c,
            idempotency_key=first_tok_key,
        ),
    )
    _assert("id" in response_tok_1, "first tokenized submit succeeds")
    _assert(
        await count_documents("form_responses", {"form_id": form_c}) == 1,
        "form C has one row after first tokenized submit",
    )

    second_tok_key = _new_key()
    raised_409 = False
    try:
        await form_service.submit_form_response(
            form_c,
            SubmitFormRequest(
                responses={"name": "Tok-Replay"},
                distribution_id=dist_c,
                access_token=token_c,
                idempotency_key=second_tok_key,
            ),
        )
    except HTTPException as exc:
        raised_409 = True
        _assert(
            exc.status_code == 409,
            f"second submit raises 409 (got {exc.status_code})",
        )
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        _assert(
            "already" in detail.lower(),
            "409 detail mentions 'already submitted'",
        )
    _assert(raised_409, "tokenized form raises HTTPException on replay")
    _assert(
        await count_documents("form_responses", {"form_id": form_c}) == 1,
        "no second row on form C — single-submission gate held",
    )
    checkpoint_pause(
        "Tokenized 409 wins over idempotency key",
        [
            f"Open /forms/{form_c}?dist={dist_c}&t={token_c} (Guest C's link).",
            "Submit. Expect thank-you (already done above).",
            "Refresh and resubmit with a brand-new idempotency_key in DevTools.",
            "Expect HTTP 409 'already submitted with this link'.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 9: Tokenized 410 expired-token gate still wins.
    # ------------------------------------------------------------------
    _log_checkpoint(9, TOTAL, "Tokenized 410 beats an idempotency key")
    await _expire_distribution(dist_d)
    raised_410 = False
    try:
        await form_service.submit_form_response(
            form_d,
            SubmitFormRequest(
                responses={"name": "Stale"},
                distribution_id=dist_d,
                access_token=token_d,
                idempotency_key=_new_key(),
            ),
        )
    except HTTPException as exc:
        raised_410 = True
        _assert(
            exc.status_code == 410,
            f"expired token submit raises 410 (got {exc.status_code})",
        )
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        _assert(
            "expired" in detail.lower(),
            "410 detail mentions 'expired'",
        )
    _assert(raised_410, "expired-token submit raises HTTPException")
    _assert(
        await count_documents("form_responses", {"form_id": form_d}) == 0,
        "no row on form D — expired-token gate held",
    )
    checkpoint_pause(
        "Expired-token 410 wins over idempotency key",
        [
            f"Open /forms/{form_d}?dist={dist_d}&t={token_d}.",
            "Expect a 'this link has expired' message — even with a fresh key.",
        ],
    )

    print()
    print(f"All {TOTAL} checkpoints passed.")
    print("  ↳ run cleanup: python testbed/cleanup_form_idempotency_submit_state.py")


if __name__ == "__main__":
    asyncio.run(main())
