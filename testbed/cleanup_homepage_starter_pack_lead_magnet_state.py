#!/usr/bin/env python3
"""Cleanup paired with verify_homepage_starter_pack_lead_magnet.py.

Drops every ``marketing_leads`` row tagged with the homepage-pack
verifier's plus-suffixed visitor emails (and any row carrying the XSS
payload as ``recipient_name`` in case a stale email got rewritten to a
different alias). Idempotent — re-running on already-cleaned state
returns zeros.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    banner,
    delete_many,
    purge_marketing_leads_for_email,
)


PRIMARY_EMAIL = "test_visitor+homepage_pack@thespecialwedding.io"
DUP_EMAIL = "test_visitor+homepage_pack_dup@thespecialwedding.io"
XSS_EMAIL = "test_visitor+homepage_pack_xss@thespecialwedding.io"
RATE_EMAIL = "test_visitor+homepage_pack_rate@thespecialwedding.io"

ALL_EMAILS = (PRIMARY_EMAIL, DUP_EMAIL, XSS_EMAIL, RATE_EMAIL)

XSS_PAYLOAD = '<script>alert("xss")</script>'


async def main() -> None:
    banner("cleanup_homepage_starter_pack_lead_magnet_state")
    total_email_deleted = 0
    for email in ALL_EMAILS:
        deleted = await purge_marketing_leads_for_email(email)
        total_email_deleted += deleted
        print(f"  • marketing_leads ({email}): {deleted} deleted")

    # Belt-and-suspenders: also sweep any row whose recipient_name still
    # carries the XSS payload, in case a previous run wrote it under a
    # different email alias.
    payload_deleted = await delete_many(
        "marketing_leads", {"recipient_name": XSS_PAYLOAD}
    )
    print(
        f"  • marketing_leads (recipient_name={XSS_PAYLOAD!r}): "
        f"{payload_deleted} deleted"
    )
    print(
        f"  ↳ total marketing_leads rows reaped: "
        f"{total_email_deleted + payload_deleted}"
    )


if __name__ == "__main__":
    asyncio.run(main())
