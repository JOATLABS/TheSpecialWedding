# Vendor Scraper — Full Code Review

**Date**: 2026-04-02
**Reviewer**: Claude (engineering:code-review)
**Scope**: All 12 files comprising the vendor scraper pipeline — from config through scraping, enrichment, storage, export, import API, frontend modal, service manager integration, and data model.

---

## Dimension Ratings

| Dimension       | Rating | Notes |
|-----------------|--------|-------|
| **Security**        | B+ | Regex injection fixed, shell injection fixed, SSRF protection on import. Two residual issues: API key in photo URLs logged to stdout, and S3 creds loaded at module level (no rotation support). |
| **Performance**     | B+ | Streaming export fixed, polite API delay present, batch_size on cursors. Residual: synchronous S3 upload blocks the async loop; httpx client created per call instead of reused. |
| **Correctness**     | A- | Strong validation on config, proper dedup logic, stat counting fixed. Residual: logo_uploader still uses `city` param (stale after state refactor), meta tag regex misses reversed attribute order. |
| **Maintainability** | A- | Clean separation of concerns, lazy loading, good docstrings, consistent error handling. Minor: no `__init__.py` exports, SYSTEM_CREATED_BY duplicated between config and vendor_service. |

---

## File-by-File Findings

### 1. `config.py` — Scraper Configuration

**Positive observations:**
- Lazy `get_states()` with caching prevents FastAPI startup crash — well-designed pattern.
- Thorough validation: checks JSON structure, required keys per entry, empty strings, empty array.
- Clear error messages include the index of the bad entry and what's missing.
- `SEARCH_QUERIES` cleanly separated from config loading.

**Issues:**

**[LOW] No cache invalidation mechanism** (line 42)
`_states_cache` is set once and never cleared. If states.json is edited while the scraper process is still running (unlikely for CLI, but possible in a long-running FastAPI context), stale data is served. Not a real problem today since the CLI is short-lived, but worth noting for future use.

**[LOW] `SYSTEM_CREATED_BY` defined here but also hardcoded in vendor_service.py** (line 133 config, line 400 vendor_service)
`config.py` has `SYSTEM_CREATED_BY = "system@thespecialwedding.com"` but `vendor_service.py` line 400 hardcodes `"created_by": "system@thespecialwedding.com"` directly. If the email ever changes, one will be missed.
- **Recommendation**: Import `SYSTEM_CREATED_BY` in vendor_service.py instead of hardcoding.

---

### 2. `run.py` — Main Scraper Runner

**Positive observations:**
- `try/finally` with `mongo.close()` ensures cleanup on any exit path.
- `action="extend", nargs="+"` argparse pattern correctly handles multiple state args.
- State filtering matches both abbreviation and full name (case-insensitive) — good UX.
- Stat counting properly distinguishes insert/update/skip using `created_at == updated_at` and `source == "manual"`.
- Polite delay between queries via `asyncio.sleep(REQUEST_DELAY_SECONDS)`.

**Issues:**

**[MEDIUM] `await mongo.connect()` called before `try` block** (line 138)
If `mongo.connect()` succeeds but `VendorService()` on line 141 raises, the `finally` block runs `mongo.close()` — that's fine. But if `get_states()` on line 135 raises (before `connect()`), it raises before the `try` and `mongo.close()` is never called. This is actually correct behavior (no connection to close), but the `await mongo.connect()` should be inside the `try` so that if `connect()` itself raises a partial connection, `close()` still runs.
- **Recommendation**: Move `await mongo.connect()` to be the first line inside `try`.

**[LOW] State filter builds a new lowered list on every iteration** (line 148-149)
```python
state_list = [
    s for s in all_states
    if s[0].lower() in [x.lower() for x in states]
    or s[1].lower() in [x.lower() for x in states]
]
```
`[x.lower() for x in states]` is rebuilt for every `s` in `all_states`. With small lists this is negligible, but it should use a pre-built set:
```python
states_lower = {x.lower() for x in states}
state_list = [s for s in all_states if s[0].lower() in states_lower or s[1].lower() in states_lower]
```

---

### 3. `google_places.py` — Google Places API Client

**Positive observations:**
- API key sent via `X-Goog-Api-Key` header (not query string) for the search endpoint — correct.
- `FIELD_MASK` limits billed fields to only what's needed — cost-conscious.
- `max_results` capped at 20 to match Google's limit.
- Clean `_normalize_place` and `_parse_address_components` separation.
- Graceful fallback: returns `[]` on any error rather than crashing the scraper.

**Issues:**

**[MEDIUM] API key exposed in photo URLs** (line 156-159)
```python
return f"...?maxWidthPx={max_width}&key={GOOGLE_MAPS_API_KEY}"
```
The photo URL contains the API key as a query parameter. This URL is:
1. Logged at INFO level by `logo_uploader.py` line 107: `logger.info(f"Uploaded logo for '{business_name}' → {cdn_url}")` — the cdn_url doesn't contain the key, but `photo_url` is passed to `download_and_upload_logo` and could appear in debug logs.
2. Stored in the `photo_url` field of `places` dict during processing.
The URL with the key is not persisted to MongoDB (it's popped on run.py line 81), so the exposure is limited to process memory and logs.
- **Recommendation**: Avoid logging the raw photo_url. Consider moving the key to a header if the Google Photos media endpoint supports it (it does not for the Places Photos API, so this is a known limitation of the API design).

**[MEDIUM] API key loaded at module level, no validation** (line 19)
```python
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
```
Default is empty string. The `search_vendors` function checks for empty and returns `[]`, but the failure mode is silent — the scraper runs, finds 0 results for every query, reports success with 0 vendors. A missing API key should be loud.
- **Recommendation**: In `search_vendors`, log at WARNING or ERROR level when the key is missing (it already does on line 56 — good). Consider raising in the CLI entrypoint so the scraper fails fast.

**[LOW] New httpx.AsyncClient created per search call** (line 71)
```python
async with httpx.AsyncClient(timeout=15.0) as client:
```
Each call to `search_vendors` creates and tears down a new TCP connection. With 20 queries × N states, this means 20N TCP handshakes + TLS negotiations. A shared client with connection pooling would be more efficient.
- **Recommendation**: Accept an optional `client` parameter or use a module-level client factory.

---

### 4. `website_enricher.py` — Website Scraping for Descriptions & Pricing

**Positive observations:**
- HTML truncated to 50KB (`resp.text[:50_000]`) — prevents OOM on huge pages.
- Custom User-Agent with contact URL — polite bot behavior.
- Price filtering ($50–$100k range) prevents garbage values.
- Graceful degradation — enrichment failure doesn't block vendor insertion.
- Description capped at 2000 chars.

**Issues:**

**[MEDIUM] Meta tag regex misses reversed attribute order** (lines 72-85)
```python
r'<meta\s+(?:property|name)=["\']og:description["\']\s+content=["\']([^"\']+)["\']'
```
This expects `property="og:description" content="..."` but many sites emit `content="..." property="og:description"` (content first). This will miss descriptions on those sites.
- **Recommendation**: Use a more flexible pattern that matches both orderings, or use a lightweight HTML parser like `html.parser` from the standard library:
```python
r'<meta\s+(?:[^>]*?\b(?:property|name)=["\']og:description["\'][^>]*?\bcontent=["\']([^"\']+)["\']|[^>]*?\bcontent=["\']([^"\']+)["\'][^>]*?\b(?:property|name)=["\']og:description["\'])'
```

**[LOW] No SSRF protection on vendor website URLs** (line 45)
The enricher fetches any URL from Google Places results. While Google Places generally returns legitimate business URLs, a compromised or malicious Places listing could return internal network addresses. The import API (`vendor_import.py`) has SSRF protection (`blocked_patterns`), but the scraper's enricher does not.
- **Recommendation**: Add the same private IP/localhost check before fetching.

**[LOW] `follow_redirects=True` without redirect limit** (line 40)
httpx defaults to a max of 20 redirects, which is reasonable, but an explicit limit would make the intent clear and prevent redirect loops from hanging for the full timeout.

---

### 5. `logo_uploader.py` — Google Photos → R2 Upload

**Positive observations:**
- Validates both `S3_AD_BUCKET_NAME` and `AD_MEDIA_DOMAIN` before attempting upload.
- `_slugify` properly sanitizes for S3 key safety (lowercase, alnum + hyphens, truncated to 80 chars).
- Content-type detection from response headers with `.jpg` fallback.
- Separate try/except for download vs upload errors.

**Issues:**

**[HIGH] `city` parameter is stale after state refactor** (line 59, 92)
```python
async def download_and_upload_logo(
    photo_url: str,
    business_name: str,
    city: str,    # ← still expects city
) -> str | None:
    ...
    city_slug = _slugify(city)  # line 92
    key = f"{R2_LOGO_PREFIX}/{city_slug}/..."  # line 95
```
The caller in `run.py` line 86 passes `city=place.get("city", state)` — so when `city` is `None` (which is more likely with state-level scraping), it falls back to the state abbreviation. The R2 key path becomes `scraped-vendors/ok/...` instead of `scraped-vendors/oklahoma-city/...`. This isn't broken, but:
1. The parameter name `city` is misleading — it may contain a state abbreviation.
2. The R2 directory structure becomes inconsistent (mix of city slugs and state abbreviation slugs).
- **Recommendation**: Rename the parameter to `location` or pass both `city` and `state` explicitly, preferring city when available, falling back to state.

**[MEDIUM] Synchronous S3 upload blocks the async event loop** (line 99-104)
```python
s3.upload_fileobj(
    BytesIO(image_bytes),
    _AD_BUCKET_NAME,
    key,
    ExtraArgs={"ContentType": content_type},
)
```
`boto3` is synchronous. This `upload_fileobj` call blocks the entire async event loop for the duration of the upload. With many vendors, this serializes all uploads rather than allowing concurrent processing.
- **Recommendation**: Run in a thread executor: `await asyncio.get_event_loop().run_in_executor(None, _upload_sync, ...)` or use `aioboto3`.

**[MEDIUM] S3 client created per upload call** (line 98)
```python
s3 = _get_s3_client()
```
Every logo upload creates a new boto3 S3 client, which involves credential resolution and connection setup. Should be created once and reused.
- **Recommendation**: Cache the client at module level or use a singleton pattern similar to `get_states()`.

**[LOW] No image size limit on download** (line 79)
```python
image_bytes = resp.content
```
The full response body is read into memory. A malicious or misconfigured photo URL could return a very large file. Google Places photos are typically < 1MB, but there's no guard.
- **Recommendation**: Check `Content-Length` header or limit `resp.content` read to a reasonable max (e.g., 5MB).

**[LOW] S3 credentials loaded at module level** (lines 24-27)
Similar to the API key issue in `google_places.py`. Credentials are read once at import time. If credentials are rotated via environment variable changes, the process must be restarted.

---

### 6. `export_json.py` — JSON Export for Import Modal

**Positive observations:**
- Streaming cursor with `batch_size=5000` — no OOM risk.
- Incremental JSON writing (open bracket, comma-separated docs, close bracket).
- `try/finally` with `mongo.close()`.
- Custom `_serialize_datetime` for clean ISO format output.
- `--since` flag for incremental exports.

**Issues:**

**[LOW] Empty result writes array then overwrites** (lines 100-104)
When count is 0, the code first writes `[\n` then `\n]\n` (creating `[\n\n]\n`), then overwrites the file with `json.dump([], f)`. The first write is wasted I/O. Minor, but could be cleaner by checking count before the write loop or by buffering the open bracket.

**[LOW] No `--limit` flag for partial exports**
If the collection has 50,000 scraped vendors, the only filter is `--since`. A `--limit N` flag would be useful for testing or sampling.

---

### 7. `vendor_service.py` — `upsert_scraped_vendor` Method

**Positive observations:**
- Two-tier dedup: `google_place_id` first (reliable), then `business_name + city + category` fallback (fuzzy).
- `re.escape()` on business_name and city before regex — injection-safe.
- Manual entries (`source == "manual"`) are never overwritten — correct priority.
- Selective field update on refresh — only non-empty new values overwrite existing.
- `portfolio_urls` dedup check before appending.
- Proper `_id` stringification for JSON serialization.

**Issues:**

**[MEDIUM] Race condition on upsert** (lines 319-408)
The pattern is: find_one → check result → insert_one/update_one. Between the `find_one` and the `insert_one`, another concurrent request (e.g., two scraper instances, or a simultaneous manual import) could insert the same vendor. This would create duplicates.
- **Recommendation**: Use MongoDB's `update_one` with `upsert=True` and a unique compound filter (`google_place_id` or `business_name + city + category`). Alternatively, add a unique compound index on `(business_name, city, service_category)` so duplicate inserts fail with a known error that can be caught and retried as an update.

**[MEDIUM] Dedup fallback requires both business_name AND city** (line 325)
```python
if not existing and business_name and city:
```
With state-level scraping, some vendors may have `city = None` (Google Places didn't return a locality component). These vendors can ONLY be deduped by `google_place_id`. If a vendor has no Google Place ID and no city, it will be inserted as a new record every time the scraper runs.
- **Recommendation**: Add a third dedup tier: `business_name + state + category` when city is empty.

**[LOW] `existing.update(update_fields)` mutates the find_one result** (line 371)
```python
existing.update(update_fields)
```
This modifies the `existing` dict in-place to build the return value. Not harmful, but returning a blended dict (part from DB, part from the update) could confuse callers if they expect a pure DB document.

---

### 8. `vendor_import.py` — Import API Endpoint

**Positive observations:**
- `require_root_admin` dependency — proper authorization.
- Pydantic v2 validators for HTML stripping, SSRF protection, category validation.
- 500-vendor hard cap per import.
- Per-vendor error isolation — one bad vendor doesn't abort the batch.
- Error details returned with index and business name for debugging.
- Structured logging with user email.

**Issues:**

**[MEDIUM] SSRF protection is pattern-based, not CIDR-based** (lines 85-88)
```python
blocked_patterns = ["127.0.0.1", "localhost", "10.", "192.168.", "169.254.", "0.0.0.0"]
for pattern in blocked_patterns:
    if pattern in lower:
```
This misses:
1. IPv6 loopback (`::1`, `[::1]`)
2. Octal/hex IP encoding (`0x7f.0.0.1`, `0177.0.0.1`)
3. `172.16.0.0/12` private range
4. DNS rebinding (hostname that resolves to private IP)
The string `in` check also has false positives: a URL like `https://website10.com` matches the `"10."` pattern.
- **Recommendation**: Use `ipaddress.ip_address()` to parse the resolved IP and check against `is_private` / `is_loopback` / `is_reserved`. Add `172.16.` through `172.31.` to patterns at minimum.

**[LOW] No rate limiting on import endpoint**
A malicious or buggy client could spam the import endpoint. Each call processes up to 500 vendors with individual DB upserts. No throttle or cooldown.
- **Recommendation**: Add a rate limit (e.g., 1 import per minute) or a global import lock.

**[LOW] `exclude_none=True` in `model_dump` drops intentional None fields** (line 135)
```python
vendor_data = item.model_dump(exclude_none=True)
```
If a vendor intentionally has `logo_url=None` (to clear a stale logo), the None is excluded and the field won't be updated. This is probably fine for imports (you'd never import a "clear logo" action), but worth documenting.

---

### 9. `VendorImportModal.tsx` — Import Frontend

**Positive observations:**
- File size guard (10MB) before FileReader — prevents browser freeze.
- JSON validation with clear per-vendor error messages.
- Category validation matches backend set.
- Drag & drop with visual feedback.
- Escape key closes modal.
- Proper reset on close (including file input ref).
- Import button disabled during importing stage.
- Error details shown in done stage.
- Glass-panel design system consistently applied.

**Issues:**

**[MEDIUM] No abort/cancel mechanism during import** (lines 195-209)
Once `handleImport` fires, there's no way to cancel. The `importing` stage shows a spinner and a disabled button. If the import hangs (e.g., network issue, backend processing 500 vendors slowly), the user is stuck. The modal can be closed but the request continues in the background.
- **Recommendation**: Use an `AbortController` to cancel the fetch on modal close during importing stage.

**[LOW] `updateCount` heuristic is misleading** (lines 144-146)
```typescript
const updateCount = vendors.filter(
  (v) => v.google_place_id && (v as any).scraped_at
).length;
```
This client-side guess isn't used in the UI (I see `newCount` and `updateCount` in `ParsedData` but neither is rendered). If it's not displayed, it should be removed to avoid confusion.

**[LOW] File input accepts only `.json` by extension, not MIME type** (line 281)
```html
<input type="file" accept=".json" ... />
```
The `accept` attribute is advisory. The actual validation (line 126-127) checks `file.name.endsWith('.json')` which is correct. But `.json` accept could be more lenient by also accepting `application/json` MIME type for better cross-browser behavior.

---

### 10. `vendorManagementApi.ts` — API Client

**Positive observations:**
- `VendorImportItem` interface matches backend Pydantic model field-for-field.
- `scraped_from_state` correctly updated from `scraped_from_city`.
- Bearer token auth on import endpoint.

**Issues:**

**[LOW] No response status check before JSON parse**
(Not fully visible in grep, but typical pattern in this file) — if the import endpoint returns a 500, the `res.json()` call may throw a confusing error instead of surfacing the HTTP status. The frontend `handleImport` catch block shows `err.message` which would be a parse error rather than "Import failed: 500 Internal Server Error".
- **Recommendation**: Check `res.ok` before parsing, throw with status code and response text on failure.

---

### 11. `manage_services.sh` — Service Manager Integration

**Positive observations:**
- States loaded dynamically from `states.json` — single source of truth.
- Python one-liner uses `sys.argv[1]` for file path (not string interpolation).
- State values sanitized: abbreviations `tr -cd 'a-zA-Z0-9'`, full names `tr -cd 'a-zA-Z0-9 .-'`.
- Category input sanitized: `tr -cd 'a-zA-Z0-9,_'`.
- Numeric selection validated against actual state count range.
- Clear output showing selected mode, states, and categories before launch.

**Issues:**

**[LOW] Non-numeric selection silently ignored** (line 669)
```bash
if [[ "$sel" =~ ^[0-9]+$ ]] && (( sel >= 1 && sel <= state_count )); then
```
If the user types `a,1,2` (mixing "all" with numbers), the `a` is silently dropped and only states 1 and 2 are selected. If they type `foo`, no states are selected and the scraper runs with all states (since `state_args` is empty).
- **Recommendation**: Validate that all selections are either "a" or valid numbers. Show a warning for invalid selections.

**[LOW] `PROJECT_ROOT` in single quotes inside `bash -c`** (line 700)
```bash
local cmd="cd '$PROJECT_ROOT' && ..."
```
If `PROJECT_ROOT` contains a single quote, this breaks. Unlikely for a project path, but `printf '%q'` would be safer.

---

### 12. `vendor.py` Model — VendorProfile

**Positive observations:**
- `scraped_from_state` field correctly defined with description.
- `source` field with `"manual"` default — clean enumeration of provenance.
- `google_place_id` field for reliable dedup.
- `scraped_at` datetime for freshness tracking.

**Issues:**

**[LOW] `datetime.utcnow` in `default_factory` is deprecated** (lines 249-250)
```python
created_at: datetime = Field(default_factory=datetime.utcnow)
updated_at: datetime = Field(default_factory=datetime.utcnow)
```
`datetime.utcnow()` is deprecated in Python 3.12+ in favor of `datetime.now(timezone.utc)`. The scraper code correctly uses `datetime.now(timezone.utc)` but the model default doesn't, creating inconsistent timezone awareness (naive vs aware datetimes).
- **Recommendation**: Change to `default_factory=lambda: datetime.now(timezone.utc)`.

---

## Cross-Cutting Concerns

### Positive Patterns Across the Codebase
1. **Consistent error handling**: Every file has try/except with appropriate logging levels and graceful degradation.
2. **Clean separation of concerns**: Config, search, enrichment, upload, storage, export, and import are all independent modules.
3. **Resource cleanup**: `try/finally` for MongoDB connections in both `run.py` and `export_json.py`.
4. **Input validation at every boundary**: Config validation, Pydantic validators on import, regex escaping on dedup, shell sanitization in service manager.
5. **Progressive enhancement**: Website enrichment and logo upload are optional — missing data doesn't block vendor insertion.

### Remaining Items Worth Addressing

| Priority | Issue | File | Description |
|----------|-------|------|-------------|
| **HIGH** | Stale `city` param in logo uploader | `logo_uploader.py:59` | Parameter name misleading after state refactor; R2 key path inconsistent |
| **MEDIUM** | Synchronous S3 in async loop | `logo_uploader.py:99` | boto3 blocks event loop during upload |
| **MEDIUM** | Race condition on upsert | `vendor_service.py:319` | find_one → insert_one gap allows duplicates |
| **MEDIUM** | Meta tag regex misses reversed attrs | `website_enricher.py:72` | Some sites have `content` before `property` |
| **MEDIUM** | SSRF patterns incomplete | `vendor_import.py:85` | Missing IPv6, 172.16/12, octal encoding |
| **MEDIUM** | Dedup fails when city is None | `vendor_service.py:325` | No fallback to state-based dedup |
| **MEDIUM** | No import cancellation | `VendorImportModal.tsx:195` | User stuck if import hangs |
| **MEDIUM** | mongo.connect outside try | `run.py:138` | Partial connection won't be cleaned up |
| **LOW** | API key in photo URLs | `google_places.py:157` | Logged in debug scenarios |
| **LOW** | S3 client per upload | `logo_uploader.py:98` | Wasteful connection setup |
| **LOW** | httpx client per search | `google_places.py:71` | 20N TCP handshakes |
| **LOW** | No SSRF on enricher | `website_enricher.py:45` | Fetches any URL from Places |
| **LOW** | datetime.utcnow deprecated | `vendor.py:249` | Naive vs aware datetime mismatch |
| **LOW** | SYSTEM_CREATED_BY duplicated | `config.py:133`, `vendor_service.py:400` | Hardcoded in two places |

---

## Summary

The vendor scraper pipeline is well-structured with strong fundamentals. The city→state refactor was executed thoroughly across all 12 files with proper validation, sanitization, and error handling at every boundary. The 12 issues found and fixed during the refactor (VS1–VS12) addressed the most critical problems — particularly the shell injection, regex injection, and startup crash.

The remaining findings are mostly MEDIUM and LOW severity. The highest-priority items to address next are the stale `city` parameter in `logo_uploader.py` (correctness), the synchronous S3 upload blocking the async loop (performance), and the race condition in `upsert_scraped_vendor` (correctness under concurrency). None of these are blockers for production use at current scale, but they should be tracked and fixed before scaling up scraping to many states.
