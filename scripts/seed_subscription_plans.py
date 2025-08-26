#!/usr/bin/env python3
"""
Seed script to create default subscription plans for the Special Wedding platform
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import mongo
from app.services.subscription_service import SubscriptionService

# Initialize services
subscription_service = SubscriptionService()

def create_default_plans():
 """Create default subscription plans"""
 
 plans = [
 {
 "name": "Starter",
 "description": "Perfect for new wedding planners starting their business",
 "price_monthly": 49.99,
 "price_yearly": 479.99, # 2 months free
 "max_weddings": 3,
 "max_guests_per_wedding": 150,
 "ai_credits_monthly": 50,
 "storage_gb": 5,
 "staff_seats": 1,
 "features": {
 "basic_website_builder": True,
 "guest_management": True,
 "rsvp_system": True,
 "basic_email_templates": True,
 "photo_gallery": True,
 "basic_analytics": True,
 "mobile_app_access": True,
 "email_support": True,
 "ai_tools": False,
 "advanced_reporting": False,
 "white_label": False,
 "custom_integrations": False,
 "multi_user_collaboration": False,
 "priority_support": False,
 "custom_domain": False
 },
 "is_featured": False,
 "is_active": True,
 "display_order": 1
 },
 {
 "name": "Professional",
 "description": "For established planners managing multiple weddings",
 "price_monthly": 99.99,
 "price_yearly": 959.99, # 2 months free
 "max_weddings": 10,
 "max_guests_per_wedding": 300,
 "ai_credits_monthly": 200,
 "storage_gb": 25,
 "staff_seats": 3,
 "features": {
 "basic_website_builder": True,
 "guest_management": True,
 "rsvp_system": True,
 "basic_email_templates": True,
 "photo_gallery": True,
 "basic_analytics": True,
 "mobile_app_access": True,
 "email_support": True,
 "ai_tools": True,
 "advanced_reporting": True,
 "white_label": False,
 "custom_integrations": True,
 "multi_user_collaboration": True,
 "priority_support": True,
 "custom_domain": True
 },
 "is_featured": True, # Most popular plan
 "is_active": True,
 "display_order": 2
 },
 {
 "name": "Enterprise",
 "description": "For large wedding planning agencies and high-volume planners",
 "price_monthly": 199.99,
 "price_yearly": 1919.99, # 2 months free
 "max_weddings": -1, # Unlimited
 "max_guests_per_wedding": -1, # Unlimited
 "ai_credits_monthly": 1000,
 "storage_gb": 100,
 "staff_seats": -1, # Unlimited
 "features": {
 "basic_website_builder": True,
 "guest_management": True,
 "rsvp_system": True,
 "basic_email_templates": True,
 "photo_gallery": True,
 "basic_analytics": True,
 "mobile_app_access": True,
 "email_support": True,
 "ai_tools": True,
 "advanced_reporting": True,
 "white_label": True,
 "custom_integrations": True,
 "multi_user_collaboration": True,
 "priority_support": True,
 "custom_domain": True
 },
 "is_featured": False,
 "is_active": True,
 "display_order": 3
 },
 {
 "name": "Free Trial",
 "description": "14-day free trial to explore all features",
 "price_monthly": 0.00,
 "price_yearly": 0.00,
 "max_weddings": 1,
 "max_guests_per_wedding": 50,
 "ai_credits_monthly": 10,
 "storage_gb": 1,
 "staff_seats": 0,
 "features": {
 "basic_website_builder": True,
 "guest_management": True,
 "rsvp_system": True,
 "basic_email_templates": True,
 "photo_gallery": True,
 "basic_analytics": False,
 "mobile_app_access": True,
 "email_support": True,
 "ai_tools": False,
 "advanced_reporting": False,
 "white_label": False,
 "custom_integrations": False,
 "multi_user_collaboration": False,
 "priority_support": False,
 "custom_domain": False
 },
 "is_featured": False,
 "is_active": True,
 "display_order": 0
 }
 ]
 
 created_plans = []
 
 for plan_data in plans:
 try:
 # Check if plan already exists
 existing_plan = mongo.get_subscription_plans_collection().find_one({"name": plan_data["name"]})
 
 if existing_plan:
 print(f"Plan '{plan_data['name']}' already exists, skipping...")
 created_plans.append(existing_plan)
 continue
 
 # Create the plan using the subscription service
 result = subscription_service.create_plan(plan_data, "system@thespecialwedding.com")
 created_plans.append(result)
 
 print(f" Created subscription plan: {plan_data['name']}")
 
 except Exception as e:
 print(f" Error creating plan '{plan_data['name']}': {str(e)}")
 
 return created_plans

def main():
 """Main function to seed subscription plans"""
 print(" Starting subscription plans seeding...")
 print("-" * 50)
 
 try:
 # Connect to database
 print("Connecting to MongoDB...")
 
 # Create default plans
 plans = create_default_plans()
 
 print("-" * 50)
 print(f" Successfully created {len(plans)} subscription plans!")
 
 # Display created plans
 print("\nCreated Plans:")
 for plan in plans:
 plan_name = plan.get('name', 'Unknown')
 plan_price = plan.get('price_monthly', 0)
 plan_weddings = plan.get('max_weddings', 0)
 weddings_text = "Unlimited" if plan_weddings == -1 else str(plan_weddings)
 print(f" • {plan_name}: ${plan_price}/month ({weddings_text} weddings)")
 
 print("\n Subscription plans seeding completed successfully!")
 
 except Exception as e:
 print(f" Error during seeding: {str(e)}")
 sys.exit(1)

if __name__ == "__main__":
 main()