export const COMPARE_AUDIT_STAMP = 'April 6, 2026';
export const COMPARE_AUDIT_QUALIFIER = 'Verified against official competitor sources on April 6, 2026';

export type CompetitorSlug = 'honeybook' | 'aisle-planner';

export interface ComparisonRow {
  feature: string;
  specialWedding: string;
  honeybook: string;
  aislePlanner: string;
}

export interface ComparePageData {
  slug: CompetitorSlug;
  competitorName: string;
  pageTitle: string;
  metaDescription: string;
  heroEyebrow: string;
  heroTitle: string;
  heroSummary: string;
  heroSnapshot: string[];
  pricingSnapshot: string;
  differentiators: string[];
  auditNotes: string[];
  faq: Array<{
    question: string;
    answer: string;
  }>;
}

export const comparisonRows: ComparisonRow[] = [
  {
    feature: 'Guest Management & RSVPs',
    specialWedding: 'Built for wedding guest lists, RSVP states, plus-ones, and dietary notes.',
    honeybook: 'Adjacent: contact and client-workspace tooling exists, but the reviewed docs did not show a wedding-specific guest or RSVP workflow.',
    aislePlanner: 'Confirmed: guest list, RSVP summary, seating, and meal-selection workflows are documented in the reviewed help center.',
  },
  {
    feature: 'Client Portal / Couple Portal',
    specialWedding: 'Native couple portal with a shared dashboard, timeline, inbox, and payments.',
    honeybook: 'Adjacent: client portal, smart files, and payment workflows are documented, but not a wedding-specific couple portal.',
    aislePlanner: 'Adjacent: client-facing project and website workflows exist, but not the same couple-portal model.',
  },
  {
    feature: 'SMS & Email Reminders',
    specialWedding: 'SMS and email reminder flows with delivery tracking and fallback support.',
    honeybook: 'Adjacent: communication and scheduling flows are documented, but I did not find a cited SMS reminder or fallback workflow in the reviewed docs.',
    aislePlanner: 'Adjacent: reminder and communication tooling exists, but the reviewed docs did not show an explicit SMS reminder stack.',
  },
  {
    feature: 'Seating Charts',
    specialWedding: 'Drag-and-drop seating orchestration with AI-assisted placement logic.',
    honeybook: 'Not found in the reviewed source set.',
    aislePlanner: 'Confirmed for seating and layout canvas workflows; AI-assisted suggestions were not documented.',
  },
  {
    feature: 'AI Contract Generation & E-Sign',
    specialWedding: 'AI contract generation plus e-sign workflow for wedding-specific agreements.',
    honeybook: 'Adjacent: contracts and e-sign exist, but the reviewed docs did not show AI contract generation.',
    aislePlanner: 'Adjacent: contract and proposal lifecycle exists, but the reviewed docs did not show AI contract generation.',
  },
  {
    feature: 'Service Packages',
    specialWedding: 'AI pricing guidance and package-building support built into the workflow.',
    honeybook: 'Adjacent: AI and proposal workflows exist, but the reviewed docs did not show an explicit service-package builder.',
    aislePlanner: 'Not found in the reviewed source set.',
  },
  {
    feature: 'AI Cash Flow Predictions',
    specialWedding: 'Forecasting for milestone-based payments and expected cash flow.',
    honeybook: 'Not found: finance tools are documented, but explicit predictive cash-flow tooling was not shown.',
    aislePlanner: 'Not found in the reviewed source set.',
  },
  {
    feature: 'Budget Management',
    specialWedding: 'Category-based budgets, planned-vs-actual spend, and overrun forecasting.',
    honeybook: 'Adjacent: finances and reporting are documented, but explicit budgeting and forecasting were not shown.',
    aislePlanner: 'Confirmed for budget management; forecasting depth was not explicit in the reviewed docs.',
  },
  {
    feature: 'Photo Gallery & Guest QR Uploads',
    specialWedding: 'Guest memory uploads with QR-based entry and private review.',
    honeybook: 'Not found in the reviewed source set.',
    aislePlanner: 'Adjacent: wedding website and QR RSVP are documented, but guest photo uploads were not explicit.',
  },
  {
    feature: 'Vendor / Contact CRM',
    specialWedding: 'Vendor CRM with contracts, payments, and deliverables in one place.',
    honeybook: 'Adjacent: contact workspace plus payment tooling is documented, but not a wedding-vendor CRM as such.',
    aislePlanner: 'Confirmed / adjacent: vendor and payment workflows are documented, though the wording is broader than a strict CRM label.',
  },
  {
    feature: 'Custom Forms & Intake',
    specialWedding: 'Forms canvas with response analytics and reusable wedding workflows.',
    honeybook: 'Confirmed / adjacent: forms and questionnaires are documented; analytics depth varies by workflow.',
    aislePlanner: 'Confirmed / adjacent: lead contact forms and questionnaires are documented; analytics depth varies by workflow.',
  },
  {
    feature: 'Calendar Sync',
    specialWedding: 'Wedding calendar with Google sync support.',
    honeybook: 'Adjacent: scheduling is documented, but explicit Google sync was not shown in the reviewed sources.',
    aislePlanner: 'Confirmed: external calendar syncing with Google, Outlook, and Apple is documented.',
  },
  {
    feature: 'Team Management & Permissions',
    specialWedding: 'Role-based access with 12+ permissions for teams and agencies.',
    honeybook: 'Adjacent: team tiers are documented, but the reviewed sources did not show a granular 12+ permission model.',
    aislePlanner: 'Adjacent: collaboration exists, but the reviewed sources did not show the same permission granularity.',
  },
  {
    feature: 'Invoicing & Online Payments',
    specialWedding: 'Invoicing and online payment flow inside the platform.',
    honeybook: 'Confirmed for invoicing and payments. The reviewed pages did not name Stripe explicitly.',
    aislePlanner: 'Confirmed for invoicing and online payments. The reviewed pages did not name Stripe explicitly.',
  },
  {
    feature: 'Multi-Tenant Agency Tier',
    specialWedding: 'Agency tier for firms managing multiple weddings and teams.',
    honeybook: 'Adjacent: multi-company language exists, but the reviewed sources did not show a clearly branded agency tier.',
    aislePlanner: 'Not found in the reviewed source set.',
  },
  {
    feature: 'Vendor Advertising Portal',
    specialWedding: 'Vendor advertising portal for partner growth and placement.',
    honeybook: 'Not found in the reviewed source set.',
    aislePlanner: 'Not found in the reviewed source set.',
  },
  {
    feature: 'Day-of / Onsite Check-In',
    specialWedding: 'Touchless check-in for wedding-day operations.',
    honeybook: 'Not found in the reviewed source set.',
    aislePlanner: 'Not found in the reviewed source set.',
  },
];

const sharedFaq = [
  {
    question: 'Is this a live feature audit or a marketing page?',
    answer:
      'This page is a marketing comparison, but the claims were tightened against official vendor pricing and help-doc sources reviewed on April 6, 2026. It should still be re-checked before it becomes a source of record.',
  },
  {
    question: 'Why include an audit qualifier on the page?',
    answer:
      'Vendor feature sets move, and many rows are really adjacent capabilities rather than exact one-to-one matches. The qualifier keeps the page honest and makes room for future source-backed updates.',
  },
  {
    question: 'Where should a planner go next?',
    answer:
      'The feature page shows the full product surface area, and the resources hub gives the supporting blog and FAQ content that can reinforce the comparison story.',
  },
];

export const comparePageData: Record<CompetitorSlug, ComparePageData> = {
  'honeybook': {
    slug: 'honeybook',
    competitorName: 'HoneyBook',
    pageTitle: 'HoneyBook vs The Special Wedding',
    metaDescription:
      'A wedding-first comparison of HoneyBook vs The Special Wedding, updated against official HoneyBook sources reviewed on April 6, 2026. Compare client portal, AI workflows, pricing context, and more.',
    heroEyebrow: 'HoneyBook comparison page',
    heroTitle: 'HoneyBook vs The Special Wedding for wedding planners',
    heroSummary:
      'Use this page when a planner is deciding whether a broader CRM with portal and payment tooling is enough, or whether a wedding-first platform with a true couple portal, SMS reminders, and AI workflows makes more sense.',
    heroSnapshot: [
      'The Special Wedding is positioned as a wedding-first operating system.',
      'HoneyBook is strongest in the reviewed sources on client workspace, payments, forms, and automation.',
      'Official HoneyBook pricing reviewed on April 6, 2026 starts at $29/mo.',
    ],
    pricingSnapshot: 'HoneyBook: starts at $29/mo',
    differentiators: [
      'The Special Wedding keeps the couple portal front and center across onboarding, payments, and communication.',
      'SMS plus email reminders are treated as planner operations, not a separate communications add-on.',
      'AI sits inside contracts, package pricing, and cash flow instead of living beside the workflow.',
    ],
    auditNotes: [
      'Keep the portal row phrased carefully: HoneyBook has a client portal, but the reviewed sources did not show a wedding-specific couple portal.',
      'Do not publish an explicit SMS fallback claim for HoneyBook without a source that names it.',
      'If you mention Google Calendar sync, add a source first; the reviewed HoneyBook pages did not make that explicit.',
    ],
    faq: sharedFaq,
  },
  'aisle-planner': {
    slug: 'aisle-planner',
    competitorName: 'Aisle Planner',
    pageTitle: 'Aisle Planner vs The Special Wedding',
    metaDescription:
      'A wedding-first comparison of Aisle Planner vs The Special Wedding, updated against official Aisle Planner sources reviewed on April 6, 2026. Compare budgeting, seating, forms, pricing context, and wedding-specific workflows.',
    heroEyebrow: 'Aisle Planner comparison page',
    heroTitle: 'Aisle Planner vs The Special Wedding for wedding planners',
    heroSummary:
      'Use this page when a planner is comparing wedding-specific workflow depth: budgets, seating, forms, calendar sync, the couple portal story, and the operating model around them.',
    heroSnapshot: [
      'The Special Wedding is positioned as the planner operating system in the comparison table.',
      'Aisle Planner is strongest in the reviewed sources on guest management, seating, forms, contracts, and calendar sync.',
      'Official Aisle Planner pricing reviewed on April 6, 2026 starts at $49.99/mo.',
    ],
    pricingSnapshot: 'Aisle Planner: starts at $49.99/mo',
    differentiators: [
      'Budget management is paired with AI cash flow prediction instead of stopping at static tracking.',
      'The product surface combines guest workflows, couple communication, and day-of execution in one operating model.',
      'The reviewed Aisle Planner sources are strongest on planning workflows, but still stop short of the same couple portal and AI stack.',
    ],
    auditNotes: [
      'Do not overclaim the photo gallery row: the reviewed source set showed wedding website and QR RSVP, not explicit guest photo uploads.',
      'Keep the seating row focused on seating and layout, not AI suggestions.',
      'Calendar sync is a source-backed strength for Aisle Planner and should stay called out explicitly.',
    ],
    faq: sharedFaq,
  },
};

export function getComparePageData(slug: string): ComparePageData | null {
  return comparePageData[slug as CompetitorSlug] ?? null;
}

export function getCompareSupportedSlugs(): CompetitorSlug[] {
  return Object.keys(comparePageData) as CompetitorSlug[];
}

export function getCompareBreadcrumbs(competitorName?: string) {
  return [
    { name: 'Home', href: '/' },
    { name: 'Compare', href: '/compare' },
    ...(competitorName ? [{ name: competitorName, href: '' }] : []),
  ];
}
