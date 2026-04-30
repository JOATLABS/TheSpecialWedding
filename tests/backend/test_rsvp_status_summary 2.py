from __future__ import annotations

import pytest
from bson import ObjectId

from app.services.guest_service import GuestService
from app.utils.rsvp_status import (
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
