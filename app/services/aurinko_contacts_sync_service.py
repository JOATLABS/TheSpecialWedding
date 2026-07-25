"""One-way mirror of planner vendors and couples into Aurinko Contacts."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException

from app.core.database import mongo
from app.models.calendar_connection import CalendarConnectionStatus
from app.models.calendar_sync import CalendarSyncDirection, CalendarSyncStatusValue
from app.services.calendar_provider_service import (
    _redact_sensitive,
    calendar_provider_service,
)

logger = logging.getLogger(__name__)


class AurinkoContactsSyncService:
    """Mirror authoritative planner contact data out to connected address books."""

    def __init__(self) -> None:
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_contact_sync_records_collection()
        self.vendor_profiles = mongo.get_collection("vendor_profiles")
        self.weddings_collection = mongo.get_weddings_collection()
        self.couple_users_collection = mongo.get_couple_users_collection()
        self.provider = calendar_provider_service

    def _source_query(
        self, source_type: str, source_id: str, connection_id: str
    ) -> dict:
        return {
            "source_type": source_type,
            "source_id": source_id,
            "connection_id": connection_id,
        }

    def _external_id(self, payload: dict[str, Any]) -> str | None:
        value = payload.get("id") or payload.get("contactId")
        return str(value) if value else None

    def _external_etag(self, payload: dict[str, Any]) -> str | None:
        value = payload.get("etag") or payload.get("changeKey")
        return str(value) if value else None

    def _account_contact_book_key(self, connection: dict[str, Any]) -> tuple[str, str]:
        account_key = str(connection.get("aurinko_account_id") or "").strip()
        if not account_key:
            account_key = "|".join(
                [
                    str(connection.get("user_id") or ""),
                    str(connection.get("provider") or ""),
                    str(connection.get("provider_account_email") or ""),
                ]
            )
        book_id = str(connection.get("contact_sync_book_id") or "default").strip()
        return account_key, book_id

    def _dedupe_account_contact_book_connections(
        self, connections: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return one enabled row per connected account/contact-book resource."""
        sorted_connections = sorted(
            connections,
            key=lambda row: (
                not bool(row.get("is_default_write_target")),
                str(row.get("calendar_name") or row.get("_id") or ""),
            ),
        )
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for connection in sorted_connections:
            key = self._account_contact_book_key(connection)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(connection)
        return deduped

    def _name_parts(self, display_name: str) -> tuple[str, str]:
        parts = [part for part in display_name.strip().split() if part]
        if not parts:
            return "Wedding", "Contact"
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    def _email_entry(self, email: Any) -> list[dict[str, Any]]:
        if not email:
            return []
        return [{"address": str(email), "type": "work"}]

    def _phone_entry(self, phone: Any) -> list[dict[str, Any]]:
        if not phone:
            return []
        return [{"number": str(phone), "type": "work"}]

    def _label_keywords(
        self, connection: dict[str, Any], source_type: str
    ) -> list[str]:
        label = connection.get(
            "contact_sync_group_name"
        ) or self.provider._default_contact_group_name(connection)
        return list(dict.fromkeys([label, "TheSpecialWedding", source_type]))

    def _vendor_body(
        self, vendor: dict[str, Any], connection: dict[str, Any]
    ) -> dict[str, Any] | None:
        display_name = (
            vendor.get("contact_name") or vendor.get("business_name") or ""
        ).strip()
        if not display_name and not vendor.get("email"):
            return None
        given, surname = self._name_parts(display_name or vendor.get("email", ""))
        body: dict[str, Any] = {
            "givenName": given,
            "surname": surname,
            "company": vendor.get("business_name"),
            "jobTitle": vendor.get("service_category")
            or vendor.get("custom_service_category"),
            "notes": vendor.get("service_description"),
            "emails": self._email_entry(vendor.get("email")),
            "phones": self._phone_entry(vendor.get("phone")),
            "keywords": self._label_keywords(connection, "vendor"),
        }
        if vendor.get("website"):
            body["urls"] = [{"url": vendor["website"], "type": "work"}]
        address_parts = [
            vendor.get("address"),
            vendor.get("city"),
            vendor.get("state"),
            vendor.get("postal_code"),
            vendor.get("country"),
        ]
        if any(address_parts):
            body["addresses"] = [
                {
                    "street": vendor.get("address"),
                    "city": vendor.get("city"),
                    "state": vendor.get("state"),
                    "postalCode": vendor.get("postal_code"),
                    "country": vendor.get("country"),
                    "type": "work",
                }
            ]
        return {
            key: value for key, value in body.items() if value not in (None, [], "")
        }

    async def _couple_email(self, wedding: dict[str, Any]) -> str | None:
        for field in ("email", "couple_email", "contact_email", "reminder_from_email"):
            if wedding.get(field):
                return str(wedding[field])
        couple_user = await self.couple_users_collection.find_one(
            {"wedding_id": str(wedding.get("_id"))}
        )
        if couple_user and couple_user.get("email"):
            return str(couple_user["email"])
        return None

    async def _couple_body(
        self, wedding: dict[str, Any], connection: dict[str, Any]
    ) -> dict[str, Any] | None:
        display_name = str(wedding.get("couple_names") or "").strip()
        email = await self._couple_email(wedding)
        if not display_name and not email:
            return None
        given, surname = self._name_parts(display_name or email or "")
        notes = "Wedding couple"
        if wedding.get("date"):
            notes = f"Wedding couple. Wedding date: {wedding['date']}"
        return {
            "givenName": given,
            "surname": surname,
            "company": "Wedding client",
            "notes": notes,
            "emails": self._email_entry(email),
            "keywords": self._label_keywords(connection, "couple"),
        }

    async def _enabled_connections(
        self,
        *,
        owner_planner_email: str | None,
        owner_planner_id: str | None = None,
        connection_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "connection_status": CalendarConnectionStatus.ACTIVE.value,
            "contact_sync_enabled": True,
        }
        if owner_planner_id:
            query["owner_planner_id"] = str(owner_planner_id)
        elif owner_planner_email:
            query["owner_planner_email"] = owner_planner_email
        if connection_id:
            query["_id"] = ObjectId(connection_id)
        connections = await self.connections_collection.find(query).to_list(length=100)
        return self._dedupe_account_contact_book_connections(connections)

    async def _mirror_body(
        self,
        *,
        source_type: str,
        source_id: str,
        body: dict[str, Any],
        connection: dict[str, Any],
    ) -> None:
        connection_id = str(connection["_id"])
        token = await self.provider._account_token_for_connection(connection)
        if not token:
            return
        sync_doc = await self.syncs_collection.find_one(
            self._source_query(source_type, source_id, connection_id)
        )
        now = datetime.now(UTC)
        try:
            if sync_doc and sync_doc.get("aurinko_contact_id"):
                payload = await self.provider.client.update_contact(
                    account_token=token,
                    contact_id=str(sync_doc["aurinko_contact_id"]),
                    body=body,
                    etag=sync_doc.get("last_external_etag"),
                )
                aurinko_contact_id = str(sync_doc["aurinko_contact_id"])
            else:
                payload = await self.provider.client.create_contact(
                    account_token=token,
                    body=body,
                )
                aurinko_contact_id = self._external_id(payload)
            if not aurinko_contact_id:
                raise RuntimeError("Aurinko contact response did not include an id")
            await self.syncs_collection.update_one(
                self._source_query(source_type, source_id, connection_id),
                {
                    "$set": {
                        "source_type": source_type,
                        "source_id": source_id,
                        "connection_id": connection_id,
                        "owner_planner_id": connection.get("owner_planner_id"),
                        "owner_planner_email": connection.get("owner_planner_email"),
                        "target_user_id": connection.get("user_id"),
                        "target_user_email": connection.get("user_email"),
                        "provider": connection.get("provider"),
                        "aurinko_contact_id": aurinko_contact_id,
                        "contact_sync_book_id": connection.get("contact_sync_book_id")
                        or "default",
                        "contact_sync_group_id": connection.get(
                            "contact_sync_group_id"
                        ),
                        "sync_direction": CalendarSyncDirection.OUTBOUND.value,
                        "sync_status": CalendarSyncStatusValue.SYNCED.value,
                        "last_external_etag": self._external_etag(payload),
                        "last_sync_at": now,
                        "last_error": None,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.warning(
                "Aurinko contact mirror failed for %s %s on connection %s: %s",
                source_type,
                source_id,
                connection_id,
                _redact_sensitive(exc),
            )
            await self.syncs_collection.update_one(
                self._source_query(source_type, source_id, connection_id),
                {
                    "$set": {
                        "source_type": source_type,
                        "source_id": source_id,
                        "connection_id": connection_id,
                        "owner_planner_id": connection.get("owner_planner_id"),
                        "owner_planner_email": connection.get("owner_planner_email"),
                        "sync_status": CalendarSyncStatusValue.FAILED.value,
                        "last_error": _redact_sensitive(exc),
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )

    async def mirror_vendor_to_aurinko(
        self, vendor_id: str, connection_id: str | None = None
    ) -> None:
        vendor = await self.vendor_profiles.find_one({"_id": ObjectId(vendor_id)})
        if not vendor or not vendor.get("is_active", True):
            return
        connections = await self._enabled_connections(
            owner_planner_email=vendor.get("created_by"), connection_id=connection_id
        )
        for connection in connections:
            body = self._vendor_body(vendor, connection)
            if body:
                await self._mirror_body(
                    source_type="vendor",
                    source_id=vendor_id,
                    body=body,
                    connection=connection,
                )

    async def mirror_couple_to_aurinko(
        self, wedding_id: str, connection_id: str | None = None
    ) -> None:
        wedding = await self.weddings_collection.find_one({"_id": wedding_id})
        if not wedding:
            return
        connections = await self._enabled_connections(
            owner_planner_email=wedding.get("assigned_planner_email"),
            owner_planner_id=wedding.get("assigned_planner_id"),
            connection_id=connection_id,
        )
        for connection in connections:
            body = await self._couple_body(wedding, connection)
            if body:
                await self._mirror_body(
                    source_type="wedding",
                    source_id=wedding_id,
                    body=body,
                    connection=connection,
                )

    async def unmirror_source(
        self,
        *,
        source_type: str,
        source_id: str,
        connection_id: str | None = None,
    ) -> None:
        query: dict[str, Any] = {"source_type": source_type, "source_id": source_id}
        if connection_id:
            query["connection_id"] = connection_id
        sync_rows = await self.syncs_collection.find(query).to_list(length=100)
        now = datetime.now(UTC)
        for sync_doc in sync_rows:
            connection = None
            if ObjectId.is_valid(str(sync_doc.get("connection_id"))):
                connection = await self.connections_collection.find_one(
                    {"_id": ObjectId(str(sync_doc["connection_id"]))}
                )
            if connection and sync_doc.get("aurinko_contact_id"):
                token = await self.provider._account_token_for_connection(connection)
                if token:
                    try:
                        await self.provider.client.delete_contact(
                            account_token=token,
                            contact_id=str(sync_doc["aurinko_contact_id"]),
                        )
                    except Exception as exc:
                        logger.warning(
                            "Aurinko contact delete failed for %s %s: %s",
                            source_type,
                            source_id,
                            _redact_sensitive(exc),
                        )
                        await self.syncs_collection.update_one(
                            {"_id": sync_doc["_id"]},
                            {
                                "$set": {
                                    "sync_status": CalendarSyncStatusValue.FAILED.value,
                                    "last_error": _redact_sensitive(exc),
                                    "updated_at": now,
                                }
                            },
                        )
                        return
            await self.syncs_collection.update_one(
                {"_id": sync_doc["_id"]},
                {
                    "$set": {
                        "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                        "last_error": "Source contact removed",
                        "updated_at": now,
                    }
                },
            )

    async def bulk_mirror_for_connection(self, connection_id: str) -> dict[str, int]:
        connection = await self.connections_collection.find_one(
            {"_id": ObjectId(connection_id)}
        )
        if not connection:
            raise HTTPException(status_code=404, detail="Calendar connection not found")
        if not connection.get("contact_sync_enabled"):
            raise HTTPException(status_code=400, detail="Contact sync is not enabled")

        vendor_count = 0
        wedding_count = 0
        vendors = await self.vendor_profiles.find(
            {
                "created_by": connection.get("owner_planner_email"),
                "is_active": True,
            }
        ).to_list(length=500)
        for vendor in vendors:
            body = self._vendor_body(vendor, connection)
            if not body:
                continue
            await self._mirror_body(
                source_type="vendor",
                source_id=str(vendor["_id"]),
                body=body,
                connection=connection,
            )
            vendor_count += 1

        wedding_query: dict[str, Any] = {"status": {"$ne": "deleted"}}
        if connection.get("owner_planner_id"):
            wedding_query["assigned_planner_id"] = str(connection["owner_planner_id"])
        else:
            wedding_query["assigned_planner_email"] = connection.get(
                "owner_planner_email"
            )
        weddings = await self.weddings_collection.find(wedding_query).to_list(
            length=500
        )
        for wedding in weddings:
            body = await self._couple_body(wedding, connection)
            if not body:
                continue
            await self._mirror_body(
                source_type="wedding",
                source_id=str(wedding["_id"]),
                body=body,
                connection=connection,
            )
            wedding_count += 1
        return {"vendors": vendor_count, "weddings": wedding_count}

    async def acknowledge_external_contact_delivery(
        self,
        *,
        aurinko_account_id: str,
        change_count: int,
    ) -> None:
        logger.info(
            "Aurinko contacts delivery acknowledged without inbound mutation: "
            "account=%s changes=%d",
            aurinko_account_id,
            change_count,
        )


aurinko_contacts_sync_service = AurinkoContactsSyncService()
