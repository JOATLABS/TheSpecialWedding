#!/usr/bin/env python3
"""
CSV Export Truncation + Date Filter — Live Verification
=======================================================

Seeds a form with 10,005 form_responses spread over a known time
window. Verifies:
  - CSV export truncates at 10,000 with X-Truncated / X-Total-Count
    response headers (Phase B).
  - The Item 1 audit fix: ``date_from`` / ``date_to`` request params
    actually scope the exported dataset (previously parsed but never
    applied).

Pair: cleanup_form_csv_export_truncation_state.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    CSV_TRUNCATION,
    banner,
    checkpoint_pause,
    count_documents,
    insert_one,
    now_utc,
    short_token,
)


FORM_ID_PREFIX = "verify_csvtrunc"


async def seed_oversize_form(count: int = 10_005) -> tuple[str, list[str]]:
    """Seed an oversize form with responses spread across 5 'days' so
    the date_from / date_to filter has something meaningful to scope."""
    form_id = f"{FORM_ID_PREFIX}_{short_token()}"
    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": "CSV Truncation Verifier",
            "form_type": "general",
            "settings": {
                "title": "CSV truncation",
                "description": "Verifier-seeded — CSV truncation + date filter.",
                "submit_button_text": "Submit",
                "success_message": "Thanks!",
                "allow_multiple_submissions": True,
                "collect_email": True,
                "is_public": True,
                "requires_auth": False,
            },
            "fields": [
                {"id": "company_name", "label": "Company", "type": "text", "required": True, "order": 1}
            ],
            "created_by": CSV_TRUNCATION.email,
            "is_active": True,
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "submission_count": count,
            "planner_state": {},
        },
    )

    base = now_utc()
    bucket_days = [-4, -3, -2, -1, 0]
    bucket_iso: list[str] = []
    for d in bucket_days:
        bucket_iso.append((base + timedelta(days=d)).strftime("%Y-%m-%d"))

    per_bucket = count // 5
    written = 0
    for bucket_idx, day in enumerate(bucket_days):
        for i in range(per_bucket):
            await insert_one(
                "form_responses",
                {
                    "_id": f"{form_id}_resp_{written}",
                    "form_id": form_id,
                    "responses": {"company_name": f"Co {written:05d}"},
                    "submitted_at": base + timedelta(days=day, seconds=i),
                    "submitted_by_email": None,
                },
            )
            written += 1
    # Sprinkle the last few into "today".
    while written < count:
        await insert_one(
            "form_responses",
            {
                "_id": f"{form_id}_resp_{written}",
                "form_id": form_id,
                "responses": {"company_name": f"Co {written:05d}"},
                "submitted_at": base,
                "submitted_by_email": None,
            },
        )
        written += 1
    return form_id, bucket_iso


async def main() -> None:
    banner("verify_form_csv_export_truncation — SEED")
    print(f"Planner: {CSV_TRUNCATION.email}")
    form_id, bucket_iso = await seed_oversize_form(10_005)
    rows = await count_documents("form_responses", {"form_id": form_id})
    print(f"Seeded form: {form_id}, response count: {rows}")
    print(f"Bucket dates: {bucket_iso}")

    checkpoint_pause(
        "CSV export truncation + date filter lifecycle",
        [
            f"Login as {CSV_TRUNCATION.email} and open /admin/forms/{form_id}/responses.",
            "Click 'Export to CSV' (no date filter). Inspect response headers in Network tab:",
            "  X-Total-Count: 10005 — X-Truncated: true — X-Truncated-Count: 5 — X-Max-Export-Size: 10000.",
            "Open the downloaded CSV — exactly 10,000 rows.",
            f"Now retry with date_from={bucket_iso[2]}&date_to={bucket_iso[2]} (single-day window). Headers:",
            "  X-Total-Count: 2001 — X-Truncated: false (under cap).",
            "CSV: ~2,001 rows; ALL rows' submitted_at falls within the chosen day. (Item 1 audit fix — previously the date params were dead code).",
            f"Retry with date_from={bucket_iso[0]}&date_to={bucket_iso[1]} — header X-Total-Count ≈ 4002.",
            "Retry with date_from=NOT-A-DATE → expect 400 'Invalid date_from format'.",
        ],
    )
    print(f"  ↳ run cleanup: python testbed/cleanup_form_csv_export_truncation_state.py")


if __name__ == "__main__":
    asyncio.run(main())
