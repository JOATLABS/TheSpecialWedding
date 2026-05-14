from __future__ import annotations

import importlib
import sys
import types

import pytest


def _import_driver(monkeypatch: pytest.MonkeyPatch):
    harness_stub = types.ModuleType("testbed.harness")
    harness_stub.Harness = object
    harness_stub.PM_TOKEN_GOOD = "pm_card_visa"
    monkeypatch.setitem(sys.modules, "testbed.harness", harness_stub)
    sys.modules.pop("testbed.verify_performance_baseline", None)
    return importlib.import_module("testbed.verify_performance_baseline")


def test_cost_model_rejects_bundled_example_file(monkeypatch: pytest.MonkeyPatch):
    driver = _import_driver(monkeypatch)
    monkeypatch.setattr(
        driver,
        "COST_MODEL_PATH",
        driver.TESTBED_DIR / "performance_cost_model.example.json",
    )

    with pytest.raises(
        ValueError, match="PERF_BASELINE_COST_MODEL.*environment-specific"
    ):
        driver._load_cost_model()


def test_cost_model_loads_environment_specific_monthly_cost(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    driver = _import_driver(monkeypatch)
    cost_model_path = tmp_path / "staging-cost-model.json"
    cost_model_path.write_text(
        """
        {
          "environment": "staging",
          "monthly_infrastructure_usd": 123.45,
          "included_costs": ["coolify", "mongo", "redis"],
          "excluded_variable_costs": ["sms", "email", "ai"]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(driver, "COST_MODEL_PATH", cost_model_path)

    model = driver._load_cost_model()

    assert model["environment"] == "staging"
    assert model["monthly_infrastructure_usd"] == 123.45
    assert model["included_costs"] == ["coolify", "mongo", "redis"]
    assert model["excluded_variable_costs"] == ["sms", "email", "ai"]
    assert model["source_path"] == str(cost_model_path)


def test_efficiency_emits_requests_and_sessions_per_dollar(
    monkeypatch: pytest.MonkeyPatch,
):
    driver = _import_driver(monkeypatch)
    results = [
        {"elapsed_ms": 1000, "status_code": 200},
        {"elapsed_ms": 1000, "status_code": 200},
        {"elapsed_ms": 1000, "status_code": 200},
    ]

    efficiency = driver._efficiency(
        results,
        {"monthly_infrastructure_usd": 40},
    )

    assert efficiency["successful_requests_per_second"] == 1.0
    assert efficiency["successful_requests_per_second_per_dollar"] == 0.025
    assert efficiency["dashboard_sessions_per_hour_per_dollar"] == 30.0


def test_baseline_payload_contains_durable_load_per_dollar_artifact(
    monkeypatch: pytest.MonkeyPatch,
):
    driver = _import_driver(monkeypatch)
    cost_model = {
        "environment": "staging",
        "monthly_infrastructure_usd": 80,
        "source_path": "/tmp/staging-cost-model.json",
    }
    results = [
        {
            "label": "profile",
            "path": "/admin/profile",
            "status_code": 200,
            "elapsed_ms": 1000,
            "ok": True,
            "optional": False,
        }
    ]

    payload = driver._build_baseline_payload(
        cost_model=cost_model,
        results=results,
        wedding_id="wedding_123",
        generated_at="2026-05-13T00:00:00Z",
    )

    assert payload["environment"] == "staging"
    assert payload["cost_model"]["source_path"] == "/tmp/staging-cost-model.json"
    assert payload["artifact_version"] >= 2
    assert payload["efficiency"]["successful_requests_per_second_per_dollar"] == 0.013
    assert payload["efficiency"]["dashboard_sessions_per_hour_per_dollar"] == 45.0


def test_performance_docs_include_exact_rerun_flow():
    docs = (
        __import__("pathlib")
        .Path("docs/performance/performance-baseline-and-efficiency.md")
        .read_text(encoding="utf-8")
    )

    required_snippets = [
        "PERF_BASELINE_COST_MODEL",
        "environment-specific monthly infrastructure cost model",
        "python testbed/testbed.py up --with-frontend",
        "python testbed/verify_performance_baseline.py",
        "docs/performance/baselines/",
        "python testbed/cleanup_performance_baseline_state.py",
        "python testbed/testbed.py down",
    ]

    for snippet in required_snippets:
        assert snippet in docs
