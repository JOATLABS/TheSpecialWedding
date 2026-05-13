#!/usr/bin/env python3
"""
One-planner / one-wedding performance baseline - live testbed verifier.

This driver creates the smallest realistic paid-planner fixture, measures the
blocking backend endpoints behind the planner dashboard, and writes a baseline
JSON artifact under docs/performance/baselines/.

It belongs in testbed/ because it touches the live backend, real Mongo, and the
Stripe test-mode account configured in .env. It is intentionally not a pytest
unit test.

Usage:
    python testbed/testbed.py up --with-frontend
    export PERF_BASELINE_COST_MODEL=/path/to/environment-cost-model.json
    python testbed/verify_performance_baseline.py
    python testbed/cleanup_performance_baseline_state.py
"""

from __future__ import annotations

import json
import os
import subprocess
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from pathlib import Path
from time import perf_counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness, PM_TOKEN_GOOD  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent
TESTBED_DIR = Path(__file__).resolve().parent
BASELINE_DIR = REPO_ROOT / "docs" / "performance" / "baselines"

DRIVER_NAME = "verify_performance_baseline"
PLANNER_EMAIL = "test_planner+perfbaseline@thespecialwedding.io"
PLANNER_PASSWORD = "PerfBaseline2026!"  # pragma: allowlist secret
PLAN_ID = os.getenv("PERF_BASELINE_PLAN_ID", "plan_signature")

WEDDING_COUPLE = "Performance Baseline Couple"
WEDDING_VENUE = "Performance Baseline Venue"
REQUEST_REPEATS = int(os.getenv("PERF_BASELINE_REPEATS", "3"))
INCLUDE_AI_INSIGHTS = os.getenv("PERF_BASELINE_INCLUDE_AI", "0") in {
    "1",
    "true",
    "True",
}
COST_MODEL_PATH = Path(
    os.getenv(
        "PERF_BASELINE_COST_MODEL",
        str(TESTBED_DIR / "performance_cost_model.example.json"),
    )
)
EXAMPLE_COST_MODEL_PATH = TESTBED_DIR / "performance_cost_model.example.json"
ARTIFACT_VERSION = 2


@dataclass(frozen=True)
class TimedEndpoint:
    label: str
    path: str
    optional: bool = False


def _utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _percentile_seconds(values_ms: list[float], percentile: float) -> float:
    if not values_ms:
        return 0.0
    sorted_values = sorted(values_ms)
    index = max(ceil(len(sorted_values) * percentile) - 1, 0)
    return round(sorted_values[index] / 1000, 3)


def _load_cost_model() -> dict[str, Any]:
    if COST_MODEL_PATH.resolve() == EXAMPLE_COST_MODEL_PATH.resolve():
        raise ValueError(
            "PERF_BASELINE_COST_MODEL must point to an environment-specific "
            "monthly infrastructure cost model. Copy "
            "testbed/performance_cost_model.example.json outside the example "
            "path, fill in real costs, then export PERF_BASELINE_COST_MODEL."
        )

    if not COST_MODEL_PATH.exists():
        raise ValueError(f"PERF_BASELINE_COST_MODEL file not found: {COST_MODEL_PATH}")

    model = json.loads(COST_MODEL_PATH.read_text())
    monthly_cost = float(model.get("monthly_infrastructure_usd") or 0)
    if monthly_cost <= 0:
        raise ValueError(
            "PERF_BASELINE_COST_MODEL monthly_infrastructure_usd must be greater than 0"
        )

    model["monthly_infrastructure_usd"] = monthly_cost
    model["source_path"] = str(COST_MODEL_PATH)
    model.setdefault("included_costs", [])
    model.setdefault(
        "excluded_variable_costs", ["sms", "email", "ai", "stripe_processing"]
    )
    return model


def _git_commit_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _timed_get(
    h: Harness,
    *,
    token: str,
    endpoint: TimedEndpoint,
) -> dict[str, Any]:
    started = perf_counter()
    response = h.api_get(endpoint.path, token=token, timeout=90)
    elapsed_ms = (perf_counter() - started) * 1000
    ok = response.status_code < 400 or endpoint.optional

    result = {
        "label": endpoint.label,
        "path": endpoint.path,
        "status_code": response.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "elapsed_seconds": round(elapsed_ms / 1000, 3),
        "ok": ok,
        "optional": endpoint.optional,
    }
    if not ok:
        result["body_preview"] = response.text[:300]
    return result


def _summarize(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_path: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_path.setdefault(result["path"], []).append(result)

    summaries: list[dict[str, Any]] = []
    for path, path_results in sorted(by_path.items()):
        values = [float(item["elapsed_ms"]) for item in path_results]
        failures = [
            item
            for item in path_results
            if item["status_code"] >= 400 and not item["optional"]
        ]
        summaries.append(
            {
                "path": path,
                "request_count": len(path_results),
                "failure_count": len(failures),
                "avg_seconds": round(statistics.mean(values) / 1000, 3),
                "p50_seconds": _percentile_seconds(values, 0.50),
                "p95_seconds": _percentile_seconds(values, 0.95),
                "max_seconds": round(max(values) / 1000, 3),
                "statuses": sorted({item["status_code"] for item in path_results}),
            }
        )
    return summaries


def _efficiency(
    results: list[dict[str, Any]], cost_model: dict[str, Any]
) -> dict[str, Any]:
    total_seconds = sum(float(item["elapsed_ms"]) for item in results) / 1000
    successful = len([item for item in results if item["status_code"] < 400])
    successful_rps = successful / total_seconds if total_seconds > 0 else 0.0
    monthly_cost = float(cost_model.get("monthly_infrastructure_usd") or 0)
    per_dollar = successful_rps / monthly_cost if monthly_cost > 0 else None
    dashboard_sessions_per_hour_per_dollar = (
        (3600 / total_seconds) / monthly_cost
        if monthly_cost > 0 and total_seconds > 0
        else None
    )
    return {
        "successful_requests": successful,
        "measured_seconds": round(total_seconds, 3),
        "successful_requests_per_second": round(successful_rps, 3),
        "monthly_infrastructure_usd": monthly_cost,
        "successful_requests_per_second_per_dollar": (
            round(per_dollar, 3) if per_dollar is not None else None
        ),
        "dashboard_sessions_per_hour_per_dollar": (
            round(dashboard_sessions_per_hour_per_dollar, 3)
            if dashboard_sessions_per_hour_per_dollar is not None
            else None
        ),
    }


def _build_baseline_payload(
    *,
    cost_model: dict[str, Any],
    results: list[dict[str, Any]],
    wedding_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "artifact_version": ARTIFACT_VERSION,
        "generated_at": generated_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "driver": DRIVER_NAME,
        "commit_sha": _git_commit_sha(),
        "environment": cost_model.get("environment", "unconfigured"),
        "deployment": {
            "mode": os.getenv("PERF_BASELINE_DEPLOYMENT_MODE", "testbed"),
            "frontend_url": os.getenv("FRONTEND_URL"),
            "api_base_url": os.getenv("INTERNAL_API_BASE_URL")
            or os.getenv("NEXT_PUBLIC_API_BASE_URL"),
            "backend_worker_count": os.getenv("WEB_CONCURRENCY")
            or os.getenv("UVICORN_WORKERS"),
            "redis_enabled": bool(os.getenv("REDIS_URL")),
        },
        "fixture": {
            "planner_email": PLANNER_EMAIL,
            "planner_count": 1,
            "wedding_count": 1,
            "wedding_id": wedding_id,
            "guest_count": 50,
        },
        "cost_model": cost_model,
        "endpoint_summaries": _summarize(results),
        "raw_results": results,
        "efficiency": _efficiency(results, cost_model),
        "recommendation": (
            "Use this artifact as the baseline before changing planner "
            "dashboard loading behavior. Optimize the slowest blocking "
            "endpoint first, then rerun this same testbed driver with the "
            "same PERF_BASELINE_COST_MODEL."
        ),
    }


def _seed_one_planner_one_wedding(h: Harness, admin_token: str) -> tuple[str, str]:
    h.phase("SEED", "create isolated paid planner and one wedding")
    h.delete_user_chain(PLANNER_EMAIL)
    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
        first_name="Performance",
        last_name="Baseline",
        company_name="Performance Baseline QA",
        pm_token=PM_TOKEN_GOOD,
    )
    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)
    wedding_date = (datetime.now(timezone.utc) + timedelta(days=180)).date().isoformat()
    wedding_id = h.create_wedding(
        planner_token=planner_token,
        couple_names=WEDDING_COUPLE,
        date_iso=wedding_date,
        guest_count=50,
        venue=WEDDING_VENUE,
    )
    return planner_token, wedding_id


def _endpoint_plan(wedding_id: str) -> list[TimedEndpoint]:
    endpoints = [
        TimedEndpoint("profile bootstrap", "/admin/profile"),
        TimedEndpoint("planner dashboard metrics", "/admin/planner/metrics"),
        TimedEndpoint("engagement signals", "/admin/engagement-signals"),
    ]
    if INCLUDE_AI_INSIGHTS:
        endpoints.append(
            TimedEndpoint(
                "AI dashboard insights",
                f"/admin/ai/weddings/{wedding_id}/insights",
                optional=True,
            )
        )
    return endpoints


def main() -> int:
    cost_model = _load_cost_model()
    h = Harness(driver_name=DRIVER_NAME)
    h.preflight()
    admin_token = h.get_admin_token()
    planner_token, wedding_id = _seed_one_planner_one_wedding(h, admin_token)

    h.phase(
        "MEASURE",
        f"repeat dashboard backend endpoints {REQUEST_REPEATS} time(s)",
    )
    endpoints = _endpoint_plan(wedding_id)
    results: list[dict[str, Any]] = []
    for run_number in range(1, REQUEST_REPEATS + 1):
        h.log.info(f"Run {run_number}/{REQUEST_REPEATS}")
        for endpoint in endpoints:
            result = _timed_get(h, token=planner_token, endpoint=endpoint)
            results.append(result)
            status = result["status_code"]
            seconds = result["elapsed_seconds"]
            marker = "OK" if result["ok"] else "FAIL"
            h.log.info(f"  {marker} {endpoint.label}: {status} in {seconds}s")

    blocking_failures = [item for item in results if not item["ok"]]
    if blocking_failures:
        h.log.error("Blocking endpoint failures:")
        for failure in blocking_failures:
            h.log.error(
                f"  {failure['path']} -> {failure['status_code']} "
                f"{failure.get('body_preview', '')}"
            )
        return 1

    payload = _build_baseline_payload(
        cost_model=cost_model,
        results=results,
        wedding_id=wedding_id,
    )

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    output = BASELINE_DIR / f"{_utc_slug()}-one-planner-one-wedding.json"
    output.write_text(json.dumps(payload, indent=2) + "\n")

    h.log.info("")
    h.log.info(f"Baseline written: {output}")
    h.log.info(
        "Efficiency: "
        f"{payload['efficiency']['successful_requests_per_second']} successful rps, "
        f"{payload['efficiency']['successful_requests_per_second_per_dollar']} "
        "successful rps per dollar"
    )
    h.checkpoint(
        "PERFORMANCE_BASELINE_RECORDED",
        [
            f"Baseline JSON exists at {output}",
            "Slowest endpoint in endpoint_summaries is the first optimization target.",
            "Run cleanup_performance_baseline_state.py when finished inspecting.",
        ],
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger(DRIVER_NAME).error(
            f"Performance baseline aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
