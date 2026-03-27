from __future__ import annotations

from typing import Any, Dict, List


def build_effective_payment_schedule(package_snapshot: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    """Return the schedule couples should see and contracts should execute.

    An empty schedule does not mean "no payment" for a paid package. It means
    the planner did not define installments, so the full amount is due on
    signing as a single charge.
    """
    package_snapshot = package_snapshot or {}
    schedule = list(package_snapshot.get("payment_schedule") or [])
    if schedule:
        return schedule

    total_amount = float(package_snapshot.get("total_amount", 0) or 0)
    if total_amount <= 0:
        return []

    return [{
        "name": "Full Payment",
        "trigger": "on_signing",
        "amount": total_amount,
    }]
