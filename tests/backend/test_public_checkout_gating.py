import asyncio
import os
import sys
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.api.stripe_payment as stripe_payment_module


class FakeUsersCollection:
    def __init__(self, document):
        self.document = document

    async def find_one(self, query):
        if self.document and query.get("email") == self.document.get("email"):
            return dict(self.document)
        return None


def _request(email: str) -> stripe_payment_module.PublicCreateCheckoutSessionRequest:
    return stripe_payment_module.PublicCreateCheckoutSessionRequest(
        email=email,
        plan_id="plan_boutique",
        billing_interval="monthly",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        trial_days=0,
    )


def test_public_checkout_rejects_active_users(monkeypatch):
    stripe_payment_module.stripe_service.users_collection = FakeUsersCollection(
        {
            "_id": "user-1",
            "email": "planner@example.com",
            "subscription_status": "active",
        }
    )
    create_checkout = AsyncMock()
    monkeypatch.setattr(stripe_payment_module.stripe_service, "create_checkout_session", create_checkout)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            stripe_payment_module.create_public_checkout_session(
                _request("planner@example.com")
            )
        )

    assert exc.value.status_code == 400
    assert "Unable to create checkout session" in exc.value.detail
    create_checkout.assert_not_awaited()


@pytest.mark.parametrize("status_value", ["pending_payment", "pending_checkout"])
def test_public_checkout_allows_retryable_signup_statuses(monkeypatch, status_value):
    stripe_payment_module.stripe_service.users_collection = FakeUsersCollection(
        {
            "_id": "user-1",
            "email": "planner@example.com",
            "subscription_status": status_value,
            "registration_source": "public_signup",
            "plan_id": "plan_boutique",
        }
    )
    create_checkout = AsyncMock(return_value={"url": "https://checkout.stripe.test/session"})
    monkeypatch.setattr(stripe_payment_module.stripe_service, "create_checkout_session", create_checkout)
    stripe_payment_module.stripe_service.users_collection.update_one = AsyncMock(
        side_effect=AssertionError("public checkout should not mutate the user document before payment succeeds")
    )

    result = asyncio.run(
        stripe_payment_module.create_public_checkout_session(
            _request("planner@example.com")
        )
    )

    assert result["status"] == "success"
    assert result["checkout_session"]["url"] == "https://checkout.stripe.test/session"
    create_checkout.assert_awaited_once()


def test_public_checkout_rejects_expired_users(monkeypatch):
    stripe_payment_module.stripe_service.users_collection = FakeUsersCollection(
        {
            "_id": "user-1",
            "email": "planner@example.com",
            "subscription_status": "expired",
            "registration_source": "public_signup",
        }
    )
    create_checkout = AsyncMock()
    monkeypatch.setattr(stripe_payment_module.stripe_service, "create_checkout_session", create_checkout)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            stripe_payment_module.create_public_checkout_session(
                _request("planner@example.com")
            )
        )

    assert exc.value.status_code == 400
    assert "Unable to create checkout session" in exc.value.detail
    create_checkout.assert_not_awaited()
