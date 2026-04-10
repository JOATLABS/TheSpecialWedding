"""
Backfill vendor contract security and lineage fields.

Usage:
  python scripts/backfill_vendor_contract_security_fields.py
  python scripts/backfill_vendor_contract_security_fields.py --apply
  python scripts/backfill_vendor_contract_security_fields.py --apply --drop-plaintext-token
"""

import argparse
import asyncio
import hashlib
import hmac
import logging
import os
import sys
from collections import defaultdict
from typing import Any, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import mongo
from app.core.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def hash_vendor_contract_access_token(raw_token: str) -> str:
    secret_key = settings.secret_key
    if not secret_key:
        raise RuntimeError("SECRET_KEY is required for vendor contract token hashing")

    return hmac.new(
        secret_key.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_vendor_contract_security_backfill_ops(
    document: Dict[str, Any], *, drop_plaintext_token: bool = False
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    set_updates: Dict[str, Any] = {}
    unset_updates: Dict[str, Any] = {}

    contract_id = str(document["_id"])

    if not document.get("root_contract_id"):
        set_updates["root_contract_id"] = contract_id

    if not document.get("version_number"):
        set_updates["version_number"] = 1

    if not document.get("contract_kind"):
        set_updates["contract_kind"] = "original"

    if "is_current_version" not in document:
        set_updates["is_current_version"] = not bool(
            document.get("superseded_by_contract_id") or document.get("superseded_at")
        )

    raw_token = document.get("access_token")
    if raw_token and not document.get("access_token_hash"):
        set_updates["access_token_hash"] = hash_vendor_contract_access_token(raw_token)
    elif "access_token_hash" not in document:
        set_updates["access_token_hash"] = None

    if "token_revoked_at" not in document:
        set_updates["token_revoked_at"] = None

    if "token_last_sent_at" not in document:
        set_updates["token_last_sent_at"] = document.get("sent_at")

    if "token_last_viewed_at" not in document:
        set_updates["token_last_viewed_at"] = document.get("viewed_at")

    if drop_plaintext_token and raw_token:
        unset_updates["access_token"] = ""

    return set_updates, unset_updates


async def detect_lineage_conflicts(collection) -> Dict[str, list[dict]]:
    duplicate_version_groups: dict[tuple[str, int], list[Any]] = defaultdict(list)
    current_version_groups: dict[str, list[Any]] = defaultdict(list)

    async for document in collection.find({}):
        normalized_root_contract_id = document.get("root_contract_id") or str(document["_id"])
        normalized_version_number = document.get("version_number") or 1
        normalized_is_current_version = document.get("is_current_version")
        if normalized_is_current_version is None:
            normalized_is_current_version = not bool(
                document.get("superseded_by_contract_id") or document.get("superseded_at")
            )

        duplicate_version_groups[
            (normalized_root_contract_id, normalized_version_number)
        ].append(document["_id"])

        if normalized_is_current_version:
            current_version_groups[normalized_root_contract_id].append(document["_id"])

    duplicate_versions = [
        {
            "_id": {
                "root_contract_id": root_contract_id,
                "version_number": version_number,
            },
            "ids": ids,
            "count": len(ids),
        }
        for (root_contract_id, version_number), ids in duplicate_version_groups.items()
        if len(ids) > 1
    ]

    multiple_current = [
        {
            "_id": root_contract_id,
            "ids": ids,
            "count": len(ids),
        }
        for root_contract_id, ids in current_version_groups.items()
        if len(ids) > 1
    ]

    return {
        "duplicate_versions": duplicate_versions,
        "multiple_current_versions": multiple_current,
    }


async def run_backfill(*, apply: bool, drop_plaintext_token: bool, verbose: bool) -> int:
    if not await mongo.test_connection():
        logger.error("MongoDB connection failed")
        return 1

    collection = mongo.db["vendor_contracts"]
    conflicts = await detect_lineage_conflicts(collection)

    if conflicts["duplicate_versions"]:
        logger.warning(
            "Found %d duplicate root/version groups",
            len(conflicts["duplicate_versions"]),
        )
    if conflicts["multiple_current_versions"]:
        logger.warning(
            "Found %d root chains with multiple current versions",
            len(conflicts["multiple_current_versions"]),
        )

    if apply and (conflicts["duplicate_versions"] or conflicts["multiple_current_versions"]):
        logger.error("Aborting apply mode until lineage conflicts are resolved.")
        return 1

    processed = 0
    changed = 0
    hashed = 0
    dropped = 0

    async for document in collection.find({}):
        processed += 1
        set_updates, unset_updates = build_vendor_contract_security_backfill_ops(
            document,
            drop_plaintext_token=drop_plaintext_token,
        )

        if not set_updates and not unset_updates:
            continue

        changed += 1
        if "access_token_hash" in set_updates and document.get("access_token"):
            hashed += 1
        if "access_token" in unset_updates:
            dropped += 1

        if verbose or not apply:
            logger.info(
                "%s contract %s set=%s unset=%s",
                "Would update" if not apply else "Updating",
                document["_id"],
                sorted(set_updates.keys()),
                sorted(unset_updates.keys()),
            )

        if not apply:
            continue

        update_doc: Dict[str, Any] = {}
        if set_updates:
            update_doc["$set"] = set_updates
        if unset_updates:
            update_doc["$unset"] = unset_updates
        await collection.update_one({"_id": document["_id"]}, update_doc)

    logger.info("Processed %d vendor contracts", processed)
    logger.info("Contracts needing updates: %d", changed)
    logger.info("Contracts hashed from plaintext token: %d", hashed)
    logger.info("Contracts dropping plaintext token: %d", dropped)
    if not apply:
        logger.info("Dry run only. Re-run with --apply to write the backfill.")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill vendor contract security and lineage fields"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the backfill instead of reporting only.",
    )
    parser.add_argument(
        "--drop-plaintext-token",
        action="store_true",
        help="Unset legacy plaintext access_token after hash backfill.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log each affected contract.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exit_code = asyncio.run(
        run_backfill(
            apply=args.apply,
            drop_plaintext_token=args.drop_plaintext_token,
            verbose=args.verbose,
        )
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
