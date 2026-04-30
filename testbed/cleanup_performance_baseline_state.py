#!/usr/bin/env python3
"""Clean up state from verify_performance_baseline.py.

Safe to re-run. Only removes the isolated plus-variant planner fixture and the
standard Mongo/Stripe chain owned by that testbed user.

Usage:
    python testbed/cleanup_performance_baseline_state.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness  # noqa: E402


PLANNER_EMAIL = "test_planner+perfbaseline@thespecialwedding.io"


def main() -> int:
    h = Harness(driver_name="cleanup_performance_baseline_state")
    h.banner("CLEANUP - Performance baseline")
    h.log.info(f"Planner fixture: {PLANNER_EMAIL}")
    h.delete_user_chain(PLANNER_EMAIL)
    h.log.info(
        "Cleanup complete. The performance baseline driver can seed fresh state."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger("cleanup_performance_baseline_state").error(
            f"Cleanup aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
