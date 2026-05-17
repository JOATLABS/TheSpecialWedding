#!/usr/bin/env python3
"""
CP1 Retro — Image Allowlist Persisted Through Mongo Round-Trip
==============================================================

Validates that the img allowlist change in app/utils/blog_content.py
holds end-to-end: create a blog article through BlogService with body
images embedded in content_html, retrieve it, and assert the imgs
survived sanitization at the service boundary.

Unit coverage (tests/backend/test_blog_content_img_allowlist.py) only
proves the sanitizer itself behaves correctly. This driver proves the
sanitizer is wired at the right boundary in BlogService.create_article
and that what we put in is what comes back out via get_article_by_slug.

Strategy
--------
SEED:
    - Insert a blog article through BlogService.create_article with
      a body containing 4 imgs: one https (must survive), one http
      (must be dropped), one javascript: (must be dropped), and one
      data: (must be dropped). Also include benign editorial HTML so
      we exercise the full sanitize_blog_content path.

VERIFY:

    [CHECKPOINT 1/3] Article persisted, retrievable by slug
    [CHECKPOINT 2/3] Body content_html still contains the https <img>
                     with src=https://... intact
    [CHECKPOINT 3/3] Body content_html does NOT contain any of the
                     dropped imgs (http://, javascript:, data:)

Pair: cleanup_blg_sync_state.py (purges the test article)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._blg_sync_common import (  # noqa: E402
    BLG_TEST_IDS,
    banner,
    checkpoint_pause,
    delete_blog_articles,
    find_blog_article,
    now_utc,
)


TEST_TITLE = "BLG Allowlist Round-Trip Test"
TEST_BLG_ID = BLG_TEST_IDS["img_allowlist_persisted"]

# Body deliberately mixes one allowed and three disallowed imgs. The
# sanitize_blog_content function should keep the https one and drop
# the other three. This is the exact failure mode we'd hit at runtime
# if the allowlist wired at the wrong layer.
TEST_CONTENT_HTML = (
    "<h2>Section heading</h2>"
    "<p>Body intro paragraph long enough to satisfy the 50-char min.</p>"
    '<img src="https://cdn.example.com/keep-me.jpg" alt="Allowed">'
    '<img src="http://insecure.example.com/drop-me.jpg" alt="HTTP">'
    '<img src="javascript:alert(1)" alt="XSS">'
    '<img src="data:image/png;base64,iVBORw0KGgo=" alt="Inline data">'
    "<p>Trailing paragraph.</p>"
)


async def seed() -> str:
    """Insert the test article through the real BlogService.

    Returns the slug the article was persisted under.
    """
    from app.models.blog import BlogArticleCreateModel
    from app.services.blog_service import blog_service

    # Idempotent seed: if a previous run left the article behind,
    # drop it first so we always insert fresh.
    await delete_blog_articles({"babylovegrowth_id": TEST_BLG_ID})
    await delete_blog_articles({"title": TEST_TITLE})

    create_model = BlogArticleCreateModel(
        title=TEST_TITLE,
        content=TEST_CONTENT_HTML,
        excerpt="Round-trip test for CP1 img allowlist persistence.",
        category="general",
        tags=["testbed", "cp1"],
        status="published",
        featured=False,
        author_name="Testbed CP1",
    )
    result = await blog_service.create_article(
        data=create_model, author_email="testbed+cp1@thespecialwedding.io"
    )

    # Tag the article with our reserved BLG ID so cleanup can sweep it
    # even if title or slug drift.
    from app.core.database import mongo

    await mongo.db["blog_articles"].update_one(
        {"slug": result["slug"]},
        {"$set": {"babylovegrowth_id": TEST_BLG_ID, "synced_at": now_utc()}},
    )

    return result["slug"]


async def main() -> None:
    banner("verify_blg_img_allowlist_persisted (CP1)")

    print("  SEED: inserting article with mixed img sources via BlogService…")
    slug = await seed()
    print(f"    • slug: {slug}")

    print()
    print("  VERIFY")

    # Checkpoint 1: article persisted, retrievable by slug.
    article = await find_blog_article({"slug": slug})
    assert article is not None, f"Article with slug {slug!r} not found after create"
    assert article.get("status") == "published"
    checkpoint_pause(
        "1/3 — Article persisted and retrievable",
        [
            f"slug={slug}",
            f"status={article.get('status')}",
            f"babylovegrowth_id={article.get('babylovegrowth_id')}",
        ],
    )

    # Checkpoint 2: https img survives.
    content = article["content"]
    assert "<img" in content, "No <img> tag survived sanitization at all"
    assert 'src="https://cdn.example.com/keep-me.jpg"' in content, (
        f"Expected https img to survive but got:\n{content[:400]}"
    )
    checkpoint_pause(
        "2/3 — https <img> survives sanitization",
        [
            "content contains <img>",
            'src="https://cdn.example.com/keep-me.jpg" present',
            'alt="Allowed" present',
        ],
    )

    # Checkpoint 3: disallowed imgs dropped.
    forbidden = ["http://insecure.example.com", "javascript:", "data:image/png"]
    leaks = [token for token in forbidden if token.lower() in content.lower()]
    assert not leaks, f"Sanitizer leaked disallowed sources: {leaks}"
    checkpoint_pause(
        "3/3 — disallowed imgs dropped",
        [
            "http:// img absent",
            "javascript: img absent",
            "data: img absent",
        ],
    )

    print()
    print("  ✅ CP1 allowlist round-trip verified.")
    print("  Run testbed/cleanup_blg_sync_state.py to remove the seeded article.")


if __name__ == "__main__":
    asyncio.run(main())
