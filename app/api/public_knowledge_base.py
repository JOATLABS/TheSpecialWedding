"""
Public Knowledge Base API Endpoints
Read-only documentation routes for unauthenticated marketing-site visitors.
"""

import logging

from fastapi import APIRouter, Query, Request

from app.services.knowledge_base_service import knowledge_base_service
from app.utils.rate_limiter import (
    check_rate_limit,
    get_client_ip,
    public_read_limiter,
    public_search_limiter,
    public_slug_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/public/kb/articles", tags=["Public Knowledge Base"])
async def get_public_articles(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, min_length=2, description="Search query"),
    featured_only: bool = Query(False, description="Only featured articles"),
    official_only: bool = Query(False, description="Only official articles"),
):
    """Return published KB article cards for the public docs surface."""
    client_ip = get_client_ip(request)
    await check_rate_limit(client_ip, public_read_limiter)

    return await knowledge_base_service.get_public_articles(
        page=page,
        limit=limit,
        category=category,
        search=search,
        featured_only=featured_only,
        official_only=official_only,
    )


@router.get("/public/kb/articles/slug/{slug}", tags=["Public Knowledge Base"])
async def get_public_article_by_slug(request: Request, slug: str):
    """Return a single published KB article by slug."""
    client_ip = get_client_ip(request)
    await check_rate_limit(client_ip, public_slug_limiter)

    return await knowledge_base_service.get_public_article_by_slug(
        slug, increment_view=True
    )


@router.get("/public/kb/categories", tags=["Public Knowledge Base"])
async def get_public_categories(request: Request):
    """Return published KB categories and counts."""
    client_ip = get_client_ip(request)
    await check_rate_limit(client_ip, public_read_limiter)

    return await knowledge_base_service.get_categories_with_counts(status="published")


@router.get("/public/kb/search", tags=["Public Knowledge Base"])
async def search_public_articles(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Max results"),
):
    """Search published KB articles without exposing editor-only fields."""
    client_ip = get_client_ip(request)
    await check_rate_limit(client_ip, public_search_limiter)

    return await knowledge_base_service.search_public_articles(query=q, limit=limit)
