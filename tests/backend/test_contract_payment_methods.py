import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import stripe

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.api.contracts as contracts_module
import app.core.database as database_module
import app.core.settings as settings_module


class AsyncCollection:
    def __init__(self):
        self.calls = []

    async def update_one(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return SimpleNamespace(modified_count=1)


class AsyncDatabase:
    def __init__(self):
        self.collections = {"contracts": AsyncCollection()}

    def __getitem__(self, name):
        return self.collections[name]


class FakeMongo:
    def __init__(self):
        self.db = AsyncDatabase()


def test_confirm_payment_method_update_derives_card_metadata(monkeypatch):
    fake_mongo = FakeMongo()
    monkeypatch.setattr(database_module, "mongo", fake_mongo)
    monkeypatch.setattr(settings_module.settings, "stripe_secret_key", "sk_test_123", raising=False)
    monkeypatch.setattr(
        contracts_module.contract_service,
        "get_contract_by_token",
        AsyncMock(return_value={
            "stripe_customer_id": "cus_123",
            "planner_email": None,
            "couple": {"partner1_name": "Alex"},
        }),
    )

    customer_modify_calls = []
    monkeypatch.setattr(
        stripe.SetupIntent,
        "retrieve",
        lambda _setup_intent_id: SimpleNamespace(
            status="succeeded",
            customer="cus_123",
            metadata={"contract_token": "portal-token", "action": "update_payment_method"},
            payment_method="pm_123",
        ),
    )
    monkeypatch.setattr(
        stripe.PaymentMethod,
        "retrieve",
        lambda _payment_method_id: SimpleNamespace(
            customer="cus_123",
            type="card",
            card=SimpleNamespace(last4="4242", brand="visa"),
        ),
    )
    monkeypatch.setattr(
        stripe.Customer,
        "modify",
        lambda customer_id, **kwargs: customer_modify_calls.append((customer_id, kwargs)),
    )

    result = asyncio.run(
        contracts_module.confirm_payment_method_update(
            "portal-token",
            contracts_module.UpdatePaymentMethodRequest(
                payment_method_id="pm_123",
                setup_intent_id="seti_123",
            ),
        )
    )

    assert result["payment_method"] == {"last4": "4242", "brand": "visa"}
    assert customer_modify_calls == [
        ("cus_123", {"invoice_settings": {"default_payment_method": "pm_123"}})
    ]
    update_args, _update_kwargs = fake_mongo.db["contracts"].calls[0]
    assert update_args[0] == {"token": "portal-token"}
    assert update_args[1]["$set"]["payment_method_last4"] == "4242"
    assert update_args[1]["$set"]["payment_method_brand"] == "visa"


def test_sign_contract_derives_card_metadata_before_persisting(monkeypatch):
    monkeypatch.setattr(settings_module.settings, "stripe_secret_key", "sk_test_123", raising=False)

    captured = {}

    async def fake_sign_contract(**kwargs):
        captured.update(kwargs)
        return {
            "id": "contract-1",
            "status": "signed",
            "signed_at": "2026-04-05T00:00:00+00:00",
            "scheduled_payments": [],
            "document_url": None,
        }

    monkeypatch.setattr(contracts_module.contract_service, "sign_contract", fake_sign_contract)
    monkeypatch.setattr(
        contracts_module.contract_service,
        "get_contract_by_token",
        AsyncMock(return_value={"stripe_customer_id": "cus_123"}),
    )
    monkeypatch.setattr(
        stripe.SetupIntent,
        "retrieve",
        lambda _setup_intent_id: SimpleNamespace(
            status="succeeded",
            customer="cus_123",
            metadata={"contract_token": "contract-token", "action": "contract_sign"},
            payment_method="pm_123",
        ),
    )
    monkeypatch.setattr(
        stripe.PaymentMethod,
        "retrieve",
        lambda _payment_method_id: SimpleNamespace(
            customer="cus_123",
            type="card",
            card=SimpleNamespace(last4="4242", brand="visa"),
        ),
    )

    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest-suite"},
    )

    result = asyncio.run(
        contracts_module.sign_contract(
            "contract-token",
            contracts_module.SignContractRequest(
                signature_name="Alex Example",
                stripe_customer_id="cus_123",
                stripe_payment_method_id="pm_123",
                setup_intent_id="seti_123",
                accept_terms=True,
            ),
            request,
        )
    )

    assert result["message"] == "Contract signed successfully"
    assert captured["payment_method_last4"] == "4242"
    assert captured["payment_method_brand"] == "visa"


def test_sign_contract_uses_contract_customer_when_request_omits_it(monkeypatch):
    monkeypatch.setattr(settings_module.settings, "stripe_secret_key", "sk_test_123", raising=False)

    captured = {}

    async def fake_sign_contract(**kwargs):
        captured.update(kwargs)
        return {
            "id": "contract-1",
            "status": "signed",
            "signed_at": "2026-04-05T00:00:00+00:00",
            "scheduled_payments": [],
            "document_url": None,
        }

    monkeypatch.setattr(contracts_module.contract_service, "sign_contract", fake_sign_contract)
    monkeypatch.setattr(
        contracts_module.contract_service,
        "get_contract_by_token",
        AsyncMock(return_value={"stripe_customer_id": "cus_456"}),
    )
    monkeypatch.setattr(
        stripe.SetupIntent,
        "retrieve",
        lambda _setup_intent_id: SimpleNamespace(
            status="succeeded",
            customer="cus_456",
            metadata={"contract_token": "contract-token", "action": "contract_sign"},
            payment_method="pm_123",
        ),
    )
    monkeypatch.setattr(
        stripe.PaymentMethod,
        "retrieve",
        lambda _payment_method_id: SimpleNamespace(
            customer="cus_456",
            type="card",
            card=SimpleNamespace(last4="4242", brand="visa"),
        ),
    )

    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest-suite"},
    )

    result = asyncio.run(
        contracts_module.sign_contract(
            "contract-token",
            contracts_module.SignContractRequest(
                signature_name="Alex Example",
                stripe_payment_method_id="pm_123",
                setup_intent_id="seti_123",
                accept_terms=True,
            ),
            request,
        )
    )

    assert result["message"] == "Contract signed successfully"
    assert captured["stripe_customer_id"] == "cus_456"
    assert captured["payment_method_last4"] == "4242"
    assert captured["payment_method_brand"] == "visa"
