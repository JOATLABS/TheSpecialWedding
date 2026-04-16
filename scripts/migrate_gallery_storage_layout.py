#!/usr/bin/env python3
"""Copy legacy wedding gallery objects into planner-scoped prefixes and update wedding references."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botocore.exceptions import ClientError  # noqa: E402

from app.core.database import mongo  # noqa: E402
from app.services.gallery_media_service import GalleryUploadService  # noqa: E402

GALLERY_FOLDERS = ("gallery", "our-story", "wedding-party")


def _is_relative_storage_key(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value != ""
        and not value.startswith(("http://", "https://"))
    )


def _collect_reference_updates(
    wedding: dict[str, Any], key_map: dict[str, str]
) -> dict[str, str]:
    updates: dict[str, str] = {}

    featured_image = wedding.get("featured_image")
    if _is_relative_storage_key(featured_image) and featured_image in key_map:
        updates["featured_image"] = key_map[featured_image]

    our_story = wedding.get("our_story")
    if isinstance(our_story, dict):
        story_image = our_story.get("image_url")
        if _is_relative_storage_key(story_image) and story_image in key_map:
            updates["our_story.image_url"] = key_map[story_image]

    wedding_party = wedding.get("wedding_party") or []
    if isinstance(wedding_party, list):
        for index, member in enumerate(wedding_party):
            if not isinstance(member, dict):
                continue
            member_image = member.get("image_url")
            if _is_relative_storage_key(member_image) and member_image in key_map:
                updates[f"wedding_party.{index}.image_url"] = key_map[member_image]

    return updates


def _object_exists(service: GalleryUploadService, key: str) -> bool:
    try:
        service.s3.head_object(Bucket=service.bucket_name, Key=key)
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def _copy_object(
    service: GalleryUploadService, source_key: str, destination_key: str
) -> None:
    service.s3.copy_object(
        Bucket=service.bucket_name,
        CopySource={"Bucket": service.bucket_name, "Key": source_key},
        Key=destination_key,
    )


def _delete_object(service: GalleryUploadService, key: str) -> None:
    service.s3.delete_object(Bucket=service.bucket_name, Key=key)


async def migrate_gallery_storage_layout(
    execute: bool,
    delete_legacy: bool,
    wedding_slug: str | None,
    planner_email: str | None,
) -> int:
    service = GalleryUploadService()
    query: dict[str, Any] = {}
    if wedding_slug:
        query["slug"] = wedding_slug
    if planner_email:
        query["assigned_planner_email"] = planner_email

    summary = {
        "weddings": 0,
        "copied_objects": 0,
        "existing_objects": 0,
        "updated_references": 0,
        "deleted_legacy_objects": 0,
    }

    cursor = mongo.db["weddings"].find(query)
    async for wedding in cursor:
        slug = str(wedding.get("slug") or "").strip()
        if not slug:
            continue

        summary["weddings"] += 1
        planner_scope = service.get_planner_scope_from_wedding(wedding)
        key_map: dict[str, str] = {}
        legacy_keys_to_delete: list[str] = []

        print(f"\n[{slug}] planner scope -> {planner_scope}")

        for folder in GALLERY_FOLDERS:
            legacy_prefix = service.build_wedding_storage_prefix(
                folder=folder, wedding_slug=slug
            )
            legacy_items = service.list_uploaded_files(prefix=legacy_prefix)

            if not legacy_items:
                continue

            for item in legacy_items:
                source_key = item["key"]
                parsed_key = service.parse_wedding_storage_key(source_key)
                if not parsed_key:
                    continue

                destination_key = (
                    service.build_wedding_storage_prefix(
                        folder=parsed_key["folder"],
                        wedding_slug=parsed_key["wedding_slug"],
                        planner_scope=planner_scope,
                    )
                    + parsed_key["remainder"]
                )
                key_map[source_key] = destination_key

                if _object_exists(service, destination_key):
                    summary["existing_objects"] += 1
                    print(f"  = exists {source_key} -> {destination_key}")
                    if delete_legacy:
                        legacy_keys_to_delete.append(source_key)
                    continue

                print(
                    f"  {'+' if execute else '-'} copy {source_key} -> {destination_key}"
                )
                if execute:
                    _copy_object(service, source_key, destination_key)
                    summary["copied_objects"] += 1
                    if delete_legacy:
                        legacy_keys_to_delete.append(source_key)

        updates = _collect_reference_updates(wedding, key_map)
        if updates:
            print(
                f"  {'+' if execute else '-'} update wedding refs: {sorted(updates.keys())}"
            )
            if execute:
                await mongo.db["weddings"].update_one(
                    {"_id": wedding["_id"]}, {"$set": updates}
                )
            summary["updated_references"] += len(updates)

        if execute and delete_legacy:
            for legacy_key in legacy_keys_to_delete:
                print(f"  - delete legacy {legacy_key}")
                _delete_object(service, legacy_key)
                summary["deleted_legacy_objects"] += 1

    print("\nSummary")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    if not execute:
        print("\nDry run only. Re-run with --execute to apply the migration.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy legacy wedding gallery assets into planner-scoped prefixes and update wedding references.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply the migration instead of running a dry run.",
    )
    parser.add_argument(
        "--delete-legacy",
        action="store_true",
        help="Delete legacy objects after successful copy. Requires --execute.",
    )
    parser.add_argument(
        "--wedding-slug", help="Limit the migration to a single wedding slug."
    )
    parser.add_argument(
        "--planner-email", help="Limit the migration to a single planner email."
    )
    args = parser.parse_args()

    if args.delete_legacy and not args.execute:
        parser.error("--delete-legacy requires --execute")

    return asyncio.run(
        migrate_gallery_storage_layout(
            execute=args.execute,
            delete_legacy=args.delete_legacy,
            wedding_slug=args.wedding_slug,
            planner_email=args.planner_email,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
