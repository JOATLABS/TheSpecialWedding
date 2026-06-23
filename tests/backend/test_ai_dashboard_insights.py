import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-this-is-long-enough-for-validation"
)
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

import app.api.ai as ai_api  # noqa: E402


def _current_user():
    return SimpleNamespace(user_data={"_id": "user-1"})


@pytest.mark.asyncio
async def test_dashboard_insights_cache_only_returns_cached_without_generation(
    monkeypatch,
):
    generate = AsyncMock()
    monkeypatch.setattr(ai_api, "check_wedding_access", AsyncMock(return_value=True))
    monkeypatch.setattr(
        ai_api,
        "get_wedding_by_id",
        AsyncMock(return_value={"_id": "wedding-1", "couple_names": "Ava and Noah"}),
    )
    monkeypatch.setattr(
        ai_api.ai_service,
        "_resolve_subscription_plan",
        AsyncMock(return_value="active"),
    )
    monkeypatch.setattr(ai_api.ai_service, "generate", generate)
    monkeypatch.setattr(
        ai_api.ai_cache_service,
        "get_latest_cached_response",
        AsyncMock(
            return_value={
                "response": {
                    "insights": [
                        {
                            "title": "RSVP follow-up",
                            "description": "12 guests are pending.",
                            "priority": "medium",
                        }
                    ]
                }
            }
        ),
    )

    result = await ai_api.get_dashboard_insights(
        "wedding-1",
        cache_only=True,
        current_user=_current_user(),
    )

    assert result["cached"] is True
    assert result["cache_only"] is True
    assert result["credits_used"] == 0
    assert result["insights"][0]["title"] == "RSVP follow-up"
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_dashboard_insights_cache_only_does_not_generate_on_cache_miss(
    monkeypatch,
):
    generate = AsyncMock()
    monkeypatch.setattr(ai_api, "check_wedding_access", AsyncMock(return_value=True))
    monkeypatch.setattr(
        ai_api,
        "get_wedding_by_id",
        AsyncMock(return_value={"_id": "wedding-1", "couple_names": "Ava and Noah"}),
    )
    monkeypatch.setattr(
        ai_api.ai_service,
        "_resolve_subscription_plan",
        AsyncMock(return_value="active"),
    )
    monkeypatch.setattr(ai_api.ai_service, "generate", generate)
    monkeypatch.setattr(
        ai_api.ai_cache_service,
        "get_latest_cached_response",
        AsyncMock(return_value=None),
    )

    result = await ai_api.get_dashboard_insights(
        "wedding-1",
        cache_only=True,
        current_user=_current_user(),
    )

    assert result == {
        "insights": [],
        "wedding_id": "wedding-1",
        "cached": False,
        "credits_used": 0,
        "cache_only": True,
        "requires_generation": True,
    }
    generate.assert_not_awaited()
