"""
Blog API Endpoints
Public endpoints for the /resources page (no auth) + Admin CRUD (ROOT_ADMIN only)
"""
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.services.blog_service import blog_service
from app.models.blog import BLOG_CATEGORIES
from app.utils.rate_limiter import (
    public_read_limiter,
    public_slug_limiter,
    check_rate_limit,
    get_client_ip,
)
import logging

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
    Used by the /resources page on the marketing site.
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
    from app.services.gallery_upload_service import BlogUploadService
    blog_upload = BlogUploadService()
    return blog_upload.create_presigned_upload_url(
        filename=filename,
        folder=folder,
        content_type=content_type,
    )
