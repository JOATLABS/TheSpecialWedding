"""
Blog Article Models for Public-Facing Marketing Blog
Separate collection from Knowledge Base — these are SEO-targeted blog posts
visible on /resources/blog to the public (no auth required).
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.base import MongoModel

# Valid blog categories
BLOG_CATEGORIES = [
    "platform-updates",
    "pricing-strategy",
    "guest-management",
    "industry-comparison",
    "contracts-legal",
    "ai-technology",
    "event-logistics",
    "tips-guides",
    "general",
]

BLOG_CATEGORY_DISPLAY_NAMES = {
    "platform-updates": "Platform Updates",
    "pricing-strategy": "Pricing Strategy",
    "guest-management": "Guest Management",
    "industry-comparison": "Industry Comparison",
    "contracts-legal": "Contracts & Legal",
    "ai-technology": "AI & Technology",
    "event-logistics": "Event Logistics",
    "tips-guides": "Tips & Guides",
    "general": "General",
}


class BlogArticleModel(MongoModel):
    """
    Blog Article Model for public marketing blog.
    Stored in 'blog_articles' collection.
    Unlike KB articles, these are public (no auth required to read).
    """

    # Article Content
    title: str = Field(..., min_length=5, max_length=200, description="Article title")
    slug: str = Field(
        ..., min_length=5, max_length=220, description="URL-friendly slug"
    )
    content: str = Field(
        ...,
        min_length=50,
        max_length=100000,
        description="Markdown or basic editorial HTML rendered in React",
    )
    excerpt: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="Short summary for card listings",
    )

    # Classification
    category: str = Field(default="general", description="Blog category")
    tags: list[str] = Field(default_factory=list, description="SEO tags")

    # Status & Visibility
    status: str = Field(default="published", description="draft | published | archived")
    featured: bool = Field(default=False, description="Show as featured/hero card")

    # Author
    author_name: str = Field(default="The Special Wedding", max_length=100)
    author_email: str = Field(default="hello@thespecialwedding.io", max_length=254)

    # SEO
    meta_title: str | None = Field(
        None, max_length=70, description="SEO title override"
    )
    meta_description: str | None = Field(
        None, max_length=160, description="SEO description override"
    )
    og_image: str | None = Field(None, description="Open Graph image URL")

    # Metrics
    view_count: int = Field(default=0, ge=0)
    estimated_read_minutes: int = Field(default=5, ge=1, le=60)

    # Display
    card_image: str | None = Field(None, description="Card thumbnail URL")
    published_at: datetime | None = Field(
        default=None, description="When the article was published"
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v not in BLOG_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(BLOG_CATEGORIES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = ["draft", "published", "archived"]
        if v not in valid:
            raise ValueError(f"Status must be one of: {', '.join(valid)}")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        import re

        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError("Slug must be lowercase with hyphens only")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if v:
            cleaned = [tag.lower().strip() for tag in v if tag.strip()]
            return cleaned[:15]
        return v


class BlogArticleCreateModel(BaseModel):
    """Input model for creating a blog article"""

    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=50, max_length=100000)
    excerpt: str = Field(..., min_length=20, max_length=500)
    category: str = Field(default="general")
    tags: list[str] = Field(default_factory=list)
    status: str = Field(default="published")
    featured: bool = Field(default=False)
    author_name: str = Field(default="The Special Wedding")
    meta_title: str | None = Field(None, max_length=70)
    meta_description: str | None = Field(None, max_length=160)
    og_image: str | None = None
    card_image: str | None = None

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


class BlogArticleUpdateModel(BaseModel):
    """Partial update model for blog articles"""

    title: str | None = Field(None, min_length=5, max_length=200)
    content: str | None = Field(None, min_length=50, max_length=100000)
    excerpt: str | None = Field(None, min_length=20, max_length=500)
    category: str | None = None
    tags: list[str] | None = None
    status: str | None = None
    featured: bool | None = None
    author_name: str | None = Field(None, max_length=100)
    meta_title: str | None = Field(None, max_length=70)
    meta_description: str | None = Field(None, max_length=160)
    og_image: str | None = None
    card_image: str | None = None

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


def generate_blog_slug(title: str) -> str:
    """Generate URL-friendly slug from title"""
    import re

    slug = title.lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug
