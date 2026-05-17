#!/usr/bin/env python3
"""
Form FILE_UPLOAD — Live Verification
====================================

Verifies the FILE_UPLOAD field plumbing end-to-end:
- Upload through ``POST /public/forms/{form_id}/uploads`` with a valid
  (distribution_id, access_token) pair.
- Per-distribution aggregate quota (50 MB) and per-distribution count
  cap (25 files) reject excess uploads with 413/429.
- Submission with the returned file_id resolves on the server, and
  the responses row carries file metadata.
- Cross-distribution replay (file_id from another guest) is rejected.

Pair: cleanup_form_file_upload_state.py
"""

from __future__ import annotations

import asyncio
import hmac
import os
import sys
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    FILE_UPLOAD,
    banner,
    checkpoint_pause,
    insert_one,
    now_utc,
    short_token,
)


FORM_ID_PREFIX = "verify_upload"


async def seed_form_with_upload_field() -> tuple[str, str, str]:
    form_id = f"{FORM_ID_PREFIX}_{short_token()}"
    dist_id = f"{form_id}_dist"
    raw_token = f"verify_upl_{short_token()}"
    secret = os.environ.get("SECRET_KEY") or "test-secret"
    token_hash = hmac.new(secret.encode(), raw_token.encode(), sha256).hexdigest()

    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": "File Upload Verifier",
            "form_type": "general",
            "settings": {
                "title": "Vendor Onboarding",
                "description": "Verifier-seeded — file_upload path.",
                "submit_button_text": "Submit",
                "success_message": "Thanks!",
                "allow_multiple_submissions": True,
                "collect_email": True,
                "is_public": True,
                "requires_auth": False,
            },
            "fields": [
                {
                    "id": "coi",
                    "label": "Certificate of Insurance",
                    "type": "file_upload",
                    "required": True,
                    "order": 1,
                }
            ],
            "created_by": FILE_UPLOAD.email,
            "wedding_id": None,
            "is_active": True,
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "submission_count": 0,
            "planner_state": {},
        },
    )
    await insert_one(
        "form_distributions",
        {
            "_id": dist_id,
            "form_id": form_id,
            "recipient_email": "vendor@example.com",
            "sent_at": now_utc(),
            "status": "sent",
            "access_token_hash": token_hash,
            "token_expires_at": now_utc() + timedelta(days=14),
            "send_reminder": False,
            "reminder_days": 7,
            "reminder_sent_at": None,
            "reminder_count": 0,
        },
    )
    return form_id, dist_id, raw_token


async def main() -> None:
    banner("verify_form_file_upload_lifecycle — SEED")
    print(f"Planner: {FILE_UPLOAD.email}")
    form_id, dist_id, raw_token = await seed_form_with_upload_field()
    print(f"Seeded form: {form_id}, distribution: {dist_id}")
    print(f"Recipient URL: /forms/{form_id}?dist={dist_id}&t={raw_token}")

    checkpoint_pause(
        "File upload lifecycle",
        [
            "Open the recipient URL above in a private window.",
            "Attach a small (<1 MB) PDF named 'coi.pdf'. Expect upload succeeds and the field shows the filename.",
            "Submit. Expect a thank-you. The responses row stores {coi: {file_id, filename, url, content_type, size_bytes}}.",
            "Try uploading a 12 MB file → expect a 413 'too large' error (per-file cap).",
            "Upload 25 small files in succession → 26th upload returns 429 (per-distribution count cap).",
            "Upload files cumulating >50 MB → expect a 413 quota error.",
            "From a separate browser, attempt to forge POST /public/forms/{form_id}/submit with the file_id you saw and a different distribution_id → expect 400 (cross-distribution replay rejected).",
        ],
    )
    print("  ↳ run cleanup: python testbed/cleanup_form_file_upload_state.py")


if __name__ == "__main__":
    asyncio.run(main())
