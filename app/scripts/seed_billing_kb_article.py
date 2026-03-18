"""
Seed the Knowledge Base with a billing & subscription guide for planners.

Usage:
  python -m app.scripts.seed_billing_kb_article

Idempotent — skips if the article slug already exists.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.database import mongo, init_database  # noqa: E402


ARTICLE_SLUG = "understanding-your-trial-billing-and-subscription"

ARTICLE = {
    "title": "Understanding Your Trial, Billing & Subscription",
    "slug": ARTICLE_SLUG,
    "category": "billing-subscription",
    "status": "published",
    "is_official": True,
    "featured": True,
    "order": 1,
    "tags": ["billing", "subscription", "trial", "upgrade", "payment", "plans", "stripe"],
    "estimated_read_minutes": 5,
    "author_email": os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"),
    "author_name": "Special Wedding Team",
    "author_id": "system",
    "excerpt": "Everything you need to know about your free trial, choosing a plan, managing your subscription, and what happens when your trial ends.",
    "content": """# Understanding Your Trial, Billing & Subscription

Welcome to Special Wedding! This guide covers everything about your trial period, subscription plans, and billing.

---

## Your Free Trial

When you sign up, you get a **30-day free trial** on the plan you selected. During your trial you have full access to all features included in your plan — no limitations.

### What's included in your trial?

- Full access to all features of your selected plan
- Create and manage weddings, guests, vendors, and more
- Use AI-powered tools (credits included with your plan)
- Send invitations and manage RSVPs
- Access the seating chart, budget tracker, and timeline builder

### Trial timeline

| When | What happens |
|---|---|
| **Day 1** | Trial starts — full access to your plan |
| **Day 24** | You'll receive an email reminder that your trial ends in 7 days |
| **Day 28** | A 3-day countdown begins with daily email reminders |
| **Day 29** | "2 days left" reminder + in-app banner |
| **Day 30** | "Last day" reminder |
| **Day 31** | Trial ends — account moves to upgrade page |

### What happens when my trial ends?

- Your account is **not deleted** — all your data is safe
- You'll be redirected to the billing page when you log in
- A banner at the top of the app will prompt you to upgrade
- You won't be able to access weddings, guests, or other features until you subscribe
- Once you upgrade, everything is restored instantly

---

## Subscription Plans

Special Wedding offers three plans to match your business:

### Boutique — $29/month
Perfect for solo planners just getting started.
- Up to 3 weddings
- 150 guests per wedding
- Guest & RSVP manager
- Email invitations
- Wedding website
- Timeline builder
- 100 AI credits/month

### Signature — $59/month *(Most Popular)*
For growing businesses that need more power.
- Up to 10 weddings
- 350 guests per wedding
- Everything in Boutique, plus:
- Seating orchestration
- QR check-in & live counts
- Automated reminders
- Vendor collaboration
- 300 AI credits/month
- Priority support

### Enterprise — $149/month
For established agencies managing high volumes.
- Unlimited weddings & guests
- Everything in Signature, plus:
- White-label branding
- API access
- 1000 AI credits/month
- 10 staff seats
- Dedicated support
- Custom integrations

---

## Managing Your Subscription

### How to upgrade or change your plan

1. Go to **Billing** in the left sidebar (or click the "Upgrade" button if you see a banner)
2. View your current plan and available options
3. Click **Change Plan** to switch to a different tier
4. Stripe handles the payment — prorated charges apply automatically

### Switching between monthly and yearly billing

You can switch between monthly and yearly billing at any time from the Billing page. Yearly billing saves you 15% compared to monthly.

### Updating your payment method

1. Go to **Billing** in the sidebar
2. Click **Manage Payment Method**
3. You'll be redirected to the Stripe Customer Portal
4. Update your card details securely through Stripe

### Viewing invoices and billing history

All past invoices are available on the Billing page. You can download PDF receipts for your records.

---

## Cancellation & Reactivation

### How to cancel

You can cancel your subscription at any time from the Billing page. When you cancel:
- Your access continues until the end of your current billing period
- Your data is preserved for 90 days
- You can reactivate at any time during this period

### How to reactivate after cancellation or trial expiration

1. Log in to your account
2. You'll be redirected to the Billing page automatically
3. Choose your plan and complete payment
4. Your account and all data are restored immediately

---

## Frequently Asked Questions

**Will I be charged during my trial?**
No. Your card is collected at signup for a seamless transition, but you won't be charged until the trial ends and only if you choose to continue.

**Can I change plans during my trial?**
Yes! Go to Billing and select a different plan. Your trial continues on the new plan.

**What happens to my data if I don't upgrade?**
Your data is safely stored for 90 days after your trial or subscription ends. After that, it may be permanently deleted.

**Do you offer refunds?**
If you're not satisfied within the first 14 days of a paid subscription, contact us for a full refund.

**How do I get help with billing?**
Email us at support@thespecialwedding.io or use the in-app support chat.
""",
}


async def seed():
    await init_database()
    db = mongo.db
    kb_col = db["knowledge_base"]

    existing = await kb_col.find_one({"slug": ARTICLE_SLUG})
    if existing:
        print(f"[SKIP] Article already exists: {ARTICLE_SLUG}")
        mongo.close()
        return

    now = datetime.now(timezone.utc)
    doc = {
        **ARTICLE,
        "created_at": now,
        "updated_at": now,
        "created_by": ARTICLE["author_email"],
        "updated_by": ARTICLE["author_email"],
        "view_count": 0,
        "helpful_count": 0,
        "not_helpful_count": 0,
        "feedback": [],
    }

    await kb_col.insert_one(doc)
    print(f"[CREATED] KB article seeded: {ARTICLE['title']}")

    mongo.close()


if __name__ == "__main__":
    asyncio.run(seed())
