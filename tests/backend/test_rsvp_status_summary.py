from __future__ import annotations

import pytest
from bson import ObjectId

from app.services.guest_service import GuestService
from app.utils.rsvp_status import (
    GUEST_RSVP_STATUS_FILTERS,
    RSVP_FILTER_NOT_INVITED,
    RSVP_FILTER_RESPONDED,
    RSVP_STATUS_CONFIRMED,
    RSVP_STATUS_DECLINED,
    RSVP_STATUS_PENDING,
    get_rsvp_status,
)


class _FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    async def to_list(self, length: int | None = None) -> list[dict]:
        if length is None:
            return list(self._docs)
        return list(self._docs[:length])


class _FakeCollection:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    def find(self, query: dict, projection: dict | None = None) -> _FakeCursor:
        return _FakeCursor([doc for doc in self._docs if self._matches(doc, query)])

    def _matches(self, doc: dict, query: dict) -> bool:
        for key, expected in query.items():
            if key == "$or":
                return any(self._matches(doc, clause) for clause in expected)

            value = doc.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if value not in expected["$in"]:
                    return False
                continue

            if value != expected:
                return False

        return True


class _AggregateSpyCollection:
    def __init__(self):
        self.pipeline: list[dict] | None = None

    def aggregate(self, pipeline: list[dict]) -> _FakeCursor:
        self.pipeline = pipeline
        return _FakeCursor([{"items": [], "totalCount": []}])


async def _empty_summary(_wedding_id: str) -> dict:
    return {}


async def _empty_filter_options(_wedding_id: str) -> dict:
    return {"groups": [], "roles": []}


def test_rsvp_status_helper_classifies_empty_attending_as_declined() -> None:
    assert get_rsvp_status({"attending": ["ceremony"]}) == RSVP_STATUS_CONFIRMED
    assert get_rsvp_status({"attending": []}) == RSVP_STATUS_DECLINED
    assert get_rsvp_status({"attending": {"ceremony": False}}) == RSVP_STATUS_DECLINED
    assert get_rsvp_status({"attending": None}) == RSVP_STATUS_PENDING


@pytest.mark.asyncio
async def test_guest_summary_counts_declined_rsvps_outside_confirmed_total() -> None:
    confirmed_guest_id = ObjectId()
    declined_guest_id = ObjectId()
    pending_guest_id = ObjectId()
    not_invited_guest_id = ObjectId()

    service = GuestService.__new__(GuestService)
    service.collection = _FakeCollection(
        [
            {
                "_id": confirmed_guest_id,
                "wedding_id": "wedding_1",
                "invite_sent": True,
                "number_of_plus_ones_allowed": 2,
            },
            {
                "_id": declined_guest_id,
                "wedding_id": "wedding_1",
                "invite_sent": True,
                "number_of_plus_ones_allowed": 3,
            },
            {
                "_id": pending_guest_id,
                "wedding_id": "wedding_1",
                "invite_sent": True,
                "number_of_plus_ones_allowed": 1,
            },
            {
                "_id": not_invited_guest_id,
                "wedding_id": "wedding_1",
                "invite_sent": False,
                "number_of_plus_ones_allowed": 4,
            },
        ]
    )
    service.rsvp_collection = _FakeCollection(
        [
            {
                "guest_id": str(confirmed_guest_id),
                "wedding_id": "wedding_1",
                "attending": ["ceremony"],
            },
            {
                "guest_id": str(declined_guest_id),
                "wedding_id": "wedding_1",
                "attending": [],
            },
        ]
    )
    service.plus_one_collection = _FakeCollection(
        [
            {"guest_id": str(confirmed_guest_id)},
            {"guest_id": str(confirmed_guest_id)},
            {"guest_id": str(declined_guest_id)},
        ]
    )

    summary = await service._build_guest_summary("wedding_1")

    assert summary["totalGuests"] == 4
    assert summary["invitedGuests"] == 3
    assert summary["respondedGuests"] == 2
    assert summary["confirmedGuests"] == 1
    assert summary["declinedGuests"] == 1
    assert summary["pendingGuests"] == 1
    assert summary["notInvitedGuests"] == 1
    assert summary["totalPlusOneSlots"] == 10
    assert summary["respondedPlusOnes"] == 3
    assert summary["pendingPlusOneSlots"] == 1
    assert summary["submittedPlusOnes"] == 3


def test_guest_rsvp_filter_statuses_include_declined_and_confirmed() -> None:
    assert RSVP_STATUS_CONFIRMED in GUEST_RSVP_STATUS_FILTERS
    assert RSVP_STATUS_DECLINED in GUEST_RSVP_STATUS_FILTERS
    assert RSVP_FILTER_RESPONDED in GUEST_RSVP_STATUS_FILTERS
    assert RSVP_FILTER_NOT_INVITED in GUEST_RSVP_STATUS_FILTERS


def test_guest_rsvp_object_expression_uses_backend_truthiness() -> None:
    service = GuestService.__new__(GuestService)

    expression = service._rsvp_object_true_count_expression("$rsvp_attending")
    filter_expression = expression["$cond"][1]["$size"]["$filter"]

    assert filter_expression["cond"] == {"$toBool": "$$entry.v"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rsvp_status", "expected_match"),
    [
        (RSVP_FILTER_RESPONDED, {"has_rsvp": True}),
        (RSVP_STATUS_CONFIRMED, {"rsvp_status_detail": RSVP_STATUS_CONFIRMED}),
        (RSVP_STATUS_DECLINED, {"rsvp_status_detail": RSVP_STATUS_DECLINED}),
        (RSVP_STATUS_PENDING, {"invite_sent": True, "has_rsvp": False}),
        (
            RSVP_FILTER_NOT_INVITED,
            {"invite_sent": {"$ne": True}, "has_rsvp": False},
        ),
    ],
)
async def test_guest_list_builds_server_side_rsvp_status_filters(
    rsvp_status: str, expected_match: dict
) -> None:
    collection = _AggregateSpyCollection()
    service = GuestService.__new__(GuestService)
    service.collection = collection
    service._build_guest_summary = _empty_summary
    service._build_guest_filter_options = _empty_filter_options

    await service.list_guests_by_wedding("wedding_1", rsvp_status=rsvp_status)

    assert collection.pipeline is not None
    assert any("$lookup" in stage for stage in collection.pipeline)
    assert any(
        stage == {"$match": expected_match} for stage in collection.pipeline
    ), collection.pipeline
    assert any(
        stage == {
            "$project": {
                "rsvp_docs": 0,
                "plus_one_docs": 0,
                "has_rsvp": 0,
                "rsvp_attending": 0,
                "rsvp_status_detail": 0,
                "plus_one_count": 0,
                "rsvp_sort_order": 0,
            }
        }
        for facet in [
            stage.get("$facet", {}).get("items", [])
            for stage in collection.pipeline
            if "$facet" in stage
        ]
        for stage in facet
    )


@pytest.mark.asyncio
async def test_guest_list_all_filter_keeps_default_query_without_rsvp_lookup() -> None:
    collection = _AggregateSpyCollection()
    service = GuestService.__new__(GuestService)
    service.collection = collection
    service._build_guest_summary = _empty_summary
    service._build_guest_filter_options = _empty_filter_options

    await service.list_guests_by_wedding("wedding_1", rsvp_status="all")

    assert collection.pipeline is not None
    assert not any("$lookup" in stage for stage in collection.pipeline)
