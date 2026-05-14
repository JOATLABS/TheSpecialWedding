# BabyLoveGrowth Blog Sync — Implementation Mockup

> **Status:** Mockup pending review. No code has been written. Do not implement until Etastic signs off.

## TL;DR

We **already have** a full blog system (`blog_articles` Mongo collection, `BlogService`, public route `/resources/blog/[slug]`, admin CRUD, sanitization, slug dedup, view counter). The BabyLoveGrowth integration is a thin adapter, not a new subsystem.

Five additions:

1. One new field on existing `blog_articles` docs: `babylovegrowth_id` (unique sparse index) for idempotent upserts.
2. One new service: `app/services/babylovegrowth_sync_service.py` — pulls articles from their REST API, maps fields, upserts.
3. One new admin endpoint: `POST /api/v1/blog/sync-babylovegrowth` — `require_root_admin`-gated, uses `BackgroundTasks` (same pattern as `app/api/billing_jobs.py::sync_usage_to_stripe`).
4. One new method on existing `BlogUploadService`: `upload_from_url(remote_url, folder)` — server-side image ingestion into the existing R2 bucket. Sync re-hosts BLG hero images on our own CDN so synced articles look architecturally identical to admin-authored ones.
5. One new single-row Mongo collection: `babylovegrowth_sync_runs` — holds the advisory lock + last run state (status, counts, recent errors). Read by `GET /sync-babylovegrowth/status`.

No new Next.js page. No new R2 bucket. No new external dependencies.

## Why API (pull), not Webhook (push)

Both contracts are confirmed. The disqualifier on the webhook: **no automatic retries**. If the FastAPI dyno is restarting, mid-deploy, or transiently 5xx-ing when an article publishes, the article is silently lost — recoverable only by clicking Publish again in their UI. The pull model is idempotent and re-runnable. A failed sync just runs again on the next cron tick.

Hybrid (webhook + API safety net) is possible later. Not in this scope.

## BabyLoveGrowth API contract (confirmed)

- Base: `https://api.babylovegrowth.ai/api/integrations`
- Auth header: `X-API-Key: <key>` (key generated in BLG dashboard → Settings → Integrations → API)
- `GET /v1/articles?limit=<n>&offset=<n>` → array of summaries (no body)
- `GET /v1/articles/{id}` → full content
- Pagination: limit max 500, default 100, sorted newest-first
- 429 rate-limited; FAQ recommends exponential backoff

## Field mapping — BabyLoveGrowth → `BlogArticleModel`

| BLG field (single-fetch) | Type | → Our field | Mapping notes |
|---|---|---|---|
| `id` (int) | number | `babylovegrowth_id` (NEW) | Persisted alongside our `_id`; unique sparse index |
| `title` | string | `title` | Direct. Their max is unbounded; our cap is 200 chars — **truncate with ellipsis** if longer (open question: warn vs. silent truncate) |
| `slug` | string | `slug` | Validate against our regex `^[a-z0-9]+(?:-[a-z0-9]+)*$`. If invalid, regenerate via `generate_blog_slug(title)`. Dedupe via existing `-1, -2…` suffixing in `BlogService.create_article` |
| `content_html` | string | `content` | Run through `sanitize_blog_content()`. After Option A is implemented (see "Inline `<img>` policy" section), body `<img>` tags survive with `https`-only `src`. Inline image URLs remain on BLG's CDN in v1; body-image R2 proxy is a tracked v1.1 follow-up |
| `meta_description` | string | `meta_description` | Truncate to 160 chars (our hard cap) |
| `meta_description` | string | `excerpt` (fallback) | BLG single-fetch has no `excerpt`. Derive: prefer `meta_description` truncated to 500. If absent, strip HTML from first ~400 chars of content |
| `hero_image_url` | string | `og_image`, `card_image` | **Re-hosted on our R2.** Sync streams the BLG URL via httpx → `BlogUploadService.upload_from_url(...)` → stores returned `cdn_url`. If fetch fails (404/oversized/wrong content-type), set both fields to `None`, log warning, do not fail the article |
| `languageCode` | string | _(not stored)_ | We're English-only today. **Open question** — should we filter to `en` only and skip the rest? |
| `keywords` (list endpoint) | array | `tags` | Lowercased, max 15 (matches our `validate_tags`) |
| `seedKeyword` (list endpoint) | string | _(not stored)_ | **Open question** — store for SEO categorization later? Could feed a keyword→category mapper |
| `jsonLd`, `faqJsonLd` | object | _(not stored)_ | **Open question** — we don't surface JSON-LD today. Drop, or add a field to render in `<head>` for SEO? |
| `publicUrl` | string | _(not stored, webhook only)_ | Where BLG hosts the article. Not relevant — we host it ourselves |
| `created_at` | ISO 8601 | `published_at` AND `created_at` | Treat BLG's `created_at` as authoritative for "when this article became real" |
| n/a | | `category` | Default `"general"`. **Open question** — keyword→category mapper later? |
| n/a | | `status` | `"published"` (BLG only exposes published articles). **Open question** — config to land as `"draft"` for review-first? |
| n/a | | `author_name` | Default from `BlogArticleCreateModel` (`"The Special Wedding"`) |
| n/a | | `featured` | Always `False` for synced articles. Manually promoted in admin UI |

## Schema delta on `blog_articles`

Only one new field added to existing docs:

```python
# In sync service, NOT in BlogArticleModel (which validates user-authored creates).
# We add this directly via $set during upsert.
{
    "babylovegrowth_id": 151241,   # int — their article ID
    "synced_at": datetime,         # last time we ran sync against this doc
    "sync_source": "babylovegrowth"  # for future multi-source support
}
```

**Migration:** none required. Field is optional, sparse-indexed. Existing admin-authored articles have `babylovegrowth_id = None`. The unique index has `partialFilterExpression` so it only enforces uniqueness when the field is set.

Index to add:

```javascript
db.blog_articles.createIndex(
  { babylovegrowth_id: 1 },
  { unique: true, partialFilterExpression: { babylovegrowth_id: { $exists: true } } }
)
```

## Sync flow

```
POST /api/v1/blog/sync-babylovegrowth   (root_admin only)
  │
  ├─ enqueue BackgroundTasks(run_babylovegrowth_sync)
  └─ return 202 { "status": "accepted" }

run_babylovegrowth_sync():
  # Acquire single-row advisory lock (see "Concurrency" section).
  # Atomic find_one_and_update on babylovegrowth_sync_runs with
  # precondition status=="idle". Refuse to run if already running.
  if not acquire_sync_lock(): return

  cursor_offset = 0
  page_limit = 50
  known_blg_ids = await fetch_existing_blg_ids()    # one query, in-memory set
  newly_synced = 0
  skipped = 0
  image_failed = 0
  errors = []

  while True:
    summaries = GET /v1/articles?limit=page_limit&offset=cursor_offset
    if not summaries: break

    for s in summaries:
      if s.id in known_blg_ids:
        # v1 is insert-only — see "Article edits" section.
        # BLG has no `updated_at` field, so we can't cheaply detect
        # edits. Skipped articles are intentional, not a bug.
        skipped += 1
        continue

      full = GET /v1/articles/{s.id}    # retries per Error Taxonomy
      mapped = map_blg_to_blog_article(full, summary=s)
      try:
        sanitized = sanitize_blog_content(mapped["content"])
        if not sanitized or len(sanitized) < 50:
          log.warning("Skipped — content empty/short after sanitize", blg_id=s.id)
          continue

        slug = ensure_unique_slug(mapped["slug"])

        # Re-host hero image on our R2. Best-effort: missing image
        # is not a fatal error, just downgrades the card visual.
        hero_cdn_url = None
        if full.get("hero_image_url"):
          try:
            result = blog_upload_service.upload_from_url(
              full["hero_image_url"],
              folder=f"blog/synced/{s.id}",
            )
            hero_cdn_url = result["cdn_url"]
          except Exception:
            log.warning("Hero image fetch failed; persisting without it", blg_id=s.id)
            image_failed += 1

        await blog_articles.update_one(
          {"babylovegrowth_id": s.id},
          {
            "$set": {
              **mapped,
              "content": sanitized,
              "slug": slug,
              "og_image": hero_cdn_url,
              "card_image": hero_cdn_url,
              "synced_at": now_utc(),
              "sync_source": "babylovegrowth",
            },
            "$setOnInsert": {
              "_id": ObjectId(),
              "created_at": now_utc(),
              "view_count": 0,
            },
          },
          upsert=True,
        )
        newly_synced += 1
      except Exception as e:
        log.exception("Sync failed for BLG article", blg_id=s.id)
        errors.append({"blg_id": s.id, "stage": "upsert", "message": str(e)})
        # Continue — don't fail the batch

    if len(summaries) < page_limit: break
    cursor_offset += page_limit

  # Determine final run status per "Per-run failure threshold":
  total = newly_synced + skipped + len(errors)
  if errors and len(errors) > total * 0.2:
    final_status = "failed"
  elif errors:
    final_status = "partial"
  else:
    final_status = "succeeded"

  release_sync_lock(
    status=final_status,
    new_count=newly_synced,
    skipped_count=skipped,
    image_failed_count=image_failed,
    errors=errors[-50:],   # cap retained errors per schema
  )
  log.info("Sync complete", new=newly_synced, skipped=skipped, errors=len(errors))
```

**Idempotency.** Every upsert is keyed on `babylovegrowth_id`. Re-running the sync end-to-end is safe — duplicates are impossible at the index level.

**Backfill.** First sync pulls everything — all historical articles. Subsequent syncs only fetch IDs we don't already have.

## Concurrency / double-run protection

**Inherited gap from the existing pattern.** `app/api/billing_jobs.py:19-32` (the pattern we mirror) uses `background_tasks.add_task(process_daily_usage_check)` with no lock check, no in-flight detection, no idempotency token. FastAPI `BackgroundTasks` runs after the HTTP response and has no built-in deduplication — see https://fastapi.tiangolo.com/tutorial/background-tasks/. So an external cron firing twice within seconds (transient network retry, misconfigured scheduler, manual admin trigger overlapping cron) spawns two concurrent runs.

**What's NOT at risk.** Duplicate documents are impossible:

- `babylovegrowth_id` unique sparse index from this mockup
- `idx_blog_slug_unique` already exists — `app/core/database_indexes.py:1193`

A losing second writer's `insert_one`/`upsert` raises `DuplicateKeyError` and the sync wrapper catches it.

**What IS at risk under concurrent runs:**

- Wasted BLG API quota (every article fetched twice)
- Wasted R2 PUTs (every hero image uploaded twice — costs egress + storage on the loser)
- Log noise — every duplicate insert raises and gets caught

**Mitigation.** A single-row advisory lock in the new `babylovegrowth_sync_runs` collection (specced below). Sync entry does an atomic `find_one_and_update` with precondition `status: "idle"` and sets `status: "running"` + `lock_token`. If preconditioned update returns `None`, another run is in flight — log and return without running. Sync exit (success or failure) clears `status: "idle"`. A `lock_acquired_at + 30 min` TTL guard releases the lock if a crashed run forgot to clear it.

## Sync run state — `babylovegrowth_sync_runs` collection

**This solves both the lock primitive above AND the `get_last_run_status` storage question** (which the prior draft of the mockup left as "a small sync_runs collection or last log" — pick one).

Pick the collection. Schema:

```python
{
  "_id": ObjectId(),
  "status": "idle" | "running" | "succeeded" | "failed" | "partial",
  "lock_token": str | None,          # uuid4 set when status="running"
  "lock_acquired_at": datetime | None,
  "started_at": datetime,
  "ended_at": datetime | None,
  "new_count": int,                  # articles inserted
  "skipped_count": int,              # articles already present
  "image_failed_count": int,         # hero image fetches that failed
  "error_count": int,
  "errors": [                        # capped to last 50
    {"blg_id": int, "stage": str, "message": str, "occurred_at": datetime}
  ],
  "triggered_by": "cron" | "manual"  # informational
}
```

Only one document exists at a time — `_id` is a known constant string `"babylovegrowth_sync_state"` (not `ObjectId()`; that comment in the schema above is wrong — corrected here). Every run mutates this single document. `GET /sync-babylovegrowth/status` reads it directly.

No new collection if you'd rather store this in an existing one — but a dedicated single-doc collection is cleaner than overloading anything else, and matches your existing pattern in places like `behavioral_analytics_service.py` (singleton state docs).

## Error taxonomy

Two layers — what BLG's docs commit to, and general HTTP hygiene they don't address.

**BLG-documented error responses.** Citation: https://www.babylovegrowth.ai/docs/integrations/api → "Troubleshooting & FAQ" section. Their FAQ enumerates exactly three categories:

| BLG error | Cause (per their docs) | Handler |
|---|---|---|
| `401 Unauthorized` | Bad/revoked API key, or `X-API-Key` header malformed | **Fail loud.** Log error, write to `sync_runs.errors`, set `BABYLOVEGROWTH_SYNC_ENABLED=false` (kill switch — manual re-enable after key rotation), exit run. Do not retry — the key won't fix itself |
| `404` (on `GET /v1/articles/{id}`) | Article ID not in our account | Skip article, log warning, continue. Should never happen if the ID came from the list endpoint, but treat as soft failure |
| Rate limit (429) | Their docs recommend "exponential backoff" without specifying retry-after header behavior | Retry with backoff 1s, 2s, 4s. After 3 failures, skip article, log warning, continue |

**Not in BLG docs — defensive HTTP hygiene.** Their docs do not mention 5xx, network timeouts, 502/503, connection resets. This is general engineering hygiene, not a BLG contract requirement.

| Condition | Handler |
|---|---|
| 5xx (5 < status < 600) | Treat like 429: backoff 1s, 2s, 4s. After 3 failures, skip article, log warning |
| `httpx.ReadTimeout`, `httpx.ConnectError`, `httpx.NetworkError` | Same retry policy as 5xx |
| Malformed JSON / schema-violating payload | Log error with full response body (truncated to 4 KB), skip article, continue |

**Per-run failure threshold.** If `error_count > 20% of total fetched` on a single run, mark run `status: "failed"` (vs `"partial"`) — likely an upstream BLG outage; better to abort than to half-sync.

## Article edits — what we DON'T detect

**Verified fact.** Citation: https://www.babylovegrowth.ai/docs/integrations/api response examples:

- List endpoint returns: `id, title, slug, hero_image_url, languageCode, meta_description, excerpt, orgWebsite, created_at, seedKeyword, keywords` — **no `updated_at`**.
- Single-fetch endpoint returns: `id, title, slug, content_markdown, content_html, jsonLd, faqJsonLd, meta_description, hero_image_url, orgWebsite, created_at, seedKeyword, keywords` — **no `updated_at`**.

So we cannot cheaply diff a synced article against its BLG source. Options:

1. **v1 choice — insert-only.** First sync wins. If a BLG article is edited post-publish, our `blog_articles` document is frozen at the version captured on first sync. Document this as a known limitation. Manual reconciliation: an admin deletes the local document; the next sync re-imports the current BLG version.
2. **Hash-and-refetch.** Every Nth run, refetch all articles and compare a content hash. Doubles the API quota cost; defers the edit detection but doesn't eliminate the cost. Defer to v2 if/when needed.
3. **Webhook re-publish behavior.** Unverified — the webhook docs at https://www.babylovegrowth.ai/docs/integrations/webhook describe the Publish Flow as "when an article is published" but don't say whether re-clicking Publish on an edited article re-fires the webhook with the updated payload or fires once per article-ID forever. Would need to test in their UI or ask their support. Not a v1 dependency.

**Recommendation:** v1 = option 1 (insert-only). Document the limitation in the synced article view (admin UI badge — out of scope for this mockup) so future-you doesn't get surprised.

The `updated` counter that appeared in the prior draft pseudocode was dead — removed below.

## Endpoint mockup — matches `billing_jobs.py` pattern

```python
# app/api/blog.py (additions)

@router.post("/blog/admin/sync-babylovegrowth")
async def sync_babylovegrowth(
    background_tasks: BackgroundTasks,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Trigger a BabyLoveGrowth → blog_articles sync.
    Should be called periodically (every 1–4h) via external cron.
    """
    background_tasks.add_task(babylovegrowth_sync_service.run_full_sync)
    return {"status": "accepted", "message": "BabyLoveGrowth sync started in background"}


@router.get("/blog/admin/sync-babylovegrowth/status")
async def sync_status(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Last sync timestamp + counts. Reads from a small sync_runs collection or last log."""
    return await babylovegrowth_sync_service.get_last_run_status()
```

No new router — extends existing `app/api/blog.py`, which is already wired in `main.py:921` and uses `require_root_admin`.

## R2 image ingestion — new method on existing `BlogUploadService`

Today `BlogUploadService` (`app/services/blog_upload_service.py`) only supports the **client-side presigned-PUT** flow — admin browser fetches a presigned URL from `GET /admin/blog/upload-url` and PUTs the file directly to R2. The same bucket serves the admin Blog editor and the Knowledge Base editor. The bucket, public CDN domain, `MediaStorage.BLOG_ASSETS` target, and boot-time config validator are all already wired.

What's missing: a **server-side** ingestion path. BLG sync runs on the server, holds a URL, and needs to push to R2 without a browser in the loop.

Proposed addition to `BlogUploadService`:

```python
async def upload_from_url(
    self,
    remote_url: str,
    folder: str = "blog/synced",
    *,
    max_bytes: int = MAX_BLOG_IMAGE_SIZE_BYTES,  # reuse existing 5 MB cap
    timeout_seconds: float = 15.0,
) -> dict:
    """
    Server-side: stream a remote image into R2 under the BLOG_ASSETS target.

    - Validates content-type against ALLOWED_BLOG_IMAGE_TYPES
    - Caps body size at max_bytes (early-aborts streaming if exceeded)
    - Uses MediaStorage's existing boto3 client (already health-checked)
    - Returns {"key": ..., "cdn_url": ...} matching create_presigned_upload_url's shape
    """
```

Implementation notes:

- Stream via `httpx.AsyncClient` with `stream=True`; abort if `content-length` header or running byte count exceeds cap.
- Filename derived from URL path basename + timestamp prefix (mirrors `create_presigned_upload_url`).
- Use `MediaStorage.client.put_object(Bucket=..., Key=..., Body=..., ContentType=...)` directly. The client is already initialized in `MediaStorage.__init__` and shared across targets.
- Validates content type from the response's `Content-Type` header (not from URL extension — BLG's CDN may not include `.jpg`).
- No retry inside this method. If BLG's CDN is down, the sync caller logs and persists without an image.
- Folder default is `blog/synced/<blg_id>` so future cleanup is easy if you ever bulk-delete BLG content.

This keeps the existing presigned-PUT flow untouched. Same bucket, same CDN domain, same allowlist. No new env vars.

### Env state — verified by Etastic 2026-05-14

`S3_BLOG_BUCKET_NAME` and `BLOG_MEDIA_DOMAIN` are populated in runtime. The bucket is already in production use for admin-authored Blog and KB images via the presigned-PUT path.

For future engineers landing on this doc: the boot-time config validator at `app/services/config_validator.py:104` warns if `S3_BLOG_BUCKET_NAME` is unset, and `app/services/config_validator.py:111` warns if `BLOG_MEDIA_DOMAIN` is unset. If either warning appears in boot logs, `MediaStorage.require_target(BLOG_ASSETS)` will raise `RuntimeError("Storage target 'blog_assets' is not available")` and every sync image upload will fail. Treat the warning as a deployment-blocking signal.

## Trigger / scheduling

Matches your existing pattern: **no in-process scheduler.** External cron hits `POST /api/v1/blog/admin/sync-babylovegrowth` on a 1–4h cadence. Whatever you use to drive `POST /billing/sync-usage` today drives this too.

**Open question — cadence.** BLG generates articles on their schedule (you control rate in their dashboard). Hourly seems fine; daily is probably enough for v1. Pick after watching their publish frequency for a week.

## Env vars (new)

```
BABYLOVEGROWTH_API_KEY=<paste from BLG dashboard>
BABYLOVEGROWTH_API_BASE_URL=https://api.babylovegrowth.ai/api/integrations   # optional, defaults
BABYLOVEGROWTH_SYNC_ENABLED=true                                              # kill switch
BABYLOVEGROWTH_LAND_AS_DRAFT=true                                             # see "Synced article default status" below
```

Read via the existing `Settings` class in `app/core/settings.py` (mirrors the `S3_BLOG_BUCKET_NAME` / `RESEND_API_KEY` / `STRIPE_*` patterns already established).

## Synced article default status — Etastic's judgment call, not a doc-mandated constraint

What BLG's docs do tell us:

- The list endpoint and single-fetch endpoint response examples do NOT include a `status` field. Citation: https://www.babylovegrowth.ai/docs/integrations/api response examples. We have no way to know from the payload whether BLG considers an article "draft," "published," or "scheduled."
- The webhook docs frame article delivery as a "Publish" event. Citation: https://www.babylovegrowth.ai/docs/integrations/webhook → "Publish Flow." This implies articles delivered via either channel are already "published" on BLG's side, but the API docs don't make this commitment explicit.

What BLG's docs do NOT tell us: whether articles delivered via the API have been human-reviewed by their pipeline, whether they go through QA, whether they cite sources accurately, or whether they match your brand voice.

**Decision:** this is a brand-safety call, not a documented requirement. Two options:

| Setting | Behavior | When this is right |
|---|---|---|
| `BABYLOVEGROWTH_LAND_AS_DRAFT=true` (recommended default) | Synced articles land as `status="draft"`. Invisible to `/resources/blog`. Etastic reviews each in admin UI, manually publishes | First N weeks while you build trust in BLG's output. Brand-safety wins |
| `BABYLOVEGROWTH_LAND_AS_DRAFT=false` | Synced articles land as `status="published"`. Live immediately at `/resources/blog/<slug>` | Once you've reviewed enough output to trust the pipeline and you'd rather have throughput than gate |

**My recommendation:** start with `true`. Flip to `false` after you've reviewed ~10 synced articles and they're all on-brand and factually clean.

## Inline `<img>` policy — global allowlist with `https`-only `src`

**Decision (Etastic, 2026-05-14):** Option A. Add `img` to the bleach allowlist in `app/utils/blog_content.py` so synced AND admin-authored articles can contain inline body images. This fixes a latent admin bug too: today, an admin who pastes `<img>` into the Blog/KB editor has their image silently stripped on save.

### Bleach config changes

```python
# app/utils/blog_content.py (modifications)

BLOG_ALLOWED_TAGS = [
    "a", "blockquote", "br", "code", "del", "em",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "img",  # ← new
    "input", "li", "ol", "p", "pre", "strong",
    "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
]

BLOG_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "target"],
    "code": ["class"],
    "img": ["src", "alt", "width", "height", "loading"],  # ← new
    "input": ["checked", "disabled", "type"],
    "td": ["align"],
    "th": ["align"],
}

BLOG_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]
# unchanged — protocol filtering is applied via bleach `protocols=` arg below

# In sanitize_blog_content(), after bleach.clean, enforce src strictness:
def _enforce_https_image_src(html: str) -> str:
    """Post-bleach pass: drop any <img> whose src isn't https://."""
    # Regex is safe here because bleach has already normalized the HTML and
    # we only need to reject obviously wrong protocols (http, data:, javascript:, blob:).
    return re.sub(
        r'<img\b([^>]*?)\bsrc="(?!https://)[^"]*"([^>]*)>',
        "",
        html,
        flags=re.IGNORECASE,
    )
```

The post-bleach `_enforce_https_image_src` pass is the **first guardrail**. Bleach can be configured with protocols, but in practice the `protocols` argument applies to `href`-style URL attributes; `img.src` enforcement is cleaner as a post-pass that the test suite can target directly.

### Why this is safe enough

- Bleach already escapes attribute values, so a malicious `alt` or `src` can't break out of the tag.
- `src` is constrained to `https://` only. No `http://`, no `data:`, no `javascript:`, no `blob:`.
- `BLOG_ALLOWED_ATTRIBUTES["img"]` is deliberately tight — no `onerror`, no `srcset`, no `style`.
- Admin authoring path is the only new exposure surface, and admins are trusted operators (root admin is Etastic per memory `project_root_admin_is_developer.md`).

### Tracked follow-up — body-image R2 proxy

The remaining residual risk is **third-party host control**: a body `<img src="https://some-cdn.example.com/foo.jpg">` fetched fresh from a visitor's browser on every page load is a third-party hot dependency. If that host turns malicious, drops the image, or rotates the URL, your blog page degrades or worse.

**Second guardrail (deferred to v1.1, not v1):** rewrite `content_html` body `<img src="...">` URLs the same way we proxy hero images — download via httpx, push to R2 via `BlogUploadService.upload_from_url`, rewrite the `src` attribute to the R2 CDN URL. Spec:

```python
# Pseudocode for the v1.1 follow-up
def _rewrite_body_images_to_r2(html: str, blg_id: int) -> str:
    for img_tag in find_img_tags(html):
        src = extract_src(img_tag)
        if src.startswith(f"https://{settings.normalized_blog_media_domain}"):
            continue   # already on our R2
        try:
            result = blog_upload_service.upload_from_url(
                src, folder=f"blog/synced/{blg_id}/inline"
            )
            html = html.replace(src, result["cdn_url"])
        except Exception:
            log.warning("Body image proxy failed; leaving src as-is", src=src, blg_id=blg_id)
    return html
```

This is **explicitly out of v1 scope** for the same reason hero proxying belongs in v1: consistency matters, but body inline images are a smaller blast radius than hero (they don't appear in social cards / SEO previews) so the staging is justified. Track as a separate ticket once v1 lands and stabilizes.

## Risks / open questions

Items addressed inline above are no longer listed here. Items are now decisions where Etastic has signed off, or genuinely deferred follow-ups.

1. **DECIDED — `<img>` in global allowlist.** See dedicated section "Inline `<img>` policy" below for the spec. Was Option A of three.
2. **DEFERRED — JSON-LD / FAQ schema.** BLG sends structured data (`jsonLd`, `faqJsonLd`). We don't surface schema.org markup today. Worth adding for SEO, out of scope for v1.
3. **DECIDED — language filter is `en` only.** BLG can generate non-English (`languageCode` field is present in responses — citation: https://www.babylovegrowth.ai/docs/integrations/api response examples). Our `blog_articles` model has no i18n. Sync drops anything where `languageCode != "en"` with a `logger.info("Skipped non-English BLG article", blg_id=..., language=...)`. Revisit when i18n lands on the blog.
4. **DECIDED — truncation policy is silent + warn.** Title > 200 chars, meta_description > 160 chars, etc. Sync truncates and emits `logger.warning(..., blg_id=...)`. Sentry will surface if it happens frequently.
5. **DEFERRED — category mapping.** Everything defaults to `"general"` (one of nine valid `BLOG_CATEGORIES` per `app/models/blog.py:15-25`). Not great long-term; out of scope for v1. Follow-up: keyword→category mapper from `seedKeyword`.
6. **CONTEXT — auth/session/402 cluster.** `AGENTS.md:293-302` lists two open items: (1) middleware converts 422 to 500 on `RequestValidationError`, (2) billing-block state fragmented across four layers (pre-prod blocker, task #20). **This integration does NOT interact with either.** The new sync endpoint has no request body (no validation surface), is hit by external cron (no browser billing-block path), and root admin (Etastic) shouldn't be billing-blocked per memory `project_root_admin_is_developer.md`. Land independently of those tickets.

## What stays the same

- `BlogService.get_published_articles`, `get_article_by_slug`, `get_slugs` — no change. Sync articles read like any other.
- `app/resources/blog/[slug]/page.tsx` — no change. Renders synced articles automatically.
- `app/resources/page.tsx` blog index — no change.
- Admin blog CRUD UI — no change. (Could add a "Synced from BLG" badge later.)
- Sitemap generation — no change. `get_slugs()` already returns all published slugs.

## Out of scope for v1

- Webhook endpoint (BLG → us). Add later if/when you want real-time.
- Two-way sync (us → BLG). Not supported by their API.
- JSON-LD rendering.
- Keyword → category mapping.
- Body-image R2 proxy. **Hero image IS in v1; inline body `<img>` URLs stay on BLG's CDN.** v1.1 follow-up — see "Inline `<img>` policy → Tracked follow-up" section.
- Edit detection. v1 is insert-only. If BLG edits an article post-publish, our copy stays at the first-sync version — see "Article edits" section.
- Multi-language. v1 filters to `languageCode == "en"`. i18n on `blog_articles` itself is a separate effort.
- Admin UI for sync status (just hit the status endpoint for now).
- Slack/email notification on sync failures (logs + Sentry sufficient for v1).

## File-touch plan when implementation begins

```
NEW   app/services/babylovegrowth_sync_service.py    # ~250 LOC including lock + run-state methods
NEW   tests/backend/test_babylovegrowth_sync.py      # mock httpx, table-driven mapping, error-taxonomy, lock contention
NEW   tests/backend/test_blog_upload_from_url.py     # mock httpx + S3 client, content-type + size-cap cases
NEW   tests/backend/test_blog_content_img_allowlist.py  # exhaustive bleach tests: https-only src enforced, javascript:/data:/blob: dropped, attr surface tight
EDIT  app/api/blog.py                                # +2 endpoints (sync trigger + status read), ~40 LOC
EDIT  app/services/blog_upload_service.py            # +upload_from_url method (~60 LOC)
EDIT  app/utils/blog_content.py                      # add `img` to allowlist + post-bleach https-only src enforcement
EDIT  app/core/settings.py                           # +4 BABYLOVEGROWTH_* env fields (incl. LAND_AS_DRAFT)
EDIT  app/core/database_indexes.py                   # +partial unique index on babylovegrowth_id
EDIT  AGENTS.md                                      # one-line note: server-side R2 uploads go via BlogUploadService.upload_from_url
DB    one-time migration: ensure babylovegrowth_sync_runs has a single seed doc with status="idle"
```

No changes to `app/models/blog.py` (the new field is sync-metadata, not part of the validated authoring schema). No new R2 bucket, no new `MediaStorage` target, no new public CDN domain.

## Verification plan (per CLAUDE.md two-layer rule)

- **Automated (`testbed/`):** `testbed/verify_babylovegrowth_sync.py` runs against a dedicated test Mongo DB (NOT prod `blog_articles`) and an R2 prefix scoped to `blog/synced/test-fixtures/`. Test-mode env: `BABYLOVEGROWTH_API_BASE_URL` pointed at a local httpx mock server returning fixture payloads. Cases:
  - **Mapping:** single article happy path, oversized title (verify truncate-with-warning), missing excerpt (verify fallback from `meta_description`), malformed slug (verify regeneration), non-English `languageCode` (verify skip).
  - **Idempotency:** duplicate run produces zero new inserts, `skipped_count` increases.
  - **Lock:** concurrent invocations — second caller observes `status="running"` and returns early without consuming BLG quota.
  - **Error taxonomy (BLG-documented):** 401 → kill switch flipped + run fails; 404 on single-fetch → skipped + logged; 429 → backoff 1s/2s/4s then skip.
  - **Error taxonomy (HTTP hygiene):** 503 → backoff + skip; `httpx.ReadTimeout` → backoff + skip; malformed JSON → skip with truncated body log.
  - **Per-run threshold:** > 20% errors → `status="failed"`; ≤ 20% → `status="partial"`.
  - **Image fetch:** success (asserts cdn_url under `BLOG_MEDIA_DOMAIN`), 404 (article still synced, `og_image=None`), oversized > 5 MB (rejected pre-upload), wrong content-type (rejected).
  - **Draft default:** with `BABYLOVEGROWTH_LAND_AS_DRAFT=true`, synced article has `status="draft"` and is invisible to `BlogService.get_published_articles`.
  - **Inline `<img>` allowlist:** `<img src="https://...">` survives sanitization; `<img src="http://...">`, `<img src="data:...">`, `<img src="javascript:...">`, `<img src="blob:...">`, `<img onerror="...">` all dropped or attribute-stripped. Existing admin-authored articles re-sanitize without regression.
- **Live with Etastic watching (Chrome):** generate one real BLG article in their dashboard, hit `POST /sync-babylovegrowth`, then in admin UI find the synced article in draft state, publish manually, watch it appear at `/resources/blog/<slug>` with the hero image served from your R2/CDN (verify in DevTools Network tab — `Request URL` should be your `BLOG_MEDIA_DOMAIN`, not BLG's CDN). Hit sync again, confirm no duplicate.

Sync is considered done when both layers agree.
