"""
Knowledge Base API Endpoints
Community-driven documentation system for wedding planners
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner, ExtendedAuthUser
from app.services.knowledge_base_service import knowledge_base_service
from app.models.knowledge_base import KB_CATEGORIES
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== REQUEST MODELS ====================

class ArticleCreateRequest(BaseModel):
    """Request model for creating a KB article"""
    title: str = Field(..., min_length=5, max_length=200, description="Article title")
    content: str = Field(..., min_length=50, max_length=50000, description="Markdown content")
    excerpt: str = Field(..., min_length=20, max_length=500, description="Short summary")
    category: str = Field(default="general", description="Article category")
    tags: List[str] = Field(default_factory=list, description="Article tags")
    status: str = Field(default="published", description="Article status")

    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v not in KB_CATEGORIES:
            raise ValueError(f'Category must be one of: {", ".join(KB_CATEGORIES)}')
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v not in ['draft', 'published']:
            raise ValueError('Status must be draft or published')
        return v

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if v:
            return [tag.lower().strip() for tag in v if tag.strip()][:10]
        return v


class ArticleUpdateRequest(BaseModel):
    """Request model for updating a KB article"""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    content: Optional[str] = Field(None, min_length=50, max_length=50000)
    excerpt: Optional[str] = Field(None, min_length=20, max_length=500)
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    featured: Optional[bool] = None
    order: Optional[int] = None

    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v is not None and v not in KB_CATEGORIES:
            raise ValueError(f'Category must be one of: {", ".join(KB_CATEGORIES)}')
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in ['draft', 'published', 'archived']:
            raise ValueError('Status must be draft, published, or archived')
        return v


class FeedbackRequest(BaseModel):
    """Request model for submitting article feedback"""
    helpful: bool = Field(..., description="Was the article helpful?")
    comment: Optional[str] = Field(None, max_length=500, description="Optional comment")


class MarkOfficialRequest(BaseModel):
    """Request model for marking article as official"""
    is_official: bool = Field(..., description="Mark as official platform documentation")


# ==================== PUBLIC ENDPOINTS ====================
# These endpoints are accessible to all authenticated planners


@router.get("/kb/articles", tags=["Knowledge Base"])
async def get_articles(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, min_length=2, description="Search query"),
    featured_only: bool = Query(False, description="Only featured articles"),
    official_only: bool = Query(False, description="Only official articles"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get published KB articles with optional filtering
    - All authenticated planners can access
    - Supports search, category filter, and pagination
    """
    return await knowledge_base_service.get_articles(
        page=page,
        limit=limit,
        category=category,
        search=search,
        status="published",
        featured_only=featured_only,
        official_only=official_only
    )


@router.get("/kb/articles/slug/{slug}", tags=["Knowledge Base"])
async def get_article_by_slug(
    slug: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get a specific article by its slug
    - Increments view count on access
    - Returns full article content with author info
    """
    return await knowledge_base_service.get_article_by_slug(slug, increment_view=True)


@router.get("/kb/categories", tags=["Knowledge Base"])
async def get_categories(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get all KB categories with article counts
    - Used for sidebar navigation
    """
    return await knowledge_base_service.get_categories_with_counts()


@router.get("/kb/search", tags=["Knowledge Base"])
async def search_articles(
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Max results"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Full-text search across KB articles
    - Searches title, excerpt, content, and tags
    - Returns only published articles
    """
    return await knowledge_base_service.search_articles(query=q, limit=limit)


@router.get("/kb/my-articles", tags=["Knowledge Base"])
async def get_my_articles(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Get articles created by the current user
    - ROOT_ADMIN only — for managing your own articles
    """
    return await knowledge_base_service.get_my_articles(
        author_email=current_user.email,
        page=page,
        limit=limit
    )


@router.get("/kb/articles/{article_id}/related", tags=["Knowledge Base"])
async def get_related_articles(
    article_id: str,
    limit: int = Query(5, ge=1, le=10),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get related articles based on category and tags
    """
    return await knowledge_base_service.get_related_articles(
        article_id=article_id,
        limit=limit
    )


# ==================== CREATE/UPDATE ENDPOINTS ====================
# Community-driven: All planners can create articles


@router.post("/kb/articles", tags=["Knowledge Base"])
async def create_article(
    article_data: ArticleCreateRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Create a new KB article
    - ROOT_ADMIN only — knowledge base is platform documentation
    - Author is automatically set from current user
    """
    # Get author name from user profile
    from app.core.database import mongo
    users_collection = mongo.get_users_collection()
    user_doc = await users_collection.find_one(
        {"email": current_user.email},
        {"first_name": 1, "last_name": 1, "company_name": 1, "_id": 1}
    )

    author_name = "Unknown"
    author_id = ""
    if user_doc:
        author_id = str(user_doc.get("_id", ""))
        if user_doc.get("company_name"):
            author_name = user_doc["company_name"]
        else:
            first = user_doc.get("first_name", "")
            last = user_doc.get("last_name", "")
            author_name = f"{first} {last}".strip() or current_user.email

    from app.models.knowledge_base import KnowledgeBaseArticleCreateModel
    create_model = KnowledgeBaseArticleCreateModel(
        title=article_data.title,
        content=article_data.content,
        excerpt=article_data.excerpt,
        category=article_data.category,
        tags=article_data.tags,
        status=article_data.status
    )

    logger.info(f"Creating KB article '{article_data.title}' by {current_user.email}")

    return await knowledge_base_service.create_article(
        article_data=create_model,
        author_email=current_user.email,
        author_id=author_id,
        author_name=author_name
    )


@router.put("/kb/articles/{article_id}", tags=["Knowledge Base"])
async def update_article(
    article_id: str,
    article_data: ArticleUpdateRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Update a KB article
    - ROOT_ADMIN only — knowledge base is platform documentation
    """
    from app.models.knowledge_base import KnowledgeBaseArticleUpdateModel
    update_model = KnowledgeBaseArticleUpdateModel(
        title=article_data.title,
        content=article_data.content,
        excerpt=article_data.excerpt,
        category=article_data.category,
        tags=article_data.tags,
        status=article_data.status,
        featured=article_data.featured,
        order=article_data.order
    )

    return await knowledge_base_service.update_article(
        article_id=article_id,
        update_data=update_model,
        current_user=current_user
    )


@router.delete("/kb/articles/{article_id}", tags=["Knowledge Base"])
async def delete_article(
    article_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Delete a KB article
    - ROOT_ADMIN only — knowledge base is platform documentation
    """
    return await knowledge_base_service.delete_article(
        article_id=article_id,
        current_user=current_user
    )


# ==================== FEEDBACK ENDPOINTS ====================


@router.post("/kb/articles/{article_id}/feedback", tags=["Knowledge Base"])
async def submit_feedback(
    article_id: str,
    feedback_data: FeedbackRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Submit helpful/not helpful feedback for an article
    - Users can update their feedback if they change their mind
    """
    return await knowledge_base_service.submit_feedback(
        article_id=article_id,
        helpful=feedback_data.helpful,
        user_email=current_user.email,
        comment=feedback_data.comment
    )


# ==================== ROOT_ADMIN ONLY ENDPOINTS ====================


@router.put("/kb/articles/{article_id}/official", tags=["Knowledge Base"])
async def mark_article_official(
    article_id: str,
    request_data: MarkOfficialRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Mark an article as official platform documentation
    - ROOT_ADMIN only
    - Official articles appear at the top of listings
    """
    return await knowledge_base_service.mark_official(
        article_id=article_id,
        is_official=request_data.is_official,
        current_user=current_user
    )


@router.get("/kb/admin/all-articles", tags=["Knowledge Base"])
async def get_all_articles_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None, min_length=2),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Get all articles regardless of status (ROOT_ADMIN only)
    - Includes draft, published, and archived articles
    - For moderation purposes
    """
    return await knowledge_base_service.get_articles(
        page=page,
        limit=limit,
        category=category,
        search=search,
        status=status if status else "published",
        featured_only=False,
        official_only=False
    )
