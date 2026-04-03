from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import behavioral_analytics as analytics_api
from app.dependencies.auth_extended import ExtendedAuthUser
from app.services.behavioral_analytics_service import BehavioralAnalyticsService
import app.services.behavioral_analytics_service as behavioral_analytics_service_module


class FakeCache:
    def __init__(self):
        self.store = {}
        self.set_calls = []

    async def get(self, key, default=None):
        return self.store.get(key, default)

    async def set(self, key, value, expire=None):
        self.store[key] = value
        self.set_calls.append((key, expire))
        return True


@pytest.mark.asyncio
async def test_engagement_signals_require_view_analytics_permission():
    user = ExtendedAuthUser("team@example.com", "team_member", {})
    user.team_permissions = {"view_analytics": False}

    with pytest.raises(HTTPException) as exc_info:
        await analytics_api.get_engagement_signals(current_user=user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_engagement_signals_scope_team_member_to_owner_and_assigned_weddings(monkeypatch):
    user = ExtendedAuthUser("team@example.com", "team_member", {})
    user.team_permissions = {"view_analytics": True}
    user.team_owner_email = "owner@example.com"
    user.team_wedding_access = "assigned"
    user.team_assigned_wedding_ids = ["507f1f77bcf86cd799439011"]

    captured: dict[str, object] = {}

    async def fake_get_planner_engagement_signals(*, planner_email=None, accessible_wedding_ids=None):
        captured["planner_email"] = planner_email
        captured["accessible_wedding_ids"] = accessible_wedding_ids
        return []

    monkeypatch.setattr(
        analytics_api.analytics_service,
        "get_planner_engagement_signals",
        fake_get_planner_engagement_signals,
    )

    result = await analytics_api.get_engagement_signals(current_user=user)

    assert result == {"signals": [], "count": 0}
    assert captured == {
        "planner_email": "owner@example.com",
        "accessible_wedding_ids": ["507f1f77bcf86cd799439011"],
    }


@pytest.mark.asyncio
async def test_non_responders_require_wedding_access(monkeypatch):
    user = ExtendedAuthUser("planner@example.com", "wedding_planner", {})

    async def deny_access(_user, _wedding_id):
        return False

    monkeypatch.setattr(analytics_api, "check_wedding_access", deny_access)

    with pytest.raises(HTTPException) as exc_info:
        await analytics_api.get_non_responders(
            wedding_id="507f1f77bcf86cd799439011",
            current_user=user,
        )

    assert exc_info.value.status_code == 403


def test_retention_month_math_preserves_calendar_boundaries():
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)

    assert BehavioralAnalyticsService._add_months(now, 0) == datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
    assert BehavioralAnalyticsService._add_months(now, -1) == datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    assert BehavioralAnalyticsService._add_months(now, -2) == datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    assert BehavioralAnalyticsService._add_months(now, -3) == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


def test_trial_conversion_queries_use_trial_end_dates_instead_of_state_history():
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end = datetime(2026, 3, 31, 23, 59, tzinfo=timezone.utc)

    conversion_query, total_query = BehavioralAnalyticsService._trial_conversion_queries(start, end)

    assert "state_history" not in conversion_query
    assert conversion_query["status"] == "active"
    assert conversion_query["trial_end_date"] == {"$gte": start, "$lte": end}
    assert total_query == {"trial_end_date": {"$gte": start, "$lte": end}}


@pytest.mark.asyncio
async def test_compile_behavioral_metrics_caches_payload(monkeypatch):
    service = BehavioralAnalyticsService(SimpleNamespace())
    fake_cache = FakeCache()
    monkeypatch.setattr(behavioral_analytics_service_module, "cache", fake_cache)

    call_counts = {
        "wau": 0,
        "activation": 0,
        "retention": 0,
        "engagement": 0,
        "mrr": 0,
        "wow": 0,
    }

    async def fake_wau(_now):
        call_counts["wau"] += 1
        return {"current": 1, "previous_week": 0, "change": 1, "change_percent": 0, "mau": 1, "stickiness_ratio": 100}

    async def fake_activation(_now):
        call_counts["activation"] += 1
        return {"period": "last_30_days", "steps": [], "conversion_rate": 0, "signups_90d": 0}

    async def fake_retention(_now):
        call_counts["retention"] += 1
        return {"cohorts": []}

    async def fake_engagement(_now):
        call_counts["engagement"] += 1
        return {"north_star_metric": 0, "rsvp_velocity": {"current_7d": 0, "previous_7d": 0, "change": 0, "trend": "flat"}, "platform_response_rate": 0, "active_engaged_weddings": 0}

    async def fake_mrr(_now):
        call_counts["mrr"] += 1
        return {"current_mrr": 0, "new_mrr": 0, "churned_mrr": 0, "net_change": 0, "net_change_percent": 0, "trial_conversions": 0, "trial_conversion_rate": 0}

    async def fake_wow(_now, _period_days):
        call_counts["wow"] += 1
        return {
            "new_users": {"current": 0, "previous": 0, "change": 0, "change_percent": 0, "trend": "flat"},
            "new_weddings": {"current": 0, "previous": 0, "change": 0, "change_percent": 0, "trend": "flat"},
            "new_rsvps": {"current": 0, "previous": 0, "change": 0, "change_percent": 0, "trend": "flat"},
            "active_users": {"current": 0, "previous": 0, "change": 0, "change_percent": 0, "trend": "flat"},
        }

    monkeypatch.setattr(service, "_compute_wau", fake_wau)
    monkeypatch.setattr(service, "_compute_activation_funnel", fake_activation)
    monkeypatch.setattr(service, "_compute_retention_cohorts", fake_retention)
    monkeypatch.setattr(service, "_compute_engagement_signals", fake_engagement)
    monkeypatch.setattr(service, "_compute_mrr_movement", fake_mrr)
    monkeypatch.setattr(service, "_compute_wow_changes", fake_wow)

    first = await service.compile_behavioral_metrics("30d")
    second = await service.compile_behavioral_metrics("30d")

    assert first == second
    assert call_counts == {
        "wau": 1,
        "activation": 1,
        "retention": 1,
        "engagement": 1,
        "mrr": 1,
        "wow": 1,
    }
    assert fake_cache.set_calls


@pytest.mark.asyncio
async def test_planner_engagement_signals_uses_sorted_scope_cache_key(monkeypatch):
    service = BehavioralAnalyticsService(SimpleNamespace())
    fake_cache = FakeCache()
    monkeypatch.setattr(behavioral_analytics_service_module, "cache", fake_cache)

    key_a = service._planner_engagement_cache_key("owner@example.com", ["w2", "w1"])
    key_b = service._planner_engagement_cache_key("owner@example.com", ["w1", "w2"])
    assert key_a == key_b

    expected = [{"wedding_id": "wed_1", "needs_attention": []}]
    fake_cache.store[key_a] = expected

    result = await service.get_planner_engagement_signals(
        planner_email="owner@example.com",
        accessible_wedding_ids=["w1", "w2"],
    )

    assert result == expected
