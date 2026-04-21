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

export const MARKETING_FEATURES: MarketingFeature[] = [
  {
    id: 'dashboard',
    icon: '📊',
    title: 'Planner Dashboard',
    category: 'Operations',
    image: '/dashboard.png',
    tagline: 'Portfolio health, AI insights, wedding progress, and recent activity in one command view.',
    description:
      'Run your book of business from a dashboard that highlights RSVP health, quick actions, AI insights, wedding progress, and the latest activity across active weddings.',
    ai: true,
  },
  {
    id: 'wedding-website',
    icon: '🌐',
    title: 'The Wedding Website, Built In',
    category: 'Experience',
    // TODO: replace with /wedding_microsite.png once captured from staging
    image: '/couple_portal_dashboard.png',
    tagline: 'Every wedding gets a branded public site with gallery, RSVP, and QR memory uploads — no Squarespace, no The Knot.',
    description:
      "Each wedding slug ships as a public microsite with the couple's branding, event schedule, gallery, RSVP flow, and guest memory uploads via QR. You stop paying for a separate wedding website builder and your couples stop maintaining one. All of it is wired to the same guest list, gallery, and RSVP data you already work in.",
    ai: false,
    blogSlug: 'the-built-in-wedding-website',
  },
  {
    id: 'couple-portal',
    icon: '💍',
    title: 'Couple Portal',
    category: 'Client Experience',
    image: '/couple_portal_dashboard.png',
    tagline: 'Give each couple a dedicated login where the whole wedding conversation lives.',
    description:
      'Give every couple their own login with a curated dashboard, split-panel inbox with their planner, form submissions, payment history, and photo memories — so the couple-planner conversation has one home instead of leaking across texts and email.',
    ai: false,
  },
  {
    id: 'couple-answers',
    icon: '💬',
    title: 'Everything Couples Ask, Already Answered',
    category: 'Client Experience',
    // TODO: replace with /couple_registry_faqs.png once captured; using existing registry screenshot
    image: '/couple_portal_registry.png',
    tagline: 'Registry, FAQs, meeting scheduler, memory wall, push notifications — so couples stop texting you the same five questions.',
    description:
      'The couple portal answers itself. Registry URLs, FAQ entries the couple maintains, a meeting scheduler for check-ins, a QR memory wall for guest photos, and real-time push notifications when anything changes. You stop being the human API between your couple and their plan, and they stop feeling out of the loop.',
    ai: false,
    blogSlug: 'why-your-couples-stop-texting-you',
  },
  {
    id: 'guests',
    icon: '👥',
    title: 'Guest Management',
    category: 'Planning',
    image: '/guest_management_view.png',
    tagline: 'Households, plus-ones, dietary notes, and RSVP status from one live guest list.',
    description:
      'Keep every guest record, household relationship, RSVP status, meal note, and plus-one rule in one searchable workspace built for multi-event weddings. Import from CSV or Google Sheets in seconds.',
    ai: false,
  },
  {
    id: 'seating',
    icon: '🪑',
    title: 'Seating Orchestrator',
    category: 'Planning',
    image: '/seating.png',
    tagline: 'Drag guests into sections and tables without losing family or group constraints.',
    description:
      'Build seating charts visually, preserve group rules, and rebalance counts fast when RSVPs shift close to the event. AI suggestions help resolve conflicts automatically.',
    ai: true,
  },
  {
    id: 'reminders',
    icon: '📲',
    title: 'SMS & Email Reminders',
    category: 'Communication',
    image: '/reminders.png',
    tagline: 'Send RSVP invites, reminders, and updates via SMS or email with AI-drafted messages and delivery tracking.',
    description:
      'Reach guests through Twilio, Telnyx, or Resend with tone-aware AI drafts (formal, friendly, casual), automatic SMS-to-email fallback, segmented targeting, and a full message log with delivery status.',
    ai: true,
  },
  {
    id: 'real-time',
    icon: '⚡',
    title: 'Real-Time Planning, Not Email Tag',
    category: 'Operations',
    // TODO: replace with /realtime_updates.png once captured; using planner inbox as proxy
    image: '/planner_inbox.png',
    tagline: 'Changes appear instantly, every action is logged, and inbound emails thread straight into the planner inbox.',
    description:
      'Server-sent events push updates to the couple portal the moment you save them — no refresh, no "did you get my email." An activity audit log captures every write so your team can trace who changed what. Inbound emails forwarded to your wedding address automatically thread into the planner inbox against the right couple. Planning stops being a sync-every-morning operation.',
    ai: false,
    blogSlug: 'real-time-planning-not-email-tag',
  },
  {
    id: 'contracts',
    icon: '📝',
    title: 'Contract Canvas',
    category: 'Business',
    image: '/contract_canvas.png',
    tagline: 'Draft polished agreements with AI-assisted clauses, placeholders, and e-sign support.',
    description:
      'Create contracts from scratch or templates, generate clauses with AI assistance, send for e-signature via secure token links, and keep signatures tied to the client record with full version history.',
    ai: true,
  },
  {
    id: 'packages',
    icon: '🏷️',
    title: 'Service Packages',
    category: 'Business',
    image: '/planner_package_preview.png',
    tagline: 'Publish bookable packages with AI pricing guidance and polished client-facing proposals.',
    description:
      'Package your services into clear tiers, preview how clients will see them, manage add-ons, and use AI suggestions to tighten positioning and pricing based on your market.',
    ai: true,
  },
  {
    id: 'vendor-network',
    icon: '🏛️',
    title: 'Your Vendor Network, Inside the Platform',
    category: 'Business',
    // TODO: replace with /vendor_network.png once captured; reusing vendor management screenshot
    image: '/vendor_management.png',
    tagline: 'Source from the public directory, advertise to planners via the ad portal, or collaborate through the contract portal — every vendor path lives here.',
    description:
      "The Special Wedding is also a vendor marketplace. Browse photographers, venues, and caterers in the public directory, invite contract vendors into token-based workspaces for signatures and payments, and let advertising vendors buy CPL campaigns that surface leads in your planner inbox. The vendor side of a wedding — discovery, contracting, payment, advertising — is not a separate universe anymore.",
    ai: false,
    blogSlug: 'your-vendor-network-inside-the-platform',
  },
  {
    id: 'vendors',
    icon: '🤝',
    title: 'Vendor CRM (Planner Side)',
    category: 'Business',
    image: '/vendor_management.png',
    tagline: 'Your private rolodex — track contracts, owners, payments, and collaboration for every venue and vendor partner.',
    description:
      'Separate from the public directory, the Vendor CRM is your private planner-side rolodex: coordinate photographers, caterers, venues, and other partners with shared records, inline contract notes, payment tracking, file exchange, and a full collaboration history per vendor.',
    ai: false,
  },
  {
    id: 'budget',
    icon: '💰',
    title: 'Budget Management',
    category: 'Finance',
    image: '/budget_management_dark_mode.png',
    tagline: 'Track budgets by category, compare planned vs. actual spend, and forecast costs across vendors.',
    description:
      'Create category-based budgets, track every expense against vendor costs, compare budget vs. actual in real time, and use AI to forecast where overruns are likely before they happen.',
    ai: true,
  },
  {
    id: 'payments',
    icon: '💳',
    title: 'Payment Management',
    category: 'Finance',
    image: '/payment_management.png',
    tagline: 'Track invoices, payment schedules, balances, and cash flow without a second finance tool.',
    description:
      'Manage incoming and outgoing payments, Stripe-connected billing, milestone-based schedules, due dates, and outstanding balances — with AI cash flow predictions from the same platform as the contract.',
    ai: true,
  },
  {
    id: 'inbox',
    icon: '📨',
    title: 'Planner Inbox',
    category: 'Communication',
    image: '/planner_inbox.png',
    tagline: 'Centralize planner-to-couple conversations instead of chasing texts and scattered email threads.',
    description:
      'Use the split-panel inbox to manage couple conversations, unread activity, and project updates in one shared communication channel — synced to the couple portal in real time.',
    ai: false,
  },
  {
    id: 'gallery',
    icon: '📸',
    title: 'Photo Gallery & Memories',
    category: 'Experience',
    image: '/gallery_management.png',
    tagline: 'Manage photo galleries, organize by event, and let guests upload memories via QR code.',
    description:
      'Upload and organize photos across folders (gallery, our-story, wedding-party), set featured images, and enable guest memory uploads via QR code — with private couple review before publishing.',
    ai: false,
  },
  {
    id: 'forms',
    icon: '📋',
    title: 'Forms Canvas',
    category: 'Experience',
    image: '/forms_canvas.png',
    tagline: 'Build intake forms, questionnaires, and approval flows with a drag-and-drop canvas.',
    description:
      'Design reusable forms for onboarding, design preferences, approvals, and post-event follow-up with AI-assisted field ideas and built-in response analytics.',
    ai: true,
  },
  {
    id: 'calendar',
    icon: '📅',
    title: 'Calendar & Google Sync',
    category: 'Planning',
    image: '/calendar_management.png',
    tagline: 'Plan every milestone with a shared calendar that syncs to Google Calendar automatically.',
    description:
      'Manage planning tasks, vendor meetings, and event milestones from one calendar view with two-way Google Calendar sync so nothing falls through the cracks.',
    ai: false,
  },
  {
    id: 'team',
    icon: '🧑‍🤝‍🧑',
    title: 'Team Management',
    category: 'Operations',
    image: '/planner_team_management.png',
    tagline: 'Assign wedding access and granular permissions so every planner sees the right work.',
    description:
      'Invite team members, assign them to specific weddings, control 12+ granular permissions (guests, budget, gallery, vendors, contracts, forms, and more), and track all team activity in a full audit log.',
    ai: false,
  },
  {
    id: 'config',
    icon: '⚙️',
    title: 'Wedding Configuration',
    category: 'Setup',
    image: '/wedding_config1.png',
    tagline: 'Tailor each wedding with custom branding, events, privacy, and RSVP behavior.',
    description:
      'Configure each wedding independently — custom colors, fonts, background styles, event types, privacy controls, RSVP rules, and branded presentation for both the couple portal and guest-facing pages.',
    ai: false,
  },
  {
    id: 'analytics',
    icon: '📈',
    title: 'Analytics & Metrics',
    category: 'Operations',
    image: '/dashboard.png',
    tagline: 'Track RSVP velocity, engagement signals, form completion rates, and platform health in real time.',
    description:
      'Monitor weekly/monthly active users, activation funnels, retention cohorts, RSVP turnaround trends, response rates, and form analytics — all built in so you never need a separate analytics tool.',
    ai: false,
  },
  {
    id: 'knowledge',
    icon: '📚',
    title: 'Knowledge Base',
    category: 'Support',
    image: '/knowledgebase.png',
    tagline: 'Support planners and teams with searchable guides, FAQs, and self-serve documentation.',
    description:
      'Publish internal and client-facing help content so teams onboard faster and couples can answer common questions without extra support load.',
    ai: false,
  },
];
