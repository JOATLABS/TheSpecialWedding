from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib
import os
import sys
from types import SimpleNamespace

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

couple_portal_module = importlib.import_module("app.services.couple_portal_service")


class _ScheduledPaymentsCursor:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    def sort(self, field: str, direction: int):
        reverse = direction < 0
        self.documents.sort(key=lambda document: document.get(field), reverse=reverse)
        return self

    async def to_list(self, length=None):
        return deepcopy(self.documents)


class _ContractsCollection:
    def __init__(self, contract: dict):
        self.contract = contract

    async def find_one(self, query: dict, projection: dict | None = None):
        if query.get("wedding_id") != self.contract["wedding_id"]:
            return None
        return deepcopy(self.contract)


class _ScheduledPaymentsCollection:
    def __init__(self, payments: list[dict]):
        self.payments = payments

    def find(self, query: dict):
        matching = [
            payment
            for payment in self.payments
            if payment.get("contract_id") == query.get("contract_id")
        ]
        return _ScheduledPaymentsCursor(deepcopy(matching))


def _fake_mongo() -> SimpleNamespace:
    contract_id = "contract-1"
    contract = {
        "_id": contract_id,
        "wedding_id": "wedding-1",
        "couple": {"email": "couple@couples.thespecialwedding.io", "name": "Sofia"},
        "status": "active",
        "package_snapshot": {
            "name": "Signature Planning + Production",
            "total_amount": 12_800,
        },
        "signed_at": datetime(2026, 7, 5, tzinfo=timezone.utc),
        "sent_at": datetime(2026, 7, 3, tzinfo=timezone.utc),
        "viewed_at": datetime(2026, 7, 4, tzinfo=timezone.utc),
        "created_at": datetime(2026, 7, 2, tzinfo=timezone.utc),
    }
    payments = [
        {
            "_id": "payment-1",
            "contract_id": contract_id,
            "name": "Retainer",
            "amount": 3_200,
            "currency": "usd",
            "due_date": datetime(2026, 7, 5, tzinfo=timezone.utc),
            "status": "succeeded",
            "paid_at": datetime(2026, 7, 5, tzinfo=timezone.utc),
        },
        {
            "_id": "payment-2",
            "contract_id": contract_id,
            "name": "Design lock",
            "amount": 4_800,
            "currency": "usd",
            "due_date": datetime(2026, 8, 26, tzinfo=timezone.utc),
            "status": "scheduled",
            "paid_at": None,
        },
        {
            "_id": "payment-3",
            "contract_id": contract_id,
            "name": "Final production",
            "amount": 4_800,
            "currency": "usd",
            "due_date": datetime(2027, 1, 4, tzinfo=timezone.utc),
            "status": "scheduled",
            "paid_at": None,
        },
    ]
    return SimpleNamespace(
        db={
            "contracts": _ContractsCollection(contract),
            "scheduled_payments": _ScheduledPaymentsCollection(payments),
        }
    )


@pytest.mark.asyncio
async def test_dashboard_contract_uses_canonical_scheduled_payments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(couple_portal_module, "mongo", _fake_mongo())

    result = await couple_portal_module.CouplePortalService()._get_contract_info(
        "wedding-1",
        "couple@couples.thespecialwedding.io",
    )

    assert result is not None
    assert result["package_name"] == "Signature Planning + Production"
    assert [payment["name"] for payment in result["payments"]] == [
        "Retainer",
        "Design lock",
        "Final production",
    ]
    assert result["summary"] == {
        "total_amount": 12_800,
        "paid_amount": 3_200,
        "remaining": 9_600,
    }


@pytest.mark.asyncio
async def test_contract_detail_uses_same_canonical_scheduled_payments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(couple_portal_module, "mongo", _fake_mongo())

    result = await couple_portal_module.CouplePortalService().get_contract_for_couple(
        "wedding-1",
        "couple@couples.thespecialwedding.io",
    )

    assert result is not None
    assert result["package_name"] == "Signature Planning + Production"
    assert [payment["name"] for payment in result["payments"]] == [
        "Retainer",
        "Design lock",
        "Final production",
    ]
    assert result["summary"] == {
        "total_amount": 12_800,
        "paid_amount": 3_200,
        "remaining": 9_600,
    }
