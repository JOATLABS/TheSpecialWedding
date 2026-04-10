from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

import app.services.vendor_service as vendor_service_module
from app.api import vendor_management as vendor_management_api
from app.dependencies.auth_extended import ExtendedAuthUser
from app.models.vendor import ContractKind, VendorCategory
from app.models.vendor_contracts import (
    ApplyVendorContractFormDataRequest,
    CreateVendorContractRequest,
    CreateVendorContractRevisionRequest,
    CreateVendorContractTemplateRequest,
    CreateVendorPaymentMilestonesRequest,
    PaymentMilestoneInput,
    RecordVendorMilestonePaymentRequest,
    SendVendorContractRequest,
    UpdateVendorContractRequest,
    UpdateVendorContractSectionsRequest,
    VendorContractActivityResponse,
)
from app.services.vendor_service import vendor_service


@pytest.fixture
def planner_user() -> ExtendedAuthUser:
    return ExtendedAuthUser(
        "planner@example.com",
        "wedding_planner",
        {"_id": "planner-1"},
    )


class _FakeServiceCursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    def skip(self, value: int):
        self._docs = self._docs[value:]
        return self

    def limit(self, value: int):
        self._docs = self._docs[:value]
        return self

    def sort(self, field: str, direction: int):
        reverse = direction == -1
        self._docs = sorted(
            self._docs, key=lambda item: item.get(field), reverse=reverse
        )
        return self

    async def to_list(self, length=None):
        docs = deepcopy(self._docs)
        if length is None:
            return docs
        return docs[:length]


class _FakeServiceCollection:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    def find(self, query):
        def _matches(document: dict) -> bool:
            for key, expected in query.items():
                if key == "$or":
                    return any(
                        all(
                            (
                                document.get(branch_key) == branch_value
                                if not isinstance(branch_value, dict)
                                else (
                                    "$exists" in branch_value
                                    and (branch_key in document)
                                    == branch_value["$exists"]
                                )
                            )
                            for branch_key, branch_value in branch.items()
                        )
                        for branch in expected
                    )
                if document.get(key) != expected:
                    return False
            return True

        return _FakeServiceCursor([doc for doc in self._docs if _matches(doc)])

    async def find_one(self, query):
        for doc in self._docs:
            if doc.get("_id") == query.get("_id") and doc.get(
                "created_by"
            ) == query.get("created_by"):
                return deepcopy(doc)
        return None


@pytest.mark.asyncio
async def test_create_contract_template_uses_typed_payload(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    create_mock = AsyncMock(return_value={"_id": "template-1"})
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "create_contract_template", create_mock
    )

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
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "create_contract", create_mock
    )

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
async def test_create_contract_revision_forwards_typed_payload(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    create_mock = AsyncMock(return_value={"_id": "contract-2"})
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "create_contract_revision", create_mock
    )

    request = CreateVendorContractRevisionRequest(
        revision_kind="revision",
        reason="Updated scope",
    )

    await vendor_management_api.create_contract_revision(
        contract_id="contract-1",
        data=request,
        current_user=planner_user,
    )

    create_mock.assert_awaited_once_with(
        contract_id="contract-1",
        created_by="planner@example.com",
        revision_kind="revision",
        reason="Updated scope",
        copy_sections=True,
        copy_terms_and_conditions=True,
        copy_cancellation_policy=True,
        copy_custom_clauses=True,
    )


@pytest.mark.asyncio
async def test_list_contracts_forwards_scoped_filters_and_pagination(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    list_mock = AsyncMock(return_value=[{"_id": "contract-1"}])
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "get_contracts", list_mock
    )

    await vendor_management_api.list_contracts(
        wedding_id="wedding-1",
        vendor_profile_id="vendor-1",
        status="draft",
        skip=10,
        limit=25,
        current_user=planner_user,
    )

    list_mock.assert_awaited_once_with(
        created_by="planner@example.com",
        wedding_id="wedding-1",
        vendor_profile_id="vendor-1",
        status="draft",
        skip=10,
        limit=25,
    )


@pytest.mark.asyncio
async def test_get_contract_endpoint_forwards_owner_scope(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    get_mock = AsyncMock(return_value={"_id": "contract-1"})
    monkeypatch.setattr(vendor_management_api.vendor_service, "get_contract", get_mock)

    await vendor_management_api.get_contract(
        contract_id="contract-1",
        current_user=planner_user,
    )

    get_mock.assert_awaited_once_with("contract-1", created_by="planner@example.com")


@pytest.mark.asyncio
async def test_list_contract_revisions_forwards_to_service(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    revision_mock = AsyncMock(
        return_value={
            "current_contract_id": "contract-2",
            "root_contract_id": "contract-1",
            "versions": [],
        }
    )
    monkeypatch.setattr(
        vendor_management_api.vendor_service,
        "get_contract_revision_history",
        revision_mock,
    )

    await vendor_management_api.list_contract_revisions(
        contract_id="contract-1",
        current_user=planner_user,
    )

    revision_mock.assert_awaited_once_with(
        contract_id="contract-1",
        created_by="planner@example.com",
    )


@pytest.mark.asyncio
async def test_update_contract_uses_exclude_none_payload(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    update_mock = AsyncMock(return_value={"_id": "contract-1"})
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "update_contract", update_mock
    )

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
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "update_contract_sections", update_mock
    )

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
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "apply_form_data_to_contract", apply_mock
    )

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
    send_mock = AsyncMock(
        return_value={"message": "sent", "sent_to": "vendor@example.com"}
    )
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "send_contract", send_mock
    )

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
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "create_payment_milestones", create_mock
    )

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
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "record_payment", record_mock
    )

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


@pytest.mark.asyncio
async def test_list_payment_milestones_endpoint_scopes_to_planner(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    list_mock = AsyncMock(return_value=[{"_id": "milestone-1"}])
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "get_payment_milestones", list_mock
    )

    await vendor_management_api.list_payment_milestones(
        contract_id="contract-1",
        wedding_id=None,
        status="pending",
        current_user=planner_user,
    )

    list_mock.assert_awaited_once_with(
        contract_id="contract-1",
        wedding_id=None,
        status="pending",
        created_by="planner@example.com",
    )


@pytest.mark.asyncio
async def test_get_contract_activity_endpoint_forwards_scoped_lookup(
    monkeypatch: pytest.MonkeyPatch,
    planner_user: ExtendedAuthUser,
) -> None:
    activity_mock = AsyncMock(
        return_value=VendorContractActivityResponse(
            contract_id="contract-1",
            root_contract_id="contract-1",
            items=[],
        ).model_dump()
    )
    monkeypatch.setattr(
        vendor_management_api.vendor_service, "get_contract_activity", activity_mock
    )

    await vendor_management_api.get_contract_activity(
        contract_id="contract-1",
        current_user=planner_user,
    )

    activity_mock.assert_awaited_once_with(
        contract_id="contract-1",
        created_by="planner@example.com",
    )


@pytest.mark.asyncio
async def test_vendor_service_get_contracts_defaults_to_current_versions_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_id = ObjectId()
    legacy_id = ObjectId()
    historical_id = ObjectId()
    monkeypatch.setattr(
        vendor_service,
        "vendor_contracts",
        _FakeServiceCollection(
            [
                {
                    "_id": current_id,
                    "created_by": "planner@example.com",
                    "created_at": datetime(2026, 4, 10, tzinfo=timezone.utc),
                    "status": "draft",
                    "is_current_version": True,
                    "version_number": 2,
                    "root_contract_id": "root-1",
                    "contract_kind": ContractKind.REVISION.value,
                },
                {
                    "_id": legacy_id,
                    "created_by": "planner@example.com",
                    "created_at": datetime(2026, 4, 9, tzinfo=timezone.utc),
                    "status": "draft",
                },
                {
                    "_id": historical_id,
                    "created_by": "planner@example.com",
                    "created_at": datetime(2026, 4, 8, tzinfo=timezone.utc),
                    "status": "signed",
                    "is_current_version": False,
                    "version_number": 1,
                    "root_contract_id": "root-1",
                    "contract_kind": ContractKind.ORIGINAL.value,
                },
            ]
        ),
    )

    result = await vendor_service.get_contracts(created_by="planner@example.com")

    assert [contract["id"] for contract in result] == [str(current_id), str(legacy_id)]
    assert all(
        contract.get("is_current_version", True) is not False for contract in result
    )


@pytest.mark.asyncio
async def test_vendor_service_get_contract_returns_lineage_metadata_for_admin_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_id = ObjectId()
    monkeypatch.setattr(
        vendor_service,
        "vendor_contracts",
        _FakeServiceCollection(
            [
                {
                    "_id": contract_id,
                    "created_by": "planner@example.com",
                    "status": "sent",
                    "version_number": 3,
                    "root_contract_id": "root-1",
                    "parent_contract_id": "root-1",
                    "supersedes_contract_id": "contract-2",
                    "superseded_by_contract_id": None,
                    "is_current_version": True,
                    "contract_kind": ContractKind.AMENDMENT.value,
                    "created_at": datetime(2026, 4, 10, tzinfo=timezone.utc),
                    "updated_at": datetime(2026, 4, 10, tzinfo=timezone.utc),
                }
            ]
        ),
    )

    result = await vendor_service.get_contract(
        str(contract_id),
        created_by="planner@example.com",
    )

    assert result["id"] == str(contract_id)
    assert result["version_number"] == 3
    assert result["root_contract_id"] == "root-1"
    assert result["parent_contract_id"] == "root-1"
    assert result["supersedes_contract_id"] == "contract-2"
    assert result["contract_kind"] == ContractKind.AMENDMENT.value


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
    assert (
        result["vendor_submissions"][0]["data"]["portfolio_link"]
        == "https://example.com/work"
    )
    assert (
        result["suggested_contract_fields"]["{{vendor_portfolio}}"]["source_field"]
        == "portfolio_link"
    )


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

    monkeypatch.setattr(
        vendor_service, "vendor_contracts", FakeVendorContractsCollection()
    )
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
    assert (
        update_payload["terms_and_conditions"] == "Terms https://example.com/portfolio"
    )
    assert (
        update_payload["cancellation_policy"] == "Cancel https://example.com/portfolio"
    )
    assert update_payload["custom_clauses"] == "Clause https://example.com/portfolio"
    assert update_payload["form_data_applied"] is True
    assert update_payload["form_submission_id"] == submission_id
    assert update_payload["form_submission_ids"] == ["older-submission", submission_id]
    assert update_payload["form_data_mappings"] == {
        "portfolio_link": "{{vendor_portfolio}}"
    }
