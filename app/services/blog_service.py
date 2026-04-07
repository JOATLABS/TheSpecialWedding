"""
Blog Service — CRUD operations for public-facing marketing blog.
Mirrors KnowledgeBaseService architecture but uses 'blog_articles' collection.
Blog articles are PUBLIC (no auth to read), admin-only to write.
"""

from fastapi import HTTPException
from app.core.database import mongo
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone
from bson import ObjectId
import logging
import re
import math

from app.models.blog import (
    generate_blog_slug,
    BlogArticleCreateModel,
    BlogArticleUpdateModel,
)
from app.utils.blog_content import blog_content_word_count, sanitize_blog_content

logger = logging.getLogger(__name__)


class BlogService:
    def __init__(self):
        self.collection = mongo.db["blog_articles"]

    # ───────────────── PUBLIC READ ─────────────────

    async def get_published_articles(
        self,
        page: int = 1,
        limit: int = 20,
        category: Optional[str] = None,
        search: Optional[str] = None,
        featured_only: bool = False,
    ) -> dict:
        """Get published blog articles (public, no auth)"""
        try:
            query: Dict[str, Any] = {"status": "published"}

            if category and category != "all":
                query["category"] = category

            if featured_only:
                query["featured"] = True

            if search:
                search_regex = {"$regex": re.escape(search), "$options": "i"}
                query["$or"] = [
                    {"title": search_regex},
                    {"excerpt": search_regex},
                    {"tags": search_regex},
                ]

            total = await self.collection.count_documents(query)
            skip = (page - 1) * limit
            pages = max(1, (total + limit - 1) // limit)

            cursor = (
                self.collection.find(
                    query,
                    # Exclude full content for list view
                    {"content": 0},
                )
                .sort(
                    [
                        ("featured", -1),
                        ("published_at", -1),
                        ("created_at", -1),
                    ]
                )
                .skip(skip)
                .limit(limit)
            )

            articles = []
            async for article in cursor:
                article["id"] = str(article["_id"])
                article["_id"] = str(article["_id"])
                articles.append(article)

            return {
                "articles": articles,
                "total": total,
                "page": page,
                "pages": pages,
                "limit": limit,
            }

        except Exception as e:
            logger.error(f"Error getting blog articles: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving articles: {str(e)}"
            )

    async def get_article_by_slug(self, slug: str, increment_view: bool = True) -> dict:
        """Get a single published article by slug (public)"""
        try:
            article = await self.collection.find_one(
                {"slug": slug, "status": "published"}
            )

            if not article:
                raise HTTPException(status_code=404, detail="Article not found")

            if increment_view:
                await self.collection.update_one(
                    {"_id": article["_id"]},
                    {"$inc": {"view_count": 1}},
                )
                article["view_count"] = article.get("view_count", 0) + 1

            article["id"] = str(article["_id"])
            article["_id"] = str(article["_id"])

            return article

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting blog article by slug: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving article: {str(e)}"
            )

    async def get_slugs(self) -> List[str]:
        """Return all published slugs (for sitemap)"""
        try:
            cursor = self.collection.find(
                {"status": "published"},
                {"slug": 1, "_id": 0},
            )
            slugs = []
            async for doc in cursor:
                slugs.append(doc["slug"])
            return slugs
        except Exception as e:
            logger.error(f"Error getting blog slugs: {str(e)}")
            return []

    # ───────────────── ADMIN CRUD ─────────────────

    async def create_article(
        self, data: BlogArticleCreateModel, author_email: str
    ) -> dict:
        """Create a new blog article (admin only)"""
        try:
            base_slug = generate_blog_slug(data.title)
            slug = base_slug

            counter = 1
            while await self.collection.find_one({"slug": slug}):
                slug = f"{base_slug}-{counter}"
                counter += 1

            sanitized_content = sanitize_blog_content(data.content)
            if not sanitized_content:
                raise HTTPException(
                    status_code=400,
                    detail="Article content is empty after sanitization",
                )

            word_count = blog_content_word_count(sanitized_content)
            estimated_read_minutes = max(1, math.ceil(word_count / 200))

            now = datetime.now(timezone.utc)

            article = {
                "_id": ObjectId(),
                "title": data.title,
                "slug": slug,
                "content": sanitized_content,
                "excerpt": data.excerpt,
                "category": data.category,
                "tags": [t.lower().strip() for t in data.tags if t.strip()][:15],
                "status": data.status,
                "featured": data.featured,
                "author_name": data.author_name,
                "author_email": author_email,
                "meta_title": data.meta_title,
                "meta_description": data.meta_description,
                "og_image": data.og_image,
                "card_image": data.card_image,
                "view_count": 0,
                "estimated_read_minutes": estimated_read_minutes,
                "published_at": now if data.status == "published" else None,
                "created_at": now,
                "updated_at": now,
            }

            result = await self.collection.insert_one(article)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create article")

            logger.info(f"Blog article '{data.title}' created by {author_email}")

            return {
                "id": str(result.inserted_id),
                "slug": slug,
                "message": "Blog article created successfully",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating blog article: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating article: {str(e)}"
            )

    async def update_article(
        self, article_id: str, data: BlogArticleUpdateModel
    ) -> dict:
        """Update a blog article (admin only)"""
        try:
            try:
                obj_id = ObjectId(article_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid article ID")

            existing = await self.collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Article not found")

            update_dict = {k: v for k, v in data.model_dump().items() if v is not None}

            if not update_dict:
                raise HTTPException(status_code=400, detail="No fields to update")

            if "content" in update_dict:
                sanitized_content = sanitize_blog_content(update_dict["content"])
                if not sanitized_content:
                    raise HTTPException(
                        status_code=400,
                        detail="Article content is empty after sanitization",
                    )

                update_dict["content"] = sanitized_content
                word_count = blog_content_word_count(sanitized_content)
                update_dict["estimated_read_minutes"] = max(
                    1, math.ceil(word_count / 200)
                )

            if "title" in update_dict:
                new_slug = generate_blog_slug(update_dict["title"])
                if new_slug != existing["slug"]:
                    counter = 1
                    base_slug = new_slug
                    while await self.collection.find_one(
                        {"slug": new_slug, "_id": {"$ne": obj_id}}
                    ):
                        new_slug = f"{base_slug}-{counter}"
                        counter += 1
                    update_dict["slug"] = new_slug

            # If transitioning to published and no published_at yet
            if update_dict.get("status") == "published" and not existing.get(
                "published_at"
            ):
                update_dict["published_at"] = datetime.now(timezone.utc)

            update_dict["updated_at"] = datetime.now(timezone.utc)

            await self.collection.update_one({"_id": obj_id}, {"$set": update_dict})

            logger.info(f"Blog article '{existing['title']}' updated")

            return {
                "message": "Article updated successfully",
                "slug": update_dict.get("slug", existing["slug"]),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating blog article: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error updating article: {str(e)}"
            )

    async def delete_article(self, article_id: str) -> dict:
        """Delete a blog article (admin only)"""
        try:
            try:
                obj_id = ObjectId(article_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid article ID")

            existing = await self.collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Article not found")

            await self.collection.delete_one({"_id": obj_id})

            logger.info(f"Blog article '{existing['title']}' deleted")
            return {"message": "Article deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting blog article: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error deleting article: {str(e)}"
            )

    async def get_article_by_id(self, article_id: str) -> dict:
        """Get article by ID (admin — any status)"""
        try:
            try:
                obj_id = ObjectId(article_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid article ID")

            article = await self.collection.find_one({"_id": obj_id})
            if not article:
                raise HTTPException(status_code=404, detail="Article not found")

            article["id"] = str(article["_id"])
            article["_id"] = str(article["_id"])
            return article

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting blog article: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving article: {str(e)}"
            )

    async def get_all_articles_admin(
        self,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict:
        """Get all articles regardless of status (admin only)"""
        try:
            query: Dict[str, Any] = {}

            if status:
                query["status"] = status

            if category and category != "all":
                query["category"] = category

            if search:
                search_regex = {"$regex": re.escape(search), "$options": "i"}
                query["$or"] = [
                    {"title": search_regex},
                    {"excerpt": search_regex},
                    {"tags": search_regex},
                ]

            total = await self.collection.count_documents(query)
            skip = (page - 1) * limit
            pages = max(1, (total + limit - 1) // limit)

            cursor = (
                self.collection.find(
                    query,
                    {"content": 0},
                )
                .sort(
                    [
                        ("featured", -1),
                        ("updated_at", -1),
                    ]
                )
                .skip(skip)
                .limit(limit)
            )

            articles = []
            async for article in cursor:
                article["id"] = str(article["_id"])
                article["_id"] = str(article["_id"])
                articles.append(article)

            return {
                "articles": articles,
                "total": total,
                "page": page,
                "pages": pages,
                "limit": limit,
            }

        except Exception as e:
            logger.error(f"Error getting admin blog articles: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error retrieving articles: {str(e)}"
            )


# Singleton
blog_service = BlogService()
