# app/services/email_template_service.py

import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import HTTPException
import logging

from app.core.database import mongo
from app.models.email_template import (
    EmailTemplate, EmailTemplateCreate, EmailTemplateUpdate,
    TemplateStatus, TemplateType, EmailAnalytics
)

logger = logging.getLogger(__name__)

class EmailTemplateService:
    def __init__(self):
        self.templates_collection = mongo.db["email_templates"]
        self.delivery_events_collection = mongo.db["email_delivery_events"]
        self.email_logs_collection = mongo.db["email_logs"]

    async def create_template(self, template_data: EmailTemplateCreate, created_by: str) -> Dict[str, Any]:
        """Create a new email template"""
        try:
            # Extract variables from HTML content
            variables = self._extract_variables(template_data.html_content)

            # Check if this is being set as default for this type
            if template_data.is_default:
                await self._unset_default_for_type(template_data.type)

            # Prepare template document
            template_doc = {
                "name": template_data.name,
                "type": template_data.type.value,
                "subject": template_data.subject,
                "html_content": template_data.html_content,
                "plain_text_content": template_data.plain_text_content,
                "variables": variables,
                "status": TemplateStatus.DRAFT.value,
                "version": 1,
                "is_default": template_data.is_default,
                "metadata": template_data.metadata,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": created_by,
                "updated_by": created_by
            }

            result = self.templates_collection.insert_one(template_doc)

            if not result.inserted_id:
                raise HTTPException(status_code=500, detail="Failed to create template")

            logger.info(f"Email template created: {template_data.name} by {created_by}")

            return {
                "id": str(result.inserted_id),
                "message": "Template created successfully",
                "variables": variables
            }

        except Exception as e:
            logger.error(f"Error creating email template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")

    async def get_templates(self,
                           page: int = 1,
                           limit: int = 20,
                           template_type: Optional[TemplateType] = None,
                           status: Optional[TemplateStatus] = None) -> Dict[str, Any]:
        """Get email templates with pagination and filtering"""
        try:
            # Build query
            query = {}
            if template_type:
                query["type"] = template_type.value
            if status:
                query["status"] = status.value

            # Count total documents
            total = self.templates_collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * limit
            pages = (total + limit - 1) // limit

            # Get templates
            cursor = self.templates_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit)
            templates = []

            for template in cursor:
                template["id"] = str(template["_id"])
                template["_id"] = str(template["_id"])

                # Add usage statistics
                template["usage_stats"] = await self._get_template_usage_stats(str(template["_id"]))

                templates.append(template)

            return {
                "templates": templates,
                "total": total,
                "page": page,
                "pages": pages
            }

        except Exception as e:
            logger.error(f"Error getting email templates: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")

    async def get_template(self, template_id: str) -> Dict[str, Any]:
        """Get specific email template by ID"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(template_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid template ID")

            template = self.templates_collection.find_one({"_id": obj_id})
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            template["id"] = str(template["_id"])
            template["_id"] = str(template["_id"])

            # Add usage statistics
            template["usage_stats"] = await self._get_template_usage_stats(template_id)

            # Get version history
            template["version_history"] = await self._get_version_history(template_id)

            return template

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting email template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving template: {str(e)}")

    async def update_template(self, template_id: str, update_data: EmailTemplateUpdate, updated_by: str) -> Dict[str, Any]:
        """Update an email template"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(template_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid template ID")

            # Check if template exists
            existing = self.templates_collection.find_one({"_id": obj_id})
            if not existing:
                raise HTTPException(status_code=404, detail="Template not found")

            # Prepare update data
            update_doc = {}

            if update_data.name is not None:
                update_doc["name"] = update_data.name
            if update_data.subject is not None:
                update_doc["subject"] = update_data.subject
            if update_data.html_content is not None:
                update_doc["html_content"] = update_data.html_content
                update_doc["variables"] = self._extract_variables(update_data.html_content)
            if update_data.plain_text_content is not None:
                update_doc["plain_text_content"] = update_data.plain_text_content
            if update_data.variables is not None:
                update_doc["variables"] = update_data.variables
            if update_data.status is not None:
                update_doc["status"] = update_data.status.value
            if update_data.metadata is not None:
                update_doc["metadata"] = update_data.metadata

            # Handle default template setting
            if update_data.is_default is not None:
                if update_data.is_default:
                    await self._unset_default_for_type(TemplateType(existing["type"]))
                update_doc["is_default"] = update_data.is_default

            update_doc["updated_at"] = datetime.utcnow()
            update_doc["updated_by"] = updated_by

            # If significant changes, increment version
            if any(field in update_doc for field in ["html_content", "subject"]):
                update_doc["version"] = existing["version"] + 1

                # Archive the old version
                await self._archive_version(existing)

            # Update template
            result = self.templates_collection.update_one(
                {"_id": obj_id},
                {"$set": update_doc}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Template update failed")

            logger.info(f"Email template updated: {template_id} by {updated_by}")

            return {
                "message": "Template updated successfully",
                "updated_fields": list(update_doc.keys()),
                "new_version": update_doc.get("version", existing["version"])
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating email template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating template: {str(e)}")

    async def delete_template(self, template_id: str) -> Dict[str, Any]:
        """Delete an email template"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(template_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid template ID")

            # Check if template exists and is not the only default for its type
            template = self.templates_collection.find_one({"_id": obj_id})
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            if template.get("is_default"):
                # Count other templates of the same type
                other_count = self.templates_collection.count_documents({
                    "type": template["type"],
                    "_id": {"$ne": obj_id}
                })
                if other_count == 0:
                    raise HTTPException(status_code=400, detail="Cannot delete the only template of this type")

            # Archive instead of hard delete
            result = self.templates_collection.update_one(
                {"_id": obj_id},
                {"$set": {
                    "status": TemplateStatus.ARCHIVED.value,
                    "updated_at": datetime.utcnow(),
                    "archived_at": datetime.utcnow()
                }}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Template not found")

            logger.info(f"Email template archived: {template_id}")

            return {"message": "Template archived successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting email template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error deleting template: {str(e)}")

    async def activate_template(self, template_id: str, activated_by: str) -> Dict[str, Any]:
        """Activate a template and optionally set as default"""
        try:
            # Validate ObjectId
            try:
                obj_id = ObjectId(template_id)
            except:
                raise HTTPException(status_code=400, detail="Invalid template ID")

            # Get template
            template = self.templates_collection.find_one({"_id": obj_id})
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            # Update status
            result = self.templates_collection.update_one(
                {"_id": obj_id},
                {"$set": {
                    "status": TemplateStatus.ACTIVE.value,
                    "updated_at": datetime.utcnow(),
                    "updated_by": activated_by
                }}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="Template activation failed")

            logger.info(f"Email template activated: {template_id} by {activated_by}")

            return {"message": "Template activated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error activating email template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error activating template: {str(e)}")

    async def preview_template(self, template_id: str, sample_data: Dict[str, str]) -> Dict[str, Any]:
        """Preview template with sample data"""
        try:
            # Get template
            template = await self.get_template(template_id)

            # Apply sample data to template
            rendered_html = self._render_template(template["html_content"], sample_data)
            rendered_subject = self._render_template(template["subject"], sample_data)

            return {
                "rendered_html": rendered_html,
                "rendered_subject": rendered_subject,
                "variables_used": template.get("variables", []),
                "sample_data": sample_data
            }

        except Exception as e:
            logger.error(f"Error previewing email template: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error previewing template: {str(e)}")

    async def get_template_by_type(self, template_type: TemplateType, active_only: bool = True) -> Optional[Dict[str, Any]]:
        """Get the default template for a specific type"""
        try:
            query = {"type": template_type.value}
            if active_only:
                query["status"] = TemplateStatus.ACTIVE.value

            # First try to get the default template
            template = self.templates_collection.find_one({**query, "is_default": True})

            # If no default, get the first active template of this type
            if not template:
                template = self.templates_collection.find_one(query)

            if template:
                template["id"] = str(template["_id"])
                template["_id"] = str(template["_id"])

            return template

        except Exception as e:
            logger.error(f"Error getting template by type: {str(e)}")
            return None

    async def get_analytics(self, template_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get email analytics for templates"""
        try:
            # Date range
            from_date = datetime.utcnow() - timedelta(days=days)

            pipeline = [
                {"$match": {"sent_at": {"$gte": from_date}}},
            ]

            if template_id:
                pipeline[0]["$match"]["template_id"] = template_id

            # Group by template and calculate metrics
            pipeline.extend([
                {
                    "$group": {
                        "_id": "$template_id",
                        "sent_count": {"$sum": 1},
                        "success_count": {"$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}},
                        "failed_count": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
                        "last_sent": {"$max": "$sent_at"}
                    }
                }
            ])

            email_stats = list(self.email_logs_collection.aggregate(pipeline))

            # Get delivery events for more detailed metrics
            delivery_pipeline = [
                {"$match": {"timestamp": {"$gte": from_date}}},
                {
                    "$group": {
                        "_id": {
                            "template_id": "$template_id",
                            "event_type": "$event_type"
                        },
                        "count": {"$sum": 1}
                    }
                }
            ]

            delivery_stats = list(self.delivery_events_collection.aggregate(delivery_pipeline))

            # Combine and format results
            analytics = self._format_analytics(email_stats, delivery_stats)

            return {
                "analytics": analytics,
                "date_range": {
                    "from": from_date,
                    "to": datetime.utcnow()
                },
                "total_templates": len(analytics)
            }

        except Exception as e:
            logger.error(f"Error getting email analytics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving analytics: {str(e)}")

    def _extract_variables(self, content: str) -> List[str]:
        """Extract template variables from content"""
        # Find all {variable_name} patterns
        variables = re.findall(r'\{([^}]+)\}', content)
        return list(set(variables))  # Remove duplicates

    def _render_template(self, template: str, data: Dict[str, str]) -> str:
        """Render template with provided data"""
        rendered = template
        for key, value in data.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered

    async def _unset_default_for_type(self, template_type: TemplateType):
        """Unset default flag for all templates of a specific type"""
        self.templates_collection.update_many(
            {"type": template_type.value, "is_default": True},
            {"$set": {"is_default": False, "updated_at": datetime.utcnow()}}
        )

    async def _archive_version(self, template: Dict[str, Any]):
        """Archive the previous version of a template"""
        version_doc = {
            "original_id": str(template["_id"]),
            "version": template["version"],
            "name": template["name"],
            "type": template["type"],
            "subject": template["subject"],
            "html_content": template["html_content"],
            "plain_text_content": template.get("plain_text_content"),
            "variables": template.get("variables", []),
            "metadata": template.get("metadata", {}),
            "archived_at": datetime.utcnow(),
            "created_at": template["created_at"],
            "created_by": template["created_by"]
        }

        mongo.db["email_template_versions"].insert_one(version_doc)

    async def _get_version_history(self, template_id: str) -> List[Dict[str, Any]]:
        """Get version history for a template"""
        versions = list(mongo.db["email_template_versions"].find(
            {"original_id": template_id}
        ).sort("version", -1))

        for version in versions:
            version["_id"] = str(version["_id"])

        return versions

    async def _get_template_usage_stats(self, template_id: str) -> Dict[str, Any]:
        """Get usage statistics for a template"""
        # Count emails sent with this template in last 30 days
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        sent_count = self.email_logs_collection.count_documents({
            "template_id": template_id,
            "sent_at": {"$gte": thirty_days_ago}
        })

        success_count = self.email_logs_collection.count_documents({
            "template_id": template_id,
            "sent_at": {"$gte": thirty_days_ago},
            "status": "success"
        })

        return {
            "sent_last_30_days": sent_count,
            "success_rate": (success_count / sent_count * 100) if sent_count > 0 else 0
        }

    def _format_analytics(self, email_stats: List[Dict], delivery_stats: List[Dict]) -> List[Dict[str, Any]]:
        """Format analytics data for response"""
        analytics = {}

        # Process email stats
        for stat in email_stats:
            template_id = stat["_id"]
            analytics[template_id] = {
                "template_id": template_id,
                "sent_count": stat["sent_count"],
                "success_count": stat["success_count"],
                "failed_count": stat["failed_count"],
                "last_sent": stat["last_sent"],
                "delivered_count": 0,
                "opened_count": 0,
                "clicked_count": 0,
                "bounced_count": 0,
                "complained_count": 0
            }

        # Process delivery stats
        for stat in delivery_stats:
            template_id = stat["_id"]["template_id"]
            event_type = stat["_id"]["event_type"]
            count = stat["count"]

            if template_id not in analytics:
                analytics[template_id] = {
                    "template_id": template_id,
                    "sent_count": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "delivered_count": 0,
                    "opened_count": 0,
                    "clicked_count": 0,
                    "bounced_count": 0,
                    "complained_count": 0
                }

            if event_type == "delivered":
                analytics[template_id]["delivered_count"] = count
            elif event_type == "opened":
                analytics[template_id]["opened_count"] = count
            elif event_type == "clicked":
                analytics[template_id]["clicked_count"] = count
            elif event_type == "bounced":
                analytics[template_id]["bounced_count"] = count
            elif event_type == "complained":
                analytics[template_id]["complained_count"] = count

        # Calculate rates
        for template_id, data in analytics.items():
            sent = data["sent_count"]
            if sent > 0:
                data["delivery_rate"] = (data["delivered_count"] / sent) * 100
                data["open_rate"] = (data["opened_count"] / sent) * 100
                data["click_rate"] = (data["clicked_count"] / sent) * 100
                data["bounce_rate"] = (data["bounced_count"] / sent) * 100
                data["complaint_rate"] = (data["complained_count"] / sent) * 100
            else:
                data["delivery_rate"] = 0
                data["open_rate"] = 0
                data["click_rate"] = 0
                data["bounce_rate"] = 0
                data["complaint_rate"] = 0

        return list(analytics.values())