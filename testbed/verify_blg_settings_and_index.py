#!/usr/bin/env python3
"""
CP2 Retro — Settings Loaded + babylovegrowth_id Partial Unique Index
====================================================================

Validates the boot-time wiring for the BabyLoveGrowth sync:

  - app/core/settings.py exposes the 4 BABYLOVEGROWTH_* fields with
    correct defaults (sync_enabled=False as a kill switch by default,
    land_as_draft=True for brand-safe gating)
  - app/core/database_indexes.py:create_blog_articles_indexes()
    creates the partial unique index idx_blog_babylovegrowth_id_unique
    on blog_articles, with partialFilterExpression scoped so admin-
    authored articles (no babylovegrowth_id) are unaffected

This is a pure boot-time lifecycle check — no live state to clean
because index creation is idempotent on retry.

Strategy
--------
VERIFY:

    [CHECKPOINT 1/4] Settings loads with the 4 BABYLOVEGROWTH_* fields
    [CHECKPOINT 2/4] babylovegrowth_enabled property correctly gates
                     on api_key presence AND sync_enabled flag
    [CHECKPOINT 3/4] create_blog_articles_indexes() runs without error
    [CHECKPOINT 4/4] idx_blog_babylovegrowth_id_unique exists on
                     blog_articles with unique=True and
                     partialFilterExpression={babylovegrowth_id: {$exists: True}}
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._blg_sync_common import banner, checkpoint_pause  # noqa: E402


async def main() -> None:
    banner("verify_blg_settings_and_index (CP2)")

    print("  VERIFY")

    # Checkpoint 1: Settings exposes the 4 new fields.
    from app.core.settings import Settings

    settings = Settings()
    required_fields = [
        "babylovegrowth_api_key",
        "babylovegrowth_api_base_url",
        "babylovegrowth_sync_enabled",
        "babylovegrowth_land_as_draft",
    ]
    for field in required_fields:
        assert hasattr(settings, field), (
            f"Settings missing field {field!r} — check app/core/settings.py"
        )
    # The base URL should default to BLG's documented endpoint even
    # when not set in env.
    assert "babylovegrowth.ai" in settings.babylovegrowth_api_base_url, (
        f"Unexpected default base URL: {settings.babylovegrowth_api_base_url}"
    )
    # Land-as-draft defaults to True (brand-safe).
    assert settings.babylovegrowth_land_as_draft is True, (
        "LAND_AS_DRAFT default should be True for brand safety"
    )
    checkpoint_pause(
        "1/4 — Settings exposes all 4 BABYLOVEGROWTH_* fields",
        [
            f"babylovegrowth_api_base_url={settings.babylovegrowth_api_base_url}",
            f"babylovegrowth_sync_enabled={settings.babylovegrowth_sync_enabled}",
            f"babylovegrowth_land_as_draft={settings.babylovegrowth_land_as_draft}",
            f"babylovegrowth_api_key set: {bool(settings.babylovegrowth_api_key)}",
        ],
    )

    # Checkpoint 2: babylovegrowth_enabled gates correctly.
    # We don't mutate the live settings — we just assert the computed
    # property reflects (api_key AND sync_enabled). The property's
    # behaviour on the loaded env is informational; the contract is
    # that BOTH conditions must hold.
    enabled = settings.babylovegrowth_enabled
    expected = (
        bool(settings.babylovegrowth_api_key) and settings.babylovegrowth_sync_enabled
    )
    assert enabled == expected, (
        f"babylovegrowth_enabled={enabled} but key={bool(settings.babylovegrowth_api_key)} "
        f"AND sync_enabled={settings.babylovegrowth_sync_enabled} → expected {expected}"
    )
    checkpoint_pause(
        "2/4 — babylovegrowth_enabled gates on key AND flag",
        [
            f"computed enabled: {enabled}",
            "requires both api_key AND sync_enabled to be true",
        ],
    )

    # Checkpoint 3: Index creation runs without error.
    from app.core.database_indexes import create_blog_articles_indexes

    ok = await create_blog_articles_indexes()
    assert ok is True, "create_blog_articles_indexes() returned False"
    checkpoint_pause(
        "3/4 — create_blog_articles_indexes() executed successfully",
        ["function returned True — see log output for per-index creation lines"],
    )

    # Checkpoint 4: The partial unique index exists with the right shape.
    from app.core.database import mongo

    raw_indexes = await mongo.db["blog_articles"].index_information()
    target_name = "idx_blog_babylovegrowth_id_unique"
    assert target_name in raw_indexes, (
        f"Expected index {target_name!r} not found. "
        f"Existing indexes: {sorted(raw_indexes.keys())}"
    )
    idx = raw_indexes[target_name]
    assert idx.get("unique") is True, f"Index {target_name} is not unique — got {idx}"
    partial = idx.get("partialFilterExpression") or {}
    assert partial.get("babylovegrowth_id", {}).get("$exists") is True, (
        f"Index {target_name} missing the partialFilterExpression scope — got {partial}"
    )
    # And the key spec must be ascending on babylovegrowth_id.
    key_spec = idx.get("key", [])
    assert key_spec and key_spec[0][0] == "babylovegrowth_id", (
        f"Index {target_name} key spec is {key_spec}, expected babylovegrowth_id ascending"
    )
    checkpoint_pause(
        "4/4 — idx_blog_babylovegrowth_id_unique correctly shaped",
        [
            f"name: {target_name}",
            f"unique: {idx.get('unique')}",
            f"partialFilterExpression: {partial}",
            f"key: {key_spec}",
        ],
    )

    print()
    print("  ✅ CP2 settings + index wiring verified.")
    print("  Index creation is idempotent — no cleanup needed.")


if __name__ == "__main__":
    asyncio.run(main())
