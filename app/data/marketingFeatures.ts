export type MarketingFeature = {
  id: string;
  icon: string;
  title: string;
  category: string;
  image: string;
  tagline: string;
  description: string;
  ai: boolean;
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
    id: 'couple-portal',
    icon: '💍',
    title: 'Couple Portal',
    category: 'Client Experience',
    image: '/couple_portal_dashboard.png',
    tagline: 'A dedicated portal where couples manage their timeline, payments, forms, messages, memories, registry, and FAQs.',
    description:
      'Give every couple their own login with a curated dashboard, split-panel inbox with their planner, form submissions, payment history, photo memories, gift registry, and FAQ — so they stay in the loop without a single extra email.',
    ai: false,
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
    id: 'vendors',
    icon: '🤝',
    title: 'Vendor CRM',
    category: 'Business',
    image: '/vendor_management.png',
    tagline: 'Track contracts, owners, payments, and collaboration for every venue and vendor partner.',
    description:
      'Coordinate photographers, caterers, venues, and other partners with shared records, inline contract notes, payment tracking, file exchange, and a full collaboration history per vendor.',
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
