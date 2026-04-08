"""
Ownership drift report/backfill for planner-owned weddings, couples, and team records.

Usage:
    python -m app.scripts.report_planner_ownership_drift
    python -m app.scripts.report_planner_ownership_drift --apply
    python -m app.scripts.report_planner_ownership_drift --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

from app.core.config import settings
from app.utils.planner_ownership import (
    normalize_planner_email,
    normalize_planner_id,
    normalize_query_id,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class OwnerResolver:
    def __init__(self, db):
        self.users = db["users"]
        self._email_to_id: dict[str, Optional[str]] = {}
        self._id_to_email: dict[str, Optional[str]] = {}

    async def resolve(
        self, planner_id: Any = None, planner_email: Any = None
    ) -> tuple[Optional[str], Optional[str]]:
        normalized_id = normalize_planner_id(planner_id)
        normalized_email = normalize_planner_email(planner_email)

        if normalized_id and not normalized_email:
            normalized_email = await self.email_for_id(normalized_id)
        elif normalized_email and not normalized_id:
            normalized_id = await self.id_for_email(normalized_email)

        return normalized_id, normalized_email

    async def id_for_email(self, email: str) -> Optional[str]:
        normalized_email = normalize_planner_email(email)
        if not normalized_email:
            return None
        if normalized_email not in self._email_to_id:
            user = await self.users.find_one({"email": normalized_email}, {"_id": 1})
            self._email_to_id[normalized_email] = (
                normalize_planner_id(user.get("_id")) if user else None
            )
        return self._email_to_id[normalized_email]

    async def email_for_id(self, planner_id: str) -> Optional[str]:
        normalized_id = normalize_planner_id(planner_id)
        if not normalized_id:
            return None
        if normalized_id not in self._id_to_email:
            user = await self.users.find_one(
                {"_id": normalize_query_id(normalized_id)},
                {"email": 1},
            )
            self._id_to_email[normalized_id] = (
                normalize_planner_email(user.get("email")) if user else None
            )
        return self._id_to_email[normalized_id]


async def build_wedding_owner_map(
    db, resolver: OwnerResolver, apply: bool, verbose: bool
):
    weddings = db["weddings"]
    counters = Counter()
    wedding_owner_map: dict[str, tuple[Optional[str], Optional[str]]] = {}
    updates: list[UpdateOne] = []

    async for wedding in weddings.find(
        {},
        {
            "_id": 1,
            "assigned_planner_id": 1,
            "assigned_planner_email": 1,
        },
    ):
        counters["weddings_scanned"] += 1
        wedding_id = str(wedding["_id"])
        stored_id = normalize_planner_id(wedding.get("assigned_planner_id"))
        stored_email = normalize_planner_email(wedding.get("assigned_planner_email"))
        resolved_id, resolved_email = await resolver.resolve(stored_id, stored_email)

        if not stored_id:
            counters["weddings_missing_owner_id"] += 1
        if not stored_email:
            counters["weddings_missing_owner_email"] += 1
        if not resolved_id and not resolved_email:
            counters["weddings_unresolved"] += 1
            wedding_owner_map[wedding_id] = (None, None)
            if verbose:
                logger.info(
                    "UNRESOLVED wedding owner: wedding=%s stored_id=%s stored_email=%s",
                    wedding_id,
                    stored_id,
                    stored_email,
                )
            continue

        wedding_owner_map[wedding_id] = (resolved_id, resolved_email)
        set_fields: dict[str, str] = {}
        if resolved_id and resolved_id != stored_id:
            set_fields["assigned_planner_id"] = resolved_id
        if resolved_email and resolved_email != stored_email:
            set_fields["assigned_planner_email"] = resolved_email

        if set_fields:
            counters["weddings_drifted"] += 1
            if verbose:
                logger.info("WEDDING DRIFT: wedding=%s set=%s", wedding_id, set_fields)
            if apply:
                updates.append(
                    UpdateOne(
                        {"_id": wedding["_id"]},
                        {"$set": set_fields},
                    )
                )

    if apply and updates:
        result = await weddings.bulk_write(updates)
        counters["weddings_updated"] = result.modified_count

    return wedding_owner_map, counters


async def sync_couples(
    db,
    wedding_owner_map: dict[str, tuple[Optional[str], Optional[str]]],
    apply: bool,
    verbose: bool,
):
    couples = db["couple_users"]
    counters = Counter()
    updates: list[UpdateOne] = []

    async for couple in couples.find(
        {},
        {"_id": 1, "wedding_id": 1, "planner_id": 1, "planner_email": 1},
    ):
        counters["couples_scanned"] += 1
        wedding_id = couple.get("wedding_id")
        if not wedding_id:
            counters["couples_missing_wedding"] += 1
            continue

        resolved_id, resolved_email = wedding_owner_map.get(
            str(wedding_id), (None, None)
        )
        if not resolved_id and not resolved_email:
            counters["couples_owner_unresolved"] += 1
            continue

        stored_id = normalize_planner_id(couple.get("planner_id"))
        stored_email = normalize_planner_email(couple.get("planner_email"))
        set_fields: dict[str, Any] = {}
        if resolved_id and resolved_id != stored_id:
            set_fields["planner_id"] = resolved_id
        if resolved_email and resolved_email != stored_email:
            set_fields["planner_email"] = resolved_email

        if set_fields:
            counters["couples_drifted"] += 1
            if verbose:
                logger.info(
                    "COUPLE DRIFT: couple=%s wedding=%s set=%s",
                    couple["_id"],
                    wedding_id,
                    {k: v for k, v in set_fields.items() if k != "updated_at"},
                )
            if apply:
                set_fields["updated_at"] = datetime.now(timezone.utc)
                updates.append(
                    UpdateOne(
                        {"_id": couple["_id"]},
                        {"$set": set_fields},
                    )
                )

    if apply and updates:
        result = await couples.bulk_write(updates)
        counters["couples_updated"] = result.modified_count

    return counters


async def sync_team_members(db, resolver: OwnerResolver, apply: bool, verbose: bool):
    team_members = db["team_members"]
    counters = Counter()
    updates: list[UpdateOne] = []

    async for member in team_members.find(
        {},
        {"_id": 1, "owner_id": 1, "owner_email": 1},
    ):
        counters["team_members_scanned"] += 1
        stored_id = normalize_planner_id(member.get("owner_id"))
        stored_email = normalize_planner_email(member.get("owner_email"))
        resolved_id, resolved_email = await resolver.resolve(stored_id, stored_email)

        if not resolved_id and not resolved_email:
            counters["team_members_owner_unresolved"] += 1
            continue

        set_fields: dict[str, str] = {}
        if resolved_id and resolved_id != stored_id:
            set_fields["owner_id"] = resolved_id
        if resolved_email and resolved_email != stored_email:
            set_fields["owner_email"] = resolved_email

        if set_fields:
            counters["team_members_drifted"] += 1
            if verbose:
                logger.info("TEAM DRIFT: member=%s set=%s", member["_id"], set_fields)
            if apply:
                updates.append(
                    UpdateOne(
                        {"_id": member["_id"]},
                        {"$set": set_fields},
                    )
                )

    if apply and updates:
        result = await team_members.bulk_write(updates)
        counters["team_members_updated"] = result.modified_count

    return counters


async def sync_team_member_users(db, apply: bool, verbose: bool):
    users = db["users"]
    team_members = db["team_members"]
    counters = Counter()
    updates: list[UpdateOne] = []

    async for user in users.find(
        {"role": "team_member", "team_member_id": {"$exists": True, "$ne": None}},
        {"_id": 1, "email": 1, "team_member_id": 1, "parent_planner_id": 1},
    ):
        counters["team_users_scanned"] += 1
        team_member_id = user.get("team_member_id")
        if not team_member_id:
            continue

        team_doc = await team_members.find_one(
            {"_id": normalize_query_id(team_member_id)},
            {"owner_id": 1},
        )
        if not team_doc:
            counters["team_users_missing_membership"] += 1
            continue

        expected_owner_id = normalize_planner_id(team_doc.get("owner_id"))
        current_owner_id = normalize_planner_id(user.get("parent_planner_id"))
        if not expected_owner_id:
            counters["team_users_owner_unresolved"] += 1
            continue

        if current_owner_id != expected_owner_id:
            counters["team_users_drifted"] += 1
            if verbose:
                logger.info(
                    "TEAM USER DRIFT: user=%s current=%s expected=%s",
                    user.get("email") or user["_id"],
                    current_owner_id,
                    expected_owner_id,
                )
            if apply:
                updates.append(
                    UpdateOne(
                        {"_id": user["_id"]},
                        {"$set": {"parent_planner_id": expected_owner_id}},
                    )
                )

    if apply and updates:
        result = await users.bulk_write(updates)
        counters["team_users_updated"] = result.modified_count

    return counters


async def run(apply: bool, verbose: bool):
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    resolver = OwnerResolver(db)

    logger.info("=" * 72)
    logger.info("Planner Ownership Drift Report")
    logger.info("Mode: %s", "APPLY" if apply else "DRY RUN")
    logger.info("Database: %s", settings.MONGO_DB)
    logger.info("=" * 72)

    wedding_owner_map, wedding_counters = await build_wedding_owner_map(
        db, resolver, apply, verbose
    )
    couple_counters = await sync_couples(db, wedding_owner_map, apply, verbose)
    team_counters = await sync_team_members(db, resolver, apply, verbose)
    team_user_counters = await sync_team_member_users(db, apply, verbose)

    counters = Counter()
    counters.update(wedding_counters)
    counters.update(couple_counters)
    counters.update(team_counters)
    counters.update(team_user_counters)

    logger.info("")
    logger.info("Summary")
    logger.info("-" * 72)
    logger.info(
        "Weddings: scanned=%d missing_id=%d missing_email=%d drifted=%d unresolved=%d updated=%d",
        counters["weddings_scanned"],
        counters["weddings_missing_owner_id"],
        counters["weddings_missing_owner_email"],
        counters["weddings_drifted"],
        counters["weddings_unresolved"],
        counters["weddings_updated"],
    )
    logger.info(
        "Couples: scanned=%d drifted=%d unresolved=%d missing_wedding=%d updated=%d",
        counters["couples_scanned"],
        counters["couples_drifted"],
        counters["couples_owner_unresolved"],
        counters["couples_missing_wedding"],
        counters["couples_updated"],
    )
    logger.info(
        "Team members: scanned=%d drifted=%d unresolved=%d updated=%d",
        counters["team_members_scanned"],
        counters["team_members_drifted"],
        counters["team_members_owner_unresolved"],
        counters["team_members_updated"],
    )
    logger.info(
        "Team-member users: scanned=%d drifted=%d missing_membership=%d unresolved=%d updated=%d",
        counters["team_users_scanned"],
        counters["team_users_drifted"],
        counters["team_users_missing_membership"],
        counters["team_users_owner_unresolved"],
        counters["team_users_updated"],
    )
    logger.info("=" * 72)
    if not apply:
        logger.info("Dry run only. Re-run with --apply to write the safe backfills.")

    client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Report and backfill planner ownership drift"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write safe ownership backfills instead of reporting only.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log individual drifted records.",
    )
    args = parser.parse_args()
    asyncio.run(run(apply=args.apply, verbose=args.verbose))


if __name__ == "__main__":
    main()
