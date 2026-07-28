"""
Seed Knowledge Base with platform documentation articles.
Run on deployment to keep official KB content aligned with strategy.

Usage:
    python -m app.scripts.seed_knowledge_base

Or call seed_knowledge_base() from app startup.

Refresh behavior:
- New articles (slug not in Mongo) are always inserted.
- Existing articles where ``is_official=True`` and the content differs from
  the seed are refreshed only when ``KB_SEED_REFRESH_OFFICIAL=1`` is set.
  Otherwise a ``[DRIFT]`` warning is printed so operators have visibility.
- Articles where an admin has set ``is_official=False`` are never touched —
  that's the explicit opt-out path.

Why this design (2026-05-10): The seeder used to be skip-if-exists, which
meant pricing-refresh content updates never propagated to production —
stale article bodies stayed in Mongo indefinitely. But blindly upserting
would clobber any admin edits made through the admin UI. The env flag
gives operators a one-shot align deploy without auto-clobbering on every
boot. See the parallel design in scripts/seed_subscription_plans.py.
"""

import asyncio
import os
from datetime import UTC, datetime

from app.core.database import mongo

_REFRESH_FLAG = "KB_SEED_REFRESH_OFFICIAL"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _refresh_enabled() -> bool:
    return os.getenv(_REFRESH_FLAG, "").strip().lower() in _TRUTHY


SEED_ARTICLES = [
    {
        "title": "Getting Started as a Wedding Planner",
        "slug": "getting-started-as-a-wedding-planner",
        "excerpt": "Welcome to TheSpecialWedding! This guide walks you through setting up your first wedding, adding guests, and configuring your couple's landing page.",
        "content": """# Getting Started as a Wedding Planner

Welcome to **TheSpecialWedding** — your all-in-one platform for managing weddings professionally.

## Your Dashboard

After logging in, you'll see your planner dashboard with quick access to all your weddings, upcoming tasks, and notifications.

## Creating Your First Wedding

1. Navigate to **Weddings** in the sidebar
2. Click **Create Wedding**
3. Fill in the couple's names, wedding date, and slug (this becomes their unique URL)
4. Configure the theme colors to match the couple's style

## Adding Guests

1. Go to **Guest Management**
2. Add guests individually or import from a spreadsheet
3. Assign groups (family, friends, colleagues) for easier management
4. Set plus-one permissions per guest

## Configuring the Landing Page

Each wedding gets a beautiful landing page at `thespecialwedding.io/{slug}`. You can configure:

- **Hero Section** — Couple's photo and names
- **Events** — Ceremony, reception, and other events with times and locations
- **Our Story** — The couple's story with photos
- **Wedding Party** — Bridesmaids, groomsmen, and other roles
- **Registry** — Links to gift registries
- **FAQ** — Common questions for guests

## Privacy Settings

Choose how guests access the wedding page:

- **Public** — Anyone with the link can view
- **Private** — Guests must verify their identity (phone/name) to access
- **Password Protected** — Requires a shared password

## What's Next?

- Set up RSVP invitations via SMS
- Configure budget tracking
- Explore the seating planner
""",
        "category": "getting-started",
        "tags": ["onboarding", "setup", "first-wedding", "dashboard"],
        "is_official": True,
        "featured": True,
        "order": 1,
        "estimated_read_minutes": 4,
    },
    {
        "title": "How to Collect Payments from Couples",
        "slug": "how-to-collect-payments-from-couples",
        "excerpt": "Learn how to use the Collect Payment feature to send secure payment links to your couples via Stripe — no card details needed on your end.",
        "content": """# How to Collect Payments from Couples

You can collect payments directly through the platform using **Stripe**. This means secure payment processing without ever handling card details yourself.

## How It Works

1. Open a wedding's detail page
2. Click the **Collect Payment** button in the header (next to "Seating Plan" and "Save Changes")
3. Enter the amount and a description (e.g., "Deposit for venue booking" or "Final payment for services")
4. A secure payment link is generated automatically
5. Share the link with the couple — copy to clipboard or email it directly
6. The couple clicks the link, enters their card details on a secure Stripe page, and pays

## Where to Find the Button

The **Collect Payment** button appears on every wedding detail page. Navigate to **Weddings** → click on a wedding → you'll see it in the top header bar.

## What the Couple Sees

When the couple opens the payment link:

- A branded, secure payment page
- The amount and description you entered
- A standard card payment form powered by Stripe
- Confirmation after successful payment

## Tracking Payments

- Payment status updates automatically via Stripe webhooks
- View payment history in the **Money** section
- You'll receive a notification when payment is completed

## Tips

- Always include a clear description so the couple knows what they're paying for
- You can send multiple payment links for different amounts (deposit, installments, final payment)
- Payment links don't expire immediately — the couple can pay when ready

## Security

- Your servers never see card details — Stripe handles all sensitive data
- Every payment link is unique and tied to the specific wedding
- The platform verifies you own the wedding before creating a payment link
""",
        "category": "budget-payments",
        "tags": ["payments", "stripe", "billing", "collect-payment"],
        "is_official": True,
        "featured": True,
        "order": 1,
        "estimated_read_minutes": 3,
    },
    {
        "title": "Sending RSVP Invitations via SMS",
        "slug": "sending-rsvp-invitations-via-sms",
        "excerpt": "Step-by-step guide to sending personalized RSVP invitation links to your guests via SMS using the Reminders feature.",
        "content": """# Sending RSVP Invitations via SMS

The platform uses **Twilio** to send personalized RSVP links to each guest's phone number. Each guest gets a unique link that auto-identifies them when they open it.

## Before You Start

Make sure you have:

- Added all guests with their **phone numbers**
- Configured the wedding's **privacy settings** (private weddings require verification)
- Set up the wedding landing page content (this is what guests will see)

## Sending Invitations

1. Go to **Reminders** in the sidebar
2. Select the wedding you want to send RSVPs for
3. Choose **Send RSVP Invitations**
4. Review the guest list — only guests with phone numbers will receive SMS
5. Preview the message template
6. Click **Send**

## What Guests Receive

Each guest gets an SMS like:

> "Hi [Name], you're invited to [Couple]'s wedding! View details and RSVP here: thespecialwedding.io/[slug]?rsvp_token=[unique_token]"

The unique token means:

- The guest is automatically identified when they open the link
- They don't need to search for their name
- Their RSVP is tied to their guest record

## SMS Opt-In

Guests can opt into SMS reminders during their RSVP. If opted in, they'll receive:

- Event reminders before the wedding
- Any schedule changes
- Day-of updates from you

## Tips

- Send RSVPs at least 6-8 weeks before the wedding
- Double-check phone numbers before sending — international format is best
- You can resend to individual guests who didn't receive or lost their link
""",
        "category": "rsvp-invitations",
        "tags": ["rsvp", "sms", "twilio", "invitations", "reminders"],
        "is_official": True,
        "featured": True,
        "order": 1,
        "estimated_read_minutes": 3,
    },
    {
        "title": "Managing Guest Lists and Groups",
        "slug": "managing-guest-lists-and-groups",
        "excerpt": "How to organize your guest list with groups, manage plus-ones, track RSVPs, and handle dietary requirements.",
        "content": """# Managing Guest Lists and Groups

Efficient guest management is key to a smooth wedding. Here's how to make the most of the platform's guest features.

## Adding Guests

### Individual Entry
Go to **Guest Management** → **Add Guest** and fill in:
- Name (required)
- Phone number (needed for SMS invitations)
- Email (optional, for email communications)
- Group assignment

### Bulk Import
Upload a CSV or spreadsheet with guest information. The platform will match columns automatically.

## Guest Groups

Organize guests into groups for easier management:
- **Family** — Bride's family, Groom's family
- **Friends** — Mutual friends, Bride's friends, Groom's friends
- **Colleagues** — Work friends, Business contacts
- **Wedding Party** — Bridesmaids, Groomsmen, Maid of Honor, Best Man

Groups help with:
- Sending targeted communications
- Seating arrangements
- RSVP tracking by category

## Plus-Ones

For each guest, you can:
- Allow a plus-one (the guest can add their companion during RSVP)
- Pre-assign a plus-one (add the companion's name yourself)
- Disable plus-ones (guest only)

## RSVP Tracking

The dashboard shows real-time RSVP status:
- **Pending** — Invitation sent, no response yet
- **Attending** — Guest confirmed attendance
- **Declined** — Guest cannot attend
- **Maybe** — Guest is undecided

## Dietary Requirements

Guests can specify dietary needs during RSVP:
- Vegetarian / Vegan
- Gluten-free
- Allergies
- Custom dietary notes

View a summary in Guest Management to share with your caterer.
""",
        "category": "guest-management",
        "tags": ["guests", "groups", "rsvp", "plus-ones", "dietary"],
        "is_official": True,
        "featured": False,
        "order": 1,
        "estimated_read_minutes": 4,
    },
    {
        "title": "Using the Seating Planner and Venue Floor Plan",
        "slug": "using-the-seating-planner",
        "excerpt": "Create a seating chart on top of the real event-space layout, including venue outline, fixtures, tables, guests, layout checks, and exports.",
        "content": """# Using the Seating Planner and Venue Floor Plan

The seating planner helps planners build a seating chart against the real shape of the venue instead of a blank canvas. You can map the room, upload a venue reference, add fixed venue elements, place tables, assign guests, review layout checks, and export a chart for the venue team.

## Accessing the Seating Planner

From any wedding detail page, click **Seating Plan** in the header. You can also access it from **Seating** in the sidebar.

## Guided Setup

The floor-plan toolbar includes a **Guide** button. Open it any time you want the recommended order:

1. Map the room.
2. Add a venue reference.
3. Place fixtures.
4. Place tables.
5. Seat guests.
6. Review layout checks, save, and export.

The guide uses the current chart state, so completed steps update as the planner works.

## Map the Event Space

Use the floor-plan toolbar at the top of the canvas:

- **Room** starts with a rectangular venue outline.
- **Draw** lets you adjust or draw the venue boundary.
- **Upload** adds an image reference, such as a venue-provided floor plan.
- **Lock** keeps the uploaded backdrop from moving while you work.
- **Scale** records the real-world distance for the plan, such as 100px = 10ft.

Save the floor plan after important changes so exports and future edits use the same layout.

## Add Venue Fixtures

Use **Fixture** to place non-table elements that affect the seating layout, such as:

- Dance floor
- Bar
- Stage
- Entrance
- Restrooms
- Kitchen
- Vendor path

Select a fixture to rename it, resize it, rotate it, or delete it. Fixtures appear in layout checks and exports.

## Add and Place Tables

1. Click **Add Table** to create a new table.
2. Drag tables around the canvas to position them.
3. Click a table to edit its name, shape, or capacity.
4. Use the zoom controls when working on dense layouts.

Tables can be moved independently from the floor plan and fixtures.

## Assign Guests

- Unseated guests appear in the sidebar.
- Drag the handle on one guest card onto a table to seat that guest.
- Tables show current occupancy vs capacity.
- Guests already seated show which table they are assigned to.

If the whole guest-list item moves instead of one guest, start the drag from the guest handle and drop over the target table.

## AI Suggestions

Click **AI Suggest** to get intelligent seating recommendations based on:
- Guest groups and relationships
- Dietary requirements
- Plus-one pairings
- Table capacity

Review the suggestions and accept or modify as needed.

## Review Layout Checks

The planner warns when items need attention, such as tables outside the room outline, overlapping fixtures, or objects placed outside the canvas. Review these warnings before sharing the layout with the venue or catering team.

## Exporting and Printing

- **Export** — Download the seating chart as a file
- **PDF** — Export a venue-ready chart with the floor plan, fixtures, tables, and seating details
- **Print** — Print a formatted chart for the venue

## Tips

- Build the room outline before adding tables.
- Lock the uploaded venue reference before dragging tables.
- Add large fixtures before seating guests so the layout reflects real guest flow.
- Seat families and household groups together when possible.
- Keep dietary needs visible for catering handoff.
- Use AI suggestions as a starting point, then fine-tune manually.
""",
        "category": "wedding-configuration",
        "tags": [
            "seating",
            "tables",
            "floor-plan",
            "venue-layout",
            "fixtures",
            "drag-drop",
            "ai",
            "planning",
        ],
        "is_official": True,
        "featured": False,
        "order": 2,
        "estimated_read_minutes": 5,
    },
    {
        "title": "Configuring Wedding Theme and Colors",
        "slug": "configuring-wedding-theme-and-colors",
        "excerpt": "Customize the look and feel of your couple's wedding page with theme colors, fonts, and background styles.",
        "content": """# Configuring Wedding Theme and Colors

Every wedding page is fully customizable to match the couple's style and color palette.

## Accessing Theme Settings

1. Go to **Weddings** → select a wedding
2. Click the **Theme** tab in the wedding configuration

## Color Settings

You can customize three main colors:

- **Primary Color** — Used for headings, buttons, and accents (e.g., navy blue)
- **Secondary Color** — Used for highlights and decorative elements (e.g., gold)
- **Accent Color** — Used for subtle touches and hover states (e.g., rose)

## Font Style

Choose from elegant font pairings:
- **Elegant** — Classic serif headings with clean body text
- **Modern** — Contemporary sans-serif throughout
- **Romantic** — Script-style headings with soft body text

## Background Style

- **Gradient** — Smooth color transitions
- **Solid** — Clean single-color background
- **Image** — Use the featured photo as background with parallax effect

## Dark Mode

Guests can toggle dark mode on the wedding page using the toggle in the navigation bar. The theme colors automatically adapt to look great in both light and dark modes.

## Preview

After making changes, click **Save Changes** and visit the wedding URL to see how it looks. The landing page updates immediately.

## Tips

- Ask the couple for their wedding color palette
- Test both light and dark mode
- Use the featured image that best represents the couple
- Keep contrast high for readability
""",
        "category": "wedding-configuration",
        "tags": ["theme", "colors", "fonts", "customization", "dark-mode"],
        "is_official": True,
        "featured": False,
        "order": 3,
        "estimated_read_minutes": 3,
    },
    {
        "title": "Troubleshooting Common Issues",
        "slug": "troubleshooting-common-issues",
        "excerpt": "Solutions for common problems including SMS delivery, guest access issues, payment errors, and page loading problems.",
        "content": """# Troubleshooting Common Issues

## Guests Can't Access the Wedding Page

**Problem**: Guest clicks the link but sees a verification screen or error.

**Solutions**:
- Check the wedding's **privacy settings** — if set to Private, guests must verify with their phone number or name
- Make sure the guest's phone number in the system matches what they're entering
- If using password protection, confirm the guest has the correct password
- Try resending the RSVP link — the old token may have expired

## SMS Invitations Not Delivered

**Problem**: Guests say they didn't receive the SMS invitation.

**Solutions**:
- Verify the phone number is correct and in the right format
- Check if the guest's phone can receive SMS (some landlines can't)
- The guest's carrier may have filtered it as spam — ask them to check spam/blocked messages
- Resend the invitation to that specific guest from the Reminders page

## Payment Link Not Working

**Problem**: Couple clicks the payment link but sees an error.

**Solutions**:
- Payment links are tied to Stripe — check your Stripe dashboard for the payment intent status
- The link may have been cancelled or already paid
- Generate a new payment link from the wedding detail page

## Page Loading Slowly

**Problem**: The wedding page takes too long to load.

**Solutions**:
- Large gallery images slow down loading — optimize image sizes before uploading
- The 3D background effect can be heavy on older devices — guests can use reduced motion settings
- Check your internet connection

## Need More Help?

Go to **Support** in the sidebar and create a support ticket. Include:
- What you were trying to do
- What happened instead
- The wedding slug (URL) if relevant
- Screenshots if possible

We'll get back to you as soon as possible.
""",
        "category": "troubleshooting",
        "tags": ["help", "errors", "sms", "access", "payments", "loading"],
        "is_official": True,
        "featured": False,
        "order": 1,
        "estimated_read_minutes": 4,
    },
    {
        "title": "Understanding Your Trial, Billing & Subscription",
        "slug": "understanding-your-trial-billing-and-subscription",
        "excerpt": "Everything you need to know about your free trial, choosing a plan, managing your subscription, and what happens when your trial ends.",
        "content": """# Understanding Your Trial, Billing & Subscription

Welcome to Special Wedding! This guide covers everything about your trial period, subscription plans, and billing.

---

## Your Free Trial

Every plan (Solo Founding, Solo Standard) includes a **30-day free trial**. During the trial you have full access to all features included in your plan — no limitations.

### What's included in your trial?

- Full access to all features of your selected plan
- Create and manage weddings, guests, vendors, and more
- Use AI-powered tools (credits included with your plan)
- Send invitations and manage RSVPs
- Access the seating chart, budget tracker, and timeline builder

### Trial timeline (30 days)

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

Special Wedding offers two plans, billed monthly. Every plan includes **unlimited weddings and unlimited guests** — what changes between them is AI credits and guest memories storage. All plans include a 30-day free trial.

### Solo Founding — $149/month
Founding-member rate for independent planners running their solo practice.
- Unlimited weddings
- Unlimited guests
- Vendor management
- Seating orchestration
- Automated reminders
- Calendar sync (Google, Outlook)
- 300 AI credits/month
- 25GB guest memories storage
- Email support

### Solo Standard — $199/month
The standard rate for independent planners — everything a solo practice needs to run client weddings end to end.
- Unlimited weddings
- Unlimited guests
- Everything in Solo Founding, plus:
- 750 AI credits/month
- 50GB guest memories storage
- Email support

---

## Managing Your Subscription

### How to upgrade or change your plan

1. Go to **Billing** in the left sidebar (or click the "Upgrade" button if you see a banner)
2. View your current plan and available options
3. Click **Change Plan** to switch to a different tier
4. Stripe handles the payment — prorated charges apply automatically

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
        "category": "billing-subscription",
        "tags": [
            "billing",
            "subscription",
            "trial",
            "upgrade",
            "payment",
            "plans",
            "stripe",
        ],
        "is_official": True,
        "featured": True,
        "order": 1,
        "estimated_read_minutes": 5,
    },
]


async def seed_knowledge_base(
    admin_email: str = "root@thespecialwedding.io",
    admin_name: str = "TheSpecialWedding",
):
    """
    Seed the knowledge base with official platform documentation.

    - New articles (by slug): always inserted.
    - Existing official articles with drifted content: refresh only when
      the ``KB_SEED_REFRESH_OFFICIAL`` env flag is truthy. Otherwise log
      ``[DRIFT]`` and skip.
    - Existing articles where ``is_official=False``: never touched
      (admin opted them out of seed management).
    """
    collection = mongo.db["kb_articles"]
    inserted = 0
    refreshed = 0
    drift_skipped = 0
    admin_owned_skipped = 0
    in_sync_skipped = 0
    refresh = _refresh_enabled()

    for article_data in SEED_ARTICLES:
        existing = await collection.find_one({"slug": article_data["slug"]})
        now = datetime.now(UTC)
        content = article_data.get("content", "")
        word_count = len(content.split()) if isinstance(content, str) and content else 0

        if existing:
            # Admin opted out of seed management for this article.
            if existing.get("is_official") is False:
                admin_owned_skipped += 1
                continue

            content_diff = (
                existing.get("content") != article_data["content"]
                or existing.get("title") != article_data["title"]
                or existing.get("excerpt") != article_data["excerpt"]
            )
            if not content_diff:
                in_sync_skipped += 1
                continue

            if not refresh:
                print(
                    f"[DRIFT] kb_articles[{article_data['slug']!r}] content differs "
                    f"from seed. Set {_REFRESH_FLAG}=1 on next deploy to align."
                )
                drift_skipped += 1
                continue

            # Refresh: $set strategy fields, leave admin-owned bookkeeping alone.
            await collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "title": article_data["title"],
                        "content": article_data["content"],
                        "excerpt": article_data["excerpt"],
                        "category": article_data["category"],
                        "tags": article_data["tags"],
                        "is_official": True,
                        "order": article_data.get("order", existing.get("order", 0)),
                        "estimated_read_minutes": article_data.get(
                            "estimated_read_minutes", max(1, word_count // 200)
                        ),
                        "updated_at": now,
                        "updated_by": admin_email,
                    }
                },
            )
            refreshed += 1
            print(f"[REFRESH] kb_articles[{article_data['slug']!r}] content updated")
            continue

        # Fresh insert.
        doc = {
            "title": article_data["title"],
            "slug": article_data["slug"],
            "content": article_data["content"],
            "excerpt": article_data["excerpt"],
            "category": article_data["category"],
            "tags": article_data["tags"],
            "status": "published",
            "is_official": article_data.get("is_official", True),
            "featured": article_data.get("featured", False),
            "author_email": admin_email,
            "author_name": admin_name,
            "author_id": "root_admin",
            "view_count": 0,
            "helpful_count": 0,
            "not_helpful_count": 0,
            "feedback": [],
            "order": article_data.get("order", 0),
            "estimated_read_minutes": article_data.get(
                "estimated_read_minutes", max(1, word_count // 200)
            ),
            "card_image": article_data.get("card_image", None),
            "og_image": article_data.get("og_image", None),
            "created_at": now,
            "updated_at": now,
            "created_by": admin_email,
            "updated_by": admin_email,
        }
        await collection.insert_one(doc)
        inserted += 1

    print(
        f"KB Seed complete: {inserted} inserted, {refreshed} refreshed, "
        f"{drift_skipped} drift-skipped, {in_sync_skipped} in-sync, "
        f"{admin_owned_skipped} admin-owned (is_official=False)"
    )
    return {
        "inserted": inserted,
        "refreshed": refreshed,
        "drift_skipped": drift_skipped,
        "in_sync_skipped": in_sync_skipped,
        "admin_owned_skipped": admin_owned_skipped,
    }


# Allow running directly
if __name__ == "__main__":
    asyncio.run(seed_knowledge_base())
