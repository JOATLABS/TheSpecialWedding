import React from 'react';

/* ═══════════════════════════════════════════════════════════
   Types & Interfaces
   ═══════════════════════════════════════════════════════════ */

export interface BlogPost {
  title: string;
  excerpt: string;
  category: string;
  date: string;
  readTime: number;
  ogDescription: string;
  content: React.ReactNode;
  /**
   * Optional list of marketing template ids (matching `MARKETING_TEMPLATES`
   * in `app/resources/templates/manifest.ts`) that are surfaced as a
   * "Related free templates" card below this post's body. 1–3 ids max.
   */
  relatedTemplates?: readonly string[];
}

export const blogPosts = {
  'introducing-the-special-wedding': {
    title: 'Introducing The Special Wedding: A Connected Operating System for Wedding Planners',
    excerpt: 'One planner-owned workspace for the wedding record, couple experience, public details, guests, seating, vendors, and business operations.',
    category: 'Industry',
    date: '2026-03-19',
    readTime: 6,
    ogDescription: 'The Special Wedding is a connected operating system built specifically for professional wedding planners.',
    relatedTemplates: ['couple_intake', 'vendor_onboarding', 'order_of_events'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          Wedding planners do not need another generic project board with wedding labels. They need one reliable place to understand the wedding, guide the couple, prepare guest-facing details, and run the private operational work that clients should never have to see.
        </p>

        <p>
          The Special Wedding is that planner-owned workspace. It brings the wedding record, event days, guest context, seating plan, budget, forms, vendor records, gallery, couple timeline, and public wedding details into one wedding-specific operating model.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">One plan, presented for each audience</h3>

        <p>
          <strong>Planner workspace:</strong> Morning View compares active weddings using RSVP movement, recent activity, pending forms, and setup progress. Each wedding then opens into its own event details, guests, seating, budget, files, vendor records, and internal controls.
        </p>

        <p>
          <strong>Couple portal:</strong> Couples receive a guided view of their wedding overview, shared timeline, payment context, and assigned forms. Planner-only controls and internal operations stay private.
        </p>

        <p>
          <strong>Public wedding:</strong> Guests see the approved story, event details, venue information, registry, FAQs, and gallery without seeing the planner workspace behind them.
        </p>

        <p>
          These are audience-specific views of one wedding plan—not shared access to the same controls. The planner remains the owner of the operational record and decides what belongs in the couple and public experiences.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Built for the work planners actually do</h3>

        <p>
          Guest Management keeps invitation, RSVP, group, meal, accessibility, and plus-one context together. Seating adds the room outline, fixtures, tables, assignments, and layout checks. Event days capture the venue, time, attire, and order of events. Forms, gallery management, budget, payments, and the planner inbox stay attached to the wedding they belong to.
        </p>

        <p>
          Vendor work is planner-owned too. The public directory supports discovery, while private Vendor Management keeps contacts, notes, files, agreements, quote context, and payment status inside the planner workspace. Vendors are not invited into the planner workspace.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Plans for independent planners and teams</h3>

        <p>
          Solo lets a planner try the platform with one active wedding. Boutique adds unlimited weddings and guests plus the paid planning toolkit. Signature adds five staff seats, higher AI and storage limits, a planner storefront, and an optional custom domain. Enterprise expands the team, AI, storage, and launch-support limits.
        </p>

        <p>
          The product is a planner management platform. Couples participate through planner-invited experiences, guests use the public wedding and RSVP flows, and the public vendor directory remains separate from the private planner workspace.
        </p>

        <p>
          Start with the planner workspace, build one fictional or real wedding record, and decide from the visible workflow whether it fits the way your studio plans.
        </p>
      </div>
    ),
  },
  'how-to-price-wedding-planning-services': {
    title: 'How to Price Your Wedding Planning Services in 2026',
    excerpt: "Most planners underprice. Here's a framework for building tiered packages that reflect your value — plus how AI can validate your pricing against market data.",
    category: 'Business',
    date: '2026-03-12',
    readTime: 8,
    ogDescription: 'A practical pricing framework for wedding planners. Learn tiered packaging, value-based pricing, and how to validate rates against market data.',
    relatedTemplates: ['couple_intake', 'vendor_performance_review'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          Most planners underprice their services by 30-50%. Not because they don't know their value. But because pricing is hard, and they haven't built a framework to defend their rates.
        </p>

        <p>
          The typical story: You started at $X per wedding. Over time, you added services, built a reputation, and now you're doing $5X worth of work for $X pay. You know you should raise rates, but you're afraid clients will bail. So you don't.
        </p>

        <p>
          This guide gives you a framework to build tiered packages, price them confidently, and validate your rates against market data.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Understand the three pricing models</h3>

        <p>
          <strong>Flat fee (per wedding):</strong> "$5,000 full-service planning." Simple, predictable, and what most planners charge. It works if you can define "full-service" clearly and scope-manage aggressively.
        </p>

        <p>
          <strong>Percentage of budget:</strong> "5% of your total wedding budget." Works if you're advising on vendor spend and have control over budget. Scales with your clients' spending but can incentivize unnecessary expense.
        </p>

        <p>
          <strong>Hourly:</strong> "$150/hour for consultation or specialized work." Works for à la carte services or overflow from fixed-fee clients. Difficult to upsell and doesn't scale well.
        </p>

        <p>
          The best approach: tiered flat fees with add-ons. You offer 3 packages (Coordination, Design, Full Planning) at different price points, each clearly scoped. Clients pick the package. You add à la carte services as needed.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Build three packages</h3>

        <p>
          <strong>Package 1: Month-of Coordination ($1,500–$3,000)</strong>
        </p>

        <p>
          Clients bring you a mostly-planned wedding 4 weeks out. You manage final vendor confirmations, create the day-of timeline, coordinate with vendors, and execute the event.
        </p>

        <p>
          What's NOT included: venue or vendor selection, design decisions, guest management, budget building, contract negotiation.
        </p>

        <p>
          Why this price: You're delivering a specific, time-bound service. 3-4 weeks of work, defined scope. Lower price attracts DIY couples who got 80% of the way but need help at the finish line.
        </p>

        <p>
          <strong>Package 2: Design & Partial Planning ($3,500–$7,000)</strong>
        </p>

        <p>
          Clients bring you a venue and a budget. You handle design direction, vendor selection and negotiation, guest management setup, and day-of coordination. You're involved from month 6–8 out through execution.
        </p>

        <p>
          What's NOT included: Engagement or major strategy (like budget restructuring). You're executing a vision, not building from zero.
        </p>

        <p>
          Why this price: You're doing 6-7 months of work with high leverage (you pick vendors, negotiate, manage the relationship). Scope is clear: design + logistics, not strategy.
        </p>

        <p>
          <strong>Package 3: Full Planning & Strategy ($7,500–$15,000+)</strong>
        </p>

        <p>
          Clients come to you at engagement. You own everything: vision development, budget strategy, vendor selection, guest management, timeline design, day-of execution. You're their coach, strategist, and executor for 12–18 months.
        </p>

        <p>
          Why this price: You're delivering 15+ months of work, strategic guidance, and full execution. High leverage, high margin.
        </p>

        <p>
          <strong>How to think about the tiers:</strong> Each tier is a clear slice of the wedding journey. Coordination is logistics only. Design/Partial is vendor selection + logistics. Full Planning is strategy + selection + logistics. Couples self-select based on how much help they need.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Price for your market and positioning</h3>

        <p>
          The ranges above are national averages, but your local market matters. A planner in rural Iowa isn't competing with Manhattan planners.
        </p>

        <p>
          <strong>Research your market:</strong>
        </p>

        <p>
          Look at planners in your city (similar market, similar cost of living). Check their websites, Instagram, and past weddings (WeddingWire, The Knot). What are people paying? $2,000? $8,000? $15,000?
        </p>

        <p>
          Then position yourself relative to competitors. Are you charging less because you're newer? More because you have a stronger reputation? In-line because you're at market value?
        </p>

        <p>
          <strong>Think about positioning:</strong> New planner (1-3 years)? Start at the lower end of the range. Established (5+ years with strong referrals)? Upper middle to upper range. Luxury/high-end market? Charge 2x the base range.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Set prices that attract the right clients</h3>

        <p>
          Your price tells a story. A $2,000 flat fee attracts budget-conscious couples. A $10,000 flat fee attracts clients who value expertise and can afford premium service.
        </p>

        <p>
          There's nothing wrong with either positioning. But be intentional. If you want fewer clients who pay more, charge more. If you want higher volume with acceptable margins, charge moderate rates and take more weddings per year.
        </p>

        <p>
          <strong>The rule:</strong> Your price should be high enough that you can afford to spend the time your clients need, while low enough that you're competitive in your market.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Add revenue streams</h3>

        <p>
          Once you've priced your base packages, add à la carte services:
        </p>

        <p>
          <strong>Rush fee:</strong> +$500–$1,000 if they book with less than 3 months' notice.
        </p>

        <p>
          <strong>Seating chart design:</strong> +$300–$500 as a standalone service.
        </p>

        <p>
          <strong>Guest list management:</strong> +$200–$400 if you're just managing RSVPs and dietary needs.
        </p>

        <p>
          <strong>Day-of coordination only:</strong> $1,500–$2,500 if a couple planned independently and just needs execution.
        </p>

        <p>
          <strong>Post-wedding consultation:</strong> Hourly rate ($125–$200/hour) for couples getting married elsewhere who want to hire you for planning advice.
        </p>

        <p>
          <strong>Team member rate:</strong> If you hire an assistant, bill their time at $75–$125/hour to clients (you pay them $30–$50/hour).
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Validate your pricing</h3>

        <p>
          Once you've set prices, validate them. Are you getting consistent inquiries? Are clients saying "yes" or "that's too much"?
        </p>

        <p>
          If you're getting 5+ inquiries per month and closing 60%+ of leads, your price is probably too low. Raise it 10–15%.
        </p>

        <p>
          If you're getting 2 inquiries per month and closing 30% or less, your price might be too high relative to your positioning. Audit your marketing first (are you attracting the right clients?), then adjust if needed.
        </p>

        <p>
          <strong>Use AI to validate:</strong> Tools like The Special Wedding can analyze your local market, your services, and your costs to suggest competitive pricing. You still make the final call, but you're making it informed, not guessing.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The psychology of price</h3>

        <p>
          Couples expecting to pay $3,000 are shopping with a different mindset than couples expecting $10,000. Higher price attracts couples who:
        </p>

        <p>
          - Value expertise over cost savings.
          - Have bigger budgets and aren't price-sensitive.
          - Want less admin work (they hire you to own it, not to explain it).
          - Expect better communication, faster turnarounds, and more flexibility.
        </p>

        <p>
          Charge premium prices if you can deliver premium service: faster response times, more flexibility, higher-end vendor relationships, strategic guidance.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Communicate your value</h3>

        <p>
          Your price doesn't justify itself. You do. On your website, in consultations, and in your proposals, explain what's included and why it costs what it costs:
        </p>

        <p>
          "Full Planning includes 15+ months of strategy, vendor management, and day-of execution. Most couples save 15-20 hours on vendor research, comparison, and negotiation alone. The vendor savings typically exceed our fee."
        </p>

        <p>
          "Month-of Coordination is $2,500. That's for 3–4 weeks of timeline creation, vendor confirmation, day-of staffing, and real-time problem-solving. Your time is worth more than that."
        </p>

        <p>
          When couples understand value, price becomes less of an objection.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Raise prices every 1-2 years</h3>

        <p>
          Your costs go up (time, software, team). Your experience grows. Raise prices every 1–2 years by 10–15%.
        </p>

        <p>
          Do this in a way that doesn't churn existing clients. New inquiries pay the new rate. Existing clients you're committed to finishing at the old rate. Next year, everyone pays the new rate.
        </p>

        <p>
          <strong>One more thing:</strong> If you're managing multiple weddings per year, your revenue model works best if you price high enough to take fewer clients. A $10,000 flat fee for 20 weddings per year = $200K revenue. A $3,000 flat fee means you'd need 67 weddings per year to match that (unsustainable). Price for the volume you want to work.
        </p>
      </div>
    ),
  },
  'managing-200-guests': {
    title: 'Managing 200+ Guests Without Losing Your Mind',
    excerpt: 'RSVP tracking, plus-one headaches, dietary requirements — a practical system for large-scale guest management.',
    category: 'Workflow',
    date: '2026-03-05',
    readTime: 6,
    ogDescription: 'Systems and strategies for managing 200+ wedding guests. RSVP tracking, plus-ones, dietary needs, and table assignments.',
    relatedTemplates: ['guest_dietary_access', 'couple_intake', 'bridal_party_logistics'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          A 200-guest wedding is a different animal than a 75-guest backyard event. The complexity doesn't scale linearly. One new dietary requirement at 75 guests is a note. One new dietary requirement at 200 guests could reshape your catering order.
        </p>

        <p>
          This guide is for planners managing large guest lists. We'll walk through RSVP systems, plus-one management, dietary tracking, and how to stay sane while coordinating logistics for 200+ people.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Start with a real source of truth</h3>

        <p>
          Your first mistake: using multiple tools. Couples text RSVPs to their planner. They send emails. They fill out online forms. You track in Google Sheets. Vendors get a PDF export. Somewhere, the data diverges, and you're sending the caterer 45 entrees when you actually have 47 RSVPs.
        </p>

        <p>
          You need one source of truth. Everything funnels there. Guest RSVPs, dietary flags, plus-ones, table assignments, special accommodations.
        </p>

        <p>
          That source should be:
        </p>

        <p>
          - <strong>Centralized:</strong> One tool, not a spreadsheet + email + text messages.
          - <strong>Real-time:</strong> When someone RSVP's online, the count updates immediately.
          - <strong>Exportable:</strong> You can pull reports for the caterer, photographer, venue, and day-of staff.
          - <strong>Accessible to couples:</strong> Ideally, couples can see their own entry and make corrections (dietary changes, plus-one name).
        </p>

        <p>
          If you're using Google Sheets, you're managing 200+ rows of data with no real-time sync, no automated reminders, and no way for couples to self-serve. You're manually updating three different CSV files for vendors. Upgrade.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Build your guest list correctly</h3>

        <p>
          <strong>Structure from day one:</strong>
        </p>

        <p>
          - First name, Last name (separate fields)
          - Email address
          - Phone number
          - Group (Family, Friend, Work, etc.)
          - Plus-one allowed? (Yes/No)
          - Dietary restrictions (field)
          - Accessibility needs (field)
          - RSVP status (Pending, Yes, No, Maybe)
          - Date RSVP'd
          - Which meal option (if offering choices)
        </p>

        <p>
          Don't improvise fields as you go. This creates inconsistent data. Define your fields upfront. When you export a report for the caterer 2 weeks before the wedding, you need clean data, not "hopefully everyone put dietary stuff in the comments."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Launch RSVP tracking 3-4 months out</h3>

        <p>
          Give couples 6 weeks to RSVP. Send your first reminder at 4 weeks out (if RSVP closes in 2 weeks). Send a second at 2 weeks out. A third at 1 week out.
        </p>

        <p>
          <strong>What works:</strong> Send a friendly email reminder with a direct link to the RSVP form (not a link to your entire website). Use their name ("Hi Sarah and Michael"). Make it easy—one click should get them there.
        </p>

        <p>
          <strong>What doesn't:</strong> A form that requires them to log in. Couples are busy and will abandon it.
        </p>

        <p>
          <strong>Final reminder:</strong> 2 days before RSVP closes, send a final "closes tomorrow" email. You'll be surprised how many people RSVP in the last 48 hours.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Handle plus-ones strategically</h3>

        <p>
          200-guest weddings often have plus-ones. And plus-ones are a nightmare:
        </p>

        <p>
          - The couple's friend RSVPs "yes for 2" but doesn't tell you the plus-one's name until 2 weeks before the wedding.
          - The plus-one dietary info comes in 10 days out and changes your catering count.
          - The seating chart was built assuming a plus-one would be John, but it's actually Jane. Different dynamic.
        </p>

        <p>
          <strong>Set boundaries early:</strong> "If you have a plus-one, submit their name by [date 3 weeks before]. After that, we can't guarantee their dietary preferences or exact seating."
        </p>

        <p>
          <strong>Track plus-ones as separate rows:</strong> In your guest list, don't put "Sarah + Guest" on one row. Create two rows: "Sarah" and "Sarah's Plus-One". Track names, dietary info, and RSVP separately. This makes seating and vendor reports cleaner.
        </p>

        <p>
          <strong>Get plus-one names early:</strong> Send a follow-up email to couples who RSVP'd "yes for 2" with a blank field. "We have you down for plus one. What's their name and any dietary restrictions?"
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Dietary requirements at scale</h3>

        <p>
          At 200 guests, you might have 40-50 dietary restrictions. Some are allergies (life-or-death). Some are preferences (vegetarian, pescatarian, kosher). Some are medical (nut-free). You need to categorize and track.
        </p>

        <p>
          <strong>Create a standard field with options:</strong>
        </p>

        <p>
          - No restrictions
          - Vegetarian
          - Vegan
          - Gluten-free
          - Nut allergy
          - Shellfish allergy
          - Dairy-free
          - Kosher
          - Halal
          - Other (please specify)
        </p>

        <p>
          This gives the caterer a standardized list instead of "I don't eat red meat but I'll eat fish except shellfish unless it's lobster."
        </p>

        <p>
          <strong>Allergies vs preferences:</strong> Create a separate "Allergy?" field (Yes/No). When you export reports for the caterer, flag all allergies in a summary. Allergies change how they cook (cross-contamination). Preferences don't.
        </p>

        <p>
          <strong>Export for the caterer two weeks out:</strong> Pull a report that says "48 guests, vegetarian" and "3 guests, shellfish allergy." Not a list of all 200 names. They just need the summary and a detailed list of allergy guests. Names help (so they know John has a nut allergy), but aggregate counts are more useful for ordering.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Track accessibility needs</h3>

        <p>
          You're planning for 200 guests. Some are using wheelchairs. Some need ASL interpreters. Some have mobility issues and can't take stairs. Some have hearing loss.
        </p>

        <p>
          Ask upfront: "Do you have any accessibility needs we should plan for?" Let couples self-report. Then coordinate with your venue and vendors early.
        </p>

        <p>
          <strong>Before booking:</strong> Confirm your venue can accommodate wheelchairs, has accessible restrooms, and can provide a reserved parking space. Confirm your caterer can modify food textures for guests with swallowing difficulties. Confirm your photographer knows about mobility aids and how to include them thoughtfully in photos.
        </p>

        <p>
          <strong>During the wedding:</strong> Have a staff member assigned to accessibility coordination. They know who needs what and check in proactively.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Keep contingency plans</h3>

        <p>
          At 200 guests, capacity is tight. You're planning for 200 with minimal buffer.
        </p>

        <p>
          <strong>Have a plan if:</strong>
        </p>

        <p>
          - 15 more people RSVP yes in the final week (overflow seating? Standing room only in cocktail hour? Caterer can add 10% without reordering?)
          - 15 people cancel in the final week (can you reduce catering, or is it a sunk cost?)
          - A vendor cancels 1 week out (do you have a backup photographer? Florist? Caterer?)
        </p>

        <p>
          Plan for 200 ± 10-15. If you're at 200 seated capacity with zero flexibility, a few last-minute changes destroy the day.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Table assignments and flow</h3>

        <p>
          With 200 guests, table logistics are critical. Let's say 20-25 guests per table (6-8 tops per table, 3 people per top). That's 8-10 tables.
        </p>

        <p>
          <strong>Seat strategically:</strong>
        </p>

        <p>
          - Family groups stay together (unless they request otherwise).
          - Mix friends with friends or family, depending on couple preference.
          - Elderly guests or those with accessibility needs get tables close to the restrooms and with easy exit.
          - Separated couples don't sit together.
          - People who said "I know Sarah and Michael but don't know anyone else" get a table with other similar guests (built-in conversation partners).
        </p>

        <p>
          <strong>Communicate assignments:</strong> A week before the wedding, send a seating chart showing table numbers and guest names. Guests can see who they're sitting with. Caterer gets a copy showing dietary requirements per table.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Create a contingency seating list</h3>

        <p>
          If someone cancels 2 days before the wedding, you don't have time to rebuild the seating chart. Have a pre-planned "overflow" or "flexible" table that adjusts dynamically.
        </p>

        <p>
          Or use software that makes this easy. Click "This guest is not coming" and the system auto-adjusts tables to rebalance capacity.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Communication cadence</h3>

        <p>
          <strong>8-10 weeks out:</strong> Welcome email with RSVP link and deadline (6 weeks).
        </p>

        <p>
          <strong>4 weeks out:</strong> "RSVP closes in 2 weeks" reminder.
        </p>

        <p>
          <strong>2 weeks out:</strong> "RSVP closes in 1 week" reminder. If you haven't heard from 30% of guests, pick up the phone. Call the couples' families. Email doesn't work at scale.
        </p>

        <p>
          <strong>1 week out:</strong> Seating chart + day-of logistics email to couples and wedding party.
        </p>

        <p>
          <strong>3 days out:</strong> Caterer gets final headcount + dietary summary + seating chart with dietary flags.
        </p>

        <p>
          <strong>Day before:</strong> All staff/vendors get final timeline, guest list (if they need to know), and contingency info.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Pro tip: Use software</h3>

        <p>
          Managing 200 guests in a spreadsheet will cost you 20+ hours and guarantees an error. A platform like The Special Wedding handles guest import, RSVP tracking, dietary management, accessibility tracking, and seating—with exports for vendors.
        </p>

        <p>
          You're not saving money using a spreadsheet. You're paying yourself in headaches and late nights.
        </p>
      </div>
    ),
  },
  'honeybook-vs-aisle-planner': {
    title: 'HoneyBook vs Aisle Planner: Which Is Better for Wedding Planners?',
    excerpt: 'A side-by-side comparison of two popular tools, including where they fall short for event-specific workflows.',
    category: 'Tools',
    date: '2026-02-26',
    readTime: 10,
    ogDescription: 'HoneyBook vs Aisle Planner: a detailed comparison for wedding planners. Pricing, features, workflows, and where each tool excels.',
    relatedTemplates: ['couple_intake', 'vendor_onboarding'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          If you're a wedding planner, you've probably looked at HoneyBook and Aisle Planner. Both are popular, both claim to be "made for wedding professionals," and both will tell you they're better than the other.
        </p>

        <p>
          This comparison is honest: where each tool excels and where they fall short. We're not here to sell you anything—we're here to help you pick the right tool for your workflow.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">HoneyBook: The generalist CRM</h3>

        <p>
          HoneyBook is built as a CRM for creative professionals. Photographers, designers, videographers, event planners. It handles proposals, contracts, invoicing, and client communication.
        </p>

        <p>
          <strong>What HoneyBook does well:</strong>
        </p>

        <p>
          - Proposal templates that look professional and close deals.
          - E-signature integration (sign contracts in-platform).
          - Invoice and payment tracking (clients pay through the platform).
          - Client portal (your clients log in to see contracts, invoices, files).
          - Automation workflows (send a proposal → if signed → send invoice → send payment reminder).
          - Integration with Stripe, PayPal, and accounting tools.
        </p>

        <p>
          If you're running a solo business and need proposals, contracts, invoicing, and client communication, HoneyBook handles that smoothly.
        </p>

        <p>
          <strong>Where HoneyBook falls short for wedding planners:</strong>
        </p>

        <p>
          - <strong>No guest management:</strong> You can't import a guest list, track RSVPs, manage dietary needs, or assign seating. You'd need a separate tool for this (spreadsheet, AirTable, or specialty guest management software).
          - <strong>No timeline/day-of management:</strong> HoneyBook doesn't help you build parallel timelines or coordinate the day-of execution.
          - <strong>No vendor collaboration:</strong> You can invite clients to a portal, but you can't invite vendors (caterer, photographer, florist) and give them access to specific timelines or deliverables.
          - <strong>Limited data:</strong> Proposals, invoices, and calendar events—but not the deep event data wedding planners need.
        </p>

        <p>
          <strong>Pricing:</strong> $39-$299/month depending on features and volume.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Aisle Planner: The specialist tool</h3>

        <p>
          Aisle Planner was built specifically for wedding planning. It handles guest lists, RSVPs, seating, vendor management, and day-of timelines. It's closer to what you actually need.
        </p>

        <p>
          <strong>What Aisle Planner does well:</strong>
        </p>

        <p>
          - Guest list management with RSVP tracking and dietary note fields.
          - Seating chart creation (drag and drop, capacity tracking).
          - Timeline builder for the day-of.
          - Vendor management (invite vendors, share timelines).
          - Budget tracking with vendor costs.
          - Mobile app for day-of coordination.
        </p>

        <p>
          If you need guest management, seating, and day-of coordination, Aisle Planner has you covered.
        </p>

        <p>
          <strong>Where Aisle Planner falls short:</strong>
        </p>

        <p>
          - <strong>No contracts or proposals:</strong> You'll need a separate tool (HoneyBook, Dubsado, PandaDoc) for contracts and proposals. You're not closing deals in Aisle Planner.
          - <strong>No invoicing or payment:</strong> You'll need Stripe, QuickBooks, or another tool to invoice and collect payments.
          - <strong>Limited client portal:</strong> Clients can see seating and timelines, but not contracts or invoices.
          - <strong>Limited automation:</strong> You can't set up workflows like "if client books → send contract → if signed → add to calendar."
        </p>

        <p>
          <strong>Pricing:</strong> $99-$299/month for wedding planners.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Direct comparison</h3>

        <p>
          <strong>Contracts & Proposals:</strong> HoneyBook wins. Aisle Planner requires a second tool.
        </p>

        <p>
          <strong>Invoicing & Payments:</strong> HoneyBook wins. Aisle Planner requires a second tool (or you invoice outside the platform).
        </p>

        <p>
          <strong>Guest Management:</strong> Aisle Planner wins. HoneyBook doesn't have this.
        </p>

        <p>
          <strong>Seating Charts:</strong> Aisle Planner wins. HoneyBook doesn't have this.
        </p>

        <p>
          <strong>Day-of Coordination:</strong> Aisle Planner wins. HoneyBook is a calendar only.
        </p>

        <p>
          <strong>Vendor Collaboration:</strong> Aisle Planner wins. HoneyBook's vendor access is limited.
        </p>

        <p>
          <strong>Budget Tracking:</strong> Aisle Planner has more detail. HoneyBook tracks invoices but not full budgets.
        </p>

        <p>
          <strong>AI Features:</strong> Neither has meaningful AI. HoneyBook has some proposal templates. Aisle Planner doesn't.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The real problem</h3>

        <p>
          Using HoneyBook or Aisle Planner alone means you're not using a complete solution. You're duct-taping tools together:
        </p>

        <p>
          <strong>If you use HoneyBook + another tool for guest management:</strong> You're managing contracts in HoneyBook and guests in AirTable or Notion. Data lives in two places. When you update a guest name, you manually update it in both tools. When a client changes their plus-one name, you update HoneyBook (client portal), Aisle Planner (guest list), and send an updated seating chart.
        </p>

        <p>
          <strong>If you use Aisle Planner + another tool for contracts:</strong> You're managing guests in Aisle Planner and contracts in HoneyBook. Your client portal is split. They sign contracts in HoneyBook but check seating in Aisle Planner. You're exporting guest lists from Aisle Planner and manually creating invoices elsewhere. You can't see if a client has signed a contract and RSVPed until you check both platforms.
        </p>

        <p>
          Both tools are good at what they do. But neither does what you actually need by itself.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The use case for each</h3>

        <p>
          <strong>Use HoneyBook if:</strong> You're a solo planner who primarily sells packages and needs professional proposals/contracts. You're comfortable managing guests in a spreadsheet or using a second tool. Your workflow is sales-heavy (lots of inquiries, lots of proposal follow-up).
        </p>

        <p>
          <strong>Use Aisle Planner if:</strong> You need deep guest management, seating, and day-of coordination. You're willing to use a second tool for contracts and invoicing. Your workflow is execution-heavy (fewer inquiries, complex multi-event coordination).
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The case for a platform</h3>

        <p>
          The real answer? You shouldn't need to choose. You should have one planner platform for proposals, contracts, payments, guest management, seating, timelines, invoicing, and private vendor records.
        </p>

        <p>
          That's not HoneyBook (it's a generalist CRM). It's not Aisle Planner (it's a guest-focused tool). It's a platform built specifically for wedding planners, end-to-end.
        </p>

        <p>
          The Special Wedding brings those planner-facing records into one operating workspace. The public vendor directory remains a separate discovery surface, and vendors are not invited into private planner operations.
        </p>

        <p>
          But if you're choosing between HoneyBook and Aisle Planner, here's the honest assessment: HoneyBook is better if your constraint is closing deals. Aisle Planner is better if your constraint is executing complex events. And the ideal solution is a platform that does both, so you're not managing data in two places.
        </p>
      </div>
    ),
  },
  'wedding-planner-contract-essentials': {
    title: 'Wedding Planner Contract Essentials: What to Include in 2026',
    excerpt: 'Protect your business and your clients. The clauses every planner contract needs — with templates you can customize.',
    category: 'Business',
    date: '2026-02-19',
    readTime: 7,
    ogDescription: 'Essential contract clauses for wedding planners. Legal protection, scope definition, payment terms, and liability coverage.',
    relatedTemplates: ['vendor_onboarding', 'couple_intake'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          A contract isn't just a document. It's the agreement that protects you and your client when things get complicated. It defines what you're delivering, what you're not, what happens if they change plans, and what they owe you if they cancel.
        </p>

        <p>
          Without a contract, you're relying on conversation and goodwill. Conversation fades. Goodwill vanishes 2 weeks before the wedding when the couple decides they want something you didn't agree to.
        </p>

        <p>
          This guide covers the essential clauses every wedding planner contract needs. Consult a lawyer in your state for specific legal language, but use this as a template.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">1. Scope of services</h3>

        <p>
          Define exactly what you're delivering. Be specific. "Full planning" is vague. "We will create a budget, select 8-10 vendors, manage contracts, coordinate timelines, and execute the day-of" is clear.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "The Planner agrees to provide the following services: (a) initial planning consultation; (b) venue selection and negotiation; (c) vendor selection, negotiation, and contract review; (d) guest list management and RSVP tracking; (e) seating chart design; (f) day-of coordination including timeline creation, vendor management, and on-site execution; (g) post-wedding follow-up and invoicing."
        </p>

        <p>
          Then list what's NOT included. "Services do NOT include: design concepts (couple provides direction), hair and makeup coordination, photography, videography, and post-event video editing."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">2. Timeline and deadlines</h3>

        <p>
          When does planning start? When does it end? What are key milestones?
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "Planning period: [Start Date] through [Wedding Date]. Key milestones: venue confirmation by [Date], vendor selections by [Date], final timeline and guest list by [Date]. The Couple will meet with the Planner [once per month] during planning, or as needed if urgent decisions arise."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">3. Pricing and payment terms</h3>

        <p>
          State your fee clearly. Is it flat-fee or percentage-based? When is it due?
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "Planning Fee: $7,500 (Full Planning Package). Payment Schedule: (a) 50% ($3,750) due upon signing this agreement; (b) 50% ($3,750) due 60 days before the wedding. If the couple books within 60 days of the wedding, full payment is due upon signing."
        </p>

        <p>
          Also include: "Vendor deposits and final payments are the couple's responsibility and are in addition to the planning fee. The Planner will coordinate but the couple pays vendors directly."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">4. Additional fees and expenses</h3>

        <p>
          What costs extra? Rush fees? Travel? Overtime on the day-of?
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "Additional fees: (a) booking within 8 weeks of wedding: $500 rush fee; (b) events outside [City], [State]: $300 travel fee plus reimbursement for lodging and mileage; (c) day-of hours beyond 8 hours: $75/hour."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">5. Changes and amendments</h3>

        <p>
          Couples change their minds. Define how you handle scope changes and what they cost.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "Any changes to scope, timeline, or deliverables after signing require a written amendment. If changes increase the Planner's time commitment beyond 25% of the original estimate, the couple may be charged additional fees at $75/hour for the additional time."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">6. Cancellation and refund policy</h3>

        <p>
          What if they cancel? What's your refund policy? Be harsh enough to protect yourself, but not so harsh that you lose every client who gets cold feet.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "Cancellation policy: (a) If the couple cancels more than 90 days before the wedding, the Planner refunds 50% of the planning fee (the couple keeps 50% as a cancellation fee). (b) If the couple cancels 31-90 days before the wedding, the Planner refunds 25%. (c) If the couple cancels 0-30 days before the wedding, no refund is issued. The couple remains responsible for all vendor deposits already made on their behalf."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">7. Force majeure and venue changes</h3>

        <p>
          What if the venue cancels, or a vendor goes out of business? What if there's a natural disaster? You need to define your responsibility.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "If a vendor cancels or becomes unavailable, the Planner will use best efforts to find a replacement, but is not responsible for replacement costs or service disruptions. If the venue becomes unavailable due to circumstances beyond the Planner's control, the Planner will assist in finding an alternative but the couple remains responsible for all vendor penalties and rescheduling costs. In the event of a force majeure event (pandemic, natural disaster), the couple and Planner will work together to postpone or cancel, with the couple retaining 50% of planning fees already paid toward future planning if postponed."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">8. Liability and responsibilities</h3>

        <p>
          Clarify what you're responsible for and what you're not. You're not responsible if a vendor messes up, unless you failed to vet them.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "The Planner is responsible for vendor selection, negotiation, and contract review. The Planner is NOT responsible for vendor performance, quality, or delays (e.g., late flowers, poor photography). The Planner will manage vendor communication and escalate issues, but the couple's contractual relationship is with the vendor, not the Planner. The Planner is not responsible for: guest behavior, weather delays, transportation issues, or third-party vendor failures."
        </p>

        <p>
          Also include: "The Planner does not provide legal, financial, or health advice. For questions regarding tax implications, legal contracts, or medical accommodations, the couple should consult appropriate professionals."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">9. Liability cap</h3>

        <p>
          If something goes really wrong, your liability should be capped. Usually at the amount the couple paid you.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "The Planner's total liability for any breach of this agreement, negligence, or other claim shall not exceed the total amount paid by the couple to the Planner under this agreement."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">10. Confidentiality</h3>

        <p>
          Couples might ask you not to share details publicly. Protect that.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "The Planner agrees to keep all couple information confidential unless given written permission to share (e.g., in marketing, case studies, social media). Exceptions: the Planner may share details with vendors as necessary for execution and with service providers (accountants, lawyers) as necessary for business operations."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">11. Dispute resolution</h3>

        <p>
          If there's a disagreement, define how you'll solve it. Mediation? Arbitration? Small claims court?
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "Any dispute arising from this agreement shall first be resolved through good-faith negotiation. If negotiation fails, the parties agree to mediation before pursuing litigation. Mediation costs are split equally."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">12. Intellectual property</h3>

        <p>
          Who owns the timelines, seating charts, designs you create? Usually you retain the right to use them as templates or portfolio examples.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "The couple owns all deliverables specific to their wedding (timelines, seating charts, proposals). The Planner retains the right to use anonymized elements (design templates, processes, workflows) for internal use and future clients. The Planner may share wedding photos and videos for marketing purposes only with written permission."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">13. Governing law</h3>

        <p>
          Which state's laws govern this contract? This matters if there's a dispute.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "This agreement is governed by the laws of [State], without regard to its conflict of laws principles."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">14. Entire agreement</h3>

        <p>
          This contract is the whole deal. No side conversations override it.
        </p>

        <p>
          <strong>Example:</strong>
        </p>

        <p>
          "This agreement constitutes the entire agreement between the parties. Any amendments must be in writing and signed by both parties. No verbal promises or side agreements are valid."
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Pro tips for your contract</h3>

        <p>
          1. <strong>Make it readable:</strong> Avoid legal jargon where possible. If couples can't understand what they're agreeing to, they'll feel duped later.
        </p>

        <p>
          2. <strong>Use e-signature:</strong> A contract is worthless if you can't prove they signed it. Use a tool like DocuSign, Stripe Contracts, or HoneyBook that time-stamps signatures.
        </p>

        <p>
          3. <strong>Customize for each couple:</strong> Name, date, specific services, specific pricing. A generic contract feels impersonal.
        </p>

        <p>
          4. <strong>Get a lawyer:</strong> This guide is a template. Have a lawyer in your state review it. Wedding planning laws vary by state, and you want legal protection specific to your jurisdiction.
        </p>

        <p>
          5. <strong>Review annually:</strong> Laws change. Your business changes. Update your contract every year to reflect new terms, new services, and lessons you've learned.
        </p>

        <p>
          A good contract protects you. A great contract protects you and is so clear that your couple never feels blindsided.
        </p>
      </div>
    ),
  },
  'ai-changing-wedding-planning': {
    title: 'How AI Is Changing Wedding Planning (And What Planners Should Actually Use)',
    excerpt: 'Beyond the hype: practical AI applications for pricing, contracts, and cash flow that save planners real time.',
    category: 'Industry',
    date: '2026-02-12',
    readTime: 9,
    ogDescription: 'Practical AI for wedding planners. How to use AI for pricing, contracts, and cash flow forecasting.',
    relatedTemplates: ['couple_intake', 'order_of_events'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          AI is everywhere in wedding planning right now. AI seating charts. AI timelines. AI design mood boards. AI this. AI that.
        </p>

        <p>
          Most of it is hype. Cute technology, rarely solves a real problem.
        </p>

        <p>
          But some AI applications actually save you time and money. They're not glamorous. They're not front-and-center marketing features. They're the quiet tools that let you stop doing tedious work and focus on strategy and creativity.
        </p>

        <p>
          This guide covers the AI applications that matter for wedding planners. Where AI genuinely helps, where it's overrated, and how to evaluate AI tools without getting seduced by the hype.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Where AI actually helps</h3>

        <p>
          <strong>1. Pricing suggestions</strong>
        </p>

        <p>
          This is the use case where AI adds real value. You build a package (e.g., "Full Planning, $500k budget, 150 guests, 12-month timeline"). AI analyzes your market (location, competitor pricing, your services) and suggests a competitive price range.
        </p>

        <p>
          It saves you research. Instead of calling 10 planners in your market to understand pricing, you input your services and AI tells you the range. Is $8k underpriced or $12k overpriced? AI answers that in seconds.
        </p>

        <p>
          <strong>Why it works:</strong> Pricing is hard because you lack data. AI gives you data fast.
        </p>

        <p>
          <strong>2. Contract generation</strong>
        </p>

        <p>
          You describe your services ("full planning, partial planning, month-of coordination") and pricing. AI generates a wedding-specific contract with all the clauses you need: scope, timeline, payment terms, cancellation policy, liability.
        </p>

        <p>
          It saves 3-4 hours per contract. Instead of starting with a blank document or a generic template, you have a draft that's 80% done. You customize it, run it by your lawyer, and you're done.
        </p>

        <p>
          <strong>Why it works:</strong> Contracts are repetitive. AI excels at templated work.
        </p>

        <p>
          <strong>3. Cash flow forecasting</strong>
        </p>

        <p>
          You log your weddings, payment schedules, and deposit timing. AI forecasts your cash flow for the next 12 months. "In May you'll have $32k coming in. In July you'll have $18k. In Q4 you'll have $54k."
        </p>

        <p>
          Most planners manage cash flow ad-hoc. They don't know their next 6 months of income. AI forecasting changes that.
        </p>

        <p>
          <strong>Why it works:</strong> Forecasting is math. AI is good at math.
        </p>

        <p>
          <strong>4. Email and proposal copy</strong>
        </p>

        <p>
          You give AI an outline ("send an inquiry follow-up email that's warm but firm, closing in 2 days"). AI generates a draft. You edit, personalize, send.
        </p>

        <p>
          Saves 20 minutes of blank-page staring. Most planners spend that time procrastinating.
        </p>

        <p>
          <strong>Why it works:</strong> Copy is creative but formulaic. AI gives you a starting point.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Where AI is overrated</h3>

        <p>
          <strong>1. Seating charts</strong>
        </p>

        <p>
          "AI seating that respects family dynamics and maximizes conversation." Sounds cool.
        </p>

        <p>
          In practice: Seating is 30% algorithm and 70% human judgment. You know the couple's family drama better than an AI. You know that Uncle Mike and Aunt Sarah haven't spoken in 5 years. You know that the bride's college friends all want to sit together. You know the groom's work colleagues don't know each other and need an icebreaker table.
        </p>

        <p>
          AI can suggest a starting layout (randomized with basic constraints), but you're rewriting 40% of it anyway. You're better off with a tool that lets you drag-and-drop easily, not one that tries to be clever.
        </p>

        <p>
          <strong>2. Timeline generation</strong>
        </p>

        <p>
          "AI creates your day-of timeline based on your vendors and ceremony time." Also sounds cool.
        </p>

        <p>
          Reality: Timelines are specific to the couple's vision, venue logistics, and family preferences. An AI timeline is generic ("ceremony 4pm, cocktail 5-6pm, dinner 6:30pm"). You customize it anyway for specific vendor timings (photographer needs 30 min before ceremony), family moments (portraits at 5:15pm), and pacing.
        </p>

        <p>
          An AI suggestion is okay as a starting point. But the real value is in a tool that makes editing and sharing timelines easy, not in AI magic.
        </p>

        <p>
          <strong>3. Design mood boards</strong>
        </p>

        <p>
          "AI generates mood boards based on the couple's aesthetic." Cute, but not useful.
        </p>

        <p>
          Couples don't want an AI mood board. They want you to understand their vision, curate inspiration, and tell them why certain choices work together. The planning process is the value, not the AI output.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">How to evaluate AI tools</h3>

        <p>
          When a tool says "AI-powered," ask:
        </p>

        <p>
          1. <strong>Does this save me time on tedious work?</strong> (Good: contract generation, forecasting. Bad: seating that you rewrite anyway.)
        </p>

        <p>
          2. <strong>Does this give me data I don't have?</strong> (Good: market pricing. Bad: mood board suggestions.)
        </p>

        <p>
          3. <strong>Does this replace human judgment or augment it?</strong> (Good: augment—pricing suggestions you review. Bad: replace—AI timelines you adopt as-is.)
        </p>

        <p>
          4. <strong>Can I override the AI output easily?</strong> (Good: you edit the contract in seconds. Bad: you're locked into the AI's logic.)
        </p>

        <p>
          5. <strong>What happens if the AI is wrong?</strong> (Good: you notice the mistake and fix it. Bad: you miss it and it harms the wedding.)
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">AI tools worth paying for</h3>

        <p>
          <strong>1. ChatGPT or Claude (via subscription or API)</strong> for copy generation, email drafting, and brainstorming. $20/month for unlimited access.
        </p>

        <p>
          <strong>2. Pricing tools built into wedding planning platforms</strong> (like The Special Wedding) that analyze your market. Value: saves 5+ hours of research per pricing decision.
        </p>

        <p>
          <strong>3. Contract generation tools</strong> (built-in or standalone) that create wedding-specific contracts. Value: saves 3-4 hours per contract + ensures you don't miss clauses.
        </p>

        <p>
          <strong>4. Forecasting tools</strong> (built-in or spreadsheet-based) that predict cash flow. Value: gives you 12-month visibility into your business.
        </p>

        <p>
          <strong>5. Email marketing automation</strong> (Substack, ConvertKit, Mailchimp) that schedules and personalizes outreach. Value: saves hours on repetitive follow-up.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">AI tools that are nice-to-have but not essential</h3>

        <p>
          - Image generation for mood boards (good for inspiration, not client deliverables)
          - Writing assistants for blog posts or social media (faster than writing from scratch, but requires heavy editing)
          - Automated meeting scheduling (nice UI, but you don't save much time)
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The future of AI in wedding planning</h3>

        <p>
          What could be genuinely useful but doesn't exist yet:
        </p>

        <p>
          - <strong>Vendor behavior analysis:</strong> "This caterer has been late 40% of events (based on reviews). Here's similar caterers in your area." Not AI-generated advice—actual data analysis.
        </p>

        <p>
          - <strong>Predictive timeline alerts:</strong> Based on historical weather, traffic, vendor performance, "there's a 60% chance your photographer will be 15 min late on this date. Move portraits 20 min earlier."
        </p>

        <p>
          - <strong>Client satisfaction prediction:</strong> "Based on the couple's budget, guest count, timeline, and vendor choices, couples like this usually report 8.2/10 satisfaction. Your current plan trends 7.1. Here's where you could improve."
        </p>

        <p>
          - <strong>Conflict detection:</strong> "The couple said budget is $75k but selected vendors totaling $91k. Highlight this before they over-commit."
        </p>

        <p>
          These are coming. They require less creativity and more data than current AI. They'll actually move the needle.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The bottom line</h3>

        <p>
          Don't chase AI for its own sake. Use AI where it saves you tedious work: pricing, contracts, forecasting, copy. Skip AI where it's a gimmick: mood boards, timelines, seating.
        </p>

        <p>
          And remember: AI is a tool. The value comes from you using it well, not from the tool being magical.
        </p>
      </div>
    ),
  },
  'seating-chart-strategy': {
    title: 'Seating Chart Strategy: Beyond Drag-and-Drop',
    excerpt: 'Family dynamics, vendor placement, accessibility — the art and science of orchestrating 200 seats across 5 sections.',
    category: 'Workflow',
    date: '2026-02-05',
    readTime: 5,
    ogDescription: 'Seating chart strategy for wedding planners. How to orchestrate 200+ guests with attention to family dynamics and experience.',
    relatedTemplates: ['guest_dietary_access', 'bridal_party_logistics', 'order_of_events'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          Seating is one of the highest-leverage decisions you make as a planner. It shapes the experience for every guest. A good seating chart feels intentional and warm. A bad one feels random and awkward.
        </p>

        <p>
          Seating isn't just about capacity. It's about experience design. You're orchestrating 200 conversations and 200 memories across 5 sections of 40 people each.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The three types of tables</h3>

        <p>
          <strong>Family tables:</strong> The couple's immediate family, extended family by choice. Grandparents, parents, siblings, and whoever "counts" as family to them.
        </p>

        <p>
          <strong>Friend tables:</strong> College friends, childhood friends, industry friends, couple friends. Usually self-selecting. You group friends together and let the chemistry happen.
        </p>

        <p>
          <strong>Mixed tables:</strong> Family + friends, or guests who know the couple but not each other. This is where you add intention. You're designing conversation.
        </p>

        <p>
          Start by asking: "Do you want family separated or together? Do your college friends need their own table?" Most couples say yes to both. Then you build mixed tables thoughtfully.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The choreography principle</h3>

        <p>
          Think of seating as choreography, not just placement. You're directing flow and experience.
        </p>

        <p>
          - <strong>VIP tables (near the couple, good view):</strong> Immediate family, grandparents, best friends. They should have unobstructed sightlines to the ceremony transitions and couple moments.
        </p>

        <p>
          - <strong>Anchor tables (center room):</strong> The couple's closest friends and family. These tables set energy. If they're happy and engaged, the whole room feels that way.
        </p>

        <p>
          - <strong>Conversation starter tables (mix of people who don't know each other):</strong> Introduce people who share interests but haven't met. College friend + work friend + friend's partner = new connections.
        </p>

        <p>
          - <strong>Vendor table:</strong> Your day-of coordinator, any ushers or VIP staff. Somewhere visible but not front-and-center. They need to see the room and move around.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The constraints you need to manage</h3>

        <p>
          <strong>Divorced or separated families:</strong> Keep exes and their new partners in different sections if possible. Not paranoid—just reduces awkwardness.
        </p>

        <p>
          <strong>Kids and elderly:</strong> Seat them away from noisy corners or loud speakers. Near restrooms if possible. Assign someone at the table to help with accessibility needs.
        </p>

        <p>
          <strong>Table capacity:</strong> Most tables are 6, 8, or 10. Know your capacity and don't overstuff. 8 is ideal—intimate but big enough for natural conversation groups.
        </p>

        <p>
          <strong>Vendor placement:</strong> Your florist needs access to the floral arrangements. Your caterer needs path to the kitchen. Your photographer needs sightlines. Don't seat guests in a way that blocks vendor movement.
        </p>

        <p>
          <strong>Known conflicts:</strong> Ask upfront: "Is there anyone you'd prefer not to sit with?" Some couples will tell you. "My ex and their new partner are both coming." "My parents aren't speaking." Honor this without judgment.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The design process</h3>

        <p>
          1. <strong>Map family tables first.</strong> Grandparents, parents, siblings. 3-4 tables likely. These are non-negotiable.
        </p>

        <p>
          2. <strong>Create friend groups.</strong> College friends, childhood friends, work friends. One table each if they're tight. Multiple tables if they're large.
        </p>

        <p>
          3. <strong>Fill remaining capacity with intentional mixed tables.</strong> Don't just scatter leftovers. Introduce people thoughtfully.
        </p>

        <p>
          4. <strong>Audit sightlines.</strong> Can tables see the ceremony? The couple's table? Any speakers? Adjust if needed.
        </p>

        <p>
          5. <strong>Audit flow.</strong> Is there a clear path from entrance to tables? From kitchen to all tables? From ceremony to cocktail hour? Don't block vendors with poor table placement.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The intro document</h3>

        <p>
          The day before the wedding, send a seating chart document that shows:
        </p>

        <p>
          - Table number and guest names
          - One-line context for mixed tables ("College friend group" or "Bride's family + groom's cousins")
          - Dietary flags for the caterer per table
          - Accessibility notes (wheelchair-accessible seat available, etc.)
        </p>

        <p>
          This does two things: (1) Guests see who they're sitting with and can find their table, (2) Caterers and staff know what to expect.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Pro tips</h3>

        <p>
          <strong>1. Print extra place cards.</strong> People forget their table number. Have 20% extra. You're placing them in 10 minutes at the reception entrance.
        </p>

        <p>
          <strong>2. Do a final check 2 days out.</strong> Any last-minute cancellations? Seating changes needed? Don't make changes the day-of unless it's an emergency.
        </p>

        <p>
          <strong>3. Consider table themes.</strong> Not cheesy—subtle. "Favorite travel destination," "hobby," "how you met." Gives people conversation starters beyond "so how do you know the couple?"
        </p>

        <p>
          <strong>4. Assign a point person.</strong> On the day-of, someone needs to manage late arrivals, seat changes, and fix mistakes. It won't be you (you're running the timeline). Assign it to your coordinator or a trusted vendor.
        </p>

        <p>
          <strong>5. Don't over-explain.</strong> Your seating is intentional, but guests don't need to hear all your logic. They just need to find their table and enjoy the experience.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Why this matters</h3>

        <p>
          People remember how a wedding *felt*, not what you served or how the flowers looked. Seating shapes feeling. A couple who trusted you enough to let you orchestrate introductions feels like you understood them. That trust is how you build referrals.
        </p>

        <p>
          Seating is an art and a science. The science is the constraints (capacity, flow, accessibility). The art is the orchestration. You're designing experiences, not just placing people.
        </p>
      </div>
    ),
  },
  'the-built-in-wedding-website': {
    title: "The Built-In Wedding Website: Why Your Couples Shouldn't Pay Squarespace or The Knot",
    excerpt: "Every wedding on The Special Wedding can present a branded public microsite with approved schedule, story, gallery, registry, RSVP, and QR-memory details prepared from the planner wedding record.",
    category: 'Product',
    date: '2026-05-04',
    readTime: 7,
    ogDescription: 'See how the planner wedding record prepares the approved schedule, story, gallery, registry, RSVP, and QR-memory details presented on the public microsite.',
    relatedTemplates: ['couple_intake', 'guest_dietary_access'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          Ask any couple what they paid for in the first month of planning, and wedding website will be on the list. Squarespace. The Knot. Zola. Minted. Some planners even stitch a WordPress site together for clients. It's a small line item, but it's the single most visible piece of digital infrastructure around the wedding — it's where guests go, it's what shows up when someone Googles the couple's names, and it's the front door of the entire event.
        </p>

        <p>
          And in almost every platform built for wedding planners, it lives outside the system.
        </p>

        <p>
          That's the hidden cost. The wedding website holds guest data (RSVPs, dietary notes, address updates, plus-one responses) that the planner needs in real time. But because it lives in Squarespace or The Knot, that data has to be copy-pasted into whatever planning tool the planner uses. Or the planner becomes a human integration, manually updating two systems whenever a guest changes their RSVP.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">What the built-in microsite actually includes</h3>

        <p>
          Every wedding on The Special Wedding ships with a branded public microsite at a couple-specific slug. It has all the things couples expect from a wedding website, wired to the same data the planner is already using:
        </p>

        <p>
          <strong>Branded presentation:</strong> The planner configures colors, fonts, background style, and event copy in Wedding Configuration. The public microsite presents the approved branding, while the couple portal keeps its own audience-appropriate view.
        </p>

        <p>
          <strong>Event schedule and gallery:</strong> Welcome event, ceremony, reception, brunch — whatever the couple's multi-event plan looks like — renders on the public site, threaded with photos from the same gallery the planner manages.
        </p>

        <p>
          <strong>RSVP flow:</strong> Guests use the microsite RSVP flow for attendance, event, meal, plus-one, dietary, and accessibility responses. The planner reviews the stored response and guest context in Guest Management before using it for seating and communications.
        </p>

        <p>
          <strong>Registry and FAQs:</strong> The planner maintains approved registry links and FAQ content in Wedding Configuration. The public microsite presents that prepared information without exposing planner controls.
        </p>

        <p>
          <strong>QR memory uploads:</strong> A QR code on every table — or printed on signs around the reception — lets guests upload photos from their phone during or after the event. Everything flows into a private review queue in the couple portal before it appears in the public gallery.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">What the connected product proof demonstrates</h3>

        <p>
          The seeded product proof lets a planner compare the wedding record with the public schedule, story, and gallery, then inspect guest-response context in Guest Management. Each surface presents the details appropriate to its audience.
        </p>

        <p>
          The public view does not expose planner notes, contracts, or operational controls. Caterer handoffs and other vendor-facing deliverables remain explicit planner workflows rather than an implied automatic vendor sync.
        </p>

        <p>
          More importantly, the guest experience stays consistent. Guests aren't bouncing between a wedding website, a random RSVP link, and some form the planner sent. Everything lives at one URL, under the couple's brand, on the same system.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">What it replaces</h3>

        <p>
          For most planners, the built-in microsite directly replaces Squarespace or The Knot as the couple's wedding website. For some, it also replaces Zola as the registry hub, Google Forms as the RSVP collector, and a shared Google Doc as the FAQ. For couples with a more elaborate multi-event wedding, it replaces the "one-off landing page my cousin built" that held the travel info.
        </p>

        <p>
          It doesn't replace every visual-design tool a couple might want — if they want a custom-built marketing site with a video hero, they can still commission one. But for 90% of weddings, the built-in microsite is what they wanted anyway: a branded public page, an RSVP flow, a gallery, a registry, and a place guests can always go back to.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Why this matters for the planner</h3>

        <p>
          The planner is the one who pays for the fragmentation. Every off-platform tool means another integration to babysit, another place guest data can drift, another surface to explain to the couple. When the wedding website lives inside the same platform as the planner's workspace, the planner stops being the human glue between systems and starts being what they're actually good at — the strategist running the wedding.
        </p>

        <p>
          The built-in microsite is one of the clearest examples of what "complete workspace" actually means in practice. It's not a feature checklist. It's one data model serving the couple's public site, the planner's operations, and the guest experience at the same time.
        </p>
      </div>
    ),
  },
  'your-vendor-network-inside-the-platform': {
    title: 'Your Planner-Owned Vendor Network: Discovery, Records, and Agreements in One Place',
    excerpt: 'Use the public directory for discovery, then keep private contacts, notes, files, agreements, and payment context in the planner workspace.',
    category: 'Product',
    date: '2026-05-11',
    readTime: 5,
    ogDescription: 'See how wedding planners can move from public vendor discovery to private, planner-owned vendor records without exposing planner operations.',
    relatedTemplates: ['vendor_onboarding', 'vendor_performance_review'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          Vendor information often arrives through search results, referrals, PDFs, email threads, and spreadsheets. The planner then has to remember which contact belongs to which wedding, what was agreed, which file is current, and what remains unpaid.
        </p>

        <p>
          The Special Wedding separates two useful jobs: public discovery and private planner operations. The public vendor directory helps planners browse vendor profiles. Planner Vendor Management keeps the selected contacts and their wedding-specific context inside the planner workspace.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">The public directory: discovery</h3>

        <p>
          Browse the public directory by vendor category and open the available profile details. This is a public research surface; it does not expose the planner's private wedding records or give a vendor access to the planner workspace.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Planner Vendor Management: private context</h3>

        <p>
          Save the vendor in the planner's own directory, attach the record to the wedding, and keep contact details, notes, files, quote context, and status in one operational view. The wedding record remains planner-owned.
        </p>

        <p>
          Vendor agreements add the scope, contract sections, and payment milestones the planner needs to review. The wedding budget provides the corresponding financial context. These are planner workflows; the public article does not promise vendor login, vendor delivery, or automatic payment behavior.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Why the boundary matters</h3>

        <p>
          A planner should be able to keep complete operational context without giving every outside party access to the studio's internal workspace. Public profiles stay public; planner records stay private; the planner decides what belongs in each wedding.
        </p>

        <p>
          That boundary is the product today: public vendor discovery plus planner-owned vendor CRM, agreements, and payment context. It is not a vendor signup or vendor-portal promise.
        </p>
      </div>
    ),
  },
  'why-your-couples-stop-texting-you': {
    title: "Why Your Couples Stop Texting You the Same Five Questions",
    excerpt: 'When registry URLs, FAQs, a meeting scheduler, a memory wall, and push notifications all live in the couple portal, couples stop treating you as the human API for their wedding.',
    category: 'Product',
    date: '2026-05-18',
    readTime: 6,
    ogDescription: 'How the couple portal kills the "did you get my text?" loop by giving couples self-serve answers, real-time updates, and one inbox with their planner.',
    relatedTemplates: ['couple_intake', 'guest_dietary_access'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          Every planner we talk to has the same story. It's Sunday evening. Two hours of texts from three different couples. One asking for the venue address. One asking what the RSVP deadline is. One wondering if their registry link is live yet. The planner already answered these questions. In some cases, they answered them three weeks ago. But the information lives in different places, and the couple doesn't remember where.
        </p>

        <p>
          The planner becomes the human API. Not because the couples are needy — they aren't — but because no single place has the answer, so they ask the one person who definitely does.
        </p>

        <p>
          The couple portal is built to stop this loop. Not by making the planner respond faster. By giving couples a surface that answers itself.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Registry and FAQs the couple actually maintains</h3>

        <p>
          The couple manages their own registry URLs (Amazon, Target, Zola, Crate & Barrel, anywhere they've set one up) inside the portal. They also maintain a FAQ list — venue address, parking instructions, dress code, kid-friendliness, accessibility, whatever they want guests to know. Both surfaces are writable by the couple and render automatically on their public microsite.
        </p>

        <p>
          This isn't the planner doing it for them. It's the couple's own content, on their own schedule. When they think of an answer, they add it. When a question comes up from a guest, the couple adds the FAQ once and it lives there for every guest after. The planner isn't in the loop for content updates.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">A meeting scheduler for check-ins</h3>

        <p>
          Instead of the couple texting "are you free Thursday?" and the planner replying "yes but only 2-4," the portal has a scheduler wired to the planner's calendar. The couple picks a slot that's actually free. The meeting goes on the calendar. Both parties see the same time without negotiation.
        </p>

        <p>
          This replaces Calendly for the couple-planner relationship specifically, but more importantly, it replaces the text-back-and-forth that every planner recognizes as a time sink.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Push notifications for everything that matters</h3>

        <p>
          The couple portal has a real notification layer. New message in the inbox? Push. Vendor signed a contract? Push. RSVP count crossed a threshold? Push. Payment was processed? Push. The couple doesn't have to check the portal to know what's happening — the portal tells them.
        </p>

        <p>
          This is the feature that most directly kills the "did you get my email?" anxiety. Couples stop feeling out of the loop because they're not out of the loop. The updates come to them.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">A memory wall guests can contribute to</h3>

        <p>
          A QR code at the reception lets guests upload photos and short videos from their phones during the event. Everything flows into a private review queue in the couple portal. The couple can accept, reject, or feature memories before they appear in the public gallery.
        </p>

        <p>
          This isn't a feature the planner has to manage. It's a couple-facing workflow that happens in the portal without the planner being in the loop. The result: the couple has a gallery of real guest-captured memories that didn't cost the planner any coordination time.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">What the planner gets back</h3>

        <p>
          The obvious return is the Sunday-night text volume dropping. But the bigger return is the couple relationship changing shape. Planners stop being treated like a search engine the couple types questions into. They start being treated like a strategist the couple brings decisions to. That's the relationship the planner signed up for.
        </p>

        <p>
          The couple portal is what makes this shift possible. Not because it replaces communication with the planner — the planner inbox is right there in the portal — but because the routine questions finally have somewhere to live that isn't the planner's phone.
        </p>
      </div>
    ),
  },
  'real-time-planning-not-email-tag': {
    title: 'Shared Wedding Views Without Exposing Planner Operations',
    excerpt: 'The planner workspace, couple portal, public microsite, and guest-response tools each present the context their audience needs while planner-only controls remain private.',
    category: 'Product',
    date: '2026-05-25',
    readTime: 7,
    ogDescription: 'See how one planner-owned wedding record supports distinct planner, couple, public, and guest-response views without exposing private operations.',
    relatedTemplates: ['order_of_events', 'day_of_emergency_contacts'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          A wedding plan serves several audiences, but those audiences should not share one unrestricted dashboard. Planners need operational controls and private context. Couples need a guided view of their wedding. Guests need clear public details and an RSVP path.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">One planner-owned record, distinct audience views</h3>

        <p>
          The planner workspace owns the detailed wedding record: event days, guest context, forms, payments, vendor records, seating, and configuration. Planner-only controls and internal notes remain inside that operational boundary.
        </p>

        <p>
          The couple portal presents a guided overview, timeline, payment context, and assigned forms. The public microsite presents the prepared story, schedule, registry, FAQ, and approved gallery for guests. Neither view exposes the planner dashboard.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Guest responses return to planner operations</h3>

        <p>
          Guests submit attendance and event choices through the RSVP flow. Guest Management then shows the stored invitation, response, group, meal, and plus-one context for planner review. Seating and communications remain explicit planner actions.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">What to verify before signing up</h3>

        <p>
          Open the seeded planner wedding record, couple portal, public wedding, and Guest Management views side by side. Compare the prepared event and guest context, and confirm that each audience sees only the information intended for it.
        </p>

        <p>
          The value is not a promise that every view updates invisibly or that every external participant joins the planner workspace. The value is a clear planner-owned source with deliberate audience boundaries and visible review points.
        </p>
      </div>
    ),
  },
  'the-ops-layer-nobody-sees': {
    title: 'The Ops Layer Nobody Sees: Team Permissions, Audit Logs, and the Operational Backbone',
    excerpt: "Team member permissions, activity history for supported operations, and OTP guest access are the less glamorous safeguards planning teams need as they grow.",
    category: 'Product',
    date: '2026-06-01',
    readTime: 7,
    ogDescription: 'Granular team permissions, activity audit logs, OTP guest access, CSV guest imports, and the operational backbone that planning teams need to actually scale.',
    relatedTemplates: ['vendor_performance_review', 'day_of_emergency_contacts'],
    content: (
      <div className="space-y-6 text-slate-300 leading-relaxed">
        <p>
          Every wedding platform markets the glamorous features. Seating charts. AI contracts. Pricing guidance. Those get the landing-page real estate and the marketing budget, because they're the features couples and solo planners actually get excited about.
        </p>

        <p>
          But nobody scales a planning team on glamorous features. Teams scale on the boring ones: permission boundaries between weddings, visible activity history for supported operations, lightweight guest access, and import safeguards that let planners review data before using it.
        </p>

        <p>
          This is the ops layer. It's the reason planners who start solo on The Special Wedding can grow into a three- or five-person team without switching platforms. It's the reason a lead planner can share a wedding with a junior planner and a day-of assistant and give each of them exactly the access they should have — and nothing more.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Team permissions across 12+ scopes</h3>

        <p>
          Every wedding has 12+ distinct permission scopes: guests, budget, gallery, vendors, contracts, forms, payments, calendar, couple portal, seating, team management, audit log. A team member gets assigned to specific weddings and specific scopes within each wedding. A junior planner might have read-only on budget and full access on guests. A day-of assistant might have full access on timeline and no access at all on payments.
        </p>

        <p>
          This is how planning teams actually work. You don't hand every team member the keys to every wedding — that's how data leaks happen. You scope access to the work each person is doing. The granularity matters: a platform that only has "admin" and "user" forces you to over-share or under-staff.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Activity audit log</h3>

        <p>
          The planner Activity Log records supported operational events so a team can review visible work history in one place. It is an operational aid for the events the platform emits, not a promise that every database write is a complete legal audit trail.
        </p>

        <p>
          This is the kind of feature you don't appreciate until you need it. But in any multi-person planning operation, "who made this change?" is a question that comes up weekly. Having a canonical answer instead of a Slack archaeology project is what keeps the team functional.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">OTP guest access</h3>

        <p>
          Guests shouldn't have to create accounts to RSVP. They shouldn't have to remember passwords to check the schedule. The Special Wedding uses OTP-based guest access — guests get a one-time code by email or SMS, verify once, and stay in a lightweight session for that device.
        </p>

        <p>
          This is the infrastructure piece that makes the public microsite actually usable. A 72-year-old guest of honor is not going to set up an account. They're going to tap a link, enter a code, and RSVP. The OTP flow is built for that reality.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">CSV and Google Sheets guest imports</h3>

        <p>
          Every planner has guest lists in a spreadsheet. Multiple spreadsheets, usually. The Special Wedding imports them cleanly — column mapping, duplicate detection, household grouping preserved. Not because importing CSVs is exciting, but because any platform that makes you manually re-enter 250 guests is a platform you'll never migrate to.
        </p>

        <p>
          Similarly, Google Sheets import. Planners who've been collaborating with a couple on a shared sheet can pull that sheet into The Special Wedding without copy-paste. The sheet becomes the starting point of the guest list, not a dead parallel version of it.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">In-app support and knowledge base</h3>

        <p>
          The in-app Knowledge Base and support ticket flow give planners documented help paths without promising an on-call day-of service. Response times follow the active plan, and the searchable guides keep routine workflow answers inside the platform.
        </p>

        <p>
          This is also where the platform documents workflows the planner might not know exist. How to split access with a team member. How to set up the inbound email address. How to wire Stripe for milestone-based payments. The knowledge base is the self-serve layer that keeps the support team focused on real incidents, not how-to questions.
        </p>

        <h3 className="text-xl font-semibold text-white mt-8">Why this is where teams make the switch</h3>

        <p>
          A solopreneur planner can run on almost anything. Their ops layer is their laptop, their phone, and their memory. They don't need granular permissions because there's only one of them. They don't need audit logs because they know what they did yesterday.
        </p>

        <p>
          The moment a planner hires a second person, the ops layer starts to matter. By the time they're a three-person team, it dominates everything else. The reason teams switch from generalist tools to The Special Wedding isn't the glamorous features. It's that the ops layer was built for teams from day one, instead of bolted on later.
        </p>

        <p>
          Nobody markets this stuff. Nobody puts "audit log" in a hero headline. But it's the reason a team that starts on The Special Wedding with one planner can grow to ten without re-platforming.
        </p>
      </div>
    ),
  },
} as const;

export type BlogPostKey = keyof typeof blogPosts;

export const relatedPosts: Record<BlogPostKey, BlogPostKey[]> = {
  'introducing-the-special-wedding': [
    'how-to-price-wedding-planning-services',
    'ai-changing-wedding-planning',
    'wedding-planner-contract-essentials',
  ],
  'how-to-price-wedding-planning-services': [
    'introducing-the-special-wedding',
    'wedding-planner-contract-essentials',
    'ai-changing-wedding-planning',
  ],
  'managing-200-guests': [
    'seating-chart-strategy',
    'introducing-the-special-wedding',
    'ai-changing-wedding-planning',
  ],
  'honeybook-vs-aisle-planner': [
    'introducing-the-special-wedding',
    'ai-changing-wedding-planning',
    'managing-200-guests',
  ],
  'wedding-planner-contract-essentials': [
    'how-to-price-wedding-planning-services',
    'introducing-the-special-wedding',
    'ai-changing-wedding-planning',
  ],
  'ai-changing-wedding-planning': [
    'introducing-the-special-wedding',
    'wedding-planner-contract-essentials',
    'how-to-price-wedding-planning-services',
  ],
  'seating-chart-strategy': [
    'managing-200-guests',
    'introducing-the-special-wedding',
    'ai-changing-wedding-planning',
  ],
  'the-built-in-wedding-website': [
    'why-your-couples-stop-texting-you',
    'real-time-planning-not-email-tag',
    'introducing-the-special-wedding',
  ],
  'your-vendor-network-inside-the-platform': [
    'introducing-the-special-wedding',
    'the-ops-layer-nobody-sees',
    'real-time-planning-not-email-tag',
  ],
  'why-your-couples-stop-texting-you': [
    'the-built-in-wedding-website',
    'real-time-planning-not-email-tag',
    'introducing-the-special-wedding',
  ],
  'real-time-planning-not-email-tag': [
    'the-ops-layer-nobody-sees',
    'why-your-couples-stop-texting-you',
    'introducing-the-special-wedding',
  ],
  'the-ops-layer-nobody-sees': [
    'real-time-planning-not-email-tag',
    'your-vendor-network-inside-the-platform',
    'introducing-the-special-wedding',
  ],
};
