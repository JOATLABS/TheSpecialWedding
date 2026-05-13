#!/usr/bin/env python3
"""
Public Form Template PDF Preview — Live Verification
====================================================

Verifies the Phase B public endpoint
``GET /public/form-templates/{template_id}/preview.pdf``: returns a
valid PDF (magic bytes %PDF), is rate-limited (60/hour/IP), is
process-side cached via ``functools.lru_cache``, and 404s on unknown
template ids.

Pair: cleanup_form_public_pdf_preview_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    PUBLIC_PDF,
    banner,
    checkpoint_pause,
)


async def main() -> None:
    banner("verify_form_public_pdf_preview — VERIFY")
    print(f"Driver tag: {PUBLIC_PDF.tag} (no planner seeded — public endpoint)")

    checkpoint_pause(
        "Public PDF preview lifecycle",
        [
            "curl -i https://app.thespecialwedding.io/public/form-templates/couple_intake/preview.pdf",
            "Expect 200, Content-Type: application/pdf, Content-Disposition: inline; filename=\"couple_intake.pdf\".",
            "Confirm the body starts with %PDF (magic bytes).",
            "Check the response headers for Cache-Control: public, max-age=300, must-revalidate.",
            "Make 60 successive calls in quick succession — the 61st should return 429 (rate limit).",
            "Hit the same URL twice in a row — second call should be served from process cache (very low latency).",
            "Hit /public/form-templates/does_not_exist/preview.pdf — expect 404.",
            "Open the PDF in a viewer — confirm 'The Special Wedding' appears in the @page header and 'Made with thespecialwedding.io' in the footer.",
        ],
    )
    print(f"  ↳ run cleanup: python testbed/cleanup_form_public_pdf_preview_state.py (no-op)")


if __name__ == "__main__":
    asyncio.run(main())
