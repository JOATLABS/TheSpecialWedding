"""
Knowledge Base Models for Community-Driven Documentation System
Provides Pydantic models with validation for KB articles
"""
from pydantic import BaseModel, Field, field_validator, field_serializer
from typing import Optional, List
from datetime import datetime
from app.models.base import MongoModel, UserRelatedModel


# Valid categories for KB articles
KB_CATEGORIES = [
    "getting-started",
    "guest-management",
    "rsvp-invitations",
    "budget-payments",
    "vendors",
    "forms-questionnaires",
    "wedding-configuration",
    "notifications",
    "calendar-tasks",
    "billing-subscription",
    "troubleshooting",
    "tips-tricks",
    "integrations",
    "general"
]


class ArticleFeedbackModel(BaseModel):
    """Individual feedback entry for an article"""
    user_email: str = Field(..., max_length=254, description="Email of user who gave feedback")
    helpful: bool = Field(..., description="Whether the article was helpful")
    feedback_at: datetime = Field(default_factory=datetime.utcnow, description="When feedback was given")
    comment: Optional[str] = Field(None, max_length=500, description="Optional feedback comment")

    @field_serializer('feedback_at', when_used='json')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat() if dt else None


class KnowledgeBaseArticleModel(MongoModel, UserRelatedModel):
    """
    Knowledge Base Article Model
    Community-driven documentation where all planners can contribute

    Multi-tenant: Articles are visible to all planners
    Authorization: Authors can edit their own articles, ROOT_ADMIN can edit all
    """

    # Article Content
    title: str = Field(..., min_length=5, max_length=200, description="Article title")
    slug: str = Field(..., min_length=5, max_length=220, description="URL-friendly identifier")
    content: str = Field(..., min_length=50, max_length=50000, description="Markdown content")
    excerpt: str = Field(..., min_length=20, max_length=500, description="Short summary for listings")

    # Classification
    category: str = Field(default="general", description="Article category")
    tags: List[str] = Field(default_factory=list, max_length=10, description="Article tags for search")

    # Status & Visibility
    status: str = Field(default="published", description="Article status: draft, published, pending_review")
    is_official: bool = Field(default=False, description="True = platform docs by ROOT_ADMIN, False = community")
    featured: bool = Field(default=False, description="Highlight important articles")

    # Author Information (extends UserRelatedModel's created_by)
    author_name: str = Field(..., max_length=100, description="Display name for attribution")
    author_id: str = Field(..., description="User ID reference for author")

    # Metrics
    view_count: int = Field(default=0, ge=0, description="Number of article views")
    helpful_count: int = Field(default=0, ge=0, description="Count of helpful votes")
    not_helpful_count: int = Field(default=0, ge=0, description="Count of not helpful votes")

    # Feedback History (optional - can store individual feedback)
    feedback: List[ArticleFeedbackModel] = Field(default_factory=list, description="User feedback entries")

    # Ordering
    order: int = Field(default=0, description="Manual sort order within category")

    # Reading metrics
    estimated_read_minutes: int = Field(default=5, ge=1, le=60, description="Estimated reading time")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        """Validate article category"""
        if v not in KB_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(KB_CATEGORIES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        """Validate article status"""
        valid_statuses = ["draft", "published", "pending_review", "archived"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        """Validate slug format (lowercase, hyphenated)"""
        import re
        if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', v):
            raise ValueError("Slug must be lowercase with hyphens only (e.g., 'my-article-title')")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if v:
            # Lowercase and strip tags, remove empty
            cleaned = [tag.lower().strip() for tag in v if tag.strip()]
            # Limit to 10 tags
            return cleaned[:10]
        return v

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "title": "Getting Started with Guest Management",
                "slug": "getting-started-guest-management",
                "content": "# Guest Management Guide\n\nLearn how to manage your wedding guests...",
                "excerpt": "Learn how to add, organize, and manage your wedding guest list effectively.",
                "category": "guest-management",
                "tags": ["guests", "getting-started", "beginner"],
                "status": "published",
                "is_official": True,
                "featured": True,
                "author_name": "The Special Wedding Team",
                "author_id": "user_001",
                "created_by": "admin@thespecialwedding.io",
                "view_count": 150,
                "helpful_count": 45,
                "not_helpful_count": 2,
                "order": 1,
                "estimated_read_minutes": 5,
                "created_at": "2025-01-19T10:30:00Z",
                "updated_at": "2025-01-19T10:30:00Z"
            }
        }


class KnowledgeBaseArticleCreateModel(BaseModel):
    """Model for creating a new KB article (input validation)"""
    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=50, max_length=50000)
    excerpt: str = Field(..., min_length=20, max_length=500)
    category: str = Field(default="general")
    tags: List[str] = Field(default_factory=list)
    status: str = Field(default="published")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v not in KB_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(KB_CATEGORIES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["draft", "published"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v


class KnowledgeBaseArticleUpdateModel(BaseModel):
    """Model for updating a KB article (partial update)"""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    content: Optional[str] = Field(None, min_length=50, max_length=50000)
    excerpt: Optional[str] = Field(None, min_length=20, max_length=500)
    category: Optional[str] = Field(None)
    tags: Optional[List[str]] = Field(None)
    status: Optional[str] = Field(None)
    featured: Optional[bool] = Field(None)
    order: Optional[int] = Field(None)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is not None and v not in KB_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(KB_CATEGORIES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["draft", "published", "pending_review", "archived"]
        if v is not None and v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v


class ArticleFeedbackRequest(BaseModel):
    """Request model for submitting article feedback"""
    helpful: bool = Field(..., description="Was the article helpful?")
    comment: Optional[str] = Field(None, max_length=500, description="Optional feedback comment")


class KnowledgeBaseCategoryStats(BaseModel):
    """Category with article count for sidebar display"""
    category: str
    display_name: str
    article_count: int
    icon: Optional[str] = None


# Helper function to generate slug from title
def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title"""
    import re
    # Convert to lowercase
    slug = title.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)
    # Remove non-alphanumeric characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


# Category display names mapping
CATEGORY_DISPLAY_NAMES = {
    "getting-started": "Getting Started",
    "guest-management": "Guest Management",
    "rsvp-invitations": "RSVP & Invitations",
    "budget-payments": "Budget & Payments",
    "vendors": "Vendors",
    "forms-questionnaires": "Forms & Questionnaires",
    "wedding-configuration": "Wedding Configuration",
    "notifications": "Notifications",
    "calendar-tasks": "Calendar & Tasks",
    "billing-subscription": "Billing & Subscription",
    "troubleshooting": "Troubleshooting",
    "tips-tricks": "Tips & Tricks",
    "integrations": "Integrations",
    "general": "General"
}
