#!/usr/bin/env python3
"""
Marketing Lead Capture — Live Verification
==========================================

Verifies Phase C: ``POST /public/marketing/template-download``
records a lead, dispatches the PDF by email, and is idempotent on
``(email, template_id)``.

Pair: cleanup_form_marketing_lead_capture_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    MARKETING,
    banner,
    checkpoint_pause,
    count_documents,
)


VISITOR_EMAIL = "test_visitor+formlife_market@thespecialwedding.io"


async def main() -> None:
    banner("verify_form_marketing_lead_capture — VERIFY")
    print(f"Driver tag: {MARKETING.tag} (visitor email: {VISITOR_EMAIL})")

    checkpoint_pause(
        "Marketing lead capture lifecycle",
        [
            "Open https://app.thespecialwedding.io/resources/templates",
            "Click 'Download as PDF' on the Couple Intake card.",
            f"Email: {VISITOR_EMAIL}, name 'Test Visitor', UTM picked up from URL if any.",
            "Submit. Expect a 'Check your inbox' success message.",
            "Inspect Mongo: db.marketing_leads.find_one({email: '<visitor>', template_id: 'couple_intake'}) → row exists with download_count=1, email_sends=1.",
            "Resend dashboard: confirm an email landed with PDF attachment named 'couple_intake.pdf'.",
            "Click the same Download button again with the SAME email. Expect another success but NO new lead row — only download_count and last_downloaded_at increment.",
            "Try 11 submissions in quick succession from the same IP — the 11th should return 429.",
            "Open the marketing footer 'Start a free trial' link — confirm it carries utm_source=template_marketing.",
        ],
    )

    leads = await count_documents("marketing_leads", {"email": VISITOR_EMAIL})
    print(f"  ↳ post-VERIFY marketing_leads count for visitor: {leads}")
    print(f"  ↳ run cleanup: python testbed/cleanup_form_marketing_lead_capture_state.py")


if __name__ == "__main__":
    asyncio.run(main())
