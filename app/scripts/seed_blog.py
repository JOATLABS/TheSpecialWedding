"""
Seed blog articles into the blog_articles MongoDB collection.
Run once on first deployment to populate the blog.

Usage:
    python -m app.scripts.seed_blog

Or call seed_blog() from app startup.
"""

import asyncio
from datetime import datetime, timezone

from bson import ObjectId

from app.core.database import mongo

SYSTEM_BLOG_AUTHOR_EMAIL = "hello@thespecialwedding.io"
PUBLIC_COPY_SEED_SLUG = "introducing-the-special-wedding"
PUBLIC_COPY_SEED_REVISION = 2
PUBLIC_COPY_SEED_REVISIONS = {
    PUBLIC_COPY_SEED_SLUG: PUBLIC_COPY_SEED_REVISION,
    "managing-200-guests": 2,
}

BLOG_ARTICLES = [
    {
        "title": "Introducing The Special Wedding: A Connected Operating System for Wedding Planners",
        "slug": "introducing-the-special-wedding",
        "excerpt": "One planner-owned workspace for the wedding record, couple experience, public details, guests, seating, vendors, and business operations.",
        "category": "platform-updates",
        "tags": [
            "wedding planner software",
            "all-in-one platform",
            "AI wedding tools",
            "launch",
        ],
        "featured": True,
        "published_date": "2026-03-19",
        "read_time": 7,
        "meta_description": "The Special Wedding is a connected operating system built specifically for professional wedding planners.",
        "content": """Wedding planners today juggle an overwhelming array of tools. Client management in HoneyBook. Seating charts in Excel. Contracts in DocuSign. Guest RSVP tracking in yet another app. Payment collection through Stripe or PayPal directly. Timeline management in Asana. Budget tracking in a spreadsheet. Vendor details and decisions disappear into email threads that spiral into 47 reply-alls.

It's inefficient. It's error-prone. And it's costing you precious hours every week that you could spend on what you actually love: making weddings special.

### We Built The Special Wedding to End Tool Fragmentation

Three months ago, we started talking to wedding planners across the country. Solo planners. Boutique agencies. Teams managing 20+ weddings simultaneously. One theme emerged immediately: **the tool stack is out of control.**

Most planners use between 8 and 12 different applications to run a single wedding. Data lives in multiple places. Information gets duplicated. Changes in one tool don't sync to another. You spend more time managing your tools than managing your weddings.

The Special Wedding is purpose-built from the ground up for wedding planners. We didn't take a generic project management tool and slap "weddings" on it. We studied the exact workflows of professional planners and built every feature around how you actually work.

### One Platform for Everything

**Client & Wedding Management:** Create weddings, invite couples, share access, collect information — all in one place. No jumping between apps.

**Guest Management at Scale:** Import guest lists, organize by groups, manage plus-ones, track dietary requirements, RSVP statuses, and send invitations via SMS or email — without needing a separate CRM.

**Seating Orchestration:** Our drag-and-drop seating planner lets you visually arrange tables and assign guests in seconds. AI-powered suggestions help you seat families together, manage dietary groups, and handle accessibility requirements — without the spreadsheet hell.

**Budget & Payment Tracking:** Track every expense, vendor quote, and payment. Send secure payment links to couples via Stripe. Track who's paid what, when, and how much. One ledger. No sync errors.

**Timeline & Reminders:** Build the wedding timeline, set automated reminders for yourself and guests, manage vendor confirmations — all on one calendar that actually works with the rest of your system.

**Planner Vendor Management:** Keep private contacts, notes, files, agreements, quote context, and payment status attached to the wedding inside the planner workspace. The public vendor directory supports discovery without giving vendors access to planner operations.

**Contracts & Documentation:** Create, send, and track contracts with e-signature. Store all planning documents in one searchable library tied to each wedding.

### AI That Actually Helps

AI in wedding tools often feels gimmicky. We built AI features that solve real problems planners told us about:

**Seating Intelligence:** Upload your guest list and our AI suggests table arrangements based on group relationships, dietary requirements, mobility needs, and social connections. You review and tweak. It's like having an assistant who never gets tired.

**Contract Templates & Customization:** Start with AI-generated contract templates customized for your region and business model, then edit naturally. No legal jargon you don't understand.

**Guest Communication:** Generate RSVP reminder messages, vendor follow-ups, day-of timeline communications — written in your voice, with AI suggestions you can reject or refine.

**Pricing Intelligence:** Wondering if your prices are competitive? Upload your service packages and we'll show you how they stack against market rates in your region, adjusted for your experience level and market positioning.

### Built for Professional Planners

The Special Wedding is designed for people who plan weddings professionally. That means:

**Multi-wedding management:** Manage dozens of weddings simultaneously without losing track of deadlines or details.

**Team collaboration:** Add staff members, assign roles, give them access to specific weddings. Built-in permission controls so junior planners can't accidentally delete the seating chart.

**Client-facing customization:** Each couple gets a beautiful, branded landing page. Guests can RSVP, view details, confirm dietary requirements, and get day-of updates — without your inbox overflowing.

**Reporting & insights:** Dashboard views show RSVP rates by day, budget status, vendor confirmations pending, timeline milestones coming up — the KPIs that actually matter to your business.

**Integrations that work:** Stripe for payments. Twilio for SMS. Zapier for custom workflows. We're not trying to replace everything, just to be the hub where your data lives and your workflows center.

### Security & Your Data

Your couples' information and wedding details are some of the most sensitive data you manage. The Special Wedding encrypts everything at rest and in transit. We use SOC 2 compliance standards, regular security audits, and automated backups. Your data belongs to you — we're just securely holding it for you.

### What You Can Verify

The public product proof shows the current planner workspace, couple portal, public wedding, guest management, seating, vendor records, budget, forms, and gallery in a fictional seeded wedding. Review those visible workflows before deciding whether the platform fits your studio.

### Get Started Today

<!-- SYNC-WITH-SEED: trial_days — update when SEED_VERSION bumps paid trial length -->
Choose a paid plan for a 30-day trial with no credit card required at signup, or start with Solo for one active wedding. Access follows the limits and features of the selected plan.

Stop managing your tools. Start managing your weddings.""",
    },
    {
        "title": "How to Price Your Wedding Planning Services in 2026",
        "slug": "how-to-price-wedding-planning-services",
        "excerpt": "Most planners underprice. Here's a framework for building tiered packages that reflect your value — plus how AI can validate your pricing against market data.",
        "category": "pricing-strategy",
        "tags": [
            "pricing",
            "wedding planner pricing",
            "service packages",
            "AI pricing",
        ],
        "featured": False,
        "published_date": "2026-03-12",
        "read_time": 8,
        "meta_description": "Learn how to price wedding planning services strategically with a proven tiered framework.",
        "content": """Let's be direct: most wedding planners underprice their services.

You're intelligent, detail-oriented, and skilled at managing complex logistics. Yet many planners charge rates that value their time at less than an entry-level software engineer. This isn't modesty. It's leaving money on the table that could fund growth, hire team members, or simply reward yourself fairly for the value you create.

Pricing wedding planning services effectively requires three things: understanding your costs and value, building a sustainable tier structure, and confidently selling that value to couples. This guide walks you through all three.

### Step 1: Calculate Your True Costs

Before you set a price, understand what it actually costs you to deliver planning services. This includes:

**Direct labor:** How many hours do you spend on a typical wedding? Include initial consultation, couple meetings, vendor research, email management, RSVP follow-ups, guest coordination, final walkthrough, and day-of support. Be honest — most planners underestimate this dramatically. A comprehensive full-service wedding plan typically requires 150-250 hours of your time.

**Software and tools:** Client management system, seating software, payment processing, SMS platform, accounting software, project management tools. Budget $150-500 per month, or roughly $50-150 per wedding if you spread it across your annual volume.

**Vendor relationships:** You maintain ongoing relationships with florists, caterers, photographers, and venues. You research new vendors. You negotiate rates. You mediate when problems arise. This relationship cost doesn't show up on an invoice but it's real. Budget 10-15% of your planning fee as the "relationship maintenance" cost.

**Insurance and legal:** Business insurance, liability coverage for planning work, contract templates, occasional legal review. Budget $100-300 per wedding.

**Marketing and sales:** Website, portfolio development, networking events, referral gifts, occasional paid advertising. Budget 10-15% of revenue for ongoing marketing.

**Administrative overhead:** Bookkeeping, tax preparation, supplies, equipment, workspace rental (if applicable).

Once you total all these, you can calculate your **break-even price** — the minimum you need to charge to not lose money. Then add your profit margin on top.

### Step 2: Research Market Rates in Your Region

Pricing varies significantly by geography, experience level, and service scope. A planner in rural Montana will charge differently than one in New York City. An experienced planner managing $500K+ weddings charges more than someone just starting out.

Market rates in 2026:

**Partial Planning (day-of coordination + light planning):** $2,000 - $7,000 nationally. Day-of coordinators in HCOL areas: $4,000-8,000. Planning work (2-4 months, limited): $3,000-6,000.

**Full Service Planning (6-12 months, all-encompassing):** $5,000 - $20,000+. Regional variation is huge. Boutique markets: $8,000-15,000. Major metros: $10,000-25,000. Destination wedding specialists: $15,000-50,000+.

**Percentage of wedding budget:** Some planners charge 10-20% of the total wedding budget instead of a flat fee. On a $100K wedding, that's $10K-20K. This model aligns your incentives with the couple's spending but can feel variable.

**Hourly rates (less common, not recommended):** $75-250/hour. This usually undervalues the strategic work you do upfront.

Research pricing by:

- Checking planner websites in your region (most publish rates now)
- Calling competitors and asking for their rate sheets (they'll likely ask back)
- Networking with planners in other cities to compare notes
- Using The Special Wedding's pricing intelligence feature, which benchmarks your rates against comparable planners in your market

### Step 3: Build Tiered Service Packages

The strongest pricing model uses tiers. Three to five clearly defined packages let couples choose the right level of service without haggling over custom pricing.

**Example Tier Structure:**

**Tier 1: Day-of Coordination** ($2,500-4,500) — You arrive 1-2 hours before the ceremony, manage the timeline, coordinate vendors, handle logistics, and troubleshoot problems during the event. Couple handles their own planning beforehand. Ideal for couples who want professional execution but don't need planning help.

**Tier 2: Partial Planning** ($5,000-8,000) — You handle vendor research, quotes, selection, and negotiation. You manage the timeline and logistics. You don't do design work or guest management. Couple provides their vision, you execute. Good for couples with clear ideas who want professional execution.

**Tier 3: Full Service** ($8,000-15,000) — Everything. You guide the couple through every decision. You research and vet vendors. You build the budget and timeline. You manage guests and seating. You handle logistics and day-of coordination. This is the premium package where you deliver maximum value.

**Tier 4: Luxury/Concierge** ($15,000-30,000+) — For high-budget weddings or particularly complex events (destination, 300+ guests, multiple events). Your role expands beyond planning to strategy and relationship management. You may attend multiple planning meetings per month, oversee design elements, and provide post-wedding services.

Each tier should have clear, specific deliverables. List them. Make the value obvious. This prevents the couple from negotiating or asking for scope creep.

### Step 4: Price According to Your Experience & Market Position

Within each tier, your exact price depends on:

**Your experience:** 0-2 years in the business? Price at the lower end of the tier. 5+ years? Upper end or higher tier. 10+ years as an established name? Premium market position.

**Your specialization:** General planner in a competitive market? Mid-tier pricing. Destination wedding specialist? Premium. Small, intimate weddings? Potentially lower absolute price but higher price per person. Ultra-high-net-worth couples? Premium luxury tier.

**Your market:** Rural/smaller cities? Lower pricing. Major metros? Higher pricing. Destination location with limited competition? Premium pricing. Saturated market with 50 other planners? Differentiate on quality or niche, then price accordingly.

**Your volume goals:** Want to do 50 weddings a year? Price lower per wedding to achieve volume. Want to do 5 weddings a year at high profit? Price higher, be selective, work with premium couples.

### Validate Your Pricing with Data

The Special Wedding includes a pricing intelligence feature that benchmarks your proposed rates against comparable planners in your region, adjusted for your experience level, market position, and service scope. This takes the guesswork out of pricing:

- See how your rates compare to planners at your experience level in your market
- Understand if you're underpricing relative to your competition
- Validate pricing for different service tiers in your region
- Get recommendations for strategic price adjustments

Use this data to feel confident in your pricing. You're not guessing anymore — you're pricing strategically based on real market data.

### Communicate Value, Not Price

Here's the shift in mindset that changes everything: **don't sell price, sell value.**

When a couple asks "Why is your full-service fee $12,000?" you don't answer by defending your hourly rate or explaining your overhead. You answer by describing the value you deliver:

"Full-service planning means you're never stressed about decisions. I guide you through every choice — venue, vendor selections, timeline, guest management, design details, day-of coordination. I handle the vendor relationships so you don't have to chase down caterers or follow up with florists. I build the budget so you never overspend. I manage your RSVP and guest list so there are no surprises. I coordinate everything on the day so you get married instead of managing a production. Couples typically report saving 200+ hours of their own time and stress, plus ending up with a better wedding because a professional is making key decisions. That value is worth $12,000."

Frame it in terms of what the couple gets, not what you cost.

### Adjust Your Pricing Over Time

You don't set pricing once and keep it forever. Review your pricing annually. If you're fully booked and getting inquiries you're turning away, raise your prices. If you're struggling to fill your calendar, investigate whether pricing is the issue or if it's marketing/positioning. As your experience grows, your pricing should grow with it.

Most planners raise rates 5-15% annually, whether tied to inflation or tied to increased experience and demand. This is normal and expected in service businesses.

### Final Thought

Pricing wedding planning services is both art and science. The science part — calculating costs, researching markets, understanding competitor rates — gives you a data-backed floor. The art part — positioning your unique value, choosing your service tier, deciding what weddings you want to do — is where you build a business you love at rates you deserve.

Stop underpricing your expertise. Price strategically. Sell the value. Build the business you deserve.""",
    },
    {
        "title": "Managing 200+ Guests Without Losing Your Mind",
        "slug": "managing-200-guests",
        "excerpt": "RSVP tracking, plus-one headaches, dietary requirements — a practical system for large-scale guest management.",
        "category": "guest-management",
        "tags": ["guest management", "RSVP tracking", "seating", "large weddings"],
        "featured": False,
        "published_date": "2026-03-05",
        "read_time": 6,
        "meta_description": "Manage large wedding guest lists of 200+ without chaos. Practical systems for RSVP tracking and guest coordination.",
        "content": """A 200-guest wedding generates exponential complexity. You're not just managing names and attendance. You're tracking RSVP status, plus-ones, dietary requirements, seating preferences, accessibility needs, vendor meal counts, table counts, chair counts, and a dozen other interconnected details that all depend on accurate guest information.

Miss something, and you get surprises on the wedding day: 8 extra guests no one planned for. A vendor meal count that's 12 short. A dietary requirement that wasn't captured. A family that's split across tables on opposite sides of the room.

This guide walks you through a system that manages large guest lists without the chaos.

### The Foundation: Digital Guest List Organization

The first mistake planners make with large guest lists is trying to manage them in spreadsheets. Email attachments get out of sync. Multiple people edit the same file and create versions. Data gets duplicated. Updates in one place don't reflect in another.

**Use a centralized system** where the planner reviews invitation, RSVP, group, meal, dietary, accessibility, and plus-one context from one Guest Management workspace. Couple-facing views remain separate from planner controls.

Import your guest list in bulk using a CSV or Google Sheet. Map your columns (name, phone, email, group, plus-one status, dietary notes), then review the mapped rows before using them for RSVP, seating, or communications.

### Step 1: Segment Guests into Groups

With 200 guests, organization is everything. Create groups that matter for your planning:

- **Family groups:** Bride's immediate family, Groom's immediate family, Extended family. This helps with seating — you want family together.
- **Social groups:** College friends, work colleagues, neighborhood friends, childhood friends. These groups often have existing social bonds and seat well together.
- **Role groups:** Wedding party members, vendors and their plus-ones, parents, kids.
- **Preference groups:** VIP guests requiring special treatment, guests with accessibility needs, guests who requested specific seating.

The benefit: you can segment communication, track RSVP rates by group, assign seating by group, and handle dietary requirements by group.

### Step 2: Manage the RSVP Chaos

With 200 guests, manual RSVP tracking is impossible. People will respond via email, text, phone call, and some won't respond at all. You need a system that:

**Centralizes RSVP collection:** Guests get a personalized RSVP link via SMS or email. They can RSVP online, confirm dietary requirements, answer preference questions, and add plus-one names. Planners review stored responses in Guest Management before using them for seating or communications.

**Tracks RSVP status by date:** Create a timeline: send invitations 8-10 weeks out, set a soft deadline 6 weeks out, send a first reminder 4 weeks out, send a hard deadline 3 weeks out, send final reminders at 2 weeks and 1 week. Track how many have responded at each stage. For large weddings, you'll need to proactively chase down responses.

**Handles late responses gracefully:** Some guests will RSVP after the deadline. Your system should handle adding them to the final count without breaking your seating chart.

**Manages no-shows and last-minute cancellations:** Capture which guests said yes but didn't show (happens more with large weddings), which guests cancelled last-minute, which guests came but didn't RSVP. This data helps you understand your response accuracy for future events and adjust final vendor counts appropriately.

**Handles plus-ones intelligently:** If you allow plus-ones, guests can add their companion's name during RSVP. This automatically creates a guest record for the plus-one with all their information tied to the primary guest. You avoid duplicate tracking.

### Step 3: Capture Dietary Requirements Accurately

Dietary requirements are critical to large weddings because they affect:

- Final meal counts to the caterer (error here = catering disaster)
- Seating charts (you may want to seat all vegetarians near each other for plating ease)
- Day-of logistics (dietary guests need to know which plate is theirs)

During RSVP, ask guests to specify dietary requirements from preset options: Omnivore, Vegetarian, Vegan, Gluten-Free, and Allergies (with text field). This gives you clean, countable data.

**Create a dietary summary report:** 145 omnivores, 32 vegetarians, 12 vegans, 8 gluten-free, 3 with nut allergies. Share this with your caterer exactly. They'll love you for the clarity. This prevents the "how many vegetarian meals again?" problem on catering day.

### Step 4: Seating Charts at Scale

Seating 200 guests across 25-30 tables is complex. Do it wrong, and you separate families, put incompatible groups together, or create obvious hierarchies. Do it right, and guests have a great time.

**Use a visual seating tool:** Don't build your seating chart in Excel. Use a drag-and-drop seating planner that shows tables and guests visually, lets you drag guests between tables, and enforces capacity limits so you don't over-seat.

**Use AI to bootstrap the chart:** Upload your guest list and let AI suggest table assignments based on groups, relationships, and dietary requirements. Review the suggestions — they'll get most of it right. Then manually adjust edge cases and specific requests.

**Create a sensible hierarchy:** Head table or sweetheart table near the front, parents' table near the head table, wedding party scattered throughout. Extended family and friends in the middle, randos you need to include in the back. This isn't rude, it's strategic seating.

**Respect specific requests:** Some guests will ask to sit with certain people or away from certain people. Honor these requests when possible. A note in the system helps you remember why specific guests are seated together.

**Plan for accessibility:** Guests using mobility aids need accessible seating near restrooms and exits. Make sure your seating chart accounts for this from the beginning, not as an afterthought.

**Export and use the seating chart:** Once finalized, export a seating chart for the venue staff, a version for your own reference, a card stock version for table cards at each seat, and a digital version for day-of reference.

### Step 5: Vendor Communication and Counts

Your vendors need accurate final counts. This is non-negotiable:

**Catering:** Final meal count (broken down by dietary requirement) needs to be accurate within 1-2 people. Off by 20? Catering disaster.

**Rental company:** Chair count, table count, linens, flatware, glassware — all tied to final guest count plus head table.

**Photographer/Videographer:** Number of groups for formal photos, special moments to capture by group.

**Florist:** Table count for centerpieces and arrangements.

Create a single document: **Final Guest Count Report** that shows total attending, breakdown by group, dietary requirements, final table assignments, vendor meal requirements. This becomes your source of truth for every vendor conversation from this point forward.

### Step 6: Day-of Execution

On the day, have your guest information accessible on your phone or tablet. You need to know:

- Who's supposed to be there (and who actually showed up)
- Which guests have dietary requirements and which meals are theirs
- Which guests are seated at which tables (for directing people to seats)
- Which guests have special notes or requests
- Which guests haven't shown up yet (for last-minute follow-up)

The Special Wedding's mobile app gives you all this information at your fingertips. Check off guests as they arrive, track dietary service, coordinate with the venue on any last-minute adjustments.

### The Reality of Large Weddings

Managing 200+ guests is harder than 75-person weddings. There's more data, more complexity, more failure points. But with a good system in place, it becomes manageable. You go from crossing your fingers and hoping everything works out to having a detailed, organized plan that executes smoothly.

The couples you serve will notice. They'll see calm professionalism, no surprises, and perfect execution. That's what they're paying you for.""",
    },
    {
        "title": "HoneyBook vs Aisle Planner: Which Is Better for Wedding Planners?",
        "slug": "honeybook-vs-aisle-planner",
        "excerpt": "A side-by-side comparison of two popular tools, including where they fall short for event-specific workflows.",
        "category": "industry-comparison",
        "tags": ["HoneyBook", "Aisle Planner", "comparison", "wedding planner tools"],
        "featured": False,
        "published_date": "2026-02-26",
        "read_time": 10,
        "meta_description": "Compare HoneyBook vs Aisle Planner for wedding planning software. Which tool is best for your business?",
        "content": """If you're shopping for wedding planning software, HoneyBook and Aisle Planner are on every shortlist. Both have name recognition, solid feature sets, and thousands of planners using them. But they approach the problem differently, and which one is better for your business depends on what you actually need.

This guide compares them honestly — the strengths of each, where they fall short, and how to think about which one fits your business model.

### What HoneyBook Does Well

**HoneyBook is a CRM-first platform.** It started in the wedding space but has evolved into a broader service business tool used by planners, photographers, florists, and other vendors. The core strength is client management and workflow automation.

**Contract and proposal management:** HoneyBook's contract workflow is solid. Create contracts, send them to clients electronically, get e-signatures, trigger follow-up actions automatically. It works well for service businesses that need to manage contracts and proposals.

**Payment collection:** Send payment links, collect deposits, set up payment plans, track who's paid. Works with Stripe and PayPal. The workflow is intuitive — create an invoice, it becomes a payment link, client pays, status updates.

**Client portal:** Clients can log in, view their wedding information, fill out questionnaires, and see documents. It's customizable and branded to your business.

**Calendar and task management:** Timeline your planning tasks, set reminders, track deadlines. Calendar view shows what's coming up.

**Integrations:** Zapier support means you can connect to other tools in your stack (Google Sheets, Slack, Salesforce, etc.).

### Where HoneyBook Falls Short

**Guest management is limited.** You can import a guest list, but the tools for organizing groups, managing RSVPs, tracking dietary requirements, and coordinating guest logistics are basic. If guest management is central to your planning (and for most planners, it is), HoneyBook leaves you short.

**Seating charts aren't really a thing.** You can theoretically track seating assignments in a custom field, but there's no visual seating planner. You're back to Excel or a separate tool.

**RSVP management requires manual work.** You can send an RSVP form to guests, but managing RSVPs at scale — tracking who responded, following up with no-responders, updating final counts — becomes tedious.

**Vendor collaboration is limited.** You can share documents with vendors through the platform, but there's no structured workflow for requests, confirmations, and feedback loops.

**The learning curve is steeper.** HoneyBook is powerful but not intuitive. It takes time to set up your workflow, and many planners end up using only a fraction of the features because the rest are too complicated or scattered.

**Pricing escalates quickly with add-ons.** The base plan covers basics, but getting advanced features (additional staff, integrations, higher transaction fees) adds up. You might end up paying more than you expect.

### What Aisle Planner Does Well

**Aisle Planner is wedding-specific.** It was built specifically for wedding planners, and you can feel that in every feature.

**Guest management is strong.** Import guest lists, organize by group, manage plus-ones, track dietary requirements, send RSVP invitations via email or SMS. Guests RSVP online, their responses populate your system automatically. This is where Aisle Planner shines.

**RSVP tracking is built-in.** See at a glance how many have RSVP'd, who hasn't responded, who's declined. Send reminders to non-responders. Track final counts automatically.

**Seating charts are visual.** Drag and drop guests into table assignments, see capacity in real time, print seating cards. It's simple and effective.

**Timeline and checklist features.** The platform includes a customizable planning checklist that guides you through the planning process with recommended tasks and due dates.

**Budget tracking.** Track vendor quotes, estimated costs, actual costs, and remaining budget in one place.

**Client portal is clean.** Couples can access wedding details, see vendor information, view the timeline, and communicate with you without information overload.

**Easy to learn and use.** Aisle Planner has a simpler interface than HoneyBook. Most planners pick it up in an afternoon.

### Where Aisle Planner Falls Short

**Contract management is basic.** You can upload and store contracts, but there's no e-signature workflow. You're still managing contracts separately (with DocuSign or similar).

**Payment collection is manual.** You can't send payment links directly from the platform. You handle payment collection separately (Stripe, PayPal, or manual invoicing).

**Vendor collaboration lacks structure.** You can share information with vendors, but there's no workflow for vendor requests, confirmations, or feedback loops. You're still coordinating via email.

**Customization is limited.** The platform is opinionated about how planning should work. If you need to customize workflows or add custom fields extensively, you hit walls quickly.

**Integrations are limited.** No Zapier support. You can't easily connect Aisle Planner to other tools in your stack.

**Mobile app is okay but not great.** It works for checking information on the go, but it's not feature-rich enough to run your business from.

### Side-by-Side Comparison Table

| **Feature** | **HoneyBook** | **Aisle Planner** |
|---|---|---|
| Client & wedding management | Strong | Good |
| Guest management | Basic | Excellent |
| RSVP tracking | Limited | Excellent |
| Seating charts | None | Good |
| Contract management | Strong | Basic |
| Payment collection | Strong | Limited |
| Budget tracking | Good | Good |
| Vendor collaboration | Limited | Limited |
| Client portal | Good | Good |
| Timeline management | Good | Good |
| Ease of use | Moderate | Easy |
| Customization | High | Low |
| Integrations | Strong (Zapier) | Limited |
| Mobile app | Good | Okay |
| Pricing | $25-60/mo base, add-ons expensive | $25-75/mo simple tiers |

### Which One Should You Choose?

**Choose HoneyBook if:** You're primarily focused on contracts and payments. You want flexibility to customize your workflow. You need strong integrations with other business tools. You work with multiple service types (photography, floral, etc.) and want one CRM for everything. You're comfortable with a steeper learning curve.

**Choose Aisle Planner if:** Guest management is central to your planning process. You need RSVP tracking and seating charts that actually work. You want something intuitive you can start using immediately. You want to keep planning workflows wedding-specific instead of generic. You want simpler pricing without surprise add-on costs.

**Neither is perfect,** which is why some planners use both (HoneyBook for contracts and payments, Aisle Planner for guest management) or supplement either platform with specialty tools like The Special Wedding, which is purpose-built for wedding planners with guest management, seating, budgets, and vendor coordination all integrated with AI assistance.

### The Future of Wedding Planning Software

Both platforms have limitations because neither was designed specifically for the complex, interconnected workflows modern wedding planning requires. The future is platforms purpose-built for wedding planners that combine the best of both approaches: strong guest management and seating tools like Aisle Planner with contract, payment, and integration capabilities like HoneyBook, all in one wedding-specific platform.

When evaluating tools, ask yourself: **What part of my workflow is most broken today?** That should guide your choice.""",
    },
    {
        "title": "Wedding Planner Contract Essentials: What to Include in 2026",
        "slug": "wedding-planner-contract-essentials",
        "excerpt": "Protect your business and your clients. The clauses every planner contract needs — with templates you can customize.",
        "category": "contracts-legal",
        "tags": ["contracts", "e-sign", "legal", "wedding planner business"],
        "featured": False,
        "published_date": "2026-02-19",
        "read_time": 7,
        "meta_description": "Essential clauses for wedding planner contracts. Protect your business legally with professional contract templates.",
        "content": """A verbal agreement with a couple or a vague email about what you'll provide is not enough. You need a written contract that clearly defines the scope of work, payment terms, cancellation policies, and liability — protecting both you and your clients.

Wedding planning contracts have gotten more important as more planners formalize their businesses. Here's what every planner contract should include, and why.

### The Core Elements

**1. Scope of Work (Services Provided)**

Be specific about what you're providing. Don't say "full-service planning." Say:

"Services include: (a) Initial consultation and planning kickoff (3 hours); (b) Vendor research, vetting, and quote collection for [categories: venue, catering, photography, florals, etc.]; (c) Venue site visits and negotiations; (d) Budget development and tracking; (e) Timeline creation and management; (f) Guest list management and RSVP coordination; (g) Seating chart development; (h) Vendor meetings and contract review; (i) Week-of logistics and day-of coordination."

Be explicit about what's NOT included: "Does not include design work, graphic design, calligraphy, or services performed by specialty vendors."

This prevents scope creep. When a couple asks if you'll redesign their save-the-date invitations, you point to the contract: "That's not in the scope of full-service planning, but I can refer you to a designer."

**2. Timeline and Important Dates**

"Planning period begins [DATE] and ends [DATE, typically 1-2 weeks after the wedding]. Retainer due [DATE]. Final payment due [DATE, typically 4 weeks before the wedding]."

Include key planning milestones: "By [DATE], venue selected. By [DATE], catering finalized. By [DATE], vendor deposits paid."

**3. Fees and Payment Terms**

Specify:

- Total planning fee
- Retainer amount (what's due to secure the date)
- Payment schedule (retainer + 2-3 installments, or retainer + final payment)
- Due dates for each payment
- Late payment policy (interest, suspension of services, etc.)
- Method of payment accepted (bank transfer, credit card, check, etc.)

Example: "Total planning fee: $10,000. Retainer: $3,000 due upon signing. Installment 1: $3,500 due [DATE]. Installment 2: $3,500 due [DATE]. Payments accepted via ACH transfer, credit card, or check."

**4. Cancellation and Refund Policy**

This protects you if the couple cancels. Be clear:

"If the Client cancels the wedding or this agreement: (a) Cancellations more than 12 weeks prior to the wedding: retainer is non-refundable, additional payments are forfeited. (b) Cancellations 12-6 weeks prior: retainer plus all payments received are non-refundable; any remaining balance is due in full. (c) Cancellations less than 6 weeks prior: 100% of the total planning fee is due regardless of prior payments."

This acknowledges that you've invested time and incurred costs. It also incentivizes couples not to cancel last-minute.

**5. Liability and Limitations**

You're not responsible for everything that happens at the wedding. Make this clear:

"The Planner is responsible for performing planning services as described in this agreement. The Planner is NOT responsible for: (a) Vendor performance or non-performance (photographer not showing up, caterer undercooking food, etc.); (b) Couple decisions that result in poor outcomes (choosing a venue with no backup power, inviting 300 guests to a 150-person space, etc.); (c) Vendor price increases after quote is accepted; (d) Acts of God (weather, natural disasters); (e) Vendor bankruptcy or business closure."

Add: "The Planner's total liability under this agreement shall not exceed the total planning fee paid."

This prevents a couple from suing you for $50,000 in damages if a vendor screws up.

**6. Dispute Resolution and Governing Law**

"This agreement is governed by the laws of [YOUR STATE]. Any disputes will be resolved through mediation, and if unresolved, through binding arbitration in [YOUR COUNTY]. Each party bears their own attorney fees."

Arbitration is better than court because it's faster and cheaper.

**7. Confidentiality**

"The Planner will maintain the confidentiality of personal information about the Client and their wedding, including guest lists, vendor contracts, dietary information, and any other sensitive information, except as required by law."

This is important if you use case studies of weddings you've planned. Get permission in writing.

**8. Independent Contractor Relationship (if applicable)**

"The Planner is an independent contractor, not an employee of the Client. The Planner is responsible for their own taxes, insurance, and business expenses."

If you hire other planners to work with you, make sure they're independent contractors (or employees, depending on your business structure).

**9. Communication and Responsiveness**

"The Planner will respond to Client communications within [2-3] business days. Regular planning meetings will be held [weekly/bi-weekly], with [number] meetings included in the planning fee. Additional meetings cost $[X] per hour."

This sets expectations about your availability and prevents couples from expecting you to be always-on.

**10. Intellectual Property**

"The Planner retains ownership of all planning documents, checklists, templates, vendor lists, and other materials created during the planning process. The Client receives a copy for their records and may use these materials for their wedding planning, but may not redistribute or resell them."

This protects your business if you've developed proprietary planning systems or vendor databases.

### Additional Clauses Worth Considering

**Team and Substitution:** "If the Planner is unable to fulfill services due to illness, emergency, or other unforeseen circumstances, a qualified substitute planner will be assigned. The Planner will make every effort to introduce this substitute planner to the Client at least 8 weeks before the wedding."

**Social Media and Photography:** "The Client grants the Planner permission to photograph elements of the wedding planning process (vendor meetings, timeline development, etc.) and may use these images for marketing and portfolio purposes, with Client name and wedding date included or withheld per Client request."

**Vendor Relationships:** "The Planner negotiates all vendor contracts on behalf of the Client. The Client authorizes the Planner to sign documents and make decisions to facilitate vendor relationships. All vendor contracts remain in the Client's name."

**Alcohol and Liability:** If you're coordinating a bar service, clarify liability: "The Planner coordinates bar service per venue and catering requirements but is not responsible for overservice, underage drinking, or guest conduct related to alcohol."

### How to Use This Information

**Option 1: Use a template.** The Special Wedding includes customizable contract templates built for wedding planners in different states. Import your business name, rate, and policies, and you have a professional, legally-sound contract.

**Option 2: Work with a lawyer.** Have an attorney in your state draft a contract template. Cost is typically $500-1,500 but worth it for a document you'll use for hundreds of clients. You can reuse the template indefinitely, just updating names and dates.

**Option 3: Use a service like LawDepot or LegalZoom.** Both offer contract templates specifically for wedding planners. Cost is $50-100 per contract template, and you can customize and reuse them.

### The Bottom Line

A good contract doesn't mean you'll never have disputes with couples. But it means when disputes happen, you have documentation of what you agreed to provide, what you actually provided, and what the couple's responsibilities are. It protects both you and them.

Update your contract every 2-3 years as your business evolves and as laws change. Ask couples to sign electronically (e-signature platforms like DocuSign or Stripe Sign make this seamless). Keep a signed copy of every contract in your files.

A contract is a sign of professionalism, not mistrust. Couples will respect you more for having clear expectations in writing.""",
    },
    {
        "title": "How AI Is Changing Wedding Planning (And What Planners Should Actually Use)",
        "slug": "ai-changing-wedding-planning",
        "excerpt": "Beyond the hype: practical AI applications for pricing, contracts, and cash flow that save planners real time.",
        "category": "ai-technology",
        "tags": ["AI", "artificial intelligence", "wedding technology", "automation"],
        "featured": False,
        "published_date": "2026-02-12",
        "read_time": 9,
        "meta_description": "How AI is transforming wedding planning. Practical AI tools that save planners time and improve business efficiency.",
        "content": """If you've been paying attention to wedding planning software over the past 18 months, you've heard a lot about AI. "AI-powered seating charts." "AI suggests vendors." "AI handles guest management." Some of it is real. Some of it is hype. This guide separates the two and helps you understand what AI tools actually save you time and improve your business.

### What AI Can Actually Do (Right Now)

**1. AI-Powered Seating Suggestions**

This is real and useful. You provide:

- Guest list with groups (family, friends, colleagues)
- Number of tables and capacity per table
- Dietary requirements
- Special requests ("seat us away from X" or "keep these people together")

AI analyzes the constraints and suggests table assignments. Its goal: keep families and friend groups together, balance dietary requirements across tables, honor special requests, and avoid obvious incompatibilities.

You review the suggestions in 10 minutes, accept most of them, and manually tweak edge cases. Result: you save 4-6 hours of seating work. This is a real time-saver.

**Example:** You have 150 guests across 15 tables. AI analysis takes 30 seconds. It groups the bride's family (24 people) across two tables, places the groom's parents with their close friends, scatters the college crew across tables with local friends to balance social energy, and puts dietary-restricted guests at tables where the kitchen can easily identify their meals. You spend 15 minutes reviewing, tweaking, and finalizing. Old process: 5 hours. New process: 30 minutes. That's legit.

**2. AI-Generated Contract Templates and Customization**

Legal AI has gotten sophisticated. You describe your business (wedding planner in Texas, full-service model, $8K average fee, 30-day cancellation policy), and AI generates a first-draft contract with all the right clauses.

It's not lawyer-perfect, but it's 80% there. You review, tweak, customize for your state's laws, then sign off. Instead of paying a lawyer $1500 to write a contract from scratch, you spend $0-50 on an AI template and 1 hour of your time to customize it.

This saves money and gets you a professional contract faster.

**3. AI-Powered Vendor Recommendations**

Some platforms now let you describe your couple's style and budget, and AI recommends vendors from its database that fit the criteria.

This works if the AI has access to a good vendor database and understands your couple's preferences. If it doesn't, recommendations are useless.

Useful version: "Show me outdoor venues in [city] with capacity for 150+ guests, within [budget]." AI filters and sorts by relevance. You review 5-10 top picks instead of 50.

Less useful version: "AI suggests vendors based on your couple's vibe." This requires AI to understand nuanced aesthetic preferences, which it struggles with. Use this as a starting point, not gospel.

**4. AI-Generated Communication Templates**

Writing the same emails over and over (RSVP reminder, vendor follow-up, dietary confirmation) is soul-crushing. AI can generate templates based on what you ask:

- "Generate an RSVP reminder email to guests who haven't responded in 2 weeks"
- "Generate a first contact email to caterers with our requirements"
- "Generate a confirmation email to the couple after their first meeting"

AI outputs a template in your voice (or a professional tone if you don't have a voice yet). You tweak it, add personal details, send it. Saves 20 minutes per email type. With a typical planner sending 100+ emails per planning cycle, this adds up.

**5. AI-Powered Pricing Analysis**

This is newer and increasingly useful. You input:

- Your service scope (what you're offering)
- Your experience level and location
- Your target couple budget and wedding size

AI analyzes comparable planner rates in your market and suggests pricing that's competitive yet doesn't underprice you. It also tells you if you're pricing higher or lower than peers, and why that might be justified (experience, specialization, market position).

This is valuable for solo planners who don't have pricing mentors or for planners entering a new market. Instead of guessing, you have data-backed pricing.

### What AI Struggles With (Or Gets Wrong)

**1. Understanding relationship dynamics**

AI can see that two guests are both in "family group," but it can't tell you that those two family members are estranged and should sit at opposite ends of the room. AI doesn't understand family drama, feuds, or sensitive dynamics. This requires human judgment.

Use AI for the baseline seating chart, but involve the couple to handle relationship nuances.

**2. Vendor quality assessment**

AI can tell you a photographer has 500 reviews and a 4.8 rating. It cannot tell you that the photographer is a nightmare to work with, doesn't respect timelines, or delivers overedited images. Quality assessment requires talking to other planners, seeing portfolios, and having conversations.

Use AI for filtering and initial research. Use human judgment for final selection.

**3. Creative and design decisions**

AI can generate color palette suggestions based on wedding aesthetics. It cannot tell you that this particular couple's vision is "modern but romantic" and what that actually means in florals, linens, and décor. Creative direction still requires human understanding.

**4. Managing unexpected problems**

Your caterer cancels two weeks before the wedding. Your venue floods. Your photographer gets injured. AI can't handle these crises. You need experience, relationships, and problem-solving skills that only humans have.

AI is great at routine, structured decisions. It's terrible at edge cases and crisis management.

### The Real ROI of AI for Wedding Planners

Be honest about where AI saves you time and money:

**High ROI:** Seating charts (4-6 hours saved per wedding), email templates (2-3 hours saved per wedding), contract generation (6-8 hours saved once for future reuse), pricing analysis (1-2 hours saved per pricing decision).

**Medium ROI:** Vendor filtering and research (saves maybe 1-2 hours if the database is good), communication scheduling (saves 30 min if integrated well).

**Low/Negative ROI:** "AI wedding design" (usually needs human redesign anyway), "AI guest coordination" (lacks context), "AI vendor management" (still need human follow-up).

If you manage 10 weddings a year and AI saves 5-8 hours per wedding through seating, emails, and contracts, that's 50-80 hours per year. At your hourly rate (let's say $100/hour for planning time), that's $5,000-8,000 in reclaimed time. If AI tooling costs you $100-300/month, the ROI is strong.

### How to Evaluate AI Tools

**1. Does it solve a specific problem you actually have?** Not "is this cool" but "does this save me hours every week?"

**2. Does it work with your workflow or does it force you to change your workflow?** The best tools integrate with how you already work.

**3. Can you override AI suggestions?** You want AI to bootstrap the work (seating chart, contract template), then you take over and make final decisions. Avoid tools that try to automate too much.

**4. Is the data quality good?** Vendor database out of date? AI pricing analysis based on old data? Worthless.

**5. Do you understand how the AI actually works?** If the tool can't explain why it made a suggestion, be skeptical.

### The Future: AI You Should Be Excited About

Coming soon (or already emerging):

**Voice-based task management:** "Hey, add 15 guests from Sarah's +1 list and reassign seating." AI updates everything and alerts you to conflicts.

**Real-time timeline optimization:** Wedding day timeline hitting bottlenecks? AI identifies problems and suggests alternatives before the day-of chaos.

**Automated vendor communication loops:** Send a request to vendors, AI tracks responses, sends follow-ups to non-responders, consolidates answers. Reduces email hell.

**Cash flow forecasting:** Based on your contract terms, payment schedule, and vendor payment obligations, AI predicts cash flow and alerts you to gaps before they become problems.

### The Bottom Line

AI is useful for wedding planners right now, but it's not magical. The tools that work are the ones that automate specific, repetitive, structured tasks (seating suggestions, email templates, contract generation). The tools that overpromise and underdeliver are the ones trying to automate nuanced, relationship-heavy, creative work.

Use AI to reclaim 5-10 hours per wedding from routine work. Invest that time in what you're actually good at: understanding couples, managing vendor relationships, and orchestrating perfect days.

That's where AI and humans work best together.""",
    },
    {
        "title": "Seating Chart Strategy: Beyond Drag-and-Drop",
        "slug": "seating-chart-strategy",
        "excerpt": "Family dynamics, vendor placement, accessibility — the art and science of orchestrating 200 seats across 5 sections.",
        "category": "event-logistics",
        "tags": ["seating charts", "event logistics", "guest management", "day-of"],
        "featured": False,
        "published_date": "2026-02-05",
        "read_time": 5,
        "meta_description": "Master seating chart strategy for large weddings. Orchestrate 200+ guests with family dynamics, accessibility, and logistics in mind.",
        "content": """Seating charts look simple on the surface: drag guests onto tables, make sure tables are full, print and done. But the real skill in seating is orchestrating a social environment where 200 people have a great time, family dynamics don't explode, and the logistics actually work.

This is the art and science of seating charts.

### The Goals of Good Seating

**1. Keep people comfortable and happy.** Guests should feel they have people to talk to. Families should sit together. Friend groups shouldn't be isolated from each other.

**2. Manage family dynamics.** Some families get along great. Others have tensions. You need to understand these dynamics and seat strategically to prevent fireworks.

**3. Balance tables socially and demographically.** Don't seat all elderly guests at one table and all young people at another. Mix ages, backgrounds, and social groups for natural conversation and mingling.

**4. Handle logistics.** Dietary guests at the same table for easier catering. Children near parents. Guests with mobility issues near exits and restrooms.

**5. Create a hierarchy that makes sense.** Head table or sweetheart table for the couple and wedding party. Parents' table visible and honored. VIPs positioned well. Extended family scattered throughout.

### The Seven-Step Seating Strategy

**Step 1: Understand family units and groups.** Don't seat individual guests. Seat groups. Who goes to the wedding together? The bride's parents, the groom's parents, their kids, and invited guests are all distinct units. Keep these together as much as possible.

**Step 2: Identify and handle difficult dynamics.** Have a conversation with the couple: Are there family members who shouldn't sit together? Exes who might show up? Friends who are going through drama? Note these constraints.

**Step 3: Create the head table.** Typically the couple sits center stage with parents on either side and the wedding party flanking. Some couples prefer a small "sweetheart table" with just the two of them. Both work — just be intentional.

**Step 4: Create parents' tables.** Seat the parents near the head table with their closest friends and family. This honors them and keeps them happy.

**Step 5: Balance the main tables.** This is where you place the bulk of guests. Seat friend groups together, but split them across tables if they're too large. Mix ages and backgrounds. Seat people who know each other with people they don't, so there's natural conversation starter ("we both know Sarah").

**Step 6: Handle logistics constraints.** Dietary-restricted guests cluster for plating. Elderly guests on the ground floor or nearest accessible parking. Guests with mobility issues at accessible tables. Kids' table near parents but visible. Wedding emergencies (groomsman with an allergy, etc.) noted clearly.

**Step 7: Review and stress-test.** Before finalizing, walk through your seating chart with fresh eyes. Are there obvious incompatibilities? Are family groups split awkwardly? Do any tables look lopsided socially? Adjust.

### Seating Dynamics to Manage

**The "Single Guest" Problem:** A single guest invited without a plus-one might feel isolated. Seat them near people they know, or actively seat them with other singles or welcoming groups who can make them feel included.

**The "Work Friends vs. Real Friends" Tension:** If a couple invites work colleagues, don't scatter them all around tables. They'll feel out of place. Cluster them with one or two couples the bride/groom knows socially, so they have work friends to talk to plus a bridge to other guests.

**The "Out-of-Town Guests" Cluster:** Distant relatives or friends who traveled far will want to stick together initially. Seat them together, but with one local person per table to help them mingle and feel oriented.

**The "Extended Family Sprawl":** Large families can be tricky. The nuclear family sits together, but aunts, uncles, and cousins get scattered. This is fine, but make sure each sub-family group (the aunt's immediate family) sits together, and position the tables so family can still see and wave to each other.

**The "Age Gap" Problem:** A table of all elderly guests might be quiet. A table of all young people might be chaotic. Mix ages intentionally. An older couple, a younger couple, and a middle-aged family creates better conversation.

### Practical Seating Rules

**Table capacity:** 8 people per table is the sweet spot for conversation (full table, everyone can talk). 10 is doable but tight. More than 10 and you lose intimacy.

**Odd numbers are fine:** Don't force a table to be exactly 8. A table of 7 or 9 is perfectly acceptable and more realistic. The couple's total RSVP count rarely divides evenly by 8.

**Don't put randos alone:** Every table should have at least one person who knows someone else at that table. This is the conversation anchor.

**Avoid "nosebleed seats":** Don't seat important people (parents, best friends, VIPs) at tables in the back corner of the reception. Position good tables throughout the room with good sightlines to the couple.

**Use the seating chart as a tool, not doctrine:** If guests arrive and want to sit somewhere different, let them (within reason). The seating chart is a guide to optimize the experience, not a rigid assignment.

### Using Technology for Seating

Beyond paper and pen, use tools that let you:

- Visualize tables and capacity in real time
- Drag guests between tables and see impacts immediately
- Export multiple views (cards for table placement, lists for catering, diagram for venue staff)
- Get AI suggestions as a starting point, then manually optimize
- Track special requests and dietary requirements in context
- Print seating cards for place settings or a diagram showing guests where they're seated

The Special Wedding's seating planner includes all of this. Import your guest list with groups and dietary info, get AI suggestions, tweak manually, and export in multiple formats for your team and vendors.

### Final Thought

A perfect seating chart prevents drunk relatives from yelling at each other, keeps people feeling welcomed and included, and makes logistics run smoothly. It's one of the highest-leverage planning tasks you do. Spend the time to get it right, use tools that make it easy to visualize and adjust, and think beyond just "fill the tables."

The couple will notice. Their guests will have a better time. That's what it's all about.""",
    },
]


async def seed_blog():
    """
    Seed the blog_articles collection with blog posts.

    Existing collections receive only the revision-gated canonical public-copy
    refresh. Operator-authored articles and already-refreshed seed records are
    never overwritten.
    """
    collection = mongo.db["blog_articles"]

    existing_count = await collection.count_documents({})
    if existing_count > 0:
        updated = 0
        for slug, seed_revision in PUBLIC_COPY_SEED_REVISIONS.items():
            canonical_article = next(
                article for article in BLOG_ARTICLES if article["slug"] == slug
            )
            refresh_result = await collection.update_one(
                {
                    "slug": slug,
                    "created_by": SYSTEM_BLOG_AUTHOR_EMAIL,
                    "$or": [
                        {"seed_revision": {"$exists": False}},
                        {"seed_revision": {"$lt": seed_revision}},
                    ],
                    "$expr": {"$eq": ["$created_at", "$updated_at"]},
                },
                {
                    "$set": {
                        "title": canonical_article["title"],
                        "excerpt": canonical_article["excerpt"],
                        "content": canonical_article["content"],
                        "category": canonical_article["category"],
                        "tags": canonical_article["tags"],
                        "featured": canonical_article.get("featured", False),
                        "meta_description": canonical_article.get(
                            "meta_description", canonical_article["excerpt"]
                        ),
                        "estimated_read_minutes": canonical_article.get("read_time", 5),
                        "seed_revision": seed_revision,
                        # Keep the editorial timestamp untouched. The
                        # created_at == updated_at invariant is the durable
                        # signal that no operator has edited this seeded copy,
                        # so later canonical revisions can still advance.
                        "seed_refreshed_at": datetime.now(timezone.utc),
                    }
                },
            )
            updated += refresh_result.modified_count
        return {
            "inserted": 0,
            "updated": updated,
            "message": "public copy refreshed" if updated else "already seeded",
        }

    inserted = 0
    now = datetime.now(timezone.utc)

    for article_data in BLOG_ARTICLES:
        # Parse published date
        pub_date_str = article_data.get("published_date", "2026-02-05")
        pub_date = datetime.fromisoformat(f"{pub_date_str}T00:00:00+00:00")

        doc = {
            "_id": ObjectId(),
            "title": article_data["title"],
            "slug": article_data["slug"],
            "excerpt": article_data["excerpt"],
            "content": article_data["content"],
            "category": article_data["category"],
            "tags": article_data["tags"],
            "featured": article_data.get("featured", False),
            "author_name": "The Special Wedding",
            "author_email": SYSTEM_BLOG_AUTHOR_EMAIL,
            "created_by": SYSTEM_BLOG_AUTHOR_EMAIL,
            "meta_title": None,
            "meta_description": article_data.get(
                "meta_description", article_data["excerpt"]
            ),
            "og_image": None,
            "card_image": None,
            "published_at": pub_date,
            "estimated_read_minutes": article_data.get("read_time", 5),
            "status": "published",
            "view_count": 0,
            "created_at": now,
            "updated_at": now,
            "seed_revision": PUBLIC_COPY_SEED_REVISIONS.get(article_data["slug"], 1),
        }

        await collection.insert_one(doc)
        inserted += 1

    return {"inserted": inserted, "updated": 0}


# Allow running directly
if __name__ == "__main__":
    asyncio.run(seed_blog())
