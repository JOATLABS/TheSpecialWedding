"""Hardening tests covering the small-but-critical fixes from the
post-Phase-1 audit:

- F1: phone field validation branch in FormSecurityValidator
- A4: Gemini model IDs are env-overridable via settings
- A5: zero-credit AI features are throttled per-tenant per-day
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

from app.utils.security_utils import FormSecurityValidator  # noqa: E402


# =============================================================================
# F1 — phone field validation
# =============================================================================


PHONE_FIELD = [
    {"id": "phone", "type": "phone", "required": False, "label": "Phone"}
]


@pytest.mark.parametrize(
    "raw_value,expected_present,expected_value",
    [
        # Accepted formats
        ("+15551234567", True, "+15551234567"),
        ("(555) 123-4567", True, "(555) 123-4567"),
        ("555-123-4567", True, "555-123-4567"),
        ("+44 20 7946 0958", True, "+44 20 7946 0958"),
        # Trim is preserved on the inside; sanitizer strips outer whitespace.
        ("  555-1234567  ", True, "555-1234567"),
    ],
)
def test_validate_phone_accepts_canonical_shapes(
    raw_value, expected_present, expected_value
):
    out = FormSecurityValidator.validate_form_response(
        {"phone": raw_value}, PHONE_FIELD
    )
    assert ("phone" in out) is expected_present
    if expected_present:
        assert out["phone"] == expected_value


@pytest.mark.parametrize(
    "raw_value",
    [
        # XSS / SQL injection attempt
        "<script>alert(1)</script>",
        "1' OR '1'='1",
        # Unicode-ish "phone number" attempt (letters)
        "DROP TABLE users",
        "phoenicia",
        # Way too short
        "12",
        # Way too long
        "+" + "1" * 33,
        # Empty / whitespace
        "",
        "   ",
        # Non-string types
    ],
)
def test_validate_phone_rejects_garbage(raw_value):
    out = FormSecurityValidator.validate_form_response(
        {"phone": raw_value}, PHONE_FIELD
    )
    # Rejected values are simply absent from the sanitized payload — the
    # caller's required-field check then raises 400 if the field was
    # required, otherwise the response is just stored without it.
    assert "phone" not in out


def test_validate_phone_rejects_non_string_types():
    out = FormSecurityValidator.validate_form_response(
        {"phone": 5551234567}, PHONE_FIELD
    )
    assert "phone" not in out


# =============================================================================
# A4 — Gemini model IDs sourced from settings
# =============================================================================


def test_ai_service_model_ids_resolvable_from_settings():
    """A4: importing ai_service must not pin Gemini model strings at module level."""
    from app.core.settings import settings
    from app.services import ai_service

    # Defaults are set, but they're settings-driven, not module-level constants.
    assert ai_service.MODEL_PRIMARY == (
        settings.ai_gemini_model_primary or "gemini-2.5-flash"
    )
    assert ai_service.MODEL_ECONOMY == (
        settings.ai_gemini_model_economy or "gemini-2.0-flash"
    )
    assert ai_service.LOW_CREDIT_THRESHOLD == settings.ai_low_credit_threshold


# =============================================================================
# A5 — internal-feature quota for zero-credit AI features
# =============================================================================


@pytest.mark.asyncio
async def test_internal_feature_quota_allows_calls_under_cap():
    from app.services.ai_service import AIService

    service = AIService()
    fake_log = MagicMock()
    fake_log.count_documents = AsyncMock(return_value=0)
    service.usage_log = fake_log

    allowed = await service._check_internal_feature_quota(
        feature="payment_retry_timing", tenant_id="tenant-1"
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_internal_feature_quota_blocks_calls_over_cap():
    from app.services.ai_service import AIService

    service = AIService()
    fake_log = MagicMock()
    fake_log.count_documents = AsyncMock(
        return_value=service.INTERNAL_FEATURE_DAILY_CAP
    )
    service.usage_log = fake_log

    allowed = await service._check_internal_feature_quota(
        feature="payment_retry_timing", tenant_id="tenant-1"
    )
    assert allowed is False


@pytest.mark.asyncio
async def test_internal_feature_quota_fails_open_on_telemetry_error():
    """If Mongo for ai_usage_log is broken we'd rather serve traffic than 500."""
    from app.services.ai_service import AIService

    service = AIService()
    fake_log = MagicMock()
    fake_log.count_documents = AsyncMock(side_effect=RuntimeError("mongo down"))
    service.usage_log = fake_log

    allowed = await service._check_internal_feature_quota(
        feature="payment_retry_timing", tenant_id="tenant-1"
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_internal_feature_quota_only_counts_today():
    """The 24h window resets at UTC midnight; yesterday's calls don't count."""
    from app.services.ai_service import AIService

    service = AIService()
    captured_query: Dict[str, Any] = {}

    async def fake_count(query):
        captured_query.update(query)
        return 0

    fake_log = MagicMock()
    fake_log.count_documents = fake_count
    service.usage_log = fake_log

    await service._check_internal_feature_quota(
        feature="payment_retry_timing", tenant_id="tenant-1"
    )
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    assert captured_query["created_at"] == {"$gte": today_start}
    assert captured_query["feature"] == "payment_retry_timing"
    assert captured_query["tenant_id"] == "tenant-1"
