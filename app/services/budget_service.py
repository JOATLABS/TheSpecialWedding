from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from bson import ObjectId
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
import logging

logger = logging.getLogger(__name__)

class BudgetService:
    def __init__(self):
        self.budget_categories = mongo.db["budget_categories"]
        self.vendor_quotes = mongo.db["vendor_quotes"]
        self.budget_templates = mongo.db["budget_templates"]
        self.payment_records = mongo.db["payment_records"]
        self.budget_alerts = mongo.db["budget_alerts"]
        self.weddings = mongo.get_weddings_collection()
        self.security_validator = SecurityValidator()
    
    # ===== BUDGET CATEGORY MANAGEMENT =====
    
    def create_budget_category(self, wedding_id: str, category_data: Dict) -> Dict:
        """Create a new budget category for a wedding"""
        try:
            # Validate wedding exists and user has access
            wedding = self.weddings.find_one({"_id": ObjectId(wedding_id)})
            if not wedding:
                raise ValueError("Wedding not found")
            
            # Create category
            category = BudgetCategory(
                wedding_id=wedding_id,
                **category_data
            )
            
            # Insert into database
            result = self.budget_categories.insert_one(category.dict(by_alias=True))
            category.id = str(result.inserted_id)
            
            # Update wedding total budget if needed
            self._update_wedding_budget_total(wedding_id)
            
            # Check for budget alerts
            self._check_budget_alerts(wedding_id)
            
            logger.info(f"Created budget category {category.name} for wedding {wedding_id}")
            return category.dict()
            
        except Exception as e:
            logger.error(f"Failed to create budget category: {str(e)}")
            raise
    
    def get_wedding_budget(self, wedding_id: str) -> Dict:
        """Get complete budget for a wedding"""
        try:
            # Get all categories for this wedding
            categories = list(self.budget_categories.find({"wedding_id": wedding_id}))
            
            # Get budget summary
            summary = self._calculate_budget_summary(wedding_id)
            
            # Get recent alerts
            alerts = list(self.budget_alerts.find(
                {"wedding_id": wedding_id, "is_resolved": False}
            ).sort("created_at", -1).limit(10))
            
            return {
                "wedding_id": wedding_id,
                "summary": summary.dict(),
                "categories": categories,
                "alerts": alerts,
                "last_updated": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Failed to get wedding budget: {str(e)}")
            raise
    
    def update_budget_category(self, category_id: str, update_data: Dict) -> Dict:
        """Update an existing budget category"""
        try:
            # Validate category exists
            category = self.budget_categories.find_one({"_id": ObjectId(category_id)})
            if not category:
                raise ValueError("Budget category not found")
            
            # Update timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            # Update category
            result = self.budget_categories.update_one(
                {"_id": ObjectId(category_id)},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                raise ValueError("No changes made to category")
            
            # Get updated category
            updated_category = self.budget_categories.find_one({"_id": ObjectId(category_id)})
            
            # Update wedding totals
            self._update_wedding_budget_total(category["wedding_id"])
            
            # Check for alerts
            self._check_budget_alerts(category["wedding_id"])
            
            logger.info(f"Updated budget category {category_id}")
            return updated_category
            
        except Exception as e:
            logger.error(f"Failed to update budget category: {str(e)}")
            raise
    
    def delete_budget_category(self, category_id: str) -> bool:
        """Delete a budget category"""
        try:
            # Get category to get wedding_id
            category = self.budget_categories.find_one({"_id": ObjectId(category_id)})
            if not category:
                raise ValueError("Budget category not found")
            
            wedding_id = category["wedding_id"]
            
            # Delete associated quotes and payments
            self.vendor_quotes.delete_many({"category_id": category_id})
            self.payment_records.delete_many({"category_id": category_id})
            
            # Delete category
            result = self.budget_categories.delete_one({"_id": ObjectId(category_id)})
            
            if result.deleted_count == 0:
                raise ValueError("Failed to delete category")
            
            # Update wedding totals
            self._update_wedding_budget_total(wedding_id)
            
            logger.info(f"Deleted budget category {category_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete budget category: {str(e)}")
            raise
    
    # ===== VENDOR QUOTE MANAGEMENT =====
    
    def create_vendor_quote(self, wedding_id: str, quote_data: Dict) -> Dict:
        """Create a new vendor quote"""
        try:
            quote = VendorQuote(
                wedding_id=wedding_id,
                **quote_data
            )
            
            result = self.vendor_quotes.insert_one(quote.dict(by_alias=True))
            quote.id = str(result.inserted_id)
            
            logger.info(f"Created vendor quote from {quote.vendor_name} for wedding {wedding_id}")
            return quote.dict()
            
        except Exception as e:
            logger.error(f"Failed to create vendor quote: {str(e)}")
            raise
    
    def get_vendor_quotes(self, wedding_id: str, service_category: Optional[str] = None) -> List[Dict]:
        """Get vendor quotes for a wedding, optionally filtered by category"""
        try:
            query = {"wedding_id": wedding_id}
            if service_category:
                query["service_category"] = service_category
            
            quotes = list(self.vendor_quotes.find(query).sort("created_at", -1))
            return quotes
            
        except Exception as e:
            logger.error(f"Failed to get vendor quotes: {str(e)}")
            raise
    
    def compare_vendor_quotes(self, wedding_id: str, service_category: str) -> Dict:
        """Compare vendor quotes for a specific service category"""
        try:
            quotes = self.get_vendor_quotes(wedding_id, service_category)
            
            if len(quotes) < 2:
                return {"error": "Need at least 2 quotes to compare", "quotes": quotes}
            
            # Calculate comparison metrics
            quote_amounts = [q["quote_amount"] for q in quotes]
            comparison = {
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
            highest_quote = max(quotes, key=lambda x: x["quote_amount"])
            
            comparison["recommendations"].append({
                "type": "lowest_price",
                "vendor": lowest_quote["vendor_name"],
                "amount": lowest_quote["quote_amount"],
                "message": f"Lowest price option"
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
    
    def update_quote_status(self, quote_id: str, status: str, notes: Optional[str] = None) -> Dict:
        """Update vendor quote status (accept/reject)"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow()
            }
            if notes:
                update_data["notes"] = notes
            
            result = self.vendor_quotes.update_one(
                {"_id": ObjectId(quote_id)},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                raise ValueError("Quote not found or no changes made")
            
            # Get updated quote
            updated_quote = self.vendor_quotes.find_one({"_id": ObjectId(quote_id)})
            
            # If quote was accepted, update budget category actual spending
            if status == "accepted":
                self._update_category_from_accepted_quote(updated_quote)
            
            logger.info(f"Updated quote {quote_id} status to {status}")
            return updated_quote
            
        except Exception as e:
            logger.error(f"Failed to update quote status: {str(e)}")
            raise
    
    # ===== BUDGET TEMPLATES =====
    
    def get_budget_templates(self, wedding_type: Optional[str] = None) -> List[Dict]:
        """Get available budget templates"""
        try:
            query = {"is_public": True}
            if wedding_type:
                query["wedding_type"] = wedding_type
            
            templates = list(self.budget_templates.find(query).sort("name", 1))
            return templates
            
        except Exception as e:
            logger.error(f"Failed to get budget templates: {str(e)}")
            raise
    
    def apply_budget_template(self, wedding_id: str, template_id: str, total_budget: float) -> Dict:
        """Apply a budget template to a wedding"""
        try:
            # Get template
            template = self.budget_templates.find_one({"_id": ObjectId(template_id)})
            if not template:
                raise ValueError("Budget template not found")
            
            # Clear existing categories (optional - could be made configurable)
            existing_categories = list(self.budget_categories.find({"wedding_id": wedding_id}))
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
                
                category = self.create_budget_category(wedding_id, category_data)
                created_categories.append(category)
            
            # Update wedding with total budget
            self.weddings.update_one(
                {"_id": ObjectId(wedding_id)},
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
    
    # ===== PAYMENT TRACKING =====
    
    def record_payment(self, category_id: str, payment_data: Dict) -> Dict:
        """Record a payment for a budget category"""
        try:
            payment = PaymentRecord(
                category_id=category_id,
                **payment_data
            )
            
            result = self.payment_records.insert_one(payment.dict())
            payment.id = str(result.inserted_id)
            
            # Update category actual spending
            category = self.budget_categories.find_one({"_id": ObjectId(category_id)})
            if category:
                new_actual_spent = category.get("actual_spent", 0) + payment.amount
                self.budget_categories.update_one(
                    {"_id": ObjectId(category_id)},
                    {"$set": {
                        "actual_spent": new_actual_spent,
                        "updated_at": datetime.utcnow()
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
                
                self.budget_categories.update_one(
                    {"_id": ObjectId(category_id)},
                    {"$set": {"payment_status": payment_status}}
                )
                
                # Check for over-budget alerts
                self._check_budget_alerts(category["wedding_id"])
            
            logger.info(f"Recorded payment of ${payment.amount} for category {category_id}")
            return payment.dict()
            
        except Exception as e:
            logger.error(f"Failed to record payment: {str(e)}")
            raise
    
    def get_payment_history(self, wedding_id: str) -> List[Dict]:
        """Get payment history for a wedding"""
        try:
            # Get all categories for this wedding
            categories = list(self.budget_categories.find({"wedding_id": wedding_id}))
            category_ids = [str(cat["_id"]) for cat in categories]
            
            # Get all payments for these categories
            payments = list(self.payment_records.find(
                {"category_id": {"$in": category_ids}}
            ).sort("payment_date", -1))
            
            # Add category name to each payment
            category_names = {str(cat["_id"]): cat["name"] for cat in categories}
            for payment in payments:
                payment["category_name"] = category_names.get(payment["category_id"], "Unknown")
            
            return payments
            
        except Exception as e:
            logger.error(f"Failed to get payment history: {str(e)}")
            raise
    
    # ===== FINANCIAL REPORTING =====
    
    def generate_financial_report(self, wedding_id: str) -> Dict:
        """Generate comprehensive financial report"""
        try:
            # Get budget summary
            summary = self._calculate_budget_summary(wedding_id)
            
            # Get categories with details
            categories = list(self.budget_categories.find({"wedding_id": wedding_id}))
            
            # Get payment history
            payments = self.get_payment_history(wedding_id)
            
            # Get vendor quotes summary
            quotes_summary = self._get_quotes_summary(wedding_id)
            
            # Calculate trends and insights
            insights = self._calculate_budget_insights(wedding_id, categories, payments)
            
            report = {
                "wedding_id": wedding_id,
                "report_date": datetime.utcnow(),
                "summary": summary.dict(),
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
    
    def _calculate_budget_summary(self, wedding_id: str) -> BudgetSummary:
        """Calculate budget summary for a wedding"""
        categories = list(self.budget_categories.find({"wedding_id": wedding_id}))
        
        total_budget = sum(cat.get("budgeted_amount", 0) for cat in categories)
        total_spent = sum(cat.get("actual_spent", 0) for cat in categories)
        
        # Calculate committed amounts (accepted quotes)
        accepted_quotes = list(self.vendor_quotes.find({
            "wedding_id": wedding_id,
            "status": "accepted"
        }))
        total_committed = sum(quote.get("quote_amount", 0) for quote in accepted_quotes)
        
        remaining_budget = total_budget - total_spent
        variance = total_spent - total_budget
        variance_percentage = (variance / total_budget * 100) if total_budget > 0 else 0
        
        paid_categories = len([cat for cat in categories if cat.get("payment_status") == "paid"])
        overdue_categories = len([cat for cat in categories if cat.get("payment_status") == "overdue"])
        
        quotes_count = self.vendor_quotes.count_documents({"wedding_id": wedding_id})
        
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
    
    def _update_wedding_budget_total(self, wedding_id: str):
        """Update the total budget amount in the wedding document"""
        categories = list(self.budget_categories.find({"wedding_id": wedding_id}))
        total_budget = sum(cat.get("budgeted_amount", 0) for cat in categories)
        
        self.weddings.update_one(
            {"_id": ObjectId(wedding_id)},
            {"$set": {"total_budget": total_budget}}
        )
    
    def _check_budget_alerts(self, wedding_id: str):
        """Check for budget alerts and create notifications"""
        categories = list(self.budget_categories.find({"wedding_id": wedding_id}))
        
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
                existing = self.budget_alerts.find_one({
                    "wedding_id": wedding_id,
                    "category_id": str(category["_id"]),
                    "alert_type": "over_budget",
                    "is_resolved": False
                })
                
                if not existing:
                    self.budget_alerts.insert_one(alert.dict())
            
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
                
                existing = self.budget_alerts.find_one({
                    "wedding_id": wedding_id,
                    "category_id": str(category["_id"]),
                    "alert_type": "approaching_limit",
                    "is_resolved": False
                })
                
                if not existing:
                    self.budget_alerts.insert_one(alert.dict())
    
    def _update_category_from_accepted_quote(self, quote: Dict):
        """Update category spending when a quote is accepted"""
        if quote.get("status") == "accepted":
            self.budget_categories.update_one(
                {"_id": ObjectId(quote.get("category_id"))},
                {"$inc": {"actual_spent": quote["quote_amount"]}}
            )
    
    def _get_quotes_summary(self, wedding_id: str) -> Dict:
        """Get summary of vendor quotes for a wedding"""
        quotes = list(self.vendor_quotes.find({"wedding_id": wedding_id}))
        
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
            month = payment.get("payment_date", datetime.utcnow()).strftime("%Y-%m")
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