export type MarketingFeature = {
  id: string;
  icon: string;
  title: string;
  category: string;
  image: string;
  tagline: string;
  description: string;
  ai: boolean;
  /**
   * Optional blog post slug in app/resources/blog/data.tsx. When present, the
   * landing card and /features showcase render a "Read the story →" link to
   * /resources/blog/{blogSlug}. Not every feature has a dedicated post.
   */
  blogSlug?: string;
};

// Brand anchor: "Run every wedding from one record."
// Every entry tells a story, not a capability bullet: open with a recognizable
// planner moment, name the tools TSW replaces, and ladder back to one record,
// five surfaces (planner, couple, guest, vendor, team) — synced live.
// Guests, config, calendar, and knowledge are NOT standalone entries; they're
// infrastructure folded into the stories they power.
export const MARKETING_FEATURES: MarketingFeature[] = [
  {
    id: 'dashboard',
    icon: '📊',
    title: 'The Morning View',
    category: 'Operations',
    image: '/dashboard.png',
    tagline: 'Open the app at 8am and see exactly what changed overnight — no CSV, no refresh.',
    description:
      "Most planners start their week stitching together HoneyBook pipeline, Aisle Planner tasks, a Google Sheet of RSVPs, and a Stripe tab for overdue invoices. The Morning View replaces that ritual. One live dashboard surfaces every wedding's RSVP velocity, cash-flow alerts, overdue payments, unread couple messages, upcoming milestones, and AI-surfaced insights — because every surface writes to the same record this reads from. Activation funnels, retention cohorts, and the full audit log live here too, so you know what your business is doing without ever exporting anything.",
    ai: true,
  },
  {
    id: 'real-time',
    icon: '⚡',
    title: 'Live, Not Synced',
    category: 'Operations',
    // TODO: replace with /realtime_updates.png once captured; using planner inbox as proxy
    image: '/planner_inbox.png',
    tagline: "The platform doesn't sync — it streams. Every change lands on every surface the moment you save.",
    description:
      "You update the timeline Tuesday night at 10pm. Before HoneyBook, the couple would've seen it at their 9am 'refresh the shared doc' ritual. Here, server-sent events push it to the couple portal, the microsite, and the team member's phone the second you hit save. Guests forwarding questions to your wedding email auto-thread into the right couple's inbox. The activity log captures every write so your assistant can trace who changed what. Planning stops being a sync-every-morning operation and becomes a single nervous system.",
    ai: false,
    blogSlug: 'real-time-planning-not-email-tag',
  },
  {
    id: 'couple-portal',
    icon: '💍',
    title: 'The Couple Sees What You See',
    category: 'Client Experience',
    image: '/couple_portal_dashboard.png',
    tagline: 'Stop being the human API between the couple and every planning tool.',
    description:
      "Nine months out, your couple texts for the fourth time: 'what time is cocktail hour again?' Because the answer lives in a Google Doc they can't find, a venue email they've archived, and a timeline PDF you sent in January. The Couple Portal ends that loop. Couples log into the same record you work in — dashboard, timeline, payments, forms, inbox, meetings, push notifications. They maintain their own registry URLs and FAQ entries (rendered on both the portal and the public microsite). They annotate events and order-of-events with threaded, status-tracked notes you reply to in place. They submit forms on their schedule. The inbound texts stop because the answer is always live on the record they're already reading.",
    ai: false,
    blogSlug: 'why-your-couples-stop-texting-you',
  },
  {
    id: 'wedding-website',
    icon: '🌐',
    title: 'The Microsite Auto-Publishes',
    category: 'Client Experience',
    // TODO: replace with /wedding_microsite.png once captured from staging
    image: '/couple_portal_dashboard.png',
    tagline: 'Every wedding ships with a branded microsite — no Squarespace, no extra login, never out of date.',
    description:
      "Booking a couple used to mean another $200/yr Squarespace site, another login, another place the schedule can go stale. Not here. The second a wedding exists in your dashboard, its public microsite is live: theme colors, fonts, the couple's story, wedding party, event schedule, gallery, RSVP flow, and guest memory uploads. Every surface reads the same record you write to — so the website can never drift from the plan. The wedding-website builder category, for this couple, ceases to exist.",
    ai: false,
    blogSlug: 'the-built-in-wedding-website',
  },
  {
    id: 'rsvp-seating',
    icon: '🪑',
    title: 'RSVP → Reminders → Seating, One Guest List',
    category: 'Guest Pipeline',
    image: '/seating.png',
    tagline: "Import the guest list once. Every downstream surface writes back to it — so seating never goes stale.",
    description:
      "Twelve days before the wedding, six guests cancel. On the old stack, that's an afternoon: update the Google Sheet, re-export to the seating tool, re-send the meal count to the caterer, re-tell the partner. Here, one edit on the guest record ripples everywhere: RSVP page, microsite schedule, seating chart, reminder sends, caterer export. Households, plus-one rules, dietary notes, and multi-event RSVP status stay coherent across surfaces. AI proposes seating solutions when family and group constraints collide — and reaches guests via Twilio SMS, Telnyx fallback, or Resend email with tone-aware AI drafts (formal / friendly / casual) and a full delivery log per guest. Mailchimp audience, Zola RSVP, AllSeated — one record, one flow.",
    ai: true,
  },
  {
    id: 'guest-memories',
    icon: '📷',
    title: 'Guest Memories',
    category: 'Guest Pipeline',
    // TODO: replace with /guest_memories.png once captured; using gallery screenshot as closest proxy
    image: '/gallery_management.png',
    tagline: 'QR on the table → guests upload → couple reviews in the portal → export as a ZIP.',
    description:
      "Wedding day: 180 guests with phones, zero app downloads. Generate a QR sign from the planner dashboard, set it on the tables. Guests scan and upload photos and videos to a public link — no account, no app, up to 25 files per batch, tagged by event. If the link leaks, you rotate it from the portal mid-reception. Over the next week, the couple reviews each asset as kept / rejected / pending from their portal, filters by event or uploader, and exports any subset (kept-only, all, up to 5,000 assets) as a ZIP. Every asset lands on the same wedding record as the RSVPs, the gallery, and the seating chart. That's the entire WedShoots and Guest-a-Pic category, collapsed.",
    ai: false,
  },
  {
    id: 'inbox',
    icon: '📨',
    title: 'One Thread Per Couple',
    category: 'Communication',
    image: '/planner_inbox.png',
    tagline: 'Every couple conversation — DM, email, forwarded guest question — threaded against the right wedding.',
    description:
      "Today your couple-conversation history is scattered: iMessage on your phone, Gmail in your inbox, venue coordinator in Slack, a text from the mother-of-the-bride you can barely find. The Planner Inbox threads all of it against the wedding record. Inbound emails forwarded to your wedding address (via Resend with Svix signature verification) auto-thread into the right couple with full delivery tracking — sent, delivered, opened, clicked, bounced. The couple portal reads the same thread live. Web-push notifications fire when anything new lands. No more 'can you resend that message so I have it on record.'",
    ai: false,
  },
  {
    id: 'book-the-client',
    icon: '📝',
    title: 'Shop Window → Signed Contract → Saved Card',
    category: 'Business Engine',
    image: '/contract_canvas.png',
    tagline: 'Packages, contracts, and payment method capture — the entire booking funnel on one record.',
    description:
      "A lead comes in Tuesday. You need to quote, contract, and lock a card down by Friday so they don't drift to the next planner. Old stack: Squarespace for the package page, DocuSign for the contract, Stripe Checkout for the deposit, HoneyBook to tie it together. Here it's one arc. Publish tiered service packages with AI pricing guidance; preview exactly what the client sees before publishing. Draft contracts with AI-assisted clause generation and pull pricing from the package they chose. Send for e-signature via secure token links. On signature, a Stripe SetupIntent captures the payment method and the milestone schedule slots into the record. Every write — package, clause, signature, saved card — stays on the same couple record as the inbox thread and the dashboard.",
    ai: true,
  },
  {
    id: 'payments-autopilot',
    icon: '🤖',
    title: 'Payment Autopilot',
    category: 'Business Engine',
    image: '/payment_management.png',
    tagline: 'Stripe charges on schedule; failed payments retry on a 1 / 2 / 4 / 7-day backoff without your touch.',
    description:
      "Deposit is paid. Now it's six months of milestone invoices you either chase manually or watch slip into net-60. Payment Autopilot is a cron service that runs four times a day: it charges saved cards on milestone dates, sends reminders three days out, retries failed charges on a 1-day / 2-day / 4-day / 7-day backoff (max four attempts), and posts every outcome to an immutable log. Wedding date moves — the schedule recalculates automatically. A payment hits 402 — the autopilot status panel surfaces it to you before the couple notices. QuickBooks invoicing, Dubsado recurring charges, the manual Stripe dashboard — gone.",
    ai: false,
  },
  {
    id: 'budget',
    icon: '💰',
    title: 'Budget & Quote Negotiation',
    category: 'Business Engine',
    image: '/budget_management_dark_mode.png',
    tagline: "Category budgets that warn you before overruns, with AI that pressure-tests every vendor quote.",
    description:
      "Three quotes from three florists, three PDFs, and no easy way to compare whether $14,000 for centerpieces is market or a rip-off. Budget here isn't a spreadsheet — it's a quote-negotiation workflow. Apply a budget template to a wedding or let AI generate one from event type and guest count. Log vendor quotes against the right category; the `quotes/compare` endpoint pressure-tests them against historical data and flags the outlier. Planned-vs-actual spend reads from the same record as the contracts and payments it references, so overrun alerts fire before a line item ships — not after.",
    ai: true,
  },
  {
    id: 'vendor-network',
    icon: '🏛️',
    title: 'Vendor Network',
    category: 'Business Engine',
    // TODO: replace with /vendor_network.png once captured; reusing vendor management screenshot
    image: '/vendor_management.png',
    tagline: "Discover vendors in the public directory; run contract vendors in token-gated workspaces from your rolodex.",
    description:
      "Two separate vendor problems, one network. Public directory: browse photographers, venues, caterers, and florists inside the platform — no bouncing to The Knot or WeddingWire for discovery. Contract vendors: invite a photographer into a token-gated workspace for signatures, Stripe payouts, deliverables kanban with inline contract notes, and AI-assisted quote comparison — so the coordination happens against the same wedding record as the couple portal, not in a side thread of emails. Your private Vendor CRM keeps a rolodex of every vendor you've ever worked with: shared records, inline notes, payment history, file exchange, full collaboration log. Discovery, contracting, and recordkeeping stop being three separate universes.",
    ai: true,
    blogSlug: 'your-vendor-network-inside-the-platform',
  },
  {
    id: 'ai-intelligence',
    icon: '🧠',
    title: 'The Intelligence Layer',
    category: 'Intelligence',
    image: '/dashboard.png',
    tagline: "AI isn't a sprinkle — it's a metered product woven through every surface, with credits and usage tracking.",
    description:
      "Most planning tools bolt 'AI' onto one feature as a demo. Here it's a first-class product with over twenty endpoints and a credit meter: budget insights, seating optimization, communication drafting (tone-aware), progress reports, pricing suggestions, contract clause generation, vendor recommendations, task prioritization, timeline generation, payment forecasting, vendor quote analysis, chat, message and form-question generation. Every call tracks credits used, with structured error handling for rate limits, quota exhaustion, and service outages — so you know exactly what the AI costs before you run it. The intelligence is threaded into the workflows that need it, not pinned to a sidebar as a chatbot you have to open.",
    ai: true,
  },
  {
    id: 'forms',
    icon: '📋',
    title: 'Forms Canvas',
    category: 'Client Experience',
    image: '/forms_canvas.png',
    tagline: "Build intake, preference, and follow-up forms that land responses straight on the couple record.",
    description:
      "Onboarding a new couple used to mean a Typeform link, a CSV export, and an hour copying answers into your CRM. Drag-and-drop a form here — intake, design preferences, final approvals, post-event follow-up. AI suggests fields when you tell it the form's purpose. The couple fills it in from their portal; the response lands on the same record as their contract, inbox, and timeline. Built-in analytics show completion rates per wedding and per field. No Typeform bill, no Jotform export, no stale copies.",
    ai: true,
  },
  {
    id: 'team',
    icon: '🧑‍🤝‍🧑',
    title: 'Team, Permissions & Audit',
    category: 'Operations',
    image: '/planner_team_management.png',
    tagline: 'Invite teammates, scope them to specific weddings, and trace every action in the audit log.',
    description:
      "Your assistant joins in March and needs to run point on three weddings while staying out of the other eight. In HoneyBook that's a shared login and crossed fingers. Here you invite her, assign her to those three weddings, and set her permissions granularly across twelve+ areas: guests, budget, gallery, vendors, contracts, forms, memories, and more. Every action she takes — an edit, a send, a delete — writes to the activity audit log alongside your own. Your team scales without the nightmare of screenshots pasted into Slack.",
    ai: false,
  },
];
