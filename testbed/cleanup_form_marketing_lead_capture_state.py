#!/usr/bin/env python3
"""Cleanup paired with verify_form_marketing_lead_capture.py."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    banner,
    purge_marketing_leads_for_email,
)


VISITOR_EMAIL = "test_visitor+formlife_market@thespecialwedding.io"


async def main() -> None:
    banner("cleanup_form_marketing_lead_capture_state")
    deleted = await purge_marketing_leads_for_email(VISITOR_EMAIL)
    print(f"  • marketing_leads ({VISITOR_EMAIL}): {deleted} deleted")


if __name__ == "__main__":
    asyncio.run(main())
