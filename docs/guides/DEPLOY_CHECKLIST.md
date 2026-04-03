# Deploy Checklist: Blog & KB Image Upload + Public Page Wiring

**Date:** 2026-03-22 | **Release:** Blog/KB Image System + Public Resources API Integration

---

## Changes in This Release

**Backend (FastAPI + MongoDB)**

- KB models now include `card_image` and `og_image` fields (models, API, service, seed)
- Blog seed content converted from HTML to Markdown (fixes rendering on public pages)
- Blog seed now includes `created_by` field (aligns with KB seed)
- KB service uses direct field access instead of `getattr` for image fields
- New blog text indexes added to `database_indexes.py` (6 indexes: unique slug, status+category, featured, full-text search, popular, published_at)
- `BlogUploadService._get_cdn_domain()` now logs warnings on CDN domain fallback
- Both seed scripts (`seed_blog`, `seed_knowledge_base`) run on startup with idempotency checks

**Frontend (Next.js 14 + TypeScript)**

- `/resources` page now fetches from blog API instead of hardcoded data, with graceful fallback
- `/resources/blog/[slug]` page fetches from API with OG meta tag support (`og_image`)
- New `BlogArticleContent.tsx` client component for Markdown rendering in server component pages
- KB `ArticleEditor.tsx` rewritten with image upload (drag-to-upload, CDN URL paste, preview)
- KB `ArticleCard.tsx` now displays `card_image` with hover animation
- `next.config.js` updated to include `BLOG_MEDIA_DOMAIN` in image remote patterns

**SEO Fixes**

- Canonical URLs added to blog article pages (`<link rel="canonical">` + `og:url`)
- BlogPosting JSON-LD structured data on every blog article (headline, author, publisher, datePublished, image)
- Sitemap now fetches blog slugs dynamically from `/api/v1/blog/slugs` (hourly revalidation, falls back to 7 seed slugs)

---

## Pre-Deploy

### Environment Variables

- [ ] `NEXT_PUBLIC_API_BASE_URL` set to production API URL (e.g. `https://api.thespecialwedding.io`)
- [ ] `S3_BLOG_BUCKET_NAME` set (currently `knowledgebase-saas-blogs`)
- [ ] `BLOG_MEDIA_DOMAIN` set (currently `blogs.thespecialwedding.io`)
- [ ] `S3_ENDPOINT_URL` set (Cloudflare R2 endpoint)
- [ ] `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` set (shared R2 credentials)
- [ ] `MEDIA_DOMAIN` set (gallery CDN fallback)
- [ ] `AD_MEDIA_DOMAIN` set (ad assets CDN fallback)

### R2 Bucket Configuration

- [ ] `knowledgebase-saas-blogs` R2 bucket exists and is accessible
- [ ] Bucket CORS allows PUT from your frontend domain (for presigned uploads)
- [ ] CDN domain `blogs.thespecialwedding.io` resolves and points to R2 bucket
- [ ] Test presigned URL upload works: `GET /admin/blog/upload-url?filename=test.jpg&content_type=image/jpeg&folder=blog`
- [ ] Test KB upload path works: `GET /admin/blog/upload-url?filename=test.jpg&content_type=image/jpeg&folder=kb/cards`

### DNS & CDN

- [ ] `blogs.thespecialwedding.io` DNS is active and serving R2 content
- [ ] HTTPS certificate valid on `blogs.thespecialwedding.io`
- [ ] Image URLs like `https://blogs.thespecialwedding.io/blog/cards/test.jpg` resolve correctly

### Code Quality

- [ ] All Python files pass syntax validation (`python3 -c "import ast; ast.parse(...)"`
- [ ] TypeScript compiles clean (no errors outside `docs/` example files)
- [ ] `react-markdown@^10.1.0` and `remark-gfm@^4.0.1` in `package.json` dependencies
- [ ] No hardcoded localhost URLs in production code paths
- [ ] `getApiBaseUrl()` throws if `NEXT_PUBLIC_API_BASE_URL` is missing (validated)

### Database

- [ ] MongoDB `blog_articles` collection exists (created by seed script on startup)
- [ ] MongoDB `kb_articles` collection exists (created by seed script on startup)
- [ ] Blog indexes will be created on startup (6 new indexes via `create_blog_articles_indexes()`)
- [ ] KB indexes already exist (7 indexes via `create_kb_articles_indexes()`)
- [ ] Verify index creation doesn't conflict with existing indexes (idempotent `create_index` calls)

### Seed Data

- [ ] Blog seed script is idempotent (checks `count_documents > 0` before inserting)
- [ ] KB seed script is idempotent (checks by slug before inserting each article)
- [ ] Blog seed content is now Markdown (no HTML tags) — matches `react-markdown` rendering
- [ ] Blog seed includes `created_by: "hello@thespecialwedding.io"` field
- [ ] KB seed includes `card_image` and `og_image` fields (currently `None`, correct for initial seed)
- [ ] Blog seed includes `card_image` and `og_image` fields (currently `None`, correct for initial seed)

---

## Deploy

### Staging Verification

- [ ] Deploy to staging environment
- [ ] Verify both seed scripts run on startup (check logs for "inserted" counts)
- [ ] Verify blog indexes created (check logs for "All blog articles indexes created")
- [ ] Verify `/resources` page loads and displays blog articles from API
- [ ] Verify `/resources` page falls back to hardcoded data if API is unavailable
- [ ] Verify clicking a blog card opens the article with full Markdown rendering
- [ ] Verify OG meta tags render correctly (use https://opengraph.xyz or browser dev tools)
- [ ] Verify `<link rel="canonical">` is present in blog article page source
- [ ] Verify BlogPosting JSON-LD is in page source (`<script type="application/ld+json">`)
- [ ] Verify `/sitemap.xml` includes all blog slugs (fetched dynamically from API)
- [ ] Verify admin KB editor loads with image upload zones
- [ ] Upload a test image via KB editor (card image) — confirm it appears in R2 bucket under `kb/cards/`
- [ ] Upload a test image via KB editor (OG image) — confirm it appears under `kb/og/`
- [ ] Upload a test image via Blog editor — confirm it appears under `blog/cards/` or `blog/og/`
- [ ] Verify uploaded images display correctly in KB ArticleCard
- [ ] Verify CDN URLs resolve (click the image URL from the editor)

### Production Deploy

- [ ] Deploy to production
- [ ] Monitor application logs for startup errors (seed scripts, index creation)
- [ ] Monitor error rates for 15 minutes post-deploy
- [ ] Check API response times for `/api/v1/blog/articles` (should be < 200ms)

---

## Post-Deploy

### Smoke Tests

- [ ] `GET /api/v1/blog/articles` returns 7 seeded articles with correct Markdown content
- [ ] `GET /api/v1/blog/articles/slug/introducing-the-special-wedding` returns full article
- [ ] `GET /api/v1/blog/slugs` returns all 7 slugs (used for sitemap)
- [ ] Public `/resources` page renders articles with images and proper formatting
- [ ] Blog article pages render Markdown correctly (headings, bold, lists, tables)
- [ ] OG tags populate correctly when sharing a blog URL on social media
- [ ] Admin KB article creation works with image upload
- [ ] Admin KB article list shows card images on article cards
- [ ] No console errors on `/resources` page
- [ ] No CORS errors when uploading images via presigned URLs

### SEO Verification

- [ ] Canonical URL in page source matches `https://thespecialwedding.io/resources/blog/{slug}`
- [ ] `og:url` matches canonical URL
- [ ] BlogPosting JSON-LD validates at https://validator.schema.org (paste page URL)
- [ ] JSON-LD includes `headline`, `datePublished`, `author`, `publisher`, `mainEntityOfPage`
- [ ] `/sitemap.xml` lists all published blog slugs (not just the 7 seed articles)
- [ ] Sitemap falls back to seed slugs if API is unreachable (test by blocking API temporarily)
- [ ] Google Rich Results Test passes for blog article URLs (https://search.google.com/test/rich-results)

### Metrics to Monitor

- [ ] API latency on blog endpoints (baseline < 200ms)
- [ ] R2 upload success rate (presigned URL → PUT → CDN resolution)
- [ ] Frontend error rate (check for hydration mismatches from Markdown rendering)
- [ ] Image CDN cache hit rate (Cloudflare analytics)
- [ ] MongoDB query performance (new blog indexes should improve search)

### Stakeholder Notification

- [ ] Confirm blog content renders correctly on production `/resources` page
- [ ] Confirm KB image upload workflow works for admin users
- [ ] Update any documentation referencing the old hardcoded blog data

---

## Rollback Plan

**Trigger rollback if:**

- Blog API returns 500 errors consistently (> 5% error rate)
- Seed script fails and blog_articles collection is empty (no fallback articles)
- Image uploads fail due to R2 credentials or CORS misconfiguration
- Markdown rendering produces broken output (raw HTML tags visible)
- OG meta tags return errors or blank content on social platforms

**Rollback steps:**

1. Revert to previous deployment (frontend and backend)
2. Blog seed is idempotent — no data cleanup needed (articles won't be re-inserted if they exist)
3. New blog indexes are harmless even if code is reverted (MongoDB ignores unused indexes)
4. If R2 bucket has test images from staging, they can remain (no impact)

---

## Known Limitations

1. **Seed images are `None`:** Both blog and KB seed articles ship without images. Card images and OG images must be uploaded manually via the admin panel after deployment.
2. **KB is auth-gated:** KB articles require planner/admin authentication. They are not exposed on the public `/resources` marketing page (only blog articles are public).
3. **Markdown table rendering:** The HoneyBook vs Aisle Planner article contains a comparison table in Markdown format. Verify `remark-gfm` renders it correctly — GFM tables require proper pipe-delimited formatting.
4. **`next/image` not used for CDN images:** Blog card images use raw `<img>` tags, not `next/image`. The `BLOG_MEDIA_DOMAIN` remote pattern in `next.config.js` enables future migration to `next/image` if needed.
