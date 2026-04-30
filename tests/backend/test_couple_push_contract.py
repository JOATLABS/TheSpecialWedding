from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api import couple_portal as couple_portal_api


class _FakePushSubscriptionsCollection:
    def __init__(self, count: int) -> None:
        self.count = count
        self.count_queries: list[dict] = []

    async def count_documents(self, query: dict) -> int:
        self.count_queries.append(query)
        return self.count


@pytest.mark.asyncio
async def test_couple_push_status_returns_disabled_when_vapid_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        couple_portal_api,
        "web_push_service",
        SimpleNamespace(enabled=False),
    )

    result = await couple_portal_api.get_couple_push_status(
        couple={"_id": "couple-1", "email": "Couple@Example.com"}
    )

    assert result == {
        "enabled": False,
        "subscribed": False,
        "reason": "Push not configured",
    }


@pytest.mark.asyncio
async def test_couple_push_status_returns_public_key_and_canonical_identity_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    push_subscriptions = _FakePushSubscriptionsCollection(count=1)
    monkeypatch.setattr(
        couple_portal_api,
        "mongo",
        SimpleNamespace(db={"push_subscriptions": push_subscriptions}),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "web_push_service",
        SimpleNamespace(
            enabled=True,
            get_public_key=lambda: "public-vapid-key",
        ),
    )

    result = await couple_portal_api.get_couple_push_status(
        couple={"_id": "couple-1", "email": "Couple@Example.com"}
    )

    assert result == {
        "enabled": True,
        "subscribed": True,
        "subscription_count": 1,
        "vapid_public_key": "public-vapid-key",
    }
    assert push_subscriptions.count_queries == [
        {"user_id": {"$in": ["couple::couple-1", "couple@example.com"]}}
    ]
