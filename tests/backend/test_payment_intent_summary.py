import asyncio
import os
import sys
from types import SimpleNamespace

import stripe

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import HTTPException

import app.api.stripe_payment as stripe_payment_module
import app.core.database as database_module
import app.core.settings as settings_module


class AsyncCollection:
    def __init__(self, document=None):
        self.document = document
        self.inserted = None

    async def find_one(self, query):
        if not self.document:
            return None
        if query.get("public_token") == self.document.get("public_token"):
            return dict(self.document)
        return None

    async def insert_one(self, document):
        self.inserted = dict(document)
        return SimpleNamespace(inserted_id="payment-request-1")


class AsyncDatabase:
    def __init__(self, payment_request=None):
        self.collections = {
            "payment_requests": AsyncCollection(payment_request),
        }

    def __getitem__(self, name):
        return self.collections[name]


class FakeMongo:
    def __init__(self, payment_request=None):
        self.db = AsyncDatabase(payment_request)


def test_payment_intent_summary_omits_client_secret(monkeypatch):
    fake_mongo = FakeMongo(
        {
            "public_token": "public-token-123",
            "payment_intent_id": "pi_123",
        }
    )
    monkeypatch.setattr(database_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        settings_module.settings, "stripe_secret_key", "sk_test_123", raising=False
    )
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        lambda payment_intent_id: SimpleNamespace(
            id=payment_intent_id,
            client_secret="pi_secret_should_not_be_exposed",
            amount=12500,
            currency="usd",
            status="succeeded",
            description="Deposit payment",
        ),
    )

    result = asyncio.run(
        stripe_payment_module.get_payment_intent_summary("public-token-123")
    )

    assert result == {
        "id": "pi_123",
        "amount": 125.0,
        "currency": "usd",
        "status": "succeeded",
        "description": "Deposit payment",
        "public_token": "public-token-123",
    }
    assert "client_secret" not in result


def test_payment_intent_details_require_public_token(monkeypatch):
    fake_mongo = FakeMongo(
        {
            "public_token": "public-token-123",
            "payment_intent_id": "pi_123",
        }
    )
    monkeypatch.setattr(database_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        settings_module.settings, "stripe_secret_key", "sk_test_123", raising=False
    )
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        lambda payment_intent_id: SimpleNamespace(
            id=payment_intent_id,
            client_secret="pi_secret_123",
            amount=12500,
            currency="usd",
            status="requires_payment_method",
            description="Deposit payment",
        ),
    )

    result = asyncio.run(
        stripe_payment_module.get_payment_intent_details("public-token-123")
    )

    assert result == {
        "id": "pi_123",
        "client_secret": "pi_secret_123",
        "amount": 125.0,
        "currency": "usd",
        "status": "requires_payment_method",
        "description": "Deposit payment",
        "public_token": "public-token-123",
    }


def test_payment_intent_details_omit_client_secret_when_not_payable(monkeypatch):
    fake_mongo = FakeMongo(
        {
            "public_token": "public-token-123",
            "payment_intent_id": "pi_123",
        }
    )
    monkeypatch.setattr(database_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        settings_module.settings, "stripe_secret_key", "sk_test_123", raising=False
    )
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        lambda payment_intent_id: SimpleNamespace(
            id=payment_intent_id,
            client_secret="pi_secret_123",
            amount=12500,
            currency="usd",
            status="succeeded",
            description="Deposit payment",
        ),
    )

    result = asyncio.run(
        stripe_payment_module.get_payment_intent_details("public-token-123")
    )

    assert result == {
        "id": "pi_123",
        "amount": 125.0,
        "currency": "usd",
        "status": "succeeded",
        "description": "Deposit payment",
        "public_token": "public-token-123",
    }
    assert "client_secret" not in result


def test_payment_intent_summary_rejects_raw_payment_intent_id(monkeypatch):
    fake_mongo = FakeMongo(
        {
            "public_token": "public-token-123",
            "payment_intent_id": "pi_123",
        }
    )
    monkeypatch.setattr(database_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        settings_module.settings, "stripe_secret_key", "sk_test_123", raising=False
    )

    try:
        asyncio.run(stripe_payment_module.get_payment_intent_summary("pi_123"))
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Payment request not found"
    else:
        raise AssertionError(
            "Expected summary lookup by raw payment_intent_id to be rejected"
        )


def test_create_payment_intent_stores_public_token_without_client_secret(monkeypatch):
    fake_mongo = FakeMongo()
    monkeypatch.setattr(database_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        stripe_payment_module.stripe_service,
        "create_payment_intent_for_couple",
        lambda **_kwargs: {
            "payment_intent_id": "pi_999",
            "client_secret": "pi_secret_should_not_be_persisted",
            "amount": 50.0,
            "currency": "usd",
            "status": "requires_payment_method",
        },
    )

    current_user = SimpleNamespace(
        is_root_admin=True,
        user_data={"_id": "planner-1"},
    )

    result = asyncio.run(
        stripe_payment_module.create_payment_intent(
            stripe_payment_module.CreatePaymentIntentRequest(
                amount=50.0,
                currency="usd",
                wedding_id="wedding_123",
                description="Deposit request",
            ),
            current_user=current_user,
        )
    )

    inserted = fake_mongo.db["payment_requests"].inserted
    assert inserted is not None
    assert inserted["payment_intent_id"] == "pi_999"
    assert inserted["public_token"]
    assert "client_secret" not in inserted
    assert result["payment_intent"]["public_token"] == inserted["public_token"]
