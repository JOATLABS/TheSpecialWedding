"""Unit tests for Aurinko contact mirroring.

Contacts are intentionally outbound-only. These tests pin the payload shape and
lifecycle bookkeeping without depending on Mongo or a live Aurinko account.
"""

from __future__ import annotations

from typing import Any

import pytest
from bson import ObjectId

from app.models.calendar_connection import CalendarConnectionStatus
from app.models.calendar_sync import CalendarSyncDirection, CalendarSyncStatusValue
from app.services.aurinko_contacts_sync_service import AurinkoContactsSyncService


class _Cursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self.docs = docs

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return self.docs[:length] if length is not None else self.docs


class _Collection:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self.docs = docs or []
        self.updates: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                continue
            if actual != expected:
                return False
        return True

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return next((doc for doc in self.docs if self._matches(doc, query)), None)

    def find(self, query: dict[str, Any]) -> _Cursor:
        return _Cursor([doc for doc in self.docs if self._matches(doc, query)])

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        self.updates.append((query, update, upsert))
        doc = await self.find_one(query)
        if doc is None:
            if not upsert:
                return
            doc = {
                key: value
                for key, value in query.items()
                if not isinstance(value, dict)
            }
            doc.update(update.get("$setOnInsert", {}))
            self.docs.append(doc)
        doc.update(update.get("$set", {}))


class _ContactClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.updated: list[dict[str, Any]] = []
        self.deleted: list[dict[str, Any]] = []

    async def create_contact(
        self, *, account_token: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        self.created.append({"account_token": account_token, "body": body})
        return {"id": "contact-1", "etag": "etag-1"}

    async def update_contact(
        self,
        *,
        account_token: str,
        contact_id: str,
        body: dict[str, Any],
        etag: str | None = None,
    ) -> dict[str, Any]:
        self.updated.append(
            {
                "account_token": account_token,
                "contact_id": contact_id,
                "body": body,
                "etag": etag,
            }
        )
        return {"id": contact_id, "etag": "etag-2"}

    async def delete_contact(self, *, account_token: str, contact_id: str) -> None:
        self.deleted.append({"account_token": account_token, "contact_id": contact_id})


class _Provider:
    def __init__(self) -> None:
        self.client = _ContactClient()

    async def _account_token_for_connection(self, connection: dict[str, Any]) -> str:
        return f"token:{connection['_id']}"

    def _default_contact_group_name(self, connection: dict[str, Any]) -> str:
        return (
            connection.get("workspace_name")
            or connection.get("owner_planner_email")
            or "Wedding planner"
        ) + " (TheSpecialWedding)"


def _service(
    *,
    connections: _Collection,
    syncs: _Collection,
    vendors: _Collection | None = None,
    weddings: _Collection | None = None,
    couples: _Collection | None = None,
    provider: _Provider | None = None,
) -> AurinkoContactsSyncService:
    service = AurinkoContactsSyncService.__new__(AurinkoContactsSyncService)
    service.connections_collection = connections
    service.syncs_collection = syncs
    service.vendor_profiles = vendors or _Collection()
    service.weddings_collection = weddings or _Collection()
    service.couple_users_collection = couples or _Collection()
    service.provider = provider or _Provider()
    return service


@pytest.mark.asyncio
async def test_mirror_vendor_creates_contact_with_workspace_keywords() -> None:
    vendor_id = ObjectId()
    connection_id = ObjectId()
    provider = _Provider()
    service = _service(
        vendors=_Collection(
            [
                {
                    "_id": vendor_id,
                    "business_name": "Lens & Light",
                    "contact_name": "Ada Lovelace",
                    "email": "ada@example.com",
                    "phone": "+15551230000",
                    "website": "https://lens.example.com",
                    "service_category": "photographer",
                    "service_description": "Editorial wedding photography",
                    "address": "1 Main St",
                    "city": "Chicago",
                    "state": "IL",
                    "postal_code": "60601",
                    "country": "US",
                    "created_by": "planner@example.com",
                    "is_active": True,
                }
            ]
        ),
        connections=_Collection(
            [
                {
                    "_id": connection_id,
                    "connection_status": CalendarConnectionStatus.ACTIVE.value,
                    "contact_sync_enabled": True,
                    "contact_sync_book_id": "default",
                    "contact_sync_group_name": "Smith-Jones (TheSpecialWedding)",
                    "owner_planner_email": "planner@example.com",
                    "owner_planner_id": "planner-1",
                    "user_id": "user-1",
                    "user_email": "planner@example.com",
                    "provider": "google",
                }
            ]
        ),
        syncs=_Collection(),
        provider=provider,
    )

    await service.mirror_vendor_to_aurinko(str(vendor_id))

    body = provider.client.created[0]["body"]
    assert body["givenName"] == "Ada"
    assert body["surname"] == "Lovelace"
    assert body["company"] == "Lens & Light"
    assert body["emails"] == [{"address": "ada@example.com", "type": "work"}]
    assert body["phones"] == [{"number": "+15551230000", "type": "work"}]
    assert body["urls"] == [{"url": "https://lens.example.com", "type": "work"}]
    assert body["keywords"] == [
        "Smith-Jones (TheSpecialWedding)",
        "TheSpecialWedding",
        "vendor",
    ]
    sync_doc = service.syncs_collection.docs[0]
    assert sync_doc["source_type"] == "vendor"
    assert sync_doc["source_id"] == str(vendor_id)
    assert sync_doc["connection_id"] == str(connection_id)
    assert sync_doc["aurinko_contact_id"] == "contact-1"
    assert sync_doc["sync_direction"] == CalendarSyncDirection.OUTBOUND.value
    assert sync_doc["sync_status"] == CalendarSyncStatusValue.SYNCED.value


@pytest.mark.asyncio
async def test_mirror_couple_uses_wedding_owner_scope_and_couple_user_email() -> None:
    connection_id = ObjectId()
    wedding_id = "wedding-1"
    provider = _Provider()
    service = _service(
        weddings=_Collection(
            [
                {
                    "_id": wedding_id,
                    "couple_names": "Grace Hopper",
                    "date": "2026-09-20",
                    "assigned_planner_id": "planner-1",
                    "assigned_planner_email": "planner@example.com",
                    "status": "active",
                }
            ]
        ),
        couples=_Collection(
            [
                {
                    "_id": ObjectId(),
                    "wedding_id": wedding_id,
                    "email": "grace@example.com",
                }
            ]
        ),
        connections=_Collection(
            [
                {
                    "_id": connection_id,
                    "connection_status": CalendarConnectionStatus.ACTIVE.value,
                    "contact_sync_enabled": True,
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                    "provider": "google",
                }
            ]
        ),
        syncs=_Collection(),
        provider=provider,
    )

    await service.mirror_couple_to_aurinko(wedding_id)

    body = provider.client.created[0]["body"]
    assert body["givenName"] == "Grace"
    assert body["surname"] == "Hopper"
    assert body["company"] == "Wedding client"
    assert body["emails"] == [{"address": "grace@example.com", "type": "work"}]
    assert body["keywords"] == [
        "planner@example.com (TheSpecialWedding)",
        "TheSpecialWedding",
        "couple",
    ]
    sync_doc = service.syncs_collection.docs[0]
    assert sync_doc["source_type"] == "wedding"
    assert sync_doc["source_id"] == wedding_id
    assert sync_doc["aurinko_contact_id"] == "contact-1"


@pytest.mark.asyncio
async def test_unmirror_source_deletes_contact_and_orphans_sync_record() -> None:
    connection_id = ObjectId()
    provider = _Provider()
    service = _service(
        connections=_Collection([{"_id": connection_id}]),
        syncs=_Collection(
            [
                {
                    "_id": ObjectId(),
                    "source_type": "vendor",
                    "source_id": "vendor-1",
                    "connection_id": str(connection_id),
                    "aurinko_contact_id": "contact-9",
                    "sync_status": CalendarSyncStatusValue.SYNCED.value,
                }
            ]
        ),
        provider=provider,
    )

    await service.unmirror_source(source_type="vendor", source_id="vendor-1")

    assert provider.client.deleted == [
        {"account_token": f"token:{connection_id}", "contact_id": "contact-9"}
    ]
    sync_doc = service.syncs_collection.docs[0]
    assert sync_doc["sync_status"] == CalendarSyncStatusValue.ORPHANED.value
    assert sync_doc["last_error"] == "Source contact removed"
