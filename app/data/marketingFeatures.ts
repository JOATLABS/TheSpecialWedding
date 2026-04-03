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
    id: 'guests',
    icon: '👥',
    title: 'Guest Management',
    category: 'Planning',
    image: '/guest_management_view.png',
    tagline: 'Households, plus-ones, dietary notes, and RSVP status from one live guest list.',
    description:
      'Keep every guest record, household relationship, RSVP status, meal note, and plus-one rule in one searchable workspace built for multi-event weddings.',
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
      'Build seating charts visually, preserve group rules, and rebalance counts fast when RSVPs shift close to the event.',
    ai: false,
  },
  {
    id: 'contracts',
    icon: '📝',
    title: 'Contract Canvas',
    category: 'Business',
    image: '/contract_canvas.png',
    tagline: 'Draft polished agreements with AI-assisted clauses, placeholders, and e-sign support.',
    description:
      'Create contracts from scratch or templates, generate clauses with AI assistance, and keep signatures tied to the client record.',
    ai: true,
  },
  {
    id: 'packages',
    icon: '🏷️',
    title: 'Service Packages',
    category: 'Business',
    image: '/planner_package_preview.png',
    tagline: 'Publish bookable packages with pricing guidance and polished proposal flows.',
    description:
      'Package your services into clear tiers, preview how clients will see them, and use AI suggestions to tighten positioning and pricing.',
    ai: true,
  },
  {
    id: 'vendors',
    icon: '🤝',
    title: 'Vendor CRM',
    category: 'Business',
    image: '/vendor_management.png',
    tagline: 'Track contracts, owners, and collaboration for every venue and vendor partner.',
    description:
      'Coordinate photographers, caterers, venues, and other partners with shared records, responsibilities, payments, and collaboration history.',
    ai: false,
  },
  {
    id: 'inbox',
    icon: '📨',
    title: 'Planner Inbox',
    category: 'Communication',
    image: '/planner_inbox.png',
    tagline: 'Centralize planner-to-couple conversations instead of chasing texts and scattered email threads.',
    description:
      'Use the split-panel inbox to manage couple conversations, unread activity, and project updates in one shared communication channel.',
    ai: false,
  },
  {
    id: 'couple-portal',
    icon: '💍',
    title: 'Couple Portal',
    category: 'Client Experience',
    image: '/couple_portal_dashboard.png',
    tagline: 'Give couples a clean portal for updates, forms, payments, FAQs, and their timeline.',
    description:
      'Let couples review their dashboard, forms, contracts, payments, FAQ content, and planner updates from one curated portal.',
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
      'Design reusable forms for onboarding, design preferences, approvals, and post-event follow-up with AI-assisted field ideas.',
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
      'Manage incoming and outgoing payments, Stripe-connected billing, due dates, and outstanding balances from the same platform as the contract.',
    ai: true,
  },
  {
    id: 'team',
    icon: '🧑‍🤝‍🧑',
    title: 'Team Management',
    category: 'Operations',
    image: '/planner_team_management.png',
    tagline: 'Assign wedding access and roles so every planner sees the right work at the right time.',
    description:
      'Control team member access by assignment, keep permissions scoped, and scale planner operations without losing visibility.',
    ai: false,
  },
  {
    id: 'config',
    icon: '⚙️',
    title: 'Wedding Configuration',
    category: 'Setup',
    image: '/wedding_config1.png',
    tagline: 'Tailor each wedding with custom settings for events, branding, privacy, and RSVP behavior.',
    description:
      'Configure each wedding independently with event details, experience settings, privacy controls, and branded presentation.',
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
