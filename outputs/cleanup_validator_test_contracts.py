"""
One-shot cleanup for the polluted draft contracts created during the live
verification run that surfaced the deposit-exceeds-total API-boundary bug.

Two draft contracts were created during the test:
  - contract_title="Photographer Services Contract"
  - status="draft"
  - total_amount=1000
  - vendor_name="Configured Test Vendor"
  - is_soft_deleted not True

This script soft-deletes the most-recent two matches (sorted by created_at DESC)
and prints what it touched. It does NOT hard-delete — soft-delete is consistent
with how the rest of the contract collection handles archival.

Run:
    python outputs/cleanup_validator_test_contracts.py            # dry-run
    python outputs/cleanup_validator_test_contracts.py --execute  # actually delete

Requires the same env the app uses (MONGODB_URL, MONGODB_NAME).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Load .env from the project root so the script doesn't depend on the
# user pre-sourcing it (the repo's .env contains unquoted values with
# spaces, which breaks `source .env` under zsh).
try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:
    load_dotenv = None
if load_dotenv:
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


QUERY = {
    "contract_title": "Photographer Services Contract",
    "status": "draft",
    "total_amount": 1000,
    "vendor_name": "Configured Test Vendor",
    "is_soft_deleted": {"$ne": True},
}


async def main(execute: bool) -> int:
    # Match the env-var fallback chain the app uses (settings.py reads both
    # MONGO_URI/MONGO_NAME and MONGODB_URI/MONGODB_NAME). .env in this repo
    # uses the MONGO_* names; the original script only checked MONGODB_*.
    mongo_url = (
        os.environ.get("MONGODB_URL")
        or os.environ.get("MONGODB_URI")
        or os.environ.get("MONGO_URI")
        or "mongodb://localhost:27017"
    )
    mongo_name = (
        os.environ.get("MONGODB_NAME")
        or os.environ.get("MONGO_NAME")
        or os.environ.get("MONGO_DB")
    )
    if not mongo_name:
        print(
            "Set one of MONGODB_NAME / MONGO_NAME / MONGO_DB in env; aborting",
            file=sys.stderr,
        )
        return 2

    client = AsyncIOMotorClient(mongo_url)
    db = client[mongo_name]
    coll = db["vendor_contracts"]

    # Sort by created_at DESC and take the most recent 2.
    cursor = coll.find(QUERY).sort("created_at", -1).limit(2)
    candidates = await cursor.to_list(length=2)

    if not candidates:
        print("No matching contracts found.")
        return 0

    print(f"Found {len(candidates)} match(es):")
    for doc in candidates:
        print(
            f"  _id={doc['_id']}  created_at={doc.get('created_at')}  "
            f"deposit_amount={doc.get('deposit_amount')}  "
            f"created_by={doc.get('created_by')}"
        )

    if not execute:
        print("\nDry run. Re-run with --execute to soft-delete these contracts.")
        return 0

    ids = [doc["_id"] for doc in candidates]
    now = datetime.now(timezone.utc)
    result = await coll.update_many(
        {"_id": {"$in": ids}},
        {
            "$set": {
                "is_soft_deleted": True,
                "soft_deleted_at": now,
                "soft_delete_reason": "validator-test-pollution-cleanup",
            }
        },
    )
    print(f"\nSoft-deleted {result.modified_count} contract(s).")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually mark the contracts as soft-deleted (default is dry-run).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(execute=args.execute)))
