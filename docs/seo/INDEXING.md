# SEO indexing policy

Last updated: 2026-05-14

## TL;DR

- `app/robots.ts` is permissive on purpose. Don't add Disallow entries for paths that we want Google to de-index.
- `app/main.py::add_robots_headers` emits `X-Robots-Tag: noindex, nofollow` on every response under non-public path prefixes.
- `/admin/login` is the one explicit exception — it stays indexable because it's the public sign-in landing.

If you're tempted to "lock down" a route by adding it to `robots.txt`, read the next section first.

## Why `Disallow` does not de-index

This is the trap that produced the 2026-05-14 Google Search Console "Some fixes failed for Page indexing issues" email.

Robots.txt `Disallow` controls **crawling**, not **indexing**. Google can — and does — keep a URL in its index after a Disallow appears, as long as it has knowledge of the URL from some other source (inbound links, prior crawls, sitemap submissions, the Search Console URL inspector). Affected URLs show up in GSC as:

- `Indexed, though blocked by robots.txt`
- `Crawled — currently not indexed`
- `Discovered — currently not indexed`

When you then submit a re-validation in GSC asking "please verify this is fixed," Googlebot tries to re-crawl the URL, hits the `Disallow`, can't read the page, and reports the validation as **failed** — even though the page itself is now correctly noindex/410/404 server-side. The robots block is the very thing preventing Google from confirming the fix.

## The correct pattern

To remove a URL from the index:

1. **Remove it from `Disallow`** so Googlebot can fetch it.
2. **Return `X-Robots-Tag: noindex, nofollow`** in the HTTP response (or `<meta name="robots" content="noindex">` on the page).
3. Submit for validation in GSC. Googlebot fetches the URL, reads the header/meta, and removes it from the index on the next index update.
4. **Optionally**, once GSC reports the URLs as de-indexed, you may re-add `Disallow` for crawl-budget protection. Be aware this only stops *future* re-crawling; if the URL is ever re-discovered through links, you're back where you started.

The middleware in `app/main.py::add_robots_headers` implements step 2 in a single place so the policy lives next to the cache-headers logic and stays auditable.

## Path-prefix taxonomy

| Prefix              | Public? | Indexed? | Notes                                                          |
| ------------------- | ------- | -------- | -------------------------------------------------------------- |
| `/`                 | ✅      | ✅       | Marketing home — fully indexed.                                |
| `/features`         | ✅      | ✅       | Product features.                                              |
| `/compare/*`        | ✅      | ✅       | Competitor comparison pages.                                   |
| `/resources/*`      | ✅      | ✅       | Blog + templates.                                              |
| `/vendors[/...]`    | ✅      | ✅       | Public vendor directory + per-vendor SEO profiles.             |
| `/privacy`, `/terms`, `/support`, `/google-*` | ✅ | ✅ | Legal / data-deletion (required by Google for OAuth scopes).   |
| `/admin/login`      | ✅      | ✅       | Public sign-in page. Explicit exemption in middleware.         |
| `/admin/*` (other)  | ❌      | ❌       | Authenticated planner workspace.                               |
| `/couple/*`         | ❌      | ❌       | Token-gated couple workspace.                                  |
| `/couple-portal/*`  | ❌      | ❌       | Token-gated couple portal redirect surface.                    |
| `/vendor-contract/*`| ❌      | ❌       | Token-gated vendor contract surface.                           |
| `/api/*`            | ❌      | ❌       | JSON API. Never useful in a public index.                      |
| `/otp/*`            | ❌      | ❌       | One-time-password flows.                                       |
| `/setup-account`    | ❌      | ❌       | Post-signup onboarding (only reachable with a session).        |
| `/reset-password`   | ❌      | ❌       | Reached via emailed reset token.                               |
| `/forgot-password`  | ❌      | ❌       | Form to request reset token. No SEO value, leaks no info.      |
| `/login`            | ❌ (legacy) | ❌  | Footer links now point at `/admin/login`; this is kept noindex in case of inbound links from old domains. |
| `/token`, `/auth`   | ❌      | ❌       | Auth-related machine surfaces.                                 |

When adding a new private surface, add the prefix to both:

- `app/main.py::_NOINDEX_PATH_PREFIXES`
- `tests/backend/test_robots_headers_middleware.py::REQUIRED_NOINDEX_PREFIXES`

The test will fail loudly if you forget either.

## Verifying after deploy

After this branch ships:

```bash
# Should now show X-Robots-Tag: noindex, nofollow:
curl -sSI https://thespecialwedding.io/admin | grep -i x-robots
curl -sSI https://thespecialwedding.io/setup-account | grep -i x-robots
curl -sSI https://thespecialwedding.io/reset-password | grep -i x-robots
curl -sSI https://thespecialwedding.io/api/health | grep -i x-robots

# Should NOT have a noindex header:
curl -sSI https://thespecialwedding.io/admin/login | grep -i x-robots   # expect empty
curl -sSI https://thespecialwedding.io/                | grep -i x-robots  # expect empty

# robots.txt should no longer Disallow the noindexed prefixes:
curl -sS  https://thespecialwedding.io/robots.txt
```

Then in Google Search Console:

1. Open the original "Page indexing issues" report.
2. For each affected URL, click **Validate fix**.
3. Wait for the email confirmation (usually 2–7 days). Googlebot has to re-crawl each URL, read the new `X-Robots-Tag`, and re-evaluate index inclusion.

If the validation still fails after a week, check the URL Inspection tool — it will show the live response Googlebot sees, including whether `X-Robots-Tag` is present.

## See also

- `app/main.py::add_robots_headers` — the middleware that adds the header.
- `app/main.py::_NOINDEX_PATH_PREFIXES` — the canonical list of noindex prefixes.
- `app/robots.ts` — robots.txt source. Must stay in lockstep with the middleware.
- `tests/backend/test_robots_headers_middleware.py` — AST-level guard that pins both lists.
