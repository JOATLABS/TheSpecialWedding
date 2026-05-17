#!/usr/bin/env python3
"""
E2E #5/6 — 401 From BLG Flips The Sync Kill Switch
==================================================

Mockup contract: per the BLG error taxonomy
(https://www.babylovegrowth.ai/docs/integrations/api), a 401 means the
API key is bad/revoked. We treat this as a TERMINAL failure: no retry,
write the run as failed, and flip BABYLOVEGROWTH_SYNC_ENABLED=false in
the in-process settings so cron stops re-firing on the bad key until
manual intervention.

This driver exercises the full path: HTTP endpoint → sync service →
BabyLoveGrowthClient receives 401 → BabyLoveGrowthAuthError →
run_full_sync catches it → settings flag flipped + run finalized as failed.

Strategy
--------
SEED:
    - Cleanup state.
    - Fixture client raises BabyLoveGrowthAuthError on every
      list_articles call.
    - Settings start with sync_enabled=True. After the run, we verify
      the flag is now False.

VERIFY:

    [CHECKPOINT 1/4] sync_enabled is True at start
    [CHECKPOINT 2/4] POST returns accepted; sync runs
    [CHECKPOINT 3/4] Status reports status="failed", error_count=1,
                     errors[0].stage="auth"
    [CHECKPOINT 4/4] settings.babylovegrowth_sync_enabled is now False
                     — cron will return {"status": "skipped",
                     "reason": "sync_disabled"} on next trigger

Pair: cleanup_blg_sync_state.py
NOTE: the kill switch flip is IN-MEMORY only. The .env file is
untouched. After running this driver, manually restore
sync_enabled in your live env / re-run with `BABYLOVEGROWTH_SYNC_ENABLED=true`
to resume normal operation.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import httpx  # noqa: E402

from testbed._blg_sync_common import (  # noqa: E402
    banner,
    build_blog_test_app,
    checkpoint_pause,
    install_fixture_blg_client,
    install_test_settings,
    make_fixture_client_class,
    poll_sync_status,
    purge_blg_test_articles,
    purge_blg_test_r2_fixtures,
    reset_blg_sync_runs,
)


async def main() -> None:
    banner("verify_blg_e2e_kill_switch (E2E #5/6)")

    print("  SEED")
    await purge_blg_test_articles()
    await reset_blg_sync_runs()
    purge_blg_test_r2_fixtures()

    from app.services.babylovegrowth_sync_service import (
        BabyLoveGrowthAuthError,
    )

    FixtureClient = make_fixture_client_class(
        summaries_by_offset={0: []},  # Never reached — list raises first
        list_error=BabyLoveGrowthAuthError,
    )
    restore_client = install_fixture_blg_client(FixtureClient)
    restore_settings = install_test_settings()

    try:
        from app.core.settings import settings as _settings

        print()
        print("  VERIFY")

        # Checkpoint 1: precondition.
        assert _settings.babylovegrowth_sync_enabled is True, (
            f"Test setup wrong: sync_enabled should start True, got "
            f"{_settings.babylovegrowth_sync_enabled}"
        )
        checkpoint_pause(
            "1/4 — sync_enabled is True at start",
            [f"sync_enabled: {_settings.babylovegrowth_sync_enabled}"],
        )

        app, _ = build_blog_test_app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post("/admin/blog/sync-babylovegrowth")
            assert response.status_code == 200, response.text
            checkpoint_pause(
                "2/4 — POST accepted; auth-failing run starts",
                [f"response: {response.json()}"],
            )

            state = await poll_sync_status(client)
            assert state["status"] == "failed", (
                f"Run with 401 should be failed, got status={state['status']}"
            )
            assert state["error_count"] >= 1, (
                f"Expected at least one error from 401, got error_count={state['error_count']}"
            )
            errors = state.get("errors") or []
            assert errors and errors[0].get("stage") == "auth", (
                f"Expected auth-stage error, got: {errors}"
            )
            checkpoint_pause(
                "3/4 — Run finalized as failed with auth-stage error",
                [
                    f"status: {state['status']}",
                    f"error_count: {state['error_count']}",
                    f"errors[0].stage: {errors[0].get('stage')}",
                    f"errors[0].message: {errors[0].get('message')}",
                ],
            )

            # Checkpoint 4: kill switch flipped in-process.
            assert _settings.babylovegrowth_sync_enabled is False, (
                "Kill switch was NOT flipped after 401. sync_enabled is still True — "
                "cron will keep retrying a bad key."
            )
            # Confirm the next sync attempt is short-circuited.
            await client.post("/admin/blog/sync-babylovegrowth")
            # The endpoint always returns 202-accepted, but the background
            # task will return {"status": "skipped", "reason":
            # "sync_disabled"}. Poll status — it should NOT transition
            # back to "running".
            await asyncio.sleep(0.5)
            state2 = await client.get("/admin/blog/sync-babylovegrowth/status")
            state2_doc = state2.json()
            # State doc reflects the previous failed run; the new run
            # was skipped before mutating the doc.
            assert state2_doc.get("status") in ("failed", "idle"), (
                f"After kill-switch flip, follow-up triggers should be no-ops; "
                f"unexpected status={state2_doc.get('status')}"
            )
            checkpoint_pause(
                "4/4 — sync_enabled flipped False; subsequent triggers are no-ops",
                [
                    f"sync_enabled: {_settings.babylovegrowth_sync_enabled}",
                    f"state doc status after re-trigger: {state2_doc.get('status')}",
                ],
            )

        print()
        print("  ✅ E2E kill switch verified.")
        print()
        print("  ⚠  In-memory settings flipped. To resume real syncs, restart")
        print("     the process OR re-export BABYLOVEGROWTH_SYNC_ENABLED=true.")
    finally:
        restore_settings()
        restore_client()


if __name__ == "__main__":
    asyncio.run(main())
