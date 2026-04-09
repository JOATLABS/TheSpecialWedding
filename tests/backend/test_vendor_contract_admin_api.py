from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api import vendor_management as vendor_management_api
from app.dependencies.auth_extended import ExtendedAuthUser
from app.models.vendor import VendorCategory
from app.models.vendor_contracts import (
    ApplyVendorContractFormDataRequest,
    CreateVendorContractRequest,
    CreateVendorContractTemplateRequest,
    CreateVendorPaymentMilestonesRequest,
    PaymentMilestoneInput,
    RecordVendorMilestonePaymentRequest,
    SendVendorContractRequest,
    UpdateVendorContractRequest,
    UpdateVendorContractSectionsRequest,
)
import app.services.vendor_service as vendor_service_module
from app.services.vendor_service import vendor_service


@pytest.fixture
def planner_user() -> ExtendedAuthUser:
    return ExtendedAuthUser(
        "planner@example.com",
        "wedding_planner",
        {"_id": "planner-1"},
    )


@pytest.mark.asyncio
async def test_create_contract_template_uses_typed_payload(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    create_mock = AsyncMock(return_value={"_id": "template-1"})
    monkeypatch.setattr(vendor_management_api.vendor_service, "create_contract_template", create_mock)

    request = CreateVendorContractTemplateRequest(
        name="Photography",
        service_category=VendorCategory.PHOTOGRAPHER,
        sections=[{"title": "Scope", "content": "Coverage", "order": 0}],
    )

    await vendor_management_api.create_contract_template(
        data=request,
        current_user=planner_user,
    )

    create_mock.assert_awaited_once_with(
        data={
            "name": "Photography",
            "service_category": VendorCategory.PHOTOGRAPHER,
            "sections": [{"title": "Scope", "content": "Coverage", "order": 0}],
            "default_payment_schedule": [],
            "is_public": False,
        },
        created_by="planner@example.com",
    )


@pytest.mark.asyncio
async def test_create_contract_uses_json_body_payload(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    create_mock = AsyncMock(return_value={"_id": "contract-1"})
    monkeypatch.setattr(vendor_management_api.vendor_service, "create_contract", create_mock)

    request = CreateVendorContractRequest(
        wedding_id="wedding-1",
        vendor_profile_id="vendor-1",
        total_amount=5000,
        deposit_percentage=50,
    )

    await vendor_management_api.create_contract(data=request, current_user=planner_user)

    create_mock.assert_awaited_once_with(
        created_by="planner@example.com",
        wedding_id="wedding-1",
        vendor_profile_id="vendor-1",
        total_amount=5000.0,
        deposit_percentage=50.0,
        custom_sections=[],
    )


@pytest.mark.asyncio
async def test_update_contract_uses_exclude_none_payload(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    update_mock = AsyncMock(return_value={"_id": "contract-1"})
    monkeypatch.setattr(vendor_management_api.vendor_service, "update_contract", update_mock)

    request = UpdateVendorContractRequest(
        contract_title="Updated Title",
        service_location="Austin, TX",
    )

    await vendor_management_api.update_contract(
        contract_id="contract-1",
        data=request,
        current_user=planner_user,
    )

    update_mock.assert_awaited_once_with(
        contract_id="contract-1",
        data={
            "contract_title": "Updated Title",
            "service_location": "Austin, TX",
        },
        updated_by="planner@example.com",
    )


@pytest.mark.asyncio
async def test_update_contract_sections_forwards_full_object_payload(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    update_mock = AsyncMock(return_value={"_id": "contract-1"})
    monkeypatch.setattr(vendor_management_api.vendor_service, "update_contract_sections", update_mock)

    request = UpdateVendorContractSectionsRequest(
        sections=[{"id": "sec-1", "title": "Intro", "content": "Hello", "order": 0}],
        terms_and_conditions="Terms",
        cancellation_policy="Cancel",
        custom_clauses="Custom",
    )

    await vendor_management_api.update_contract_sections(
        contract_id="contract-1",
        data=request,
        current_user=planner_user,
    )

    update_mock.assert_awaited_once_with(
        contract_id="contract-1",
        sections=[{"id": "sec-1", "title": "Intro", "content": "Hello", "order": 0}],
        terms_and_conditions="Terms",
        cancellation_policy="Cancel",
        custom_clauses="Custom",
        updated_by="planner@example.com",
    )


@pytest.mark.asyncio
async def test_apply_form_data_endpoint_uses_normalized_request(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    apply_mock = AsyncMock(return_value={"_id": "contract-1"})
    monkeypatch.setattr(vendor_management_api.vendor_service, "apply_form_data_to_contract", apply_mock)

    request = ApplyVendorContractFormDataRequest(
        form_submission_id="submission-1",
        field_mappings={"portfolio_link": "{{vendor_portfolio}}"},
    )

    await vendor_management_api.apply_form_data_to_contract(
        contract_id="contract-1",
        data=request,
        current_user=planner_user,
    )

    apply_mock.assert_awaited_once_with(
        contract_id="contract-1",
        form_submission_id="submission-1",
        field_mappings={"portfolio_link": "{{vendor_portfolio}}"},
        applied_by="planner@example.com",
    )


@pytest.mark.asyncio
async def test_send_contract_endpoint_uses_body_model_with_default_cc_list(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    send_mock = AsyncMock(return_value={"message": "sent", "sent_to": "vendor@example.com"})
    monkeypatch.setattr(vendor_management_api.vendor_service, "send_contract", send_mock)

    request = SendVendorContractRequest(message="Please review")

    await vendor_management_api.send_contract_to_vendor(
        contract_id="contract-1",
        data=request,
        current_user=planner_user,
    )

    send_mock.assert_awaited_once_with(
        contract_id="contract-1",
        created_by="planner@example.com",
        message="Please review",
        cc_emails=[],
    )


@pytest.mark.asyncio
async def test_create_payment_milestones_endpoint_wraps_milestones_body(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    create_mock = AsyncMock(return_value=[{"_id": "milestone-1"}])
    monkeypatch.setattr(vendor_management_api.vendor_service, "create_payment_milestones", create_mock)

    request = CreateVendorPaymentMilestonesRequest(
        milestones=[
            PaymentMilestoneInput(
                description="Deposit",
                amount=2500,
                due_date=datetime(2026, 4, 20, tzinfo=timezone.utc),
                percentage_of_total=50,
            )
        ]
    )

    await vendor_management_api.create_payment_milestones(
        contract_id="contract-1",
        data=request,
        current_user=planner_user,
    )

    create_mock.assert_awaited_once_with(
        contract_id="contract-1",
        milestones=[
            {
                "description": "Deposit",
                "amount": 2500.0,
                "due_date": datetime(2026, 4, 20, tzinfo=timezone.utc),
                "percentage_of_total": 50.0,
            }
        ],
        created_by="planner@example.com",
    )


@pytest.mark.asyncio
async def test_record_milestone_payment_endpoint_uses_body_model(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    record_mock = AsyncMock(return_value={"_id": "milestone-1"})
    monkeypatch.setattr(vendor_management_api.vendor_service, "record_payment", record_mock)

    request = RecordVendorMilestonePaymentRequest(
        amount=1200,
        payment_method="card",
        payment_date=datetime(2026, 4, 8, tzinfo=timezone.utc),
        notes="Paid in full",
        receipt_url="https://example.com/receipt.pdf",
    )

    await vendor_management_api.record_milestone_payment(
        milestone_id="milestone-1",
        data=request,
        current_user=planner_user,
    )

    record_mock.assert_awaited_once_with(
        milestone_id="milestone-1",
        amount=1200.0,
        payment_method="card",
        created_by="planner@example.com",
        payment_date=datetime(2026, 4, 8, tzinfo=timezone.utc),
        notes="Paid in full",
        receipt_url="https://example.com/receipt.pdf",
    )


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return list(self._docs)


class _FakeFindCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, query):
        return _FakeCursor(self._docs)


@pytest.mark.asyncio
async def test_vendor_service_get_form_data_normalizes_response_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vendor_service,
        "get_contract",
        AsyncMock(return_value={"vendor_email": "vendor@example.com"}),
    )
    monkeypatch.setattr(
        vendor_service_module,
        "mongo",
        SimpleNamespace(
            db={
                "vendor_submissions": _FakeFindCollection(
                    [
                        {
                            "_id": "submission-1",
                            "form_name": "Vendor Intake",
                            "submitted_at": datetime(2026, 4, 8, tzinfo=timezone.utc),
                            "submission_data": {
                                "portfolio_link": "https://example.com/work",
                            },
                        }
                    ]
                ),
                "vendor_forms": _FakeFindCollection([]),
            }
        ),
    )

    result = await vendor_service.get_form_data_for_contract(
        "507f1f77bcf86cd799439011",
        created_by="planner@example.com",
    )

    assert "vendor_submissions" in result
    assert "available_fields" in result
    assert "suggested_contract_fields" in result
    assert "submissions" not in result
    assert "suggested_mappings" not in result
    assert result["vendor_submissions"][0]["data"]["portfolio_link"] == "https://example.com/work"
    assert result["suggested_contract_fields"]["{{vendor_portfolio}}"]["source_field"] == "portfolio_link"


@pytest.mark.asyncio
async def test_vendor_service_apply_form_data_returns_updated_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_id = "507f1f77bcf86cd799439011"
    submission_id = "507f1f77bcf86cd799439012"
    updated_contract = {
        "_id": contract_id,
        "status": "draft",
        "sections": [],
    }

    get_contract_mock = AsyncMock(
        side_effect=[
            {
                "_id": contract_id,
                "status": "draft",
                "sections": [
                    {
                        "id": "sec-1",
                        "title": "Overview",
                        "content": "Portfolio {{vendor_portfolio}} / raw {{portfolio_link}}",
                        "order": 0,
                    }
                ],
                "terms_and_conditions": "Terms {{vendor_portfolio}}",
                "cancellation_policy": "Cancel {{portfolio_link}}",
                "custom_clauses": "Clause {{vendor_portfolio}}",
                "form_submission_ids": ["older-submission"],
            },
            updated_contract,
        ]
    )
    monkeypatch.setattr(vendor_service, "get_contract", get_contract_mock)

    captured_update: dict[str, object] = {}

    class FakeVendorContractsCollection:
        async def update_one(self, query, update):
            captured_update["query"] = query
            captured_update["update"] = update

    class FakeSubmissionCollection:
        async def find_one(self, query):
            return {
                "_id": query["_id"],
                "submission_data": {
                    "portfolio_link": "https://example.com/portfolio",
                },
            }

    class FakeEmptyCollection:
        async def find_one(self, query):
            return None

    monkeypatch.setattr(vendor_service, "vendor_contracts", FakeVendorContractsCollection())
    monkeypatch.setattr(
        vendor_service_module,
        "mongo",
        SimpleNamespace(
            db={
                "vendor_submissions": FakeSubmissionCollection(),
                "vendor_forms": FakeEmptyCollection(),
            }
        ),
    )

    result = await vendor_service.apply_form_data_to_contract(
        contract_id=contract_id,
        form_submission_id=submission_id,
        field_mappings={"portfolio_link": "{{vendor_portfolio}}"},
        applied_by="planner@example.com",
    )

    assert result is updated_contract
    update_payload = captured_update["update"]["$set"]
    assert update_payload["sections"][0]["content"] == (
        "Portfolio https://example.com/portfolio / raw https://example.com/portfolio"
    )
    assert update_payload["terms_and_conditions"] == "Terms https://example.com/portfolio"
    assert update_payload["cancellation_policy"] == "Cancel https://example.com/portfolio"
    assert update_payload["custom_clauses"] == "Clause https://example.com/portfolio"
    assert update_payload["form_data_applied"] is True
    assert update_payload["form_submission_id"] == submission_id
    assert update_payload["form_submission_ids"] == ["older-submission", submission_id]
    assert update_payload["form_data_mappings"] == {
        "portfolio_link": "{{vendor_portfolio}}"
    }
