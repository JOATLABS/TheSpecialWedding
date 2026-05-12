#!/usr/bin/env python3
"""
Homepage Starter-Pack Lead Magnet — Live Verification
=====================================================

Exercises the homepage email-gated lead-magnet that ships ALL 9
catalog templates as PDF attachments in a single email:

    POST /public/marketing/template-download
    body: {"email": ..., "template_id": "starter_pack", "name": ..., utm_*}

Service entry: ``MarketingLeadService.capture_template_download`` with
the sentinel ``STARTER_PACK_TEMPLATE_ID = "starter_pack"`` (lives in
``app/services/marketing_lead_service.py``).

The route is rate-limited 10/hr/IP and the service is idempotent on
``(email, template_id)`` via the unique compound index. This driver
verifies BOTH right-logic AND false-positive/negative paths:

    [CHECKPOINT 1/9] Fresh starter_pack POST creates a lead row with
                     download_count=1, email_sends=1, all 9 PDF
                     attachments dispatched in one email.
    [CHECKPOINT 2/9] Repeat same email → status="resent",
                     download_count=2, exactly ONE lead row (idempotent
                     on the unique compound index).
    [CHECKPOINT 3/9] UTM context persisted on first capture; resends
                     append to ``subsequent_utm`` array.
    [CHECKPOINT 4/9] Single-template POST (couple_intake) creates a
                     SEPARATE lead row alongside the bundle path.
    [CHECKPOINT 5/9] Malformed email rejected with 4xx (Pydantic
                     EmailStr) — no Mongo row created.
    [CHECKPOINT 6/9] Unknown template_id rejected with 404 (KeyError) —
                     no Mongo row created.
    [CHECKPOINT 7/9] Concurrent dup-key race (asyncio.gather of two
                     simultaneous starter_pack POSTs for the same
                     email): the loser hits the DuplicateKey path and
                     resolves as status="resent" rather than 500.
                     Exactly ONE lead row in Mongo afterwards.
    [CHECKPOINT 8/9] HTML-escape on recipient_name: a malicious
                     ``<script>...</script>`` payload is escaped in the
                     rendered email HTML body — body contains
                     ``&lt;script&gt;``, NOT the raw tag. Storage of
                     the raw string on the lead row is fine.
    [CHECKPOINT 9/9] Rate limit kicks in after the 10/hr/IP cap on the
                     route layer — the 11th request returns 429.

Stubbed dependencies
--------------------
- ``ResendEmailService`` is monkey-patched on the service instance so
  no actual email is dispatched. The stub captures every call so we
  can assert attachment count + email_type + rendered HTML body.
- ``render_form_template_pdf`` is monkey-patched module-side to return
  a tiny deterministic byte string. Real PDF rendering is exercised
  by the Phase B verifier; here it would only slow the run.

Pair: cleanup_homepage_starter_pack_lead_magnet_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    HOMEPAGE_PACK,
    banner,
    checkpoint_pause,
    count_documents,
    delete_many,
    get_async_mongo,
)


# Plus-tag emails so cleanup can target this verifier without touching
# any other scenario's rows.
PRIMARY_EMAIL = "test_visitor+homepage_pack@thespecialwedding.io"
DUP_EMAIL = "test_visitor+homepage_pack_dup@thespecialwedding.io"
XSS_EMAIL = "test_visitor+homepage_pack_xss@thespecialwedding.io"
RATE_EMAIL = "test_visitor+homepage_pack_rate@thespecialwedding.io"

ALL_EMAILS = (PRIMARY_EMAIL, DUP_EMAIL, XSS_EMAIL, RATE_EMAIL)

XSS_PAYLOAD = '<script>alert("xss")</script>'

TOTAL = 9


# ---------------------------------------------------------------------------
# Stub email service — deterministic success without hitting Resend.
# We swap this onto the MarketingLeadService instance for the verifier.
# ---------------------------------------------------------------------------


class _StubEmailService:
    """Captures every send_email call so we can assert on shape."""

    def __init__(self) -> None:
        self.configured = True
        self.calls: List[Dict[str, Any]] = []

    async def send_email(self, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "success": True,
            "email_id": f"stub_msg_{len(self.calls)}",
        }

    def calls_for(self, to_email: str) -> List[Dict[str, Any]]:
        return [c for c in self.calls if c.get("to_email") == to_email.lower()]


def _assert(cond: bool, msg: str) -> None:
    """Loud, explicit assert helper — prints a CHECKPOINT FAIL marker on
    failure so the log has a single grep-able token."""
    if not cond:
        print(f"  [CHECKPOINT FAIL] {msg}")
        raise AssertionError(msg)
    print(f"    ✓ {msg}")


def _log_checkpoint(idx: int, total: int, label: str) -> None:
    print()
    print(f"[CHECKPOINT {idx}/{total}] {label}")


async def _purge_state() -> None:
    """Idempotent SEED: drop every marketing_leads row tagged with a
    verifier email or carrying the XSS payload as recipient_name."""
    for email in ALL_EMAILS:
        await delete_many("marketing_leads", {"email": email.lower()})
    await delete_many("marketing_leads", {"recipient_name": XSS_PAYLOAD})


def _build_service():
    """Construct a MarketingLeadService with stubbed email + PDF render."""
    from app.services import marketing_lead_service as mls_module
    from app.services.marketing_lead_service import MarketingLeadService

    # Stub the PDF renderer at module level — render_form_template_pdf is
    # imported by the service and wrapped in lru_cache; replacing it on
    # the module means the bundle path no longer waits on WeasyPrint.
    def _stub_pdf(template_id: str) -> bytes:
        return f"%PDF-stub:{template_id}".encode("utf-8")

    mls_module.render_form_template_pdf = _stub_pdf  # type: ignore[assignment]

    service = MarketingLeadService()
    stub = _StubEmailService()
    service.email_service = stub  # type: ignore[assignment]
    return service, stub


async def _latest_lead(email: str, template_id: str) -> Optional[Dict[str, Any]]:
    mongo = get_async_mongo()
    return await mongo.db["marketing_leads"].find_one(
        {"email": email.lower(), "template_id": template_id}
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def main() -> None:
    banner("verify_homepage_starter_pack_lead_magnet — SEED")
    print(f"Driver tag: {HOMEPAGE_PACK.tag}")
    print(f"Primary visitor: {PRIMARY_EMAIL}")
    print(f"Dup-race visitor: {DUP_EMAIL}")
    print(f"XSS visitor: {XSS_EMAIL}")
    print(f"Rate-limit visitor: {RATE_EMAIL}")

    await _purge_state()
    pre_count = sum(
        [
            await count_documents("marketing_leads", {"email": e.lower()})
            for e in ALL_EMAILS
        ]
    )
    _assert(pre_count == 0, "SEED: zero pre-existing marketing_leads rows")

    # Local imports so the smoke-test importer never touches Mongo / Resend.
    from app.services.form_template_catalog import FORM_TEMPLATES
    from app.services.marketing_lead_service import STARTER_PACK_TEMPLATE_ID

    catalog_ids = {tpl["id"] for tpl in FORM_TEMPLATES}
    _assert(
        len(catalog_ids) == 9,
        "FORM_TEMPLATES catalog ships exactly 9 templates",
    )
    _assert(
        STARTER_PACK_TEMPLATE_ID == "starter_pack",
        "Sentinel STARTER_PACK_TEMPLATE_ID == 'starter_pack'",
    )

    service, stub = _build_service()

    banner("VERIFY")

    # ------------------------------------------------------------------
    # CHECKPOINT 1: Fresh starter_pack download.
    # ------------------------------------------------------------------
    _log_checkpoint(1, TOTAL, "Fresh starter_pack download — lead created, 9 PDFs sent")
    result_1 = await service.capture_template_download(
        email=PRIMARY_EMAIL,
        template_id=STARTER_PACK_TEMPLATE_ID,
        recipient_name="Test Visitor",
        utm_source="homepage_band",
        utm_medium="organic",
        utm_campaign="starter_pack",
        ip_address="203.0.113.7",
        user_agent="Mozilla/5.0 (verifier)",
    )
    _assert(result_1["status"] == "created", "first POST returns status='created'")
    _assert(
        result_1["email_dispatched"] is True, "first POST returns email_dispatched=True"
    )
    pack_calls = stub.calls_for(PRIMARY_EMAIL)
    _assert(len(pack_calls) == 1, "exactly ONE Resend send_email call")
    call = pack_calls[0]
    _assert(
        call.get("email_type") == "marketing_starter_pack_download",
        "email_type='marketing_starter_pack_download'",
    )
    attachments = call.get("attachments") or []
    _assert(
        len(attachments) == 9,
        "send_email attachments has exactly 9 entries (one per catalog id)",
    )
    attachment_ids = {a["filename"].rsplit(".pdf", 1)[0] for a in attachments}
    _assert(
        attachment_ids == catalog_ids,
        "attachment filenames cover every FORM_TEMPLATES id",
    )

    lead_1 = await _latest_lead(PRIMARY_EMAIL, STARTER_PACK_TEMPLATE_ID)
    _assert(lead_1 is not None, "marketing_leads row created for starter_pack")
    assert lead_1 is not None
    _assert(lead_1["template_id"] == "starter_pack", "lead.template_id='starter_pack'")
    _assert(
        lead_1["template_name"] == "Free Wedding Planner Starter Pack",
        "lead.template_name='Free Wedding Planner Starter Pack'",
    )
    _assert(int(lead_1.get("download_count") or 0) == 1, "lead.download_count=1")
    _assert(int(lead_1.get("email_sends") or 0) == 1, "lead.email_sends=1")
    _assert(lead_1.get("utm_source") == "homepage_band", "lead.utm_source persisted")
    _assert(lead_1.get("utm_medium") == "organic", "lead.utm_medium persisted")
    _assert(lead_1.get("utm_campaign") == "starter_pack", "lead.utm_campaign persisted")
    checkpoint_pause(
        "Fresh starter_pack capture",
        [
            "Open the homepage band /home (email-gated 'Free Starter Pack' card).",
            f"Submit the form with email {PRIMARY_EMAIL} and name 'Test Visitor'.",
            "Confirm a 'Check your inbox' success toast appears.",
            "Resend dashboard: confirm ONE email landed with 9 PDF attachments.",
            "Open the email and confirm the attachment names match the 9 catalog ids.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 2: Repeat same email + starter_pack → resent, no dup row.
    # ------------------------------------------------------------------
    _log_checkpoint(2, TOTAL, "Resend — status='resent', download_count=2, no dup row")
    result_2 = await service.capture_template_download(
        email=PRIMARY_EMAIL,
        template_id=STARTER_PACK_TEMPLATE_ID,
        recipient_name="Test Visitor",
        utm_source="homepage_band_v2",
        utm_medium="organic",
        utm_campaign="starter_pack",
    )
    _assert(result_2["status"] == "resent", "second POST returns status='resent'")
    _assert(
        result_2["email_dispatched"] is True,
        "second POST returns email_dispatched=True",
    )
    rows_after_resend = await count_documents(
        "marketing_leads",
        {"email": PRIMARY_EMAIL.lower(), "template_id": STARTER_PACK_TEMPLATE_ID},
    )
    _assert(
        rows_after_resend == 1,
        "still exactly ONE lead row for (email, starter_pack) after resend",
    )
    lead_2 = await _latest_lead(PRIMARY_EMAIL, STARTER_PACK_TEMPLATE_ID)
    assert lead_2 is not None
    _assert(
        int(lead_2.get("download_count") or 0) == 2,
        "lead.download_count incremented to 2",
    )
    _assert(
        int(lead_2.get("email_sends") or 0) == 2, "lead.email_sends incremented to 2"
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 3: UTM history persisted on resend.
    # ------------------------------------------------------------------
    _log_checkpoint(3, TOTAL, "UTM context: original on lead, resend in subsequent_utm")
    _assert(
        lead_2.get("utm_source") == "homepage_band",
        "ORIGINAL utm_source unchanged on resend (not overwritten)",
    )
    subsequent = lead_2.get("subsequent_utm") or []
    _assert(
        len(subsequent) == 1, "subsequent_utm has exactly one entry after one resend"
    )
    _assert(
        subsequent[0].get("utm_source") == "homepage_band_v2",
        "subsequent_utm[0].utm_source captures the new UTM context",
    )
    checkpoint_pause(
        "UTM persistence + resend behavior",
        [
            "Re-submit the homepage card with the SAME email but UTM source.",
            f"Mongo: db.marketing_leads.find_one({{email:'{PRIMARY_EMAIL}', template_id:'starter_pack'}})",
            "Confirm download_count=2, email_sends=2, ONE row total.",
            "Confirm utm_source='homepage_band' (original) and subsequent_utm[0].utm_source='homepage_band_v2'.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 4: Single-template POST creates a separate lead row.
    # ------------------------------------------------------------------
    _log_checkpoint(4, TOTAL, "Single-template path co-exists with bundle path")
    result_4 = await service.capture_template_download(
        email=PRIMARY_EMAIL,
        template_id="couple_intake",
        recipient_name="Test Visitor",
        utm_source="resources_page",
    )
    _assert(
        result_4["status"] == "created",
        "couple_intake first capture returns status='created'",
    )
    rows_total_for_email = await count_documents(
        "marketing_leads", {"email": PRIMARY_EMAIL.lower()}
    )
    _assert(
        rows_total_for_email == 2,
        "two distinct lead rows for the visitor (starter_pack + couple_intake)",
    )
    lead_couple = await _latest_lead(PRIMARY_EMAIL, "couple_intake")
    _assert(
        lead_couple is not None,
        "couple_intake lead row exists separately from the bundle row",
    )
    _assert(
        lead_couple["template_id"] == "couple_intake",
        "couple_intake lead.template_id='couple_intake'",
    )
    couple_calls = [
        c
        for c in stub.calls
        if c.get("email_type") == "marketing_template_download"
        and c.get("to_email") == PRIMARY_EMAIL.lower()
    ]
    _assert(
        len(couple_calls) == 1,
        "single-template Resend call uses email_type='marketing_template_download'",
    )
    _assert(
        len(couple_calls[0].get("attachments") or []) == 1,
        "single-template path attaches exactly 1 PDF (not 9)",
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 5: Bad email rejected.
    # ------------------------------------------------------------------
    _log_checkpoint(5, TOTAL, "Malformed email rejected (Pydantic EmailStr)")
    from pydantic import ValidationError

    from app.api.forms import _MarketingTemplateDownloadRequest

    raised = False
    try:
        _MarketingTemplateDownloadRequest(
            template_id=STARTER_PACK_TEMPLATE_ID,
            email="not-an-email",
            name="Bad Email",
            utm_source=None,
            utm_medium=None,
            utm_campaign=None,
        )
    except ValidationError:
        raised = True
    _assert(raised, "EmailStr rejects 'not-an-email' before the route handler runs")
    rows_for_bad = await count_documents("marketing_leads", {"email": "not-an-email"})
    _assert(rows_for_bad == 0, "no Mongo row created for malformed email")

    # ------------------------------------------------------------------
    # CHECKPOINT 6: Unknown template_id → KeyError → 404.
    # ------------------------------------------------------------------
    _log_checkpoint(6, TOTAL, "Unknown template_id rejected (KeyError → 404)")
    raised_key = False
    try:
        await service.capture_template_download(
            email=PRIMARY_EMAIL,
            template_id="not_a_real_template",
        )
    except KeyError:
        raised_key = True
    _assert(
        raised_key,
        "service raises KeyError for unknown template_id (route layer maps to 404)",
    )
    rows_bad_tpl = await count_documents(
        "marketing_leads",
        {"email": PRIMARY_EMAIL.lower(), "template_id": "not_a_real_template"},
    )
    _assert(rows_bad_tpl == 0, "no Mongo row created for unknown template_id")

    # ------------------------------------------------------------------
    # CHECKPOINT 7: Concurrent dup-key race.
    # NB: asyncio.gather on the same loop is cooperative, so one task
    # always wins the insert before the other awakens — the race is
    # rarely triggered in production. The API must STILL be idempotent
    # in either ordering, which is what we verify here. The DuplicateKey
    # branch in MarketingLeadService.capture_template_download falls
    # through to the update path and returns status='resent'.
    # ------------------------------------------------------------------
    _log_checkpoint(7, TOTAL, "Concurrent dup-key race resolves to one row")
    results = await asyncio.gather(
        service.capture_template_download(
            email=DUP_EMAIL,
            template_id=STARTER_PACK_TEMPLATE_ID,
            recipient_name="Race A",
            utm_source="homepage_band",
        ),
        service.capture_template_download(
            email=DUP_EMAIL,
            template_id=STARTER_PACK_TEMPLATE_ID,
            recipient_name="Race B",
            utm_source="homepage_band",
        ),
        return_exceptions=True,
    )
    failures = [r for r in results if isinstance(r, Exception)]
    _assert(
        not failures,
        f"neither concurrent task raised an unhandled exception (got: {failures})",
    )
    statuses = sorted(r.get("status") for r in results if isinstance(r, dict))
    _assert(
        statuses == ["created", "resent"] or statuses == ["resent", "resent"],
        f"loser falls through to status='resent' (got: {statuses})",
    )
    rows_dup = await count_documents(
        "marketing_leads",
        {"email": DUP_EMAIL.lower(), "template_id": STARTER_PACK_TEMPLATE_ID},
    )
    _assert(
        rows_dup == 1, "exactly ONE lead row for (dup_email, starter_pack) after race"
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 8: HTML escape on recipient_name.
    # The lead row stores the raw string verbatim (storage is fine —
    # the renderer is the trust boundary). The rendered email body MUST
    # escape the script tag so a downstream HTML viewer cannot execute
    # the payload.
    # ------------------------------------------------------------------
    _log_checkpoint(8, TOTAL, "HTML escape on recipient_name in rendered email body")
    result_xss = await service.capture_template_download(
        email=XSS_EMAIL,
        template_id=STARTER_PACK_TEMPLATE_ID,
        recipient_name=XSS_PAYLOAD,
        utm_source="homepage_band",
    )
    _assert(
        result_xss["status"] == "created",
        "XSS-named visitor still records a lead (storage allowed)",
    )
    xss_lead = await _latest_lead(XSS_EMAIL, STARTER_PACK_TEMPLATE_ID)
    _assert(xss_lead is not None, "XSS-named lead row exists")
    _assert(
        xss_lead.get("recipient_name") == XSS_PAYLOAD,
        "raw payload stored verbatim on the lead row (storage is OK)",
    )
    xss_calls = stub.calls_for(XSS_EMAIL)
    _assert(len(xss_calls) == 1, "one Resend call for XSS visitor")
    rendered_html = xss_calls[0].get("html_content") or ""
    _assert(
        "&lt;script&gt;" in rendered_html,
        "rendered email body contains escaped '&lt;script&gt;'",
    )
    _assert(
        XSS_PAYLOAD not in rendered_html,
        "raw '<script>...</script>' tag is NOT present in rendered email body",
    )
    checkpoint_pause(
        "Manual verification: XSS payload escaping",
        [
            f"Submit the homepage band with email {XSS_EMAIL} "
            f"and name '{XSS_PAYLOAD}'.",
            "Open the inbox; verify the email renders the literal text "
            "'<script>alert(\"xss\")</script>' (NOT a JS alert).",
            "View source: confirm the body shows '&lt;script&gt;', not the raw tag.",
        ],
    )

    # ------------------------------------------------------------------
    # CHECKPOINT 9: Rate limit kicks in at the 11th request from one IP.
    # The route layer's rate_limiter caps marketing_template_download
    # at 10/hour/IP. We exercise the limiter directly with the route's
    # exact key shape so this checkpoint stays deterministic without
    # spinning up a TestClient.
    # ------------------------------------------------------------------
    _log_checkpoint(9, TOTAL, "Rate limit: 11th request from one IP returns 429")
    from app.utils.security_utils import rate_limiter

    rate_ip = "203.0.113.99"
    rate_key = f"marketing_template_download_{rate_ip}"
    # Reset any prior count for this key so reruns start clean.
    if hasattr(rate_limiter, "_requests"):
        rate_limiter._requests.pop(rate_key, None)
    allowed_count = 0
    blocked_count = 0
    for i in range(11):
        if rate_limiter.check_rate_limit(rate_key, limit=10, window_seconds=3600):
            allowed_count += 1
        else:
            blocked_count += 1
    _assert(
        allowed_count == 10, "first 10 requests from one IP are allowed (10/hr cap)"
    )
    _assert(
        blocked_count == 1, "11th request from same IP is blocked (route returns 429)"
    )

    # ------------------------------------------------------------------
    # Wrap-up
    # ------------------------------------------------------------------
    final_count = sum(
        await count_documents("marketing_leads", {"email": e.lower()})
        for e in ALL_EMAILS
    )
    print()
    print(f"  ↳ final marketing_leads count across verifier emails: {final_count}")
    print(
        "  ↳ run cleanup: python testbed/cleanup_homepage_starter_pack_lead_magnet_state.py"
    )


if __name__ == "__main__":
    asyncio.run(main())
