import os
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

from app.middleware.audit_logging import (  # noqa: E402
    _extract_route_template,
    _normalize_route_template,
)


def test_normalize_route_template_groups_known_prefixed_ids():
    assert (
        _normalize_route_template(
            "/admin/ai/weddings/wedding_17821abc123/generate-timeline"
        )
        == "/admin/ai/weddings/{id}/generate-timeline"
    )
    assert (
        _normalize_route_template("/stripe/checkout-session/cs_live_123abc")
        == "/stripe/checkout-session/{id}"
    )


def test_normalize_route_template_preserves_stable_slugs():
    assert _normalize_route_template("/gallery/verified") == "/gallery/verified"


def test_extract_route_template_prefers_matched_fastapi_route():
    request = SimpleNamespace(
        scope={
            "route": SimpleNamespace(
                path="/admin/ai/weddings/{wedding_id}/generate-timeline"
            )
        }
    )

    assert (
        _extract_route_template(request)
        == "/admin/ai/weddings/{wedding_id}/generate-timeline"
    )


def test_extract_route_template_includes_mount_root_path():
    request = SimpleNamespace(
        scope={
            "root_path": "/api",
            "route": SimpleNamespace(path="/admin/gallery/upload"),
        }
    )

    assert _extract_route_template(request) == "/api/admin/gallery/upload"
