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

from app.api.admin_platform_metrics import _generate_troubleshooting_hints  # noqa: E402


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
