"""
Knowledge Base Service for Community-Driven Documentation
Handles CRUD operations, search, and feedback for KB articles
"""
from fastapi import HTTPException
from app.core.database import mongo
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone
from bson import ObjectId
import logging
import re
import math

from app.models.knowledge_base import (
    KB_CATEGORIES,
    CATEGORY_DISPLAY_NAMES,
    generate_slug,
    KnowledgeBaseArticleCreateModel,
    KnowledgeBaseArticleUpdateModel,
)

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    def __init__(self):
        self.articles_collection = mongo.db["kb_articles"]
        self.users_collection = mongo.get_users_collection()

    async def create_article(
        self,
        article_data: KnowledgeBaseArticleCreateModel,
        author_email: str,
        author_id: str,
        author_name: str
    ) -> dict:
        """Create a new KB article"""
        try:
            # Generate slug from title
            base_slug = generate_slug(article_data.title)
            slug = base_slug

            # Ensure unique slug
            counter = 1
            while await self.articles_collection.find_one({"slug": slug}):
                slug = f"{base_slug}-{counter}"
                counter += 1

            # Calculate estimated reading time (avg 200 words per minute)
            word_count = len(article_data.content.split())
            estimated_read_minutes = max(1, math.ceil(word_count / 200))

            # Prepare article document
            article = {
                "_id": ObjectId(),
                "title": article_data.title,
                "slug": slug,
                "content": article_data.content,
                "excerpt": article_data.excerpt,
                "category": article_data.category,
                "tags": [tag.lower().strip() for tag in article_data.tags if tag.strip()][:10],
                "status": article_data.status,
                "is_official": False,  # Only ROOT_ADMIN can set this later
                "featured": False,
                "author_email": author_email,
                "author_name": author_name,
                "author_id": author_id,
                "created_by": author_email,
                "updated_by": None,
                "view_count": 0,
                "helpful_count": 0,
                "not_helpful_count": 0,
                "feedback": [],
                "order": 0,
                "estimated_read_minutes": estimated_read_minutes,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            result = await self.articles_collection.insert_one(article)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create article")

            logger.info(f"KB article '{article_data.title}' created by {author_email}")

            # Log activity
            try:
                activity_logs_collection = mongo.db["activity_logs"]
                await activity_logs_collection.insert_one({
                    "type": "kb_article_created",
                    "message": f"Knowledge Base article created: {article_data.title[:50]}",
                    "timestamp": datetime.now(timezone.utc),
                    "created_at": datetime.now(timezone.utc),
                    "planner_email": author_email,
                    "actor_email": author_email,
                    "metadata": {
                        "article_id": str(result.inserted_id),
                        "slug": slug,
                        "category": article_data.category
                    }
                })
            except Exception as activity_error:
                logger.error(f"Failed to log activity for article creation: {str(activity_error)}")

            return {
                "id": str(result.inserted_id),
                "slug": slug,
                "message": "Article created successfully",
                "created_at": article["created_at"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating article: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating article: {str(e)}")

    async def get_articles(
        self,
        page: int = 1,
        limit: int = 20,
        category: Optional[str] = None,
        search: Optional[str] = None,
        status: str = "published",
        featured_only: bool = False,
        official_only: bool = False
    ) -> dict:
        """Get articles with filtering and pagination"""
        try:
            # Build query
            query: Dict[str, Any] = {"status": status}

            if category and category != "all":
                query["category"] = category

            if featured_only:
                query["featured"] = True

            if official_only:
                query["is_official"] = True

            if search:
                # Text search on title, excerpt, and tags
                search_regex = {"$regex": re.escape(search), "$options": "i"}
                query["$or"] = [
                    {"title": search_regex},
                    {"excerpt": search_regex},
                    {"tags": search_regex},
                    {"content": search_regex}
                ]

            # Count total documents
            total = await self.articles_collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * limit
            pages = max(1, (total + limit - 1) // limit)

            # Get articles sorted by featured first, then by order, then by date
            cursor = self.articles_collection.find(query).sort([
                ("featured", -1),
                ("is_official", -1),
                ("order", 1),
                ("created_at", -1)
            ]).skip(skip).limit(limit)

            articles = []
            async for article in cursor:
                article["id"] = str(article["_id"])
                article["_id"] = str(article["_id"])

                # Remove content for list view (too large)
                article.pop("content", None)
                article.pop("feedback", None)

                articles.append(article)

            return {
                "articles": articles,
                "total": total,
                "page": page,
                "pages": pages,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"Error getting articles: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving articles: {str(e)}")

    async def get_article_by_slug(self, slug: str, increment_view: bool = True) -> dict:
        """Get article by slug"""
        try:
            article = await self.articles_collection.find_one({"slug": slug})

            if not article:
                raise HTTPException(status_code=404, detail="Article not found")

            # Increment view count
            if increment_view and article.get("status") == "published":
                await self.articles_collection.update_one(
                    {"_id": article["_id"]},
                    {"$inc": {"view_count": 1}}
                )
                article["view_count"] = article.get("view_count", 0) + 1

            article["id"] = str(article["_id"])
            article["_id"] = str(article["_id"])

            # Get author info
            author = await self.users_collection.find_one(
                {"email": article["author_email"]},
                {"first_name": 1, "last_name": 1, "company_name": 1, "profile_image_url": 1}
            )
            if author:
                article["author_info"] = {
                    "name": article.get("author_name", "Unknown"),
                    "first_name": author.get("first_name"),
                    "last_name": author.get("last_name"),
                    "company_name": author.get("company_name"),
                    "profile_image_url": author.get("profile_image_url")
                }

            return article

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting article by slug: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving article: {str(e)}")

    async def get_article_by_id(self, article_id: str) -> dict:
        """Get article by ID"""
        try:
            try:
                obj_id = ObjectId(article_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid article ID")

            article = await self.articles_collection.find_one({"_id": obj_id})

            if not article:
                raise HTTPException(status_code=404, detail="Article not found")

            article["id"] = str(article["_id"])
            article["_id"] = str(article["_id"])

            return article

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting article by ID: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving article: {str(e)}")

    async def update_article(
        self,
        article_id: str,
        update_data: KnowledgeBaseArticleUpdateModel,
        current_user
    ) -> dict:
        """Update an article"""
        try:
            try:
                obj_id = ObjectId(article_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid article ID")

            existing = await self.articles_collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Article not found")

            # Check permissions: author or ROOT_ADMIN
            is_author = existing["author_email"] == current_user.email
            is_admin = current_user.role == "ROOT_ADMIN"

            if not is_author and not is_admin:
                raise HTTPException(status_code=403, detail="You can only edit your own articles")

            # Prepare update dict (only non-None values)
            update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

            if not update_dict:
                raise HTTPException(status_code=400, detail="No fields to update")

            # Recalculate reading time if content changed
            if "content" in update_dict:
                word_count = len(update_dict["content"].split())
                update_dict["estimated_read_minutes"] = max(1, math.ceil(word_count / 200))

            # Update slug if title changed
            if "title" in update_dict:
                new_slug = generate_slug(update_dict["title"])
                if new_slug != existing["slug"]:
                    # Check if new slug is unique
                    counter = 1
                    base_slug = new_slug
                    while await self.articles_collection.find_one({"slug": new_slug, "_id": {"$ne": obj_id}}):
                        new_slug = f"{base_slug}-{counter}"
                        counter += 1
                    update_dict["slug"] = new_slug

            update_dict["updated_at"] = datetime.now(timezone.utc)
            update_dict["updated_by"] = current_user.email

            result = await self.articles_collection.update_one(
                {"_id": obj_id},
                {"$set": update_dict}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Article not found")

            logger.info(f"KB article '{existing['title']}' updated by {current_user.email}")

            return {
                "message": "Article updated successfully",
                "slug": update_dict.get("slug", existing["slug"]),
                "updated_fields": list(update_dict.keys())
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating article: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating article: {str(e)}")

    async def delete_article(self, article_id: str, current_user) -> dict:
        """Delete an article"""
        try:
            try:
                obj_id = ObjectId(article_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid article ID")

            existing = await self.articles_collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Article not found")

            # Check permissions: author or ROOT_ADMIN
            is_author = existing["author_email"] == current_user.email
            is_admin = current_user.role == "ROOT_ADMIN"

            if not is_author and not is_admin:
                raise HTTPException(status_code=403, detail="You can only delete your own articles")

            result = await self.articles_collection.delete_one({"_id": obj_id})

            if result.deleted_count == 0:
                raise HTTPException(status_code=400, detail="Failed to delete article")

            logger.info(f"KB article '{existing['title']}' deleted by {current_user.email}")

            return {"message": "Article deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting article: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error deleting article: {str(e)}")

    async def submit_feedback(
        self,
        article_id: str,
        helpful: bool,
        user_email: str,
        comment: Optional[str] = None
    ) -> dict:
        """Submit feedback for an article"""
        try:
            try:
                obj_id = ObjectId(article_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid article ID")

            article = await self.articles_collection.find_one({"_id": obj_id})
            if not article:
                raise HTTPException(status_code=404, detail="Article not found")

            # Check if user already submitted feedback
            existing_feedback = next(
                (f for f in article.get("feedback", []) if f["user_email"] == user_email),
                None
            )

            if existing_feedback:
                # Update existing feedback
                old_helpful = existing_feedback["helpful"]

                # Update counts
                inc_update = {}
                if old_helpful != helpful:
                    if helpful:
                        inc_update = {"helpful_count": 1, "not_helpful_count": -1}
                    else:
                        inc_update = {"helpful_count": -1, "not_helpful_count": 1}

                await self.articles_collection.update_one(
                    {"_id": obj_id, "feedback.user_email": user_email},
                    {
                        "$set": {
                            "feedback.$.helpful": helpful,
                            "feedback.$.feedback_at": datetime.now(timezone.utc),
                            "feedback.$.comment": comment
                        },
                        "$inc": inc_update if inc_update else {}
                    }
                )
            else:
                # Add new feedback
                feedback_entry = {
                    "user_email": user_email,
                    "helpful": helpful,
                    "feedback_at": datetime.now(timezone.utc),
                    "comment": comment
                }

                inc_field = "helpful_count" if helpful else "not_helpful_count"

                await self.articles_collection.update_one(
                    {"_id": obj_id},
                    {
                        "$push": {"feedback": feedback_entry},
                        "$inc": {inc_field: 1}
                    }
                )

            return {
                "message": "Feedback submitted successfully",
                "helpful": helpful
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error submitting feedback: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error submitting feedback: {str(e)}")

    async def mark_official(self, article_id: str, is_official: bool, current_user) -> dict:
        """Mark article as official (ROOT_ADMIN only)"""
        try:
            if current_user.role != "ROOT_ADMIN":
                raise HTTPException(status_code=403, detail="Only ROOT_ADMIN can mark articles as official")

            try:
                obj_id = ObjectId(article_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid article ID")

            result = await self.articles_collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "is_official": is_official,
                        "updated_at": datetime.now(timezone.utc),
                        "updated_by": current_user.email
                    }
                }
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Article not found")

            return {
                "message": f"Article marked as {'official' if is_official else 'community'}",
                "is_official": is_official
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error marking article as official: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating article: {str(e)}")

    async def get_categories_with_counts(self, status: str = "published") -> dict:
        """Get all categories with article counts"""
        try:
            pipeline = [
                {"$match": {"status": status}},
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}}
            ]

            results = [doc async for doc in self.articles_collection.aggregate(pipeline)]

            # Build category list with display names
            categories = []
            for category_id in KB_CATEGORIES:
                count = next((r["count"] for r in results if r["_id"] == category_id), 0)
                categories.append({
                    "category": category_id,
                    "display_name": CATEGORY_DISPLAY_NAMES.get(category_id, category_id.title()),
                    "article_count": count
                })

            # Calculate total
            total_count = sum(int(c["article_count"]) for c in categories)

            return {
                "categories": categories,
                "total_articles": total_count
            }

        except Exception as e:
            logger.error(f"Error getting categories: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving categories: {str(e)}")

    async def search_articles(
        self,
        query: str,
        limit: int = 20
    ) -> dict:
        """Full-text search across articles"""
        try:
            if not query or len(query) < 2:
                raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")

            search_regex = {"$regex": re.escape(query), "$options": "i"}

            # Search in title, excerpt, content, and tags
            search_query = {
                "status": "published",
                "$or": [
                    {"title": search_regex},
                    {"excerpt": search_regex},
                    {"tags": search_regex},
                    {"content": search_regex}
                ]
            }

            cursor = self.articles_collection.find(
                search_query,
                {"content": 0, "feedback": 0}  # Exclude large fields
            ).sort([
                ("is_official", -1),
                ("helpful_count", -1),
                ("view_count", -1)
            ]).limit(limit)

            articles = []
            async for article in cursor:
                article["id"] = str(article["_id"])
                article["_id"] = str(article["_id"])
                articles.append(article)

            return {
                "articles": articles,
                "total": len(articles),
                "query": query
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error searching articles: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error searching articles: {str(e)}")

    async def get_my_articles(
        self,
        author_email: str,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        """Get articles created by specific user"""
        try:
            query = {"author_email": author_email}

            total = await self.articles_collection.count_documents(query)
            skip = (page - 1) * limit
            pages = max(1, (total + limit - 1) // limit)

            cursor = self.articles_collection.find(
                query,
                {"content": 0, "feedback": 0}
            ).sort("created_at", -1).skip(skip).limit(limit)

            articles = []
            async for article in cursor:
                article["id"] = str(article["_id"])
                article["_id"] = str(article["_id"])
                articles.append(article)

            return {
                "articles": articles,
                "total": total,
                "page": page,
                "pages": pages
            }

        except Exception as e:
            logger.error(f"Error getting user articles: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving articles: {str(e)}")

    async def get_related_articles(
        self,
        article_id: str,
        limit: int = 5
    ) -> List[dict]:
        """Get related articles based on category and tags"""
        try:
            article = await self.get_article_by_id(article_id)

            # Find articles in same category or with matching tags
            query = {
                "_id": {"$ne": ObjectId(article_id)},
                "status": "published",
                "$or": [
                    {"category": article["category"]},
                    {"tags": {"$in": article.get("tags", [])}}
                ]
            }

            cursor = self.articles_collection.find(
                query,
                {"content": 0, "feedback": 0}
            ).sort([
                ("helpful_count", -1),
                ("view_count", -1)
            ]).limit(limit)

            articles = []
            async for related in cursor:
                related["id"] = str(related["_id"])
                related["_id"] = str(related["_id"])
                articles.append(related)

            return articles

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting related articles: {str(e)}")
            return []


# Singleton instance
knowledge_base_service = KnowledgeBaseService()
