from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone
from app.utils.pydantic_objectid import PyObjectId
from app.core.database import mongo
from app.models.budget import (
    BudgetCategory,
    VendorQuote,
    BudgetTemplate,
    BudgetSummary,
    PaymentRecord,
    BudgetAlert,
    BudgetSubcategory
)
from app.utils.security_validator import SecurityValidator
from app.utils.serializers import serialize_mongo_doc
import logging

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_ai_cache_service = None


def _get_ai_cache_service():
    """Get AI cache service lazily to avoid circular imports."""
    global _ai_cache_service
    if _ai_cache_service is None:
        from app.services.ai_cache_service import ai_cache_service
        _ai_cache_service = ai_cache_service
    return _ai_cache_service


class BudgetService:
    # Safety caps for list queries to prevent memory overload
    MAX_CATEGORIES = 5000
    MAX_QUOTES = 10000
    MAX_TEMPLATES = 1000
    MAX_PAYMENT_RECORDS = 50000
    MAX_ALERTS = 5000

    def __init__(self):
        self.budget_categories = mongo.db["budget_categories"]
        self.vendor_quotes = mongo.db["vendor_quotes"]
        self.budget_templates = mongo.db["budget_templates"]
        self.payment_records = mongo.db["payment_records"]
        self.budget_alerts = mongo.db["budget_alerts"]
        self.weddings = mongo.get_weddings_collection()
        self.security_validator = SecurityValidator()

    async def _invalidate_budget_cache(self, wedding_id: str):
        """Invalidate AI cache when budget data changes."""
        try:
            cache_service = _get_ai_cache_service()
            await cache_service.invalidate_by_feature("budget_insights", wedding_id)
            logger.debug(f"Invalidated budget_insights cache for wedding {wedding_id}")
        except Exception as e:
            # Cache invalidation failures should not break main operations
            logger.warning(f"Failed to invalidate budget cache: {str(e)}")

    # ===== BUDGET CATEGORY MANAGEMENT =====

    async def create_budget_category(self, wedding_id: str, category_data: Dict) -> Dict:
        """Create a new budget category for a wedding"""
        try:
            # Validate wedding exists and user has access
            wedding = await self.weddings.find_one({"_id": wedding_id})
            if not wedding:
                raise ValueError("Wedding not found")

            # Check if adding this category would exceed the wedding's total budget
            wedding_total_budget = wedding.get("total_budget", 0)
            if wedding_total_budget > 0:
                # Get existing categories (safety cap: typical wedding has <5k categories)
                cursor = self.budget_categories.find({"wedding_id": wedding_id})
                existing_categories = await cursor.to_list(length=self.MAX_CATEGORIES)
                existing_total = sum(cat.get("budgeted_amount", 0) for cat in existing_categories)
                new_category_amount = category_data.get("budgeted_amount", 0)

                if existing_total + new_category_amount > wedding_total_budget:
                    overage = (existing_total + new_category_amount) - wedding_total_budget
                    logger.warning(
                        f"Creating category would exceed wedding budget: "
                        f"Wedding {wedding_id} total: ${wedding_total_budget:,.2f}, "
                        f"Existing categories: ${existing_total:,.2f}, "
                        f"New category: ${new_category_amount:,.2f}, "
                        f"Overage: ${overage:,.2f}"
                    )
                    # Still allow creation but alert will be triggered

            # Create category
            category = BudgetCategory(
                wedding_id=wedding_id,
                **category_data
            )

            # Insert into database
            result = await self.budget_categories.insert_one(category.model_dump(by_alias=True))
            category.id = result.inserted_id  # type: ignore[assignment]

            # Update wedding total budget if needed
            await self._update_wedding_budget_total(wedding_id)

            # Check for budget alerts
            await self._check_budget_alerts(wedding_id)

            # Invalidate AI cache for budget insights
            await self._invalidate_budget_cache(wedding_id)

            logger.info(f"Created budget category {category.name} for wedding {wedding_id}")
            return category.model_dump()

        except Exception as e:
            logger.error(f"Failed to create budget category: {str(e)}")
            raise

    async def get_wedding_budget(self, wedding_id: str) -> Dict:
        """Get complete budget for a wedding"""
        try:
            # Get all categories for this wedding (safety cap applied)
            cursor = self.budget_categories.find({"wedding_id": wedding_id})
            categories = await cursor.to_list(length=self.MAX_CATEGORIES)

            # Serialize categories (convert ObjectId to string)
            serialized_categories = []
            for cat in categories:
                serialized_cat = {**cat}
                if "_id" in serialized_cat:
                    serialized_cat["id"] = str(serialized_cat["_id"])
                    serialized_cat["_id"] = str(serialized_cat["_id"])
                serialized_categories.append(serialized_cat)

            # Get budget summary
            summary = await self._calculate_budget_summary(wedding_id)

            # Get recent alerts (already limited by .limit(10) in cursor)
            alerts_cursor = self.budget_alerts.find(
                {"wedding_id": wedding_id, "is_resolved": False}
            ).sort("created_at", -1).limit(10)
            alerts = await alerts_cursor.to_list(length=10)

            # Serialize alerts (convert ObjectId to string)
            serialized_alerts = []
            for alert in alerts:
                serialized_alert = {**alert}
                if "_id" in serialized_alert:
                    serialized_alert["id"] = str(serialized_alert["_id"])
                    serialized_alert["_id"] = str(serialized_alert["_id"])
                serialized_alerts.append(serialized_alert)

            return {
                "wedding_id": wedding_id,
                "summary": summary.model_dump(),
                "categories": serialized_categories,
                "alerts": serialized_alerts,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get wedding budget: {str(e)}")
            raise

    async def update_budget_category(self, category_id: str, update_data: Dict) -> Dict:
        """Update an existing budget category"""
        try:
            # Validate category exists
            category = await self.budget_categories.find_one({"_id": PyObjectId(category_id)})
            if not category:
                raise ValueError("Budget category not found")

            # Check if updating the budget amount would exceed wedding's total budget
            if "budgeted_amount" in update_data:
                wedding_id = category["wedding_id"]
                wedding = await self.weddings.find_one({"_id": wedding_id})
                wedding_total_budget = wedding.get("total_budget", 0) if wedding else 0

                if wedding_total_budget > 0:
                    # Get all categories except this one (safety cap applied)
                    cursor = self.budget_categories.find({
                        "wedding_id": wedding_id,
                        "_id": {"$ne": PyObjectId(category_id)}
                    })
                    other_categories = await cursor.to_list(length=self.MAX_CATEGORIES)
                    other_total = sum(cat.get("budgeted_amount", 0) for cat in other_categories)
                    new_amount = update_data["budgeted_amount"]

                    if other_total + new_amount > wedding_total_budget:
                        overage = (other_total + new_amount) - wedding_total_budget
                        logger.warning(
                            f"Updating category would exceed wedding budget: "
                            f"Wedding {wedding_id} total: ${wedding_total_budget:,.2f}, "
                            f"Other categories: ${other_total:,.2f}, "
                            f"Updated category: ${new_amount:,.2f}, "
                            f"Overage: ${overage:,.2f}"
                        )
                        # Still allow update but alert will be triggered

            # Update timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)

            # Update category
            result = await self.budget_categories.update_one(
                {"_id": PyObjectId(category_id)},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise ValueError("No changes made to category")

            # Get updated category
            updated_category = await self.budget_categories.find_one({"_id": PyObjectId(category_id)})
            if not updated_category:
                raise ValueError("Category not found after update")

            # Update wedding totals
            await self._update_wedding_budget_total(category["wedding_id"])

            # Check for alerts
            await self._check_budget_alerts(category["wedding_id"])

            # Invalidate AI cache for budget insights
            await self._invalidate_budget_cache(category["wedding_id"])

            logger.info(f"Updated budget category {category_id}")
            return serialize_mongo_doc(updated_category)

        except Exception as e:
            logger.error(f"Failed to update budget category: {str(e)}")
            raise

    async def delete_budget_category(self, category_id: str) -> bool:
        """Delete a budget category"""
        try:
            # Get category to get wedding_id
            category = await self.budget_categories.find_one({"_id": PyObjectId(category_id)})
            if not category:
                raise ValueError("Budget category not found")

            wedding_id = category["wedding_id"]

            # Delete associated quotes and payments
            await self.vendor_quotes.delete_many({"category_id": category_id})
            await self.payment_records.delete_many({"category_id": category_id})

            # Delete category
            result = await self.budget_categories.delete_one({"_id": PyObjectId(category_id)})

            if result.deleted_count == 0:
                raise ValueError("Failed to delete category")

            # Update wedding totals
            await self._update_wedding_budget_total(wedding_id)

            # Invalidate AI cache for budget insights
            await self._invalidate_budget_cache(wedding_id)

            logger.info(f"Deleted budget category {category_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete budget category: {str(e)}")
            raise

    # ===== VENDOR QUOTE MANAGEMENT =====

    async def create_vendor_quote(self, wedding_id: str, quote_data: Dict) -> Dict:
        """Create a new vendor quote"""
        try:
            quote = VendorQuote(
                wedding_id=wedding_id,
                **quote_data
            )

            await self.vendor_quotes.insert_one(quote.model_dump(by_alias=True))
            # Note: id is already set by default_factory

            logger.info(f"Created vendor quote from {quote.vendor_name} for wedding {wedding_id}")
            return quote.model_dump()

        except Exception as e:
            logger.error(f"Failed to create vendor quote: {str(e)}")
            raise

    async def get_vendor_quotes(self, wedding_id: str, service_category: Optional[str] = None) -> List[Dict]:
        """Get vendor quotes for a wedding, optionally filtered by category"""
        try:
            query = {"wedding_id": wedding_id}
            if service_category:
                query["service_category"] = service_category

            cursor = self.vendor_quotes.find(query).sort("created_at", -1)
            # Safety cap for vendor quotes (typical wedding has <10k quotes)
            quotes = await cursor.to_list(length=self.MAX_QUOTES)
            return [serialize_mongo_doc(quote) for quote in quotes]

        except Exception as e:
            logger.error(f"Failed to get vendor quotes: {str(e)}")
            raise

    async def compare_vendor_quotes(self, wedding_id: str, service_category: str) -> Dict:
        """Compare vendor quotes for a specific service category"""
        try:
            quotes = await self.get_vendor_quotes(wedding_id, service_category)

            if len(quotes) < 2:
                return {"error": "Need at least 2 quotes to compare", "quotes": quotes}

            # Calculate comparison metrics
            quote_amounts = [q["quote_amount"] for q in quotes]
            comparison: Dict[str, Any] = {
                "service_category": service_category,
                "quotes": quotes,
                "statistics": {
                    "count": len(quotes),
                    "lowest": min(quote_amounts),
                    "highest": max(quote_amounts),
                    "average": sum(quote_amounts) / len(quote_amounts),
                    "savings_potential": max(quote_amounts) - min(quote_amounts)
                },
                "recommendations": []
            }

            # Add recommendations
            lowest_quote = min(quotes, key=lambda x: x["quote_amount"])
            # Note: highest_quote available in statistics already

            comparison["recommendations"].append({
                "type": "lowest_price",
                "vendor": lowest_quote["vendor_name"],
                "amount": lowest_quote["quote_amount"],
                "message": "Lowest price option"
            })
            if comparison["statistics"]["savings_potential"] > 1000:
                comparison["recommendations"].append({
                    "type": "savings_alert",
                    "message": f"You could save ${comparison['statistics']['savings_potential']:.2f} by choosing the lowest quote",
                    "savings": comparison["statistics"]["savings_potential"]
                })

            return comparison

        except Exception as e:
            logger.error(f"Failed to compare vendor quotes: {str(e)}")
            raise

    async def get_vendor_quote(self, quote_id: str) -> Optional[Dict]:
        """Fetch a single vendor quote by its identifier."""
        try:
            quote = await self.vendor_quotes.find_one({"_id": PyObjectId(quote_id)})
            if not quote:
                return None
            return serialize_mongo_doc(quote)
        except Exception as e:
            logger.error(f"Failed to fetch vendor quote: {str(e)}")
            raise

    async def update_quote_status(self, quote_id: str, status: str, notes: Optional[str] = None) -> Dict:
        """Update vendor quote status (accept/reject)"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.now(timezone.utc)
            }
            if notes:
                update_data["notes"] = notes
            result = await self.vendor_quotes.update_one(
                {"_id": PyObjectId(quote_id)},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise ValueError("Quote not found or no changes made")

            # Get updated quote
            updated_quote = await self.vendor_quotes.find_one({"_id": PyObjectId(quote_id)})
            if not updated_quote:
                raise ValueError("Quote not found after update")

            # If quote was accepted, update budget category actual spending
            if status == "accepted":
                await self._update_category_from_accepted_quote(updated_quote)

            logger.info(f"Updated quote {quote_id} status to {status}")
            return serialize_mongo_doc(updated_quote)

        except Exception as e:
            logger.error(f"Failed to update quote status: {str(e)}")
            raise

    async def rate_vendor_quote(self, quote_id: str, rating: int, notes: Optional[str] = None) -> Dict:
        """Rate a vendor quote (1-5 stars)"""
        try:
            update_data: Dict[str, Any] = {
                "rating": rating,
                "updated_at": datetime.now(timezone.utc)
            }
            if notes is not None:
                update_data["rating_notes"] = notes

            result = await self.vendor_quotes.update_one(
                {"_id": PyObjectId(quote_id)},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise ValueError("Quote not found or no changes made")

            updated_quote = await self.vendor_quotes.find_one({"_id": PyObjectId(quote_id)})
            if not updated_quote:
                raise ValueError("Quote not found after update")

            logger.info(f"Rated quote {quote_id} with {rating} stars")
            return serialize_mongo_doc(updated_quote)

        except Exception as e:
            logger.error(f"Failed to rate vendor quote: {str(e)}")
            raise

    # ===== BUDGET TEMPLATES =====

    async def get_budget_templates(self, wedding_type: Optional[str] = None) -> List[Dict]:
        """Get available budget templates"""
        try:
            query: Dict[str, Any] = {"is_public": True}
            if wedding_type:
                query["wedding_type"] = wedding_type

            cursor = self.budget_templates.find(query).sort("name", 1)
            # Safety cap for templates (typically <1k public templates)
            templates = await cursor.to_list(length=self.MAX_TEMPLATES)
            return [self._serialize_template(template) for template in templates if template]

        except Exception as e:
            logger.error(f"Failed to get budget templates: {str(e)}")
            raise

    async def create_budget_template(self, template_data: Dict, created_by: Optional[str] = None) -> Dict:
        """Create a custom budget template"""
        try:
            categories = template_data.get("categories", [])
            if not categories:
                raise ValueError("At least one category is required")

            total_percentage = sum(category.get("percentage", 0) for category in categories)
            if abs(total_percentage - 100) > 0.5:
                raise ValueError("Category percentages must total 100%")

            normalized_categories = []
            seen_names = set()
            for category in categories:
                name = category.get("name", "").strip()
                if not name:
                    raise ValueError("Each category requires a name")

                normalized_name = name.lower()
                if normalized_name in seen_names:
                    raise ValueError("Category names must be unique within a template")
                seen_names.add(normalized_name)

                percentage = float(category.get("percentage", 0))
                if percentage <= 0:
                    raise ValueError("Category percentages must be greater than zero")

                priority = int(category.get("priority", 3))
                if priority < 1 or priority > 5:
                    raise ValueError("Category priority must be between 1 and 5")

                normalized_categories.append(
                    {
                        "name": name,
                        "percentage": round(percentage, 2),
                        "priority": priority,
                    }
                )

            guest_range = template_data.get("guest_count_range", {}) or {}
            guest_min = int(guest_range.get("min", 0))
            guest_max = int(guest_range.get("max", 0))
            if guest_max < guest_min:
                raise ValueError("Guest count max must be greater than or equal to min")

            target_min = float(template_data.get("target_budget_min", 0))
            target_max = float(template_data.get("target_budget_max", 0))
            if target_max < target_min:
                raise ValueError("Maximum budget must be greater than or equal to minimum budget")

            template = BudgetTemplate(
                name=template_data.get("name", "").strip(),
                description=template_data.get("description"),
                wedding_type=template_data.get("wedding_type", "").strip(),
                target_budget_min=target_min,
                target_budget_max=target_max,
                guest_count_range={"min": guest_min, "max": guest_max},
                categories=normalized_categories,
                created_by=created_by,
                is_public=bool(template_data.get("is_public", False)),
            )

            insert_payload = template.model_dump(by_alias=True)
            result = await self.budget_templates.insert_one(insert_payload)

            stored_template = await self.budget_templates.find_one({"_id": result.inserted_id})
            if not stored_template:
                raise ValueError("Failed to retrieve template after creation")
            return self._serialize_template(stored_template)

        except Exception as e:
            logger.error(f"Failed to create budget template: {str(e)}")
            raise

    async def apply_budget_template(self, wedding_id: str, template_id: str, total_budget: float) -> Dict:
        """Apply a budget template to a wedding"""
        try:
            # Get template
            template = await self.budget_templates.find_one({"_id": PyObjectId(template_id)})
            if not template:
                raise ValueError("Budget template not found")
            # Clear existing categories (optional - could be made configurable)
            cursor = self.budget_categories.find({"wedding_id": wedding_id})
            existing_categories = await cursor.to_list(length=self.MAX_CATEGORIES)
            if existing_categories:
                logger.warning(f"Wedding {wedding_id} already has {len(existing_categories)} budget categories")
            # Create categories from template
            created_categories = []
            for category_template in template["categories"]:
                category_amount = total_budget * (category_template["percentage"] / 100)
                category_data = {
                    "name": category_template["name"],
                    "description": f"Generated from {template['name']} template",
                    "budgeted_amount": category_amount,
                    "priority": category_template.get("priority", 3),
                    "percentage_of_total": category_template["percentage"]
                }

                category = await self.create_budget_category(wedding_id, category_data)
                created_categories.append(category)

            # Update wedding with total budget
            await self.weddings.update_one(
                {"_id": wedding_id},
                {"$set": {"total_budget": total_budget, "budget_template_applied": template_id}}
            )
            logger.info(f"Applied budget template {template['name']} to wedding {wedding_id}")
            return {
                "template_applied": template["name"],
                "total_budget": total_budget,
                "categories_created": len(created_categories),
                "categories": created_categories
            }

        except Exception as e:
            logger.error(f"Failed to apply budget template: {str(e)}")
            raise

    def _serialize_template(self, template_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize template documents for API responses"""
        if not template_doc:
            raise ValueError("Template not found")

        identifier = str(template_doc.get("_id"))
        guest_range = template_doc.get("guest_count_range") or {}

        def _format_datetime(value: Any) -> str:
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value) if value else ""

        categories = []
        for category in template_doc.get("categories", []):
            categories.append(
                {
                    "name": category.get("name", ""),
                    "percentage": float(category.get("percentage", 0)),
                    "priority": int(category.get("priority", 3)),
                }
            )

        return {
            "id": identifier,
            "_id": identifier,
            "name": template_doc.get("name", ""),
            "description": template_doc.get("description"),
            "wedding_type": template_doc.get("wedding_type", ""),
            "target_budget_min": float(template_doc.get("target_budget_min", 0)),
            "target_budget_max": float(template_doc.get("target_budget_max", 0)),
            "guest_count_range": {
                "min": int(guest_range.get("min", 0)),
                "max": int(guest_range.get("max", 0)),
            },
            "categories": categories,
            "created_by": template_doc.get("created_by"),
            "is_public": bool(template_doc.get("is_public", False)),
            "created_at": _format_datetime(template_doc.get("created_at")),
            "updated_at": _format_datetime(template_doc.get("updated_at")),
        }

    # ===== PAYMENT TRACKING =====

    async def get_budget_category(self, category_id: str) -> Optional[Dict]:
        """Fetch a single budget category by its identifier."""
        try:
            category = await self.budget_categories.find_one({"_id": PyObjectId(category_id)})
            if not category:
                return None

            return serialize_mongo_doc(category)
        except ValueError as e:
            logger.error(f"Invalid category id provided: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch budget category: {str(e)}")
            raise

    async def record_payment(self, category_id: str, payment_data: Dict) -> Dict:
        """Record a payment for a budget category"""
        try:
            category = await self.budget_categories.find_one({"_id": PyObjectId(category_id)})
            if not category:
                raise ValueError("Budget category not found")

            payment = PaymentRecord(
                category_id=category_id,
                **payment_data
            )

            result = await self.payment_records.insert_one(payment.model_dump())
            payment.id = result.inserted_id  # type: ignore[assignment]

            # Update category actual spending
            new_actual_spent = category.get("actual_spent", 0) + payment.amount
            await self.budget_categories.update_one(
                {"_id": PyObjectId(category_id)},
                {"$set": {
                    "actual_spent": new_actual_spent,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

            # Update payment status based on spending vs budget
            budgeted = category.get("budgeted_amount", 0)
            if new_actual_spent >= budgeted:
                payment_status = "paid"
            elif new_actual_spent > 0:
                payment_status = "partial"
            else:
                payment_status = "pending"

            await self.budget_categories.update_one(
                {"_id": PyObjectId(category_id)},
                {"$set": {"payment_status": payment_status}}
            )

            # Check for over-budget alerts
            await self._check_budget_alerts(category["wedding_id"])

            logger.info(f"Recorded payment of ${payment.amount} for category {category_id}")
            payment_dict = payment.model_dump()
            if "id" in payment_dict and payment_dict["id"] is not None:
                payment_dict["id"] = str(payment_dict["id"])
            return payment_dict

        except Exception as e:
            logger.error(f"Failed to record payment: {str(e)}")
            raise

    async def get_payment_history(self, wedding_id: str) -> List[Dict]:
        """Get payment history for a wedding"""
        try:
            # Get all categories for this wedding (safety cap applied)
            cursor = self.budget_categories.find({"wedding_id": wedding_id})
            categories = await cursor.to_list(length=self.MAX_CATEGORIES)
            category_ids = [str(cat["_id"]) for cat in categories]
            # Get all payments for these categories (safety cap applied)
            payments_cursor = self.payment_records.find(
                {"category_id": {"$in": category_ids}}
            ).sort("payment_date", -1)
            payments = await payments_cursor.to_list(length=self.MAX_PAYMENT_RECORDS)

            # Add category name to each payment
            category_names = {str(cat["_id"]): cat["name"] for cat in categories}
            for payment in payments:
                payment["category_name"] = category_names.get(payment["category_id"], "Unknown")

            # Serialize all MongoDB documents and fields for JSON response
            return [serialize_mongo_doc(payment) for payment in payments]

        except Exception as e:
            logger.error(f"Failed to get payment history: {str(e)}")
            raise

    async def get_payment(self, payment_id: str) -> Optional[Dict]:
        """Fetch a single payment by ID"""
        try:
            payment = await self.payment_records.find_one({"_id": PyObjectId(payment_id)})
            if not payment:
                return None
            return serialize_mongo_doc(payment)
        except Exception as e:
            logger.error(f"Failed to fetch payment: {str(e)}")
            raise

    async def update_payment(self, payment_id: str, update_data: Dict) -> Dict:
        """Update a payment record and adjust category spending"""
        try:
            original = await self.payment_records.find_one({"_id": PyObjectId(payment_id)})
            if not original:
                raise ValueError("Payment not found")

            category_id = original["category_id"]
            amount_diff = 0
            if "amount" in update_data:
                amount_diff = update_data["amount"] - original.get("amount", 0)

            update_data["updated_at"] = datetime.now(timezone.utc)

            await self.payment_records.update_one(
                {"_id": PyObjectId(payment_id)},
                {"$set": update_data}
            )

            if amount_diff != 0:
                await self.budget_categories.update_one(
                    {"_id": PyObjectId(category_id)},
                    {"$inc": {"actual_spent": amount_diff}}
                )
                category = await self.budget_categories.find_one({"_id": PyObjectId(category_id)})
                if category:
                    await self._check_budget_alerts(category["wedding_id"])

            updated = await self.payment_records.find_one({"_id": PyObjectId(payment_id)})
            return serialize_mongo_doc(updated)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to update payment: {str(e)}")
            raise

    async def delete_payment(self, payment_id: str) -> bool:
        """Delete a payment and adjust category spending"""
        try:
            payment = await self.payment_records.find_one({"_id": PyObjectId(payment_id)})
            if not payment:
                raise ValueError("Payment not found")

            category_id = payment["category_id"]
            amount = payment.get("amount", 0)

            result = await self.payment_records.delete_one({"_id": PyObjectId(payment_id)})
            if result.deleted_count == 0:
                raise ValueError("Failed to delete payment")

            await self.budget_categories.update_one(
                {"_id": PyObjectId(category_id)},
                {"$inc": {"actual_spent": -amount}}
            )

            category = await self.budget_categories.find_one({"_id": PyObjectId(category_id)})
            if category:
                await self._check_budget_alerts(category["wedding_id"])

            return True
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete payment: {str(e)}")
            raise

    # ===== FINANCIAL REPORTING =====

    async def generate_financial_report(self, wedding_id: str) -> Dict:
        """Generate comprehensive financial report"""
        try:
            # Get budget summary
            summary = await self._calculate_budget_summary(wedding_id)

            # Get categories with details (safety cap applied)
            cursor = self.budget_categories.find({"wedding_id": wedding_id})
            categories = await cursor.to_list(length=self.MAX_CATEGORIES)

            # Get payment history
            payments = await self.get_payment_history(wedding_id)

            # Get vendor quotes summary
            quotes_summary = await self._get_quotes_summary(wedding_id)

            # Calculate trends and insights
            insights = self._calculate_budget_insights(wedding_id, categories, payments)

            report = {
                "wedding_id": wedding_id,
                "report_date": datetime.now(timezone.utc),
                "summary": summary.model_dump(),
                "categories": categories,
                "payment_history": payments[-10:],  # Last 10 payments
                "quotes_summary": quotes_summary,
                "insights": insights,
                "recommendations": self._generate_budget_recommendations(wedding_id, summary, categories)
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate financial report: {str(e)}")
            raise

    # ===== COST ESTIMATION =====

    def estimate_costs(self, guest_count: int, wedding_type: str = "traditional", region: str = "national") -> Dict:
        """Estimate wedding costs based on guest count and type"""
        try:
            # Base cost per guest by region (these would ideally come from a database)
            regional_multipliers = {
                "national": 1.0,
                "urban": 1.3,
                "rural": 0.8,
                "luxury": 1.8
            }
            base_cost_per_guest = {
                "traditional": 180,
                "modern": 220,
                "destination": 350,
                "intimate": 400,  # Higher per-guest cost for smaller weddings
                "courthouse": 50
            }

            multiplier = regional_multipliers.get(region, 1.0)
            per_guest_cost = base_cost_per_guest.get(wedding_type, 180)

            estimated_total = guest_count * per_guest_cost * multiplier

            # Category breakdowns (percentages)
            category_percentages = {
                "Venue & Catering": 45.0,
                "Photography & Videography": 12.0,
                "Music & Entertainment": 10.0,
                "Flowers & Decorations": 8.0,
                "Attire & Beauty": 8.0,
                "Transportation": 5.0,
                "Invitations & Stationery": 3.0,
                "Favors & Gifts": 2.0,
                "Miscellaneous": 7.0
            }
            estimated_categories = {}
            for category, percentage in category_percentages.items():
                estimated_categories[category] = {
                    "amount": estimated_total * (percentage / 100),
                    "percentage": percentage,
                    "per_guest": (estimated_total * (percentage / 100)) / guest_count
                }
            return {
                "guest_count": guest_count,
                "wedding_type": wedding_type,
                "region": region,
                "estimated_total": estimated_total,
                "per_guest_cost": estimated_total / guest_count,
                "categories": estimated_categories,
                "assumptions": {
                    "base_per_guest": per_guest_cost,
                    "regional_multiplier": multiplier,
                    "calculation_method": "guest_count * base_cost * regional_multiplier"
                }
            }

        except Exception as e:
            logger.error(f"Failed to estimate costs: {str(e)}")
            raise

    # ===== PRIVATE HELPER METHODS =====

    async def _calculate_budget_summary(self, wedding_id: str) -> BudgetSummary:
        """Calculate budget summary for a wedding"""
        cursor = self.budget_categories.find({"wedding_id": wedding_id})
        categories = await cursor.to_list(length=self.MAX_CATEGORIES)

        # Get the wedding's total budget from the wedding document
        wedding = await self.weddings.find_one({"_id": wedding_id})
        wedding_total_budget = wedding.get("total_budget", 0) if wedding else 0

        # Use wedding's total_budget if set, otherwise sum category budgets
        categories_total = sum(cat.get("budgeted_amount", 0) for cat in categories)
        total_budget = wedding_total_budget if wedding_total_budget > 0 else categories_total

        total_spent = sum(cat.get("actual_spent", 0) for cat in categories)

        # Calculate committed amounts (accepted quotes) (safety cap applied)
        quotes_cursor = self.vendor_quotes.find({
            "wedding_id": wedding_id,
            "status": "accepted"
        })
        accepted_quotes = await quotes_cursor.to_list(length=self.MAX_QUOTES)
        total_committed = sum(quote.get("quote_amount", 0) for quote in accepted_quotes)

        remaining_budget = total_budget - total_spent
        variance = total_spent - total_budget
        variance_percentage = (variance / total_budget * 100) if total_budget > 0 else 0

        paid_categories = len([cat for cat in categories if cat.get("payment_status") == "paid"])
        overdue_categories = len([cat for cat in categories if cat.get("payment_status") == "overdue"])

        quotes_count = await self.vendor_quotes.count_documents({"wedding_id": wedding_id})

        return BudgetSummary(
            wedding_id=wedding_id,
            total_budget=total_budget,
            total_spent=total_spent,
            total_committed=total_committed,
            remaining_budget=remaining_budget,
            budget_variance=variance,
            variance_percentage=variance_percentage,
            categories_count=len(categories),
            paid_categories=paid_categories,
            overdue_categories=overdue_categories,
            vendor_quotes_count=quotes_count
        )

    async def _update_wedding_budget_total(self, wedding_id: str):
        """Update the total budget amount in the wedding document"""
        cursor = self.budget_categories.find({"wedding_id": wedding_id})
        categories = await cursor.to_list(length=self.MAX_CATEGORIES)
        total_budget = sum(cat.get("budgeted_amount", 0) for cat in categories)
        await self.weddings.update_one(
            {"_id": wedding_id},
            {"$set": {"total_budget": total_budget}}
        )

    async def _check_budget_alerts(self, wedding_id: str):
        """Check for budget alerts and create notifications"""
        cursor = self.budget_categories.find({"wedding_id": wedding_id})
        categories = await cursor.to_list(length=self.MAX_CATEGORIES)

        # Check if total category budgets exceed wedding's total budget
        wedding = await self.weddings.find_one({"_id": wedding_id})
        wedding_total_budget = wedding.get("total_budget", 0) if wedding else 0
        categories_total_budget = sum(cat.get("budgeted_amount", 0) for cat in categories)

        if wedding_total_budget > 0 and categories_total_budget > wedding_total_budget:
            overage = categories_total_budget - wedding_total_budget
            alert = BudgetAlert(
                wedding_id=wedding_id,
                alert_type="categories_exceed_total",
                severity="critical",
                title="Category Budgets Exceed Total Wedding Budget",
                message=f"Your category budgets total ${categories_total_budget:,.2f}, which is ${overage:,.2f} over your total wedding budget of ${wedding_total_budget:,.2f}",
                amount=overage,
                threshold=wedding_total_budget
            )
            # Check if alert already exists
            existing = await self.budget_alerts.find_one({
                "wedding_id": wedding_id,
                "alert_type": "categories_exceed_total",
                "is_resolved": False
            })

            if not existing:
                await self.budget_alerts.insert_one(alert.model_dump())
                logger.warning(f"Wedding {wedding_id}: Category budgets (${categories_total_budget:,.2f}) exceed total budget (${wedding_total_budget:,.2f})")
        else:
            # If categories are now within budget, resolve any existing alerts
            await self.budget_alerts.update_many(
                {
                    "wedding_id": wedding_id,
                    "alert_type": "categories_exceed_total",
                    "is_resolved": False
                },
                {"$set": {"is_resolved": True, "resolved_at": datetime.now(timezone.utc)}}
            )

        for category in categories:
            budgeted = category.get("budgeted_amount", 0)
            spent = category.get("actual_spent", 0)

            # Over budget alert
            if spent > budgeted and budgeted > 0:
                overage = spent - budgeted
                alert = BudgetAlert(
                    wedding_id=wedding_id,
                    category_id=str(category["_id"]),
                    alert_type="over_budget",
                    severity="high",
                    title=f"{category['name']} Over Budget",
                    message=f"This category is ${overage:.2f} over budget",
                    amount=overage,
                    threshold=budgeted
                )
                # Check if alert already exists
                existing = await self.budget_alerts.find_one({
                    "wedding_id": wedding_id,
                    "category_id": str(category["_id"]),
                    "alert_type": "over_budget",
                    "is_resolved": False
                })

                if not existing:
                    await self.budget_alerts.insert_one(alert.model_dump())

            # Approaching budget limit (90%)
            elif spent > (budgeted * 0.9) and budgeted > 0:
                remaining = budgeted - spent
                alert = BudgetAlert(
                    wedding_id=wedding_id,
                    category_id=str(category["_id"]),
                    alert_type="approaching_limit",
                    severity="medium",
                    title=f"{category['name']} Approaching Budget Limit",
                    message=f"Only ${remaining:.2f} remaining in this category",
                    amount=remaining,
                    threshold=budgeted * 0.9
                )
                existing = await self.budget_alerts.find_one({
                    "wedding_id": wedding_id,
                    "category_id": str(category["_id"]),
                    "alert_type": "approaching_limit",
                    "is_resolved": False
                })

                if not existing:
                    await self.budget_alerts.insert_one(alert.model_dump())

    # ===== BUDGET ALERT MANAGEMENT =====

    async def get_budget_alerts(self, wedding_id: str, include_resolved: bool = False) -> List[Dict]:
        """Get budget alerts for a wedding"""
        query = {"wedding_id": wedding_id}
        if not include_resolved:
            query["is_resolved"] = False

        cursor = self.budget_alerts.find(query).sort("created_at", -1)
        # Safety cap for alerts (safety cap applied)
        alerts = await cursor.to_list(length=self.MAX_ALERTS)

        return [serialize_mongo_doc(alert) for alert in alerts]

    async def mark_alert_as_read(self, alert_id: str) -> Dict:
        """Mark a budget alert as read"""
        result = await self.budget_alerts.update_one(
            {"_id": PyObjectId(alert_id)},
            {"$set": {"is_read": True}}
        )
        if result.matched_count == 0:
            raise ValueError("Alert not found")
        return {"message": "Alert marked as read"}

    async def resolve_alert(self, alert_id: str) -> Dict:
        """Resolve a budget alert"""
        result = await self.budget_alerts.update_one(
            {"_id": PyObjectId(alert_id)},
            {"$set": {"is_resolved": True, "resolved_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            raise ValueError("Alert not found")
        return {"message": "Alert resolved"}

    async def _update_category_from_accepted_quote(self, quote: Dict):
        """Update category spending when a quote is accepted"""
        category_id = quote.get("category_id")
        if quote.get("status") == "accepted" and category_id:
            await self.budget_categories.update_one(
                {"_id": PyObjectId(category_id)},
                {"$inc": {"actual_spent": quote["quote_amount"]}}
            )

    async def _get_quotes_summary(self, wedding_id: str) -> Dict:
        """Get summary of vendor quotes for a wedding"""
        cursor = self.vendor_quotes.find({"wedding_id": wedding_id})
        # Safety cap for quotes (safety cap applied)
        quotes = await cursor.to_list(length=self.MAX_QUOTES)

        if not quotes:
            return {"total_quotes": 0}

        by_status = {}
        by_category = {}

        for quote in quotes:
            status = quote.get("status", "pending")
            category = quote.get("service_category", "other")

            by_status[status] = by_status.get(status, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1

        return {
            "total_quotes": len(quotes),
            "by_status": by_status,
            "by_category": by_category,
            "total_value": sum(q.get("quote_amount", 0) for q in quotes),
            "accepted_value": sum(q.get("quote_amount", 0) for q in quotes if q.get("status") == "accepted")
        }
    def _calculate_budget_insights(self, wedding_id: str, categories: List[Dict], payments: List[Dict]) -> Dict:
        """Calculate insights and trends for the budget"""
        if not categories:
            return {}

        total_budgeted = sum(cat.get("budgeted_amount", 0) for cat in categories)
        total_spent = sum(cat.get("actual_spent", 0) for cat in categories)

        # Find most expensive category
        most_expensive = max(categories, key=lambda x: x.get("budgeted_amount", 0))

        # Find category with highest variance
        variances = []
        for cat in categories:
            budgeted = cat.get("budgeted_amount", 0)
            spent = cat.get("actual_spent", 0)
            if budgeted > 0:
                variance_pct = ((spent - budgeted) / budgeted) * 100
                variances.append((cat["name"], variance_pct, spent - budgeted))

        highest_variance = max(variances, key=lambda x: abs(x[1])) if variances else None

        # Payment frequency
        payment_frequency = {}
        for payment in payments[-30:]:  # Last 30 payments
            month = payment.get("payment_date", datetime.now(timezone.utc)).strftime("%Y-%m")
            payment_frequency[month] = payment_frequency.get(month, 0) + 1
        return {
            "budget_utilization": (total_spent / total_budgeted * 100) if total_budgeted > 0 else 0,
            "most_expensive_category": {
                "name": most_expensive["name"],
                "amount": most_expensive.get("budgeted_amount", 0)
            },
            "highest_variance": {
                "category": highest_variance[0] if highest_variance else None,
                "variance_percentage": highest_variance[1] if highest_variance else 0,
                "variance_amount": highest_variance[2] if highest_variance else 0
            } if highest_variance else None,
            "payment_frequency": payment_frequency,
            "categories_on_budget": len([cat for cat in categories
                                       if cat.get("actual_spent", 0) <= cat.get("budgeted_amount", 0)]),
            "categories_over_budget": len([cat for cat in categories
                                         if cat.get("actual_spent", 0) > cat.get("budgeted_amount", 0)])
        }

    async def record_contract_payment(
        self,
        wedding_id: str,
        contract_id: str,
        payment_name: str,
        amount: float,
        category_name: str = "Wedding Planner",
        payment_method: str = "card"
    ) -> Optional[Dict]:
        """
        Record a contract payment in the budget module.

        Called when a scheduled payment succeeds to sync with budget tracking.
        Creates a "Wedding Planner" category if it doesn't exist.

        Args:
            wedding_id: The wedding ID
            contract_id: The contract ID
            payment_name: Payment name/description
            amount: Payment amount
            category_name: Budget category name (defaults to "Wedding Planner")
            payment_method: How payment was made (card, cash, etc.)

        Returns:
            The created payment record or None if wedding not found
        """
        try:
            # Check if wedding exists
            wedding = await self.weddings.find_one({"_id": wedding_id})
            if not wedding:
                logger.warning(f"Wedding {wedding_id} not found for budget sync")
                return None

            # Find or create the category
            category = await self.budget_categories.find_one({
                "wedding_id": wedding_id,
                "name": category_name
            })

            if not category:
                # Create the category
                category_data = {
                    "name": category_name,
                    "description": f"Payments from contract: {contract_id}",
                    "budgeted_amount": amount,  # Initialize with first payment
                    "actual_spent": 0,
                    "payment_status": "pending",
                    "priority": 2,
                    "subcategories": [],
                    "vendor_quotes": [],
                    "payments": [],
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                result = await self.budget_categories.insert_one({
                    "wedding_id": wedding_id,
                    **category_data
                })
                category = await self.budget_categories.find_one({"_id": result.inserted_id})
                if not category:
                    logger.error(f"Failed to retrieve newly created category for wedding {wedding_id}")
                    return None
                logger.info(f"Created budget category '{category_name}' for wedding {wedding_id}")

            # Record the payment
            payment_data = {
                "vendor_name": category_name,
                "amount": amount,
                "payment_method": payment_method,
                "payment_date": datetime.now(timezone.utc),
                "description": payment_name,
                "status": "completed",
                "notes": f"From contract: {contract_id}"
            }

            payment = PaymentRecord(
                category_id=str(category["_id"]),
                **payment_data
            )

            result = await self.payment_records.insert_one(payment.model_dump())
            payment.id = result.inserted_id  # type: ignore[assignment]

            # Update category actual spending
            new_actual_spent = category.get("actual_spent", 0) + amount
            await self.budget_categories.update_one(
                {"_id": category["_id"]},
                {"$set": {
                    "actual_spent": new_actual_spent,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

            # Update payment status
            budgeted = category.get("budgeted_amount", 0)
            if new_actual_spent >= budgeted:
                payment_status = "paid"
            elif new_actual_spent > 0:
                payment_status = "partial"
            else:
                payment_status = "pending"

            await self.budget_categories.update_one(
                {"_id": category["_id"]},
                {"$set": {"payment_status": payment_status}}
            )

            logger.info(f"Recorded contract payment ${amount} for wedding {wedding_id}")
            return payment.model_dump()

        except Exception as e:
            logger.error(f"Failed to record contract payment in budget: {str(e)}")
            return None

    def _generate_budget_recommendations(self, wedding_id: str, summary: BudgetSummary, categories: List[Dict]) -> List[Dict]:
        """Generate actionable budget recommendations"""
        recommendations = []

        # Over budget recommendation
        if summary.budget_variance > 0:
            recommendations.append({
                "type": "over_budget",
                "priority": "high",
                "title": "Budget Exceeded",
                "message": f"You are ${summary.budget_variance:.2f} over budget ({summary.variance_percentage:.1f}%)",
                "action": "Review spending in highest categories and consider adjustments"
            })
        # Under budget recommendation
        elif summary.budget_variance < -1000:  # More than $1000 under
            recommendations.append({
                "type": "under_budget",
                "priority": "medium",
                "title": "Budget Opportunity",
                "message": f"You have ${abs(summary.budget_variance):.2f} remaining in your budget",
                "action": "Consider upgrading services or adding special touches"
            })
        # Vendor quote recommendations
        if summary.vendor_quotes_count < 3:
            recommendations.append({
                "type": "vendor_quotes",
                "priority": "medium",
                "title": "Get More Quotes",
                "message": "Consider getting more vendor quotes to ensure competitive pricing",
                "action": "Aim for at least 3 quotes per major category"
            })
        return recommendations
