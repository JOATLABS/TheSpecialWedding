#!/usr/bin/env python3
"""
Phase D Catalog Auto-Seed — Live Verification
=============================================

Verifies that a freshly-verified planner has all 9 catalog templates
auto-loaded into their workspace, and that re-running the seeder is a
zero-duplicate no-op.

Pair: cleanup_form_phase_d_seed_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    PHASE_D_SEED,
    banner,
    checkpoint_pause,
    count_documents,
)


async def main() -> None:
    banner("verify_form_phase_d_seed — VERIFY")
    print(f"Planner: {PHASE_D_SEED.email}")

    print()
    print("Step 1 — sign up and verify this planner via the public flow:")
    print("  POST /public/register with the email above.")
    print("  Click the verification link in the inbox / Resend dashboard.")
    print("  Verification triggers app/services/user_management_service.verify_email,")
    print("  which calls FormService.seed_catalog_templates_for_planner.")
    print()

    checkpoint_pause(
        "Phase D seed lifecycle",
        [
            "Open the planner dashboard at /admin/forms — expect 9 forms named after the catalog (Couple Intake, Order of Events, Guest Dietary, …).",
            "Each form's settings.title should match the catalog name.",
            "Each form should carry seeded_from_catalog=True (verify via Mongo or the Phase 1 admin tooling).",
            "Run the seeder a second time (e.g. by re-clicking the verification link). Result: still 9 forms (idempotent — Phase D's seeded_from_catalog + catalog_template_id markers prevent duplicates).",
            "Sign up a SECOND planner with a different plus-tag. Confirm their workspace also gets all 9 forms, isolated from this planner's set.",
        ],
    )
    seeded = await count_documents(
        "forms",
        {"created_by": PHASE_D_SEED.email, "seeded_from_catalog": True},
    )
    print(f"  ↳ post-VERIFY seeded form count for {PHASE_D_SEED.email}: {seeded}")
    print("  ↳ run cleanup: python testbed/cleanup_form_phase_d_seed_state.py")


if __name__ == "__main__":
    asyncio.run(main())
