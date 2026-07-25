"""
BabyLoveGrowth Sync Service.

Pulls AI-generated articles from BabyLoveGrowth's REST API and upserts
them into the existing blog_articles Mongo collection. See
docs/plans/babylovegrowth_integration_mockup.md for the full spec.

Architecture:
  - BabyLoveGrowthClient handles HTTP (auth, retry, error taxonomy).
  - BabyLoveGrowthSyncService orchestrates the lifecycle: lock,
    fetch, map, upsert hero image via R2, persist run state.

Key invariants:
  - Idempotent. Re-running over already-synced articles is a no-op
    (skipped via babylovegrowth_id check, enforced by unique sparse
    index idx_blog_babylovegrowth_id_unique).
  - Insert-only in v1. BLG's API has no updated_at field so we can't
    cheaply detect edits — see "Article edits" section in the mockup.
  - Advisory lock on the singleton babylovegrowth_sync_runs document
    prevents two concurrent runs from wasting BLG quota + R2 PUTs.
  - Brand-safety: synced articles land as `draft` by default
    (BABYLOVEGROWTH_LAND_AS_DRAFT=true). Flip to false when trusted.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from bson import ObjectId

from app.core.database import mongo
from app.core.settings import settings
from app.models.blog import generate_blog_slug
from app.services.blog_upload_service import (
    BlogUploadFromUrlError,
    BlogUploadService,
)
from app.utils.blog_content import sanitize_blog_content

logger = logging.getLogger(__name__)


# ─────────────────────────────────────── Constants ───────────────────────────

# Singleton state-document _id. There is exactly one row in
# babylovegrowth_sync_runs at all times; it holds the advisory lock
# and the most recent run summary.
SYNC_STATE_DOC_ID = "babylovegrowth_sync_state"
SYNC_STATE_COLLECTION = "babylovegrowth_sync_runs"

# After this much time without a release, the lock is considered
# stale (crashed run, killed pod, etc.) and a fresh acquire can take it.
LOCK_TTL = timedelta(minutes=30)

# BLG list-endpoint page size. Their docs recommend 50-100; we pick the
# lower end so the BackgroundTasks budget stays comfortable.
PAGE_LIMIT = 50

# Per-request retry policy applied to 429, 5xx, and httpx network errors.
# After exhausting these attempts the article is skipped (logged), not
# the whole run.
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)

# Per-run failure threshold (>20% errors marks the run "failed" rather
# than "partial" — likely an upstream BLG outage, abort vs. half-sync).
FAILURE_THRESHOLD_RATIO = 0.20

# How many recent errors to keep in the run-state doc. Older errors
# beyond this cap are dropped to keep the doc small.
MAX_RETAINED_ERRORS = 50

# Truncation caps (from BlogArticleModel).
TITLE_MAX = 200
META_DESCRIPTION_MAX = 160
EXCERPT_MAX = 500
EXCERPT_MIN = 20

# Slug regex from BlogArticleModel.validate_slug.
_VALID_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# HTML-stripper for excerpt fallback (strips tags but keeps text).
_STRIP_TAGS_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


# ─────────────────────────────────────── Exceptions ──────────────────────────


class BabyLoveGrowthAuthError(Exception):
    """Raised on 401 from BLG. Triggers the kill switch.

    Caller must persist the run as failed and stop processing — the
    API key is bad and won't fix itself before manual intervention.
    """


class BabyLoveGrowthNotFoundError(Exception):
    """Raised on 404 from BLG single-fetch. Article-level skip, not a run-level failure."""


class BabyLoveGrowthClientError(Exception):
    """Raised on any other persistent BLG API failure (5xx exhausted,
    network errors exhausted, malformed JSON).

    Caller skips the article and continues.
    """


# ─────────────────────────────────────── HTTP client ─────────────────────────


class BabyLoveGrowthClient:
    """Thin httpx wrapper enforcing the error taxonomy in the mockup."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout_seconds: float = 15.0,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)

    async def list_articles(self, *, limit: int, offset: int) -> list[dict]:
        """GET /v1/articles?limit=&offset= — returns summary objects.

        Empty list signals end of pagination.
        """
        return await self._request_json(
            "GET",
            "/v1/articles",
            params={"limit": limit, "offset": offset},
        )

    async def fetch_article(self, blg_id: int) -> dict:
        """GET /v1/articles/{id} — returns the full article payload."""
        return await self._request_json("GET", f"/v1/articles/{blg_id}")

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
    ) -> Any:
        """Send a request with retry policy and error-taxonomy mapping."""
        url = f"{self._base_url}{path}"
        headers = {
            "X-API-Key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(MAX_RETRY_ATTEMPTS):
                try:
                    response = await client.request(
                        method, url, headers=headers, params=params
                    )
                except httpx.HTTPError as exc:
                    # Network errors, timeouts, connection failures.
                    last_exc = exc
                    if attempt < MAX_RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])
                        continue
                    raise BabyLoveGrowthClientError(
                        f"Network error after {MAX_RETRY_ATTEMPTS} attempts: {exc}"
                    ) from exc

                status = response.status_code

                # 401 → kill switch. No retry — the key won't fix itself.
                if status == 401:
                    raise BabyLoveGrowthAuthError(
                        f"BLG returned 401 for {method} {path} — API key is bad or revoked"
                    )

                # 404 → article-level skip.
                if status == 404:
                    raise BabyLoveGrowthNotFoundError(
                        f"BLG returned 404 for {method} {path}"
                    )

                # 429 or 5xx → retry with backoff.
                if status == 429 or 500 <= status < 600:
                    if attempt < MAX_RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])
                        continue
                    raise BabyLoveGrowthClientError(
                        f"BLG returned {status} after {MAX_RETRY_ATTEMPTS} attempts"
                    )

                # Anything else 4xx that isn't 401/404 — surface as client error.
                if status >= 400:
                    raise BabyLoveGrowthClientError(
                        f"BLG returned unexpected {status} for {method} {path}"
                    )

                try:
                    return response.json()
                except ValueError as exc:
                    # Truncate raw body for safety — could be huge.
                    body_preview = response.text[:4096]
                    raise BabyLoveGrowthClientError(
                        f"BLG returned non-JSON for {method} {path}: {body_preview!r}"
                    ) from exc

        # Unreachable — all loop paths either return or raise.
        raise BabyLoveGrowthClientError(
            f"Exhausted attempts for {method} {path}: {last_exc}"
        )


# ─────────────────────────────────────── Sync service ────────────────────────


class BabyLoveGrowthSyncService:
    """Orchestrates the full sync lifecycle.

    Usage:
        await babylovegrowth_sync_service.run_full_sync(triggered_by="cron")

    The service is a singleton — instantiated below at module load.
    """

    def __init__(self):
        self._upload_service = BlogUploadService()

    # ──────────────── Public API ────────────────

    async def run_full_sync(self, *, triggered_by: str = "cron") -> dict:
        """Run a complete sync. Returns the final state document.

        Refuses to run if another sync is in flight, or if BLG is
        disabled / missing key. Always returns a status dict — never
        raises.
        """
        if not settings.babylovegrowth_sync_enabled:
            logger.info(
                "BabyLoveGrowth sync disabled (BABYLOVEGROWTH_SYNC_ENABLED=false)"
            )
            return {"status": "skipped", "reason": "sync_disabled"}

        if not settings.babylovegrowth_api_key:
            logger.warning(
                "BabyLoveGrowth sync triggered but BABYLOVEGROWTH_API_KEY is unset"
            )
            return {"status": "skipped", "reason": "no_api_key"}

        lock_token = uuid.uuid4().hex
        if not await self._acquire_lock(lock_token, triggered_by):
            logger.info("BabyLoveGrowth sync already running — skipping (lock held)")
            return {"status": "skipped", "reason": "lock_held"}

        try:
            return await self._run_sync_body(lock_token)
        except BabyLoveGrowthAuthError as exc:
            # Kill switch — flip env to keep cron from re-firing on a bad key
            # until manual intervention. NOTE: this only mutates the in-process
            # settings cache; the .env file is untouched. Operator must rotate
            # the key and set BABYLOVEGROWTH_SYNC_ENABLED=true again.
            logger.error(
                "BLG auth error: %s — sync_enabled flipped to false in-memory", exc
            )
            settings.babylovegrowth_sync_enabled = False
            return await self._finalize_run(
                lock_token,
                final_status="failed",
                new_count=0,
                skipped_count=0,
                image_failed_count=0,
                errors=[
                    {
                        "blg_id": None,
                        "stage": "auth",
                        "message": str(exc),
                        "occurred_at": _now_utc(),
                    }
                ],
            )
        except Exception as exc:
            logger.exception("Unhandled sync error: %s", exc)
            return await self._finalize_run(
                lock_token,
                final_status="failed",
                new_count=0,
                skipped_count=0,
                image_failed_count=0,
                errors=[
                    {
                        "blg_id": None,
                        "stage": "unhandled",
                        "message": str(exc),
                        "occurred_at": _now_utc(),
                    }
                ],
            )

    async def backfill_hero_images(self) -> dict:
        """Retry hero image proxy for articles where og_image is None.

        Used when the original sync persisted articles but the hero
        image fetch failed (counts toward image_failed_count). This
        method:

          1. Finds blog_articles where sync_source="babylovegrowth"
             AND og_image is None
          2. For each, re-fetches the full BLG article to get the
             current hero_image_url
          3. Attempts BlogUploadService.upload_from_url
          4. On success: updates the article with the R2 cdn_url
          5. On failure: records the exact error message in the
             returned report so the operator can debug

        Diagnostic-first design: this method does NOT swallow image
        errors silently. Every failure returns its reason string from
        BlogUploadFromUrlError verbatim so we can see what BLG's CDN
        is actually serving (content-type, HTTP status, etc.).
        """
        if not settings.babylovegrowth_api_key:
            return {"status": "skipped", "reason": "no_api_key", "results": []}

        cursor = mongo.db["blog_articles"].find(
            {
                "sync_source": "babylovegrowth",
                "babylovegrowth_id": {"$exists": True},
                "$or": [{"og_image": None}, {"og_image": {"$exists": False}}],
            },
            {"babylovegrowth_id": 1, "slug": 1, "title": 1},
        )
        targets: list[dict] = []
        async for doc in cursor:
            targets.append(doc)

        if not targets:
            return {"status": "idle", "reason": "nothing_to_backfill", "results": []}

        client = BabyLoveGrowthClient(
            api_key=settings.babylovegrowth_api_key,
            base_url=settings.babylovegrowth_api_base_url,
        )
        results: list[dict] = []
        succeeded = 0
        failed = 0

        for doc in targets:
            blg_id = doc["babylovegrowth_id"]
            result_entry: dict = {
                "blg_id": blg_id,
                "slug": doc.get("slug"),
                "title": doc.get("title"),
            }
            try:
                full = await client.fetch_article(blg_id)
            except (
                BabyLoveGrowthAuthError,
                BabyLoveGrowthNotFoundError,
                BabyLoveGrowthClientError,
            ) as exc:
                result_entry["status"] = "error"
                result_entry["stage"] = "fetch_article"
                result_entry["error"] = str(exc)
                results.append(result_entry)
                failed += 1
                continue

            # Always patch JSON-LD whenever we touch this row, because
            # articles synced before json_ld field landed have nulls
            # that erase rich-result eligibility. Free win as long as
            # we're already paying the fetch_article round-trip.
            json_ld_patch = full.get("jsonLd")
            faq_json_ld_patch = full.get("faqJsonLd")
            if json_ld_patch is not None and not isinstance(
                json_ld_patch, (dict, list)
            ):
                json_ld_patch = None
            if faq_json_ld_patch is not None and not isinstance(
                faq_json_ld_patch, (dict, list)
            ):
                faq_json_ld_patch = None

            hero_url = full.get("hero_image_url")
            result_entry["hero_image_url"] = hero_url
            if not hero_url:
                # Still patch schema even if there's no hero to fetch.
                await mongo.db["blog_articles"].update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "json_ld": json_ld_patch,
                            "faq_json_ld": faq_json_ld_patch,
                            "updated_at": _now_utc(),
                        }
                    },
                )
                result_entry["status"] = "skipped"
                result_entry["reason"] = "no_hero_image_url_on_blg_side"
                result_entry["json_ld_patched"] = json_ld_patch is not None
                results.append(result_entry)
                continue

            try:
                upload = await self._upload_service.upload_from_url(
                    hero_url, folder=f"blog/synced/{blg_id}"
                )
            except BlogUploadFromUrlError as exc:
                # Image fetch failed — still patch schema since we
                # already paid for the BLG round-trip. Diagnostic-first:
                # surface the exact reason for the image error.
                await mongo.db["blog_articles"].update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "json_ld": json_ld_patch,
                            "faq_json_ld": faq_json_ld_patch,
                            "updated_at": _now_utc(),
                        }
                    },
                )
                result_entry["status"] = "error"
                result_entry["stage"] = "upload_from_url"
                result_entry["error"] = str(exc)
                result_entry["json_ld_patched"] = json_ld_patch is not None
                results.append(result_entry)
                failed += 1
                continue

            # Success — patch image fields AND schema together.
            cdn_url = upload["cdn_url"]
            await mongo.db["blog_articles"].update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "og_image": cdn_url,
                        "card_image": cdn_url,
                        "json_ld": json_ld_patch,
                        "faq_json_ld": faq_json_ld_patch,
                        "updated_at": _now_utc(),
                    }
                },
            )
            result_entry["status"] = "ok"
            result_entry["cdn_url"] = cdn_url
            result_entry["json_ld_patched"] = json_ld_patch is not None
            results.append(result_entry)
            succeeded += 1

        return {
            "status": "completed",
            "total_targets": len(targets),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    async def ingest_webhook_article(self, payload: dict) -> dict:
        """Persist a BLG publish-webhook payload into ``blog_articles``.

        BabyLoveGrowth webhooks are publish events, so this path treats the
        upstream action as explicit publish intent. Local archives still win:
        an article an admin intentionally archived stays archived.
        """
        if not isinstance(payload, dict):
            raise ValueError("Webhook payload must be a JSON object")

        normalized = _normalize_blg_payload(payload)
        blg_id = _coerce_blg_id(normalized.get("id"))
        if blg_id is None:
            raise ValueError("Webhook payload missing valid integer id")

        language = (normalized.get("languageCode") or "").lower()
        if language and language != "en":
            logger.info(
                "Skipped non-English BLG webhook article",
                extra={"blg_id": blg_id, "language": language},
            )
            return {
                "status": "skipped",
                "reason": "non_english",
                "babylovegrowth_id": blg_id,
            }

        mapped = _map_blg_article(
            normalized,
            normalized,
            status_override="published",
        )
        if mapped is None:
            return {
                "status": "skipped",
                "reason": "unmappable_article",
                "babylovegrowth_id": blg_id,
            }

        hero_url = normalized.get("hero_image_url")
        hero_cdn_url = await self._proxy_hero_image(hero_url, blg_id)
        image_failed = bool(hero_url and hero_cdn_url is None)

        upsert_result = await self._upsert_article(
            blg_id=blg_id,
            mapped=mapped,
            hero_cdn_url=hero_cdn_url,
        )
        return {
            "status": "processed",
            "babylovegrowth_id": blg_id,
            "slug": upsert_result["slug"],
            "article_status": upsert_result["status"],
            "inserted": upsert_result["inserted"],
            "image_failed": image_failed,
        }

    async def get_last_run_status(self) -> dict:
        """Return the singleton sync-state doc, or a default if unseeded."""
        doc = await mongo.db[SYNC_STATE_COLLECTION].find_one({"_id": SYNC_STATE_DOC_ID})
        if doc is None:
            return {
                "_id": SYNC_STATE_DOC_ID,
                "status": "idle",
                "lock_token": None,
                "lock_acquired_at": None,
                "started_at": None,
                "ended_at": None,
                "new_count": 0,
                "skipped_count": 0,
                "image_failed_count": 0,
                "error_count": 0,
                "errors": [],
            }
        return doc

    # ──────────────── Locking ────────────────

    async def _acquire_lock(self, lock_token: str, triggered_by: str) -> bool:
        """Atomic find-or-update advisory lock.

        Two states qualify for takeover:
          - Doc doesn't exist (first-ever run, no seed needed)
          - status == "idle"
          - status == "running" AND lock_acquired_at < now - LOCK_TTL
            (stale lock from a crashed run)

        Returns True if we own the lock, False otherwise.
        """
        now = _now_utc()
        stale_cutoff = now - LOCK_TTL

        result = await mongo.db[SYNC_STATE_COLLECTION].find_one_and_update(
            {
                "_id": SYNC_STATE_DOC_ID,
                "$or": [
                    {"status": {"$ne": "running"}},
                    {"lock_acquired_at": {"$lt": stale_cutoff}},
                ],
            },
            {
                "$set": {
                    "status": "running",
                    "lock_token": lock_token,
                    "lock_acquired_at": now,
                    "started_at": now,
                    "ended_at": None,
                    "triggered_by": triggered_by,
                },
            },
            upsert=True,
            return_document=True,
        )
        # If we successfully claimed (or upserted) the lock, return True.
        # find_one_and_update with upsert=True + matching filter returns
        # the new state. Confirm ownership by token (defensive — handles
        # a vanishingly unlikely race where two callers hit upsert at
        # the same time).
        return bool(result and result.get("lock_token") == lock_token)

    async def _release_lock_if_owner(self, lock_token: str) -> None:
        """Best-effort release. Only clears the lock if we still own it.

        If our run took longer than LOCK_TTL and another sync stole the
        lock, we don't trample on it.
        """
        await mongo.db[SYNC_STATE_COLLECTION].update_one(
            {"_id": SYNC_STATE_DOC_ID, "lock_token": lock_token, "status": "running"},
            {"$set": {"status": "idle", "lock_token": None, "lock_acquired_at": None}},
        )

    async def _finalize_run(
        self,
        lock_token: str,
        *,
        final_status: str,
        new_count: int,
        skipped_count: int,
        image_failed_count: int,
        errors: list[dict],
    ) -> dict:
        """Write the final run summary AND release the lock atomically."""
        now = _now_utc()
        update = {
            "$set": {
                "status": final_status,
                "lock_token": None,
                "lock_acquired_at": None,
                "ended_at": now,
                "new_count": new_count,
                "skipped_count": skipped_count,
                "image_failed_count": image_failed_count,
                "error_count": len(errors),
                "errors": errors[-MAX_RETAINED_ERRORS:],
            },
        }
        await mongo.db[SYNC_STATE_COLLECTION].update_one(
            {"_id": SYNC_STATE_DOC_ID, "lock_token": lock_token},
            update,
        )
        return {
            "status": final_status,
            "new_count": new_count,
            "skipped_count": skipped_count,
            "image_failed_count": image_failed_count,
            "error_count": len(errors),
        }

    # ──────────────── Main sync body ────────────────

    async def _run_sync_body(self, lock_token: str) -> dict:
        client = BabyLoveGrowthClient(
            api_key=settings.babylovegrowth_api_key,
            base_url=settings.babylovegrowth_api_base_url,
        )

        known_ids = await self._fetch_known_blg_ids()
        new_count = 0
        skipped_count = 0
        image_failed_count = 0
        errors: list[dict] = []
        offset = 0

        while True:
            summaries = await client.list_articles(limit=PAGE_LIMIT, offset=offset)
            if not summaries:
                break

            for summary in summaries:
                blg_id = summary.get("id")
                if blg_id is None:
                    errors.append(_make_error(None, "list", "Summary missing id"))
                    continue

                # Idempotency: skip already-synced.
                if blg_id in known_ids:
                    skipped_count += 1
                    continue

                # Language filter (v1: en only).
                language = (summary.get("languageCode") or "").lower()
                if language and language != "en":
                    logger.info(
                        "Skipped non-English BLG article",
                        extra={"blg_id": blg_id, "language": language},
                    )
                    skipped_count += 1
                    continue

                # Single-fetch for full content.
                try:
                    full = await client.fetch_article(blg_id)
                except BabyLoveGrowthNotFoundError as exc:
                    skipped_count += 1
                    errors.append(_make_error(blg_id, "fetch", str(exc)))
                    continue
                except BabyLoveGrowthClientError as exc:
                    errors.append(_make_error(blg_id, "fetch", str(exc)))
                    continue
                # BabyLoveGrowthAuthError bubbles up — handled by run_full_sync.

                # Map → upsert.
                try:
                    mapped = _map_blg_article(full, summary)
                    if mapped is None:
                        skipped_count += 1
                        continue

                    hero_cdn_url = await self._proxy_hero_image(
                        full.get("hero_image_url"), blg_id
                    )
                    if full.get("hero_image_url") and hero_cdn_url is None:
                        image_failed_count += 1

                    await self._upsert_article(
                        blg_id=blg_id,
                        mapped=mapped,
                        hero_cdn_url=hero_cdn_url,
                    )
                    new_count += 1
                except Exception as exc:
                    logger.exception("Sync upsert failed", extra={"blg_id": blg_id})
                    errors.append(_make_error(blg_id, "upsert", str(exc)))

            if len(summaries) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT

        # Determine final run status per the "Per-run failure threshold" rule.
        total = new_count + skipped_count + len(errors)
        if errors and total > 0 and len(errors) / total > FAILURE_THRESHOLD_RATIO:
            final_status = "failed"
        elif errors:
            final_status = "partial"
        else:
            final_status = "succeeded"

        return await self._finalize_run(
            lock_token,
            final_status=final_status,
            new_count=new_count,
            skipped_count=skipped_count,
            image_failed_count=image_failed_count,
            errors=errors,
        )

    # ──────────────── Mongo helpers ────────────────

    async def _fetch_known_blg_ids(self) -> set[int]:
        """Build the in-memory set of already-synced BLG article IDs."""
        cursor = mongo.db["blog_articles"].find(
            {"babylovegrowth_id": {"$exists": True}},
            {"babylovegrowth_id": 1, "_id": 0},
        )
        known: set[int] = set()
        async for doc in cursor:
            blg_id = doc.get("babylovegrowth_id")
            if isinstance(blg_id, int):
                known.add(blg_id)
        return known

    async def _upsert_article(
        self,
        *,
        blg_id: int,
        mapped: dict,
        hero_cdn_url: str | None,
    ) -> dict:
        """Upsert by babylovegrowth_id. Slug collisions retry with -N suffix.

        The unique sparse index idx_blog_babylovegrowth_id_unique
        guarantees no duplicate rows. The unique slug index
        idx_blog_slug_unique may collide with an admin-authored article;
        we regenerate with a numeric suffix and retry.
        """
        from pymongo.errors import DuplicateKeyError

        now = _now_utc()
        existing = await mongo.db["blog_articles"].find_one(
            {"babylovegrowth_id": blg_id},
            {
                "slug": 1,
                "status": 1,
                "published_at": 1,
                "og_image": 1,
                "card_image": 1,
                "category": 1,
                "featured": 1,
            },
        )
        base_slug = mapped["slug"]
        preserve_existing_slug = bool(
            existing
            and existing.get("slug")
            and (existing.get("status") != "draft" or existing.get("published_at"))
        )
        candidate_slug = existing["slug"] if preserve_existing_slug else base_slug
        suffix = 1

        for _ in range(20):  # Cap collision retries to avoid pathological loops
            set_fields = {
                **mapped,
                "slug": candidate_slug,
                "synced_at": now,
                "sync_source": "babylovegrowth",
                "updated_at": now,
            }

            if existing:
                # Preserve local curation choices for rows that have already
                # been reviewed in our admin. BLG remains the content source;
                # our Mongo row remains the publishing source of truth.
                for curated_field in ("category", "featured"):
                    if curated_field in existing:
                        set_fields[curated_field] = existing[curated_field]

                existing_status = existing.get("status")
                incoming_status = mapped.get("status")
                if existing_status == "archived":
                    set_fields["status"] = "archived"
                    set_fields["published_at"] = existing.get("published_at")
                elif incoming_status == "published":
                    set_fields["status"] = "published"
                    set_fields["published_at"] = (
                        existing.get("published_at")
                        or mapped.get("published_at")
                        or now
                    )
                else:
                    set_fields["status"] = existing_status or incoming_status
                    set_fields["published_at"] = existing.get(
                        "published_at", mapped.get("published_at")
                    )

            if hero_cdn_url is not None:
                set_fields["og_image"] = hero_cdn_url
                set_fields["card_image"] = hero_cdn_url
            elif not existing or not (
                existing.get("og_image") or existing.get("card_image")
            ):
                set_fields["og_image"] = None
                set_fields["card_image"] = None

            update = {
                "$set": set_fields,
                "$setOnInsert": {
                    "_id": ObjectId(),
                    "created_at": now,
                    "view_count": 0,
                    "babylovegrowth_id": blg_id,
                },
            }
            try:
                await mongo.db["blog_articles"].update_one(
                    {"babylovegrowth_id": blg_id},
                    update,
                    upsert=True,
                )
                return {
                    "inserted": existing is None,
                    "slug": candidate_slug,
                    "status": set_fields["status"],
                }
            except DuplicateKeyError as exc:
                # Was this the slug index or the babylovegrowth_id index?
                msg = str(exc)
                if "slug" in msg.lower():
                    candidate_slug = f"{base_slug}-{suffix}"
                    suffix += 1
                    continue
                # Hit babylovegrowth_id index — concurrent run claimed
                # this id. That's fine, idempotent skip.
                logger.info(
                    "BLG article already synced by another writer",
                    extra={"blg_id": blg_id},
                )
                return {
                    "inserted": False,
                    "slug": candidate_slug,
                    "status": set_fields["status"],
                }

        raise RuntimeError(
            f"Could not find a non-colliding slug for BLG article {blg_id} after 20 attempts"
        )

    # ──────────────── Image proxy ────────────────

    async def _proxy_hero_image(
        self, remote_url: str | None, blg_id: int
    ) -> str | None:
        """Best-effort hero image re-host. Returns CDN URL or None."""
        if not remote_url:
            return None
        try:
            result = await self._upload_service.upload_from_url(
                remote_url, folder=f"blog/synced/{blg_id}"
            )
            return result["cdn_url"]
        except BlogUploadFromUrlError as exc:
            logger.warning(
                "Hero image fetch failed; persisting without it",
                extra={"blg_id": blg_id, "remote_url": remote_url, "error": str(exc)},
            )
            return None


# ─────────────────────────────────────── Field mapping ───────────────────────


def _map_blg_article(
    full: dict,
    summary: dict,
    *,
    status_override: str | None = None,
) -> dict | None:
    """Map a BLG full-article payload to a partial blog_articles document.

    Returns None if the article cannot be mapped (e.g. content fails
    sanitization). The returned dict does NOT include `_id`,
    `created_at`, `view_count`, `og_image`, `card_image`, or
    `synced_at` — those are set by the upsert.
    """
    title = (full.get("title") or summary.get("title") or "").strip()
    if not title:
        return None

    # Truncation policy: silent + warn.
    if len(title) > TITLE_MAX:
        logger.warning(
            "Title truncated",
            extra={"blg_id": full.get("id"), "original_length": len(title)},
        )
        title = title[:TITLE_MAX]

    # Slug: prefer BLG's, but validate against our regex; regenerate if invalid.
    raw_slug = (full.get("slug") or summary.get("slug") or "").strip()
    if not raw_slug or not _VALID_SLUG_PATTERN.match(raw_slug):
        raw_slug = (
            generate_blog_slug(title) or f"blg-article-{full.get('id', 'unknown')}"
        )

    # Content: sanitize via the existing pipeline (img allowlist enforced).
    raw_html = full.get("content_html") or full.get("content_markdown") or ""
    sanitized = sanitize_blog_content(raw_html)
    if not sanitized or len(sanitized) < 50:
        logger.warning(
            "Content empty or too short after sanitization",
            extra={"blg_id": full.get("id"), "post_sanitize_length": len(sanitized)},
        )
        return None

    # Meta description (160-char cap).
    meta = (
        full.get("meta_description") or summary.get("meta_description") or ""
    ).strip()
    if len(meta) > META_DESCRIPTION_MAX:
        meta = meta[:META_DESCRIPTION_MAX]

    # Excerpt: BLG's single-fetch payload doesn't include excerpt, but
    # the list-summary does. Fall back to meta_description, then to
    # the first ~400 chars of stripped content.
    excerpt = (summary.get("excerpt") or "").strip()
    if not excerpt:
        excerpt = meta
    if not excerpt:
        excerpt = _derive_excerpt_from_content(sanitized)
    excerpt = excerpt[:EXCERPT_MAX]
    if len(excerpt) < EXCERPT_MIN:
        # Last-ditch padding to satisfy BlogArticleModel.excerpt min length.
        excerpt = (excerpt + " " + title)[:EXCERPT_MAX].strip()
        if len(excerpt) < EXCERPT_MIN:
            return None  # Genuinely no usable excerpt material.

    # Tags from BLG keywords (lowercased, capped at 15 to match BlogArticleModel).
    raw_keywords = full.get("keywords") or summary.get("keywords") or []
    tags = []
    if isinstance(raw_keywords, list):
        for kw in raw_keywords:
            if isinstance(kw, str):
                cleaned = kw.lower().strip()
                if cleaned:
                    tags.append(cleaned)
    tags = tags[:15]

    # Status: brand-safe default to draft when LAND_AS_DRAFT=true, except
    # publish webhooks, where the upstream user explicitly clicked Publish.
    if status_override is not None:
        if status_override not in {"draft", "published", "archived"}:
            raise ValueError(f"Unsupported BLG status override: {status_override}")
        status = status_override
    else:
        status = "draft" if settings.babylovegrowth_land_as_draft else "published"

    # published_at: only set if we're publishing immediately.
    source_created_at = _parse_blg_datetime(
        full.get("created_at") or summary.get("created_at")
    )
    published_at = (source_created_at or _now_utc()) if status == "published" else None

    # Schema.org JSON-LD: BLG documents these as dedicated structured
    # data fields. Their docs Best Practice says: "Use jsonLd and
    # faqJsonLd if your CMS supports dedicated schema fields; otherwise
    # consume the schema scripts embedded in content_html." Our
    # sanitizer strips <script> blocks, so we must use the dedicated
    # fields — otherwise rich-result eligibility (Article + FAQPage
    # carousels in Google) is lost.
    # Citation: https://www.babylovegrowth.ai/docs/integrations/api
    json_ld = full.get("jsonLd")
    faq_json_ld = full.get("faqJsonLd")
    # Coerce to dict-or-None defensively — BLG returns them as objects
    # but a future schema change could swap to a list/string.
    if json_ld is not None and not isinstance(json_ld, (dict, list)):
        logger.warning(
            "jsonLd dropped — unexpected type",
            extra={"blg_id": full.get("id"), "type": type(json_ld).__name__},
        )
        json_ld = None
    if faq_json_ld is not None and not isinstance(faq_json_ld, (dict, list)):
        logger.warning(
            "faqJsonLd dropped — unexpected type",
            extra={"blg_id": full.get("id"), "type": type(faq_json_ld).__name__},
        )
        faq_json_ld = None

    return {
        "title": title,
        "slug": raw_slug,
        "content": sanitized,
        "excerpt": excerpt,
        "meta_description": meta or None,
        "category": "general",  # v1: keyword→category mapping is a deferred follow-up
        "tags": tags,
        "status": status,
        "featured": False,
        "author_name": "The Special Wedding",
        "author_email": "hello@thespecialwedding.io",
        "published_at": published_at,
        "estimated_read_minutes": max(1, len(sanitized.split()) // 200),
        "json_ld": json_ld,
        "faq_json_ld": faq_json_ld,
    }


def _derive_excerpt_from_content(sanitized: str) -> str:
    """Strip HTML tags and collapse whitespace for an excerpt fallback."""
    text = _STRIP_TAGS_PATTERN.sub(" ", sanitized)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text[:400]


def _normalize_blg_payload(payload: dict) -> dict:
    """Normalize BLG's API and webhook casing into the API-shaped keys."""
    normalized = dict(payload)
    aliases = {
        "metaDescription": "meta_description",
        "heroImageUrl": "hero_image_url",
        "createdAt": "created_at",
        "publicUrl": "public_url",
    }
    for source_key, target_key in aliases.items():
        if target_key not in normalized and source_key in normalized:
            normalized[target_key] = normalized[source_key]
    return normalized


def _coerce_blg_id(value: Any) -> int | None:
    """Return a BLG article id as int, rejecting bools and non-numeric strings."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.isdigit():
            return int(cleaned)
    return None


def _parse_blg_datetime(value: Any) -> datetime | None:
    """Parse BLG ISO timestamps as UTC-aware datetimes."""
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        logger.warning(
            "Could not parse BLG created_at timestamp", extra={"value": value}
        )
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


# ─────────────────────────────────────── Helpers ─────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _make_error(blg_id: int | None, stage: str, message: str) -> dict:
    return {
        "blg_id": blg_id,
        "stage": stage,
        "message": message[:1024],  # Cap individual error messages.
        "occurred_at": _now_utc(),
    }


# Singleton instance — matches the pattern in blog_service.py.
babylovegrowth_sync_service = BabyLoveGrowthSyncService()
