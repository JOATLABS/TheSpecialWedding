import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-this-is-long-enough-for-validation"
)
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")

from app.api.admin_platform_metrics import (  # noqa: E402
    _generate_troubleshooting_hints,
    _is_auth_or_billing_rejection_status,
    _is_operational_error_status,
    _merge_endpoint_performance_buckets,
)


def test_generate_troubleshooting_hints_handles_none_values_safely():
    hints = _generate_troubleshooting_hints(
        {
            "exception_type": None,
            "endpoint": None,
            "stack_trace": None,
            "status_code": None,
        }
    )

    assert isinstance(hints, list)
    assert len(hints) >= 1
    assert all(isinstance(item, str) and item for item in hints)


def test_generate_troubleshooting_hints_includes_endpoint_specific_guidance():
    hints = _generate_troubleshooting_hints(
        {
            "exception_type": "ValidationError",
            "endpoint": "/auth/login",
            "stack_trace": "trace",
            "status_code": 401,
        }
    )

    assert any("authentication token" in hint.lower() for hint in hints)
    assert any("authentication service configuration" in hint.lower() for hint in hints)


def test_operational_error_rate_excludes_auth_and_billing_rejections():
    for status_code in (401, 402, 403):
        assert _is_auth_or_billing_rejection_status(status_code) is True
        assert _is_operational_error_status(status_code) is False

    for status_code in (400, 404, 422, 429, 500, "503"):
        assert _is_operational_error_status(status_code) is True

    assert _is_operational_error_status(None) is False
    assert _is_operational_error_status("not-a-status") is False


def test_merge_endpoint_performance_buckets_normalizes_legacy_route_keys():
    merged = _merge_endpoint_performance_buckets(
        [
            {
                "_id": "/admin/ai/weddings/wedding_17821abc/generate-message",
                "response_times": [100, 200],
                "response_statuses": [200, 500],
            },
            {
                "_id": "/admin/ai/weddings/wedding_999xyz/generate-message",
                "response_times": [300],
                "response_statuses": [401],
            },
            {
                "_id": "/stripe/checkout-session/cs_live_123",
                "response_times": [50],
                "response_statuses": [200],
            },
        ]
    )

    by_endpoint = {entry["_id"]: entry for entry in merged}
    ai_bucket = by_endpoint["/admin/ai/weddings/{id}/generate-message"]
    assert ai_bucket["total_requests"] == 3
    assert ai_bucket["avg_response_time_ms"] == 200
    assert ai_bucket["response_statuses"] == [200, 500, 401]

    assert by_endpoint["/stripe/checkout-session/{id}"]["total_requests"] == 1
