"""
Blog API Endpoints
Public endpoints for the /resources/blog page (no auth) + Admin CRUD (ROOT_ADMIN only)
"""

import logging
import secrets
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
)
from pydantic import BaseModel, Field, field_validator

from app.dependencies.auth_extended import ExtendedAuthUser, require_root_admin
from app.models.blog import BLOG_CATEGORIES
from app.services.blog_service import blog_service
from app.utils.rate_limiter import (
    check_rate_limit,
    get_client_ip,
    public_read_limiter,
    public_slug_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== REQUEST MODELS ====================


class BlogCreateRequest(BaseModel):
    """Request model for creating a blog article"""

    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=50, max_length=100000)
    excerpt: str = Field(..., min_length=20, max_length=500)
    category: str = Field(default="general")
    tags: List[str] = Field(default_factory=list)
    status: str = Field(default="published")
    featured: bool = Field(default=False)
    author_name: str = Field(default="The Special Wedding")
    meta_title: Optional[str] = Field(None, max_length=70)
    meta_description: Optional[str] = Field(None, max_length=160)
    og_image: Optional[str] = None
    card_image: Optional[str] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v not in BLOG_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(BLOG_CATEGORIES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in ["draft", "published"]:
            raise ValueError("Status must be draft or published")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if v:
            return [tag.lower().strip() for tag in v if tag.strip()][:15]
        return v


class BlogUpdateRequest(BaseModel):
    """Request model for updating a blog article"""

    title: Optional[str] = Field(None, min_length=5, max_length=200)
    content: Optional[str] = Field(None, min_length=50, max_length=100000)
    excerpt: Optional[str] = Field(None, min_length=20, max_length=500)
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    featured: Optional[bool] = None
    author_name: Optional[str] = Field(None, max_length=100)
    meta_title: Optional[str] = Field(None, max_length=70)
    meta_description: Optional[str] = Field(None, max_length=160)
    og_image: Optional[str] = None
    card_image: Optional[str] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is not None and v not in BLOG_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(BLOG_CATEGORIES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in ["draft", "published", "archived"]:
            raise ValueError("Status must be draft, published, or archived")
        return v


# ==================== PUBLIC ENDPOINTS (NO AUTH) ====================


@router.get("/api/v1/blog/articles", tags=["Blog"])
async def get_published_articles(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None, min_length=2),
    featured_only: bool = Query(False),
):
    """
    Get published blog articles — PUBLIC, no auth required.
    Used by the /resources/blog page on the marketing site.
    Rate limited to 60 requests per minute per IP.
    """
    client_ip = get_client_ip(request)
    await check_rate_limit(client_ip, public_read_limiter)

    return await blog_service.get_published_articles(
        page=page,
        limit=limit,
        category=category,
        search=search,
        featured_only=featured_only,
    )


@router.get("/api/v1/blog/articles/slug/{slug}", tags=["Blog"])
async def get_article_by_slug(request: Request, slug: str):
    """
    Get a single published article by slug — PUBLIC.
    Used by the split-panel blog reader and direct blog URLs.
    Rate limited to 100 requests per minute per IP.
    """
    client_ip = get_client_ip(request)
    await check_rate_limit(client_ip, public_slug_limiter)

    return await blog_service.get_article_by_slug(slug, increment_view=True)


@router.get("/api/v1/blog/slugs", tags=["Blog"])
async def get_all_slugs(request: Request):
    """
    Get all published blog slugs — PUBLIC.
    Used by the sitemap generator.
    Rate limited to 60 requests per minute per IP.
    """
    client_ip = get_client_ip(request)
    await check_rate_limit(client_ip, public_read_limiter)

    return await blog_service.get_slugs()


# ==================== ADMIN ENDPOINTS (ROOT_ADMIN) ====================


@router.get("/admin/blog/articles", tags=["Blog Admin"])
async def get_all_articles_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None, min_length=2),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get all blog articles regardless of status (ROOT_ADMIN only)"""
    return await blog_service.get_all_articles_admin(
        page=page,
        limit=limit,
        status=status,
        category=category,
        search=search,
    )


@router.get("/admin/blog/articles/{article_id}", tags=["Blog Admin"])
async def get_article_by_id(
    article_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get a blog article by ID (any status, ROOT_ADMIN only)"""
    return await blog_service.get_article_by_id(article_id)


@router.post("/admin/blog/articles", tags=["Blog Admin"])
async def create_article(
    article_data: BlogCreateRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Create a new blog article (ROOT_ADMIN only)"""
    from app.models.blog import BlogArticleCreateModel

    create_model = BlogArticleCreateModel(
        title=article_data.title,
        content=article_data.content,
        excerpt=article_data.excerpt,
        category=article_data.category,
        tags=article_data.tags,
        status=article_data.status,
        featured=article_data.featured,
        author_name=article_data.author_name,
        meta_title=article_data.meta_title,
        meta_description=article_data.meta_description,
        og_image=article_data.og_image,
        card_image=article_data.card_image,
    )

    return await blog_service.create_article(
        data=create_model,
        author_email=current_user.email,
    )


@router.put("/admin/blog/articles/{article_id}", tags=["Blog Admin"])
async def update_article(
    article_id: str,
    article_data: BlogUpdateRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Update a blog article (ROOT_ADMIN only)"""
    from app.models.blog import BlogArticleUpdateModel

    update_model = BlogArticleUpdateModel(
        title=article_data.title,
        content=article_data.content,
        excerpt=article_data.excerpt,
        category=article_data.category,
        tags=article_data.tags,
        status=article_data.status,
        featured=article_data.featured,
        author_name=article_data.author_name,
        meta_title=article_data.meta_title,
        meta_description=article_data.meta_description,
        og_image=article_data.og_image,
        card_image=article_data.card_image,
    )

    return await blog_service.update_article(
        article_id=article_id,
        data=update_model,
    )


@router.delete("/admin/blog/articles/{article_id}", tags=["Blog Admin"])
async def delete_article(
    article_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Delete a blog article (ROOT_ADMIN only)"""
    return await blog_service.delete_article(article_id=article_id)


# ==================== BLOG IMAGE UPLOAD (ROOT_ADMIN) ====================


@router.get("/admin/blog/upload-url", tags=["Blog Admin"])
async def get_blog_image_upload_url(
    filename: str = Query(..., min_length=1),
    content_type: str = Query(default="image/jpeg"),
    folder: str = Query(default="blog"),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get a presigned URL to upload a blog image directly to R2 (ROOT_ADMIN only)"""
    from app.services.blog_upload_service import BlogUploadService

    blog_upload = BlogUploadService()
    return blog_upload.create_presigned_upload_url(
        filename=filename,
        folder=folder,
        content_type=content_type,
    )


# ==================== BABYLOVEGROWTH WEBHOOK (PUBLIC, BEARER-GATED) ====================


@router.post("/webhook/babylovegrowth", tags=["Webhooks"])
async def handle_babylovegrowth_webhook(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Receive BabyLoveGrowth publish webhooks.

    BLG sends this when an article is published from their dashboard.
    We require a shared bearer token because the route is public and
    intentionally not tied to admin browser auth.
    """
    from app.core.settings import settings as _settings
    from app.services.babylovegrowth_sync_service import babylovegrowth_sync_service

    webhook_secret = _settings.babylovegrowth_webhook_secret
    if not webhook_secret:
        raise HTTPException(
            status_code=503,
            detail="BabyLoveGrowth webhook is not configured",
        )

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not secrets.compare_digest(token, webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    try:
        return await babylovegrowth_sync_service.ingest_webhook_article(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ==================== BABYLOVEGROWTH SYNC (ROOT_ADMIN) ====================
#
# These endpoints drive the AI-content-pipeline integration spec'd in
# docs/plans/babylovegrowth_integration_mockup.md. Sync runs in a
# BackgroundTask so the external cron caller gets a quick 202 — same
# pattern as app/api/billing_jobs.py:sync_usage_to_stripe.


@router.post("/admin/blog/sync-babylovegrowth", tags=["Blog Admin"])
async def trigger_babylovegrowth_sync(
    background_tasks: BackgroundTasks,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Trigger a BabyLoveGrowth → blog_articles sync run.

    Two response shapes:

      - ``{"status": "accepted", ...}`` — gate checks passed, real
        sync work scheduled in the background. Consult
        ``GET /admin/blog/sync-babylovegrowth/status`` for progress.
      - ``{"status": "skipped", "reason": ...}`` — gate checks failed.
        Returned SYNCHRONOUSLY because FastAPI BackgroundTasks
        discards return values; if we enqueued the task and let it
        bail inside ``run_full_sync``, the admin UI would see only a
        bare "accepted" with no way to surface the reason. Pre-flight
        gates: ``sync_disabled``, ``no_api_key``, ``lock_held``.

    Note: the lock-held check is racy in principle (we read the lock
    state, then schedule a task that re-acquires it), but the
    advisory lock in ``run_full_sync`` is the authoritative gate and
    will catch any race. The pre-flight check is a UX shortcut, not a
    correctness mechanism.
    """
    from app.core.settings import settings as _settings
    from app.services.babylovegrowth_sync_service import (
        SYNC_STATE_COLLECTION,
        SYNC_STATE_DOC_ID,
        babylovegrowth_sync_service,
    )
    from app.core.database import mongo as _mongo

    if not _settings.babylovegrowth_sync_enabled:
        return {"status": "skipped", "reason": "sync_disabled"}
    if not _settings.babylovegrowth_api_key:
        return {"status": "skipped", "reason": "no_api_key"}

    # Pre-flight lock check — see docstring for the racy-but-fine
    # rationale. If a stale "running" doc was left by a crashed run,
    # run_full_sync's stale-lock TTL handles it.
    state_doc = await _mongo.db[SYNC_STATE_COLLECTION].find_one(
        {"_id": SYNC_STATE_DOC_ID}
    )
    if state_doc and state_doc.get("status") == "running":
        return {"status": "skipped", "reason": "lock_held"}

    background_tasks.add_task(
        babylovegrowth_sync_service.run_full_sync, triggered_by="manual"
    )
    return {
        "status": "accepted",
        "message": "BabyLoveGrowth sync started in background",
    }


@router.post("/admin/blog/sync-babylovegrowth/backfill-images", tags=["Blog Admin"])
async def backfill_babylovegrowth_hero_images(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Retry hero image proxy for synced articles where og_image is None.

    Synchronous (NOT BackgroundTask) so the admin sees per-article
    results in the response. Each failure returns the exact reason
    string from BlogUploadFromUrlError — diagnostic by design.

    Use case: original sync persisted an article but the hero image
    fetch failed (CDN was rate-limiting, wrong content-type, etc.).
    This retries with full error surfacing.
    """
    from app.services.babylovegrowth_sync_service import (
        babylovegrowth_sync_service,
    )

    return await babylovegrowth_sync_service.backfill_hero_images()


@router.get("/admin/blog/sync-babylovegrowth/status", tags=["Blog Admin"])
async def get_babylovegrowth_sync_status(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Return the singleton sync-state document.

    Includes lock state, last-run timestamps, counts (new/skipped/
    image_failed/error), and the last `MAX_RETAINED_ERRORS` errors.
    Used by cron healthchecks ("last successful sync more than N
    hours ago") and by manual debug sessions.
    """
    from app.services.babylovegrowth_sync_service import (
        babylovegrowth_sync_service,
    )

    state = await babylovegrowth_sync_service.get_last_run_status()
    # Mongo's _id is the literal string "babylovegrowth_sync_state" —
    # safe to return as-is in JSON, no ObjectId stringification needed.
    return state
