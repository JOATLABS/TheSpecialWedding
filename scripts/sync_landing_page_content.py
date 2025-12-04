#!/usr/bin/env python3
"""
Sync Landing Page Content to Database
Extracts all hardcoded content from app/page.tsx and populates the SAAS config in MongoDB
"""
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "wedding")

async def sync_content():
    """Populate database with landing page content"""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    # Complete SAAS configuration matching the landing page
    saas_config = {
        "type": "main_config",

        # Hero Section
        "hero_title": "A stage-set platform where every wedding feels like a cinematic premiere.",
        "hero_subtitle": "The Special Wedding",
        "hero_description": "Sculpt invitations, RSVP journeys, wedding websites, seating, timelines, and on-site orchestration—woven together with romantic motion and intelligent automation.",
        "hero_cta_primary": "Explore pricing",
        "hero_cta_secondary": "Launch console",

        # Modern Hero Fields
        "hero_headline": "A stage-set platform where every wedding feels like a cinematic premiere",
        "hero_subheadline": "The Special Wedding",
        "hero_problem_statement": "Managing multiple weddings with spreadsheets and disconnected tools creates chaos",
        "hero_solution_statement": "One unified platform for guest lists, timelines, seating, and vendor coordination",

        # Trust indicators
        "trust_indicators": [
            "Multi-tenant architecture",
            "99.9% uptime",
            "SOC 2 aligned infrastructure"
        ],

        # Partner logos
        "partners": ["Stripe", "Mailgun", "Mapbox", "Slack", "Zoom"],

        # Metrics
        "statistics": [
            {"label": "Guest records", "value": "48k", "subtext": "managed across active weddings"},
            {"label": "Average RSVP window", "value": "5 days", "subtext": "to reach 90% response"},
            {"label": "Check-in speed", "value": "2.8s", "subtext": "median scan-to-confirm time"},
            {"label": "Automation reliability", "value": "99.9%", "subtext": "delivery across reminders"}
        ],
        "statistics_enabled": True,

        # Features (10 core features)
        "features": [
            {
                "title": "Guest lists & households",
                "description": "Unify invites, plus‑ones, and households with filters for VIPs, vendors, and families.",
                "icon": "UserGroupIcon",
                "category": "Planning",
                "status": "available",
                "order": 1
            },
            {
                "title": "Signature invitations",
                "description": "Send branded email invitations, track bounces, and personalize every RSVP link.",
                "icon": "EnvelopeIcon",
                "category": "Engagement",
                "status": "available",
                "order": 2
            },
            {
                "title": "Wedding websites",
                "description": "Launch a stunning site for every celebration—custom domains, schedules, travel, and galleries.",
                "icon": "SparklesIcon",
                "category": "Experience",
                "status": "available",
                "order": 3
            },
            {
                "title": "RSVP & meal selections",
                "description": "Capture attendance, meal preferences, allergies, and notes in real time.",
                "icon": "CheckBadgeIcon",
                "category": "Engagement",
                "status": "available",
                "order": 4
            },
            {
                "title": "Seating orchestration",
                "description": "Drag-and-drop tables, respect family groupings, and export final charts instantly.",
                "icon": "RectangleGroupIcon",
                "category": "Planning",
                "status": "available",
                "order": 5
            },
            {
                "title": "Ceremony & reception timeline",
                "description": "Publish schedules for planners, vendors, and couples with role-based visibility.",
                "icon": "CalendarDaysIcon",
                "category": "Execution",
                "status": "available",
                "order": 6
            },
            {
                "title": "Moments gallery",
                "description": "Collect guest photos, curate galleries, and share highlights after the celebration.",
                "icon": "PhotoIcon",
                "category": "Celebration",
                "status": "available",
                "order": 7
            },
            {
                "title": "Smart reminders",
                "description": "Automate nudges for RSVP deadlines, travel updates, and day-of changes.",
                "icon": "BellAlertIcon",
                "category": "Communication",
                "status": "available",
                "order": 8
            },
            {
                "title": "Touchless check-in",
                "description": "Scan QR codes, monitor arrivals, and keep lines moving with live capacity counts.",
                "icon": "QrCodeIcon",
                "category": "Execution",
                "status": "available",
                "order": 9
            },
            {
                "title": "Maps & travel",
                "description": "Share venues, shuttles, and hotel blocks with smart directions for every guest.",
                "icon": "MapPinIcon",
                "category": "Communication",
                "status": "available",
                "order": 10
            }
        ],
        "features_enabled": True,

        # Suites (enterprise features)
        "suites": [
            {
                "title": "Multi-tenant oversight",
                "description": "Serve every planner, partner, or franchise in isolated workspaces with shared brand standards.",
                "stat": "Scale to 100+ concurrent weddings with centralized governance.",
                "order": 1
            },
            {
                "title": "Vendor collaboration",
                "description": "Loop photographers, caterers, and venues into dedicated timelines and file exchanges.",
                "stat": "Reduce coordination rounds by 68% through unified updates.",
                "order": 2
            },
            {
                "title": "Insights & compliance",
                "description": "Audit-ready exports cover guest consent, messaging logs, and accessibility notes.",
                "stat": "SOC 2 aligned infrastructure keeps client data secure.",
                "order": 3
            }
        ],

        # Workflow stages
        "workflow": [
            {
                "title": "Design the experience",
                "subtitle": "Collaborative planning canvas",
                "bullets": [
                    "Launch weddings in minutes with reusable templates",
                    "Assign visibility by planner, couple, or vendor team",
                    "Model budgets, seating, and timelines side by side"
                ],
                "order": 1
            },
            {
                "title": "Invite & delight",
                "subtitle": "Intelligent guest journeys",
                "bullets": [
                    "Personalized wedding websites with per-wedding slugs",
                    "Automated reminders that adapt to RSVP behavior",
                    "Guest portal with travel guidance and gallery teasers"
                ],
                "order": 2
            },
            {
                "title": "Execute flawlessly",
                "subtitle": "Day-of command center",
                "bullets": [
                    "Touchless check-in with live headcounts and alerts",
                    "Role-based run of show for coordinators and crew",
                    "Instant galleries and thank-you follow ups post event"
                ],
                "order": 3
            }
        ],

        # Testimonials
        "testimonials": [
            {
                "quote": "The Special Wedding gives our planners and couples a shared language. Every guest touchpoint feels intentional and elegant.",
                "name": "Maya Glenn",
                "role": "Director of Events, Aurora Collective",
                "company": "Aurora Collective",
                "order": 1
            },
            {
                "quote": "Check-in lines disappeared. The live dashboards let us choreograph the day like a performance instead of fighting fires.",
                "name": "Elias Romero",
                "role": "Lead Coordinator, Harbor & Bloom",
                "company": "Harbor & Bloom",
                "order": 2
            }
        ],
        "testimonials_enabled": True,

        # Pricing tiers (will be replaced by subscription_plans collection)
        "pricing_tiers": [
            {
                "name": "Boutique",
                "price": "$29",
                "cadence": "per wedding / month",
                "features": [
                    "Guest & RSVP manager",
                    "Email invitations",
                    "Wedding website",
                    "Timeline builder"
                ],
                "cta": "Start planning",
                "emphasized": False,
                "order": 1
            },
            {
                "name": "Signature",
                "price": "$59",
                "cadence": "per wedding / month",
                "badge": "Popular",
                "features": [
                    "Seating orchestration",
                    "QR check-in & live counts",
                    "Automated reminders",
                    "Vendor collaboration"
                ],
                "cta": "Upgrade to Signature",
                "emphasized": True,
                "order": 2
            },
            {
                "name": "Agency",
                "price": "Custom",
                "cadence": "multi-tenant deployments",
                "features": [
                    "Dedicated success architect",
                    "Custom domains & branding",
                    "SSO + role provisioning",
                    "Compliance reporting"
                ],
                "cta": "Talk with sales",
                "emphasized": False,
                "order": 3
            }
        ],

        # FAQs
        "faqs": [
            {
                "question": "Can I manage multiple weddings at once?",
                "answer": "Yes. Workspaces let you run simultaneous weddings, each with their own permissions, branding, and analytics while maintaining agency-wide oversight.",
                "order": 1
            },
            {
                "question": "How do couples collaborate with planners?",
                "answer": "Invite couples to a curated dashboard where they approve guest lists, monitor RSVPs, and review timelines without seeing internal notes.",
                "order": 2
            },
            {
                "question": "Is there support on the wedding day?",
                "answer": "Signature and Agency plans include live chat with our success team plus on-call escalation for critical day-of moments.",
                "order": 3
            },
            {
                "question": "What's next for messaging?",
                "answer": "We are crafting a dedicated messaging studio that centralizes vendor, couple, and planner conversations with payment, contract, and budget context—launching soon.",
                "order": 4
            }
        ],

        # Theme configuration
        "theme": {
            "primary_color": "#d4a5a5",  # wedding-rose
            "secondary_color": "#e8c46a",  # wedding-gold
            "background_color": "#0f172a",  # slate-900
            "text_color": "#ffffff",
            "accent_color": "#1e3a5f",  # wedding-navy
            "fallback_images": []
        },

        # Section toggles
        "benefits_enabled": True,

        # CTA section
        "cta_title": "Create memories that feel effortless from the first hello.",
        "cta_description": "Give every planner, partner, and couple a stage worthy of their story with The Special Wedding.",
        "cta_primary": "Launch console",
        "cta_secondary": "Request a guided tour",
        "cta_email": "hello@weddingwebapp.ai",

        # Metadata
        "updated_by": "system_migration",
        "updated_at": datetime.utcnow(),
        "created_at": datetime.utcnow()
    }

    # Upsert the configuration
    result = await db["saas_config"].update_one(
        {"type": "main_config"},
        {"$set": saas_config},
        upsert=True
    )

    if result.upserted_id:
        print(f"✅ Created new SAAS config with ID: {result.upserted_id}")
    else:
        print(f"✅ Updated existing SAAS config (matched: {result.matched_count}, modified: {result.modified_count})")

    print("\n📊 Content Summary:")
    print(f"  - Features: {len(saas_config['features'])}")
    print(f"  - Metrics: {len(saas_config['statistics'])}")
    print(f"  - Workflow Stages: {len(saas_config['workflow'])}")
    print(f"  - Testimonials: {len(saas_config['testimonials'])}")
    print(f"  - Pricing Tiers: {len(saas_config['pricing_tiers'])}")
    print(f"  - FAQs: {len(saas_config['faqs'])}")
    print(f"  - Partner Logos: {len(saas_config['partners'])}")

    print("\n✨ SAAS config successfully synced to database!")
    print("   You can now edit all landing page content from /admin/saas")

    client.close()

if __name__ == "__main__":
    asyncio.run(sync_content())
