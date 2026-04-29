export const COMPARE_AUDIT_STAMP = 'April 6, 2026';
export const COMPARE_AUDIT_QUALIFIER = 'Verified against official competitor sources on April 6, 2026';

export type CompetitorSlug =
  | 'honeybook'
  | 'aisle-planner'
  | 'dubsado'
  | 'zola'
  | 'the-knot'
  | 'planning-pod';

export interface ComparisonRow {
  feature: string;
  specialWedding: string;
  honeybook: string;
  aislePlanner: string;
  dubsado: string;
  zola: string;
  theKnot: string;
  planningPod: string;
}

/**
 * Maps a CompetitorSlug to the field name used in ComparisonRow. Keep in sync
 * with both the type union above and any change to ComparisonRow's keys.
 */
export const COMPARISON_ROW_KEY_BY_SLUG: Record<CompetitorSlug, keyof ComparisonRow> = {
  'honeybook': 'honeybook',
  'aisle-planner': 'aislePlanner',
  'dubsado': 'dubsado',
  'zola': 'zola',
  'the-knot': 'theKnot',
  'planning-pod': 'planningPod',
};

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
    dubsado: 'Adjacent: client management is documented, but no wedding-specific guest list or RSVP workflow was shown.',
    zola: 'Confirmed for couples: guest list and RSVP tools, but Zola is built for the couple, not for the planner managing multiple weddings.',
    theKnot: 'Confirmed for couples: guest list manager + RSVP tracking on TheKnot.com Wedding Planner, but couple-side, not planner-CRM.',
    planningPod: 'Confirmed for events generally: guest manager + RSVP tracking documented for weddings, galas, and conferences.',
  },
  {
    feature: 'Client Portal / Couple Portal',
    specialWedding: 'Native couple portal with a shared dashboard, timeline, inbox, and payments.',
    honeybook: 'Adjacent: client portal, smart files, and payment workflows are documented, but not a wedding-specific couple portal.',
    aislePlanner: 'Adjacent: client-facing project and website workflows exist, but not the same couple-portal model.',
    dubsado: 'Confirmed: client portal is a strength of Dubsado — branded, gated, and customizable, but not wedding-specific.',
    zola: 'Not applicable: Zola is the couple\'s tool — there is no separate planner-side portal layered on top.',
    theKnot: 'Not applicable: The Knot is consumer-facing; planners use it for vendor-side advertising, not client management.',
    planningPod: 'Adjacent: client-facing project access exists, but the reviewed positioning is event-generic, not wedding-couple-specific.',
  },
  {
    feature: 'SMS & Email Reminders',
    specialWedding: 'SMS and email reminder flows with delivery tracking and fallback support.',
    honeybook: 'Adjacent: communication and scheduling flows are documented, but I did not find a cited SMS reminder or fallback workflow in the reviewed docs.',
    aislePlanner: 'Adjacent: reminder and communication tooling exists, but the reviewed docs did not show an explicit SMS reminder stack.',
    dubsado: 'Adjacent: email automation and workflows are deep, but SMS is not natively documented.',
    zola: 'Adjacent: couples can send save-the-dates and reminders via Zola, but it is consumer-side flow, not a planner orchestration tool.',
    theKnot: 'Adjacent: reminder emails to guests exist, but planner-orchestrated SMS was not documented.',
    planningPod: 'Adjacent: communication tooling exists, but SMS-as-a-product was not documented.',
  },
  {
    feature: 'Seating Charts',
    specialWedding: 'Drag-and-drop seating orchestration with AI-assisted placement logic.',
    honeybook: 'Not found in the reviewed source set.',
    aislePlanner: 'Confirmed for seating and layout canvas workflows; AI-assisted suggestions were not documented.',
    dubsado: 'Not found in the reviewed source set.',
    zola: 'Confirmed for couples: seating chart tool exists, single-event, no multi-wedding portfolio.',
    theKnot: 'Confirmed for couples: seating chart tool exists, single-event, no multi-wedding portfolio.',
    planningPod: 'Confirmed: seating diagrams and event floor plans are documented as a core feature.',
  },
  {
    feature: 'AI Contract Generation & E-Sign',
    specialWedding: 'AI contract generation plus e-sign workflow for wedding-specific agreements.',
    honeybook: 'Adjacent: contracts and e-sign exist, but the reviewed docs did not show AI contract generation.',
    aislePlanner: 'Adjacent: contract and proposal lifecycle exists, but the reviewed docs did not show AI contract generation.',
    dubsado: 'Adjacent: contracts and e-sign are deeply customizable, but AI generation was not documented.',
    zola: 'Not applicable: Zola does not produce planner contracts.',
    theKnot: 'Not applicable: The Knot does not produce planner contracts.',
    planningPod: 'Adjacent: contracts and proposals are documented as features, but AI generation was not shown.',
  },
  {
    feature: 'Service Packages',
    specialWedding: 'AI pricing guidance and package-building support built into the workflow.',
    honeybook: 'Adjacent: AI and proposal workflows exist, but the reviewed docs did not show an explicit service-package builder.',
    aislePlanner: 'Not found in the reviewed source set.',
    dubsado: 'Confirmed: package and proposal builders are explicit, with strong customization, but no AI pricing layer was documented.',
    zola: 'Not applicable: Zola does not host planner service packages.',
    theKnot: 'Not applicable: The Knot does not host planner service packages.',
    planningPod: 'Confirmed: proposal builder with package templates is documented.',
  },
  {
    feature: 'AI Cash Flow Predictions',
    specialWedding: 'Forecasting for milestone-based payments and expected cash flow.',
    honeybook: 'Not found: finance tools are documented, but explicit predictive cash-flow tooling was not shown.',
    aislePlanner: 'Not found in the reviewed source set.',
    dubsado: 'Not found: invoicing and reporting are documented, but predictive cash-flow tooling was not shown.',
    zola: 'Not applicable.',
    theKnot: 'Not applicable.',
    planningPod: 'Not found in the reviewed source set.',
  },
  {
    feature: 'Budget Management',
    specialWedding: 'Category-based budgets, planned-vs-actual spend, and overrun forecasting.',
    honeybook: 'Adjacent: finances and reporting are documented, but explicit budgeting and forecasting were not shown.',
    aislePlanner: 'Confirmed for budget management; forecasting depth was not explicit in the reviewed docs.',
    dubsado: 'Adjacent: project totals and invoicing exist, but a wedding-style budget tracker was not documented.',
    zola: 'Confirmed for couples: budget tracker exists, single-event, no portfolio rollup.',
    theKnot: 'Confirmed for couples: budget tracker exists, single-event, no portfolio rollup.',
    planningPod: 'Confirmed: event budget tracking is documented, generic across event types.',
  },
  {
    feature: 'Photo Gallery & Guest QR Uploads',
    specialWedding: 'Guest memory uploads with QR-based entry and private review.',
    honeybook: 'Not found in the reviewed source set.',
    aislePlanner: 'Adjacent: wedding website and QR RSVP are documented, but guest photo uploads were not explicit.',
    dubsado: 'Not found in the reviewed source set.',
    zola: 'Adjacent: wedding website includes a photo section, but no QR-driven guest upload pipeline was documented.',
    theKnot: 'Adjacent: wedding website includes a photo section, but no QR-driven guest upload pipeline was documented.',
    planningPod: 'Not found in the reviewed source set.',
  },
  {
    feature: 'Vendor / Contact CRM',
    specialWedding: 'Vendor CRM with contracts, payments, and deliverables in one place.',
    honeybook: 'Adjacent: contact workspace plus payment tooling is documented, but not a wedding-vendor CRM as such.',
    aislePlanner: 'Confirmed / adjacent: vendor and payment workflows are documented, though the wording is broader than a strict CRM label.',
    dubsado: 'Adjacent: deep contact CRM exists for clients, but a wedding-vendor-specific subset was not documented.',
    zola: 'Adjacent: vendor marketplace exists for the couple, but not a vendor-CRM for the planner.',
    theKnot: 'Adjacent: massive vendor directory for couples, but no planner-side vendor CRM workflow.',
    planningPod: 'Confirmed: vendor management is documented as a feature, generic across event types.',
  },
  {
    feature: 'Custom Forms & Intake',
    specialWedding: 'Forms canvas with response analytics and reusable wedding workflows.',
    honeybook: 'Confirmed / adjacent: forms and questionnaires are documented; analytics depth varies by workflow.',
    aislePlanner: 'Confirmed / adjacent: lead contact forms and questionnaires are documented; analytics depth varies by workflow.',
    dubsado: 'Confirmed: forms and questionnaires are a documented strength, with logic and conditional fields.',
    zola: 'Not applicable: Zola does not provide planner intake forms.',
    theKnot: 'Not applicable: The Knot does not provide planner intake forms.',
    planningPod: 'Confirmed: form builder with proposals and questionnaires is documented.',
  },
  {
    feature: 'Calendar Sync',
    specialWedding: 'Wedding calendar with Google sync support.',
    honeybook: 'Adjacent: scheduling is documented, but explicit Google sync was not shown in the reviewed sources.',
    aislePlanner: 'Confirmed: external calendar syncing with Google, Outlook, and Apple is documented.',
    dubsado: 'Confirmed: calendar with Google sync is documented.',
    zola: 'Adjacent: countdown and event timeline exist for couples, but planner calendar sync is not applicable.',
    theKnot: 'Adjacent: countdown and event timeline exist for couples, but planner calendar sync is not applicable.',
    planningPod: 'Confirmed: calendar with sync to Google, Outlook, Apple is documented.',
  },
  {
    feature: 'Team Management & Permissions',
    specialWedding: 'Role-based access with 12+ permissions for teams and agencies.',
    honeybook: 'Adjacent: team tiers are documented, but the reviewed sources did not show a granular 12+ permission model.',
    aislePlanner: 'Adjacent: collaboration exists, but the reviewed sources did not show the same permission granularity.',
    dubsado: 'Adjacent: team members are supported, but the reviewed sources did not show a granular 12+ permission model.',
    zola: 'Not applicable: Zola is single-couple; no team or agency model.',
    theKnot: 'Not applicable: The Knot is consumer-facing; no team or agency model.',
    planningPod: 'Confirmed: user roles with permissions are documented, with seat-based pricing tiers.',
  },
  {
    feature: 'Invoicing & Online Payments',
    specialWedding: 'Invoicing and online payment flow inside the platform.',
    honeybook: 'Confirmed for invoicing and payments. The reviewed pages did not name Stripe explicitly.',
    aislePlanner: 'Confirmed for invoicing and online payments. The reviewed pages did not name Stripe explicitly.',
    dubsado: 'Confirmed: invoicing with Stripe + Square + PayPal is documented; ACH carries an extra fee.',
    zola: 'Not applicable: Zola does not provide planner invoicing.',
    theKnot: 'Not applicable: The Knot does not provide planner invoicing.',
    planningPod: 'Confirmed: invoicing and online payments are documented as core features.',
  },
  {
    feature: 'Multi-Tenant Agency Tier',
    specialWedding: 'Agency tier for firms managing multiple weddings and teams.',
    honeybook: 'Adjacent: multi-company language exists, but the reviewed sources did not show a clearly branded agency tier.',
    aislePlanner: 'Not found in the reviewed source set.',
    dubsado: 'Adjacent: brand-board branding is supported, but a clearly branded agency tier was not documented.',
    zola: 'Not applicable.',
    theKnot: 'Not applicable.',
    planningPod: 'Confirmed: agency-style tiers exist with multi-event and multi-user support.',
  },
  {
    feature: 'Vendor Advertising Portal',
    specialWedding: 'Vendor advertising portal for partner growth and placement.',
    honeybook: 'Not found in the reviewed source set.',
    aislePlanner: 'Not found in the reviewed source set.',
    dubsado: 'Not found in the reviewed source set.',
    zola: 'Confirmed for vendors: vendor marketplace and paid ad placement is documented.',
    theKnot: 'Confirmed for vendors: massive paid vendor directory is the core monetization model.',
    planningPod: 'Not found in the reviewed source set.',
  },
  {
    feature: 'Day-of / Onsite Check-In',
    specialWedding: 'Touchless check-in for wedding-day operations.',
    honeybook: 'Not found in the reviewed source set.',
    aislePlanner: 'Not found in the reviewed source set.',
    dubsado: 'Not found in the reviewed source set.',
    zola: 'Not applicable.',
    theKnot: 'Not applicable.',
    planningPod: 'Adjacent: event check-in tooling exists for events generally; not wedding-specific.',
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
  'dubsado': {
    slug: 'dubsado',
    competitorName: 'Dubsado',
    pageTitle: 'Dubsado vs The Special Wedding',
    metaDescription:
      'A wedding-first comparison of Dubsado vs The Special Wedding. Compare client portal depth, automation, package builders, payments, and where a wedding-specific platform pulls ahead of a generalist CRM.',
    heroEyebrow: 'Dubsado comparison page',
    heroTitle: 'Dubsado vs The Special Wedding for wedding planners',
    heroSummary:
      'Use this page when a planner is comparing the deepest customizable freelance CRM (Dubsado) against a wedding-first platform with a couple portal, seating, day-of execution, and AI woven through the workflow.',
    heroSnapshot: [
      'Dubsado is positioned as the deepest customizable client-management CRM for service businesses.',
      'The Special Wedding is wedding-first: couple portal, guest management, seating, and day-of execution live alongside contracts and payments.',
      'Dubsado pricing reviewed on April 6, 2026 starts around $20/mo (Starter) with Premier near $44/mo annual.',
    ],
    pricingSnapshot: 'Dubsado: Starter ~$20/mo, Premier ~$44/mo annual',
    differentiators: [
      'The Special Wedding ships a wedding-shaped guest list, RSVP, seating, and couple portal — Dubsado does not.',
      'AI is woven through contract drafting, package pricing, and cash flow forecasting instead of living as an add-on.',
      'Wedding-specific surfaces (microsite, guest memories, day-of check-in) replace the integration tax of bolting Squarespace, Wedibox, and a check-in app onto a generalist CRM.',
    ],
    auditNotes: [
      'Dubsado\'s strength is genuine — deep customization on forms, workflows, and brand boards. Do not understate it.',
      'Dubsado has no native mobile app; that is a meaningful planner-side gap to call out.',
      'Stripe + Square + PayPal payment options are documented; ACH carries an extra fee.',
    ],
    faq: sharedFaq,
  },
  'zola': {
    slug: 'zola',
    competitorName: 'Zola',
    pageTitle: 'Zola vs The Special Wedding',
    metaDescription:
      'Why a planner-side platform is not the same product category as a couple-side wedding planning tool. Zola serves the couple — The Special Wedding serves the planner running multiple weddings.',
    heroEyebrow: 'Zola comparison page',
    heroTitle: 'Zola vs The Special Wedding — different audiences, different products',
    heroSummary:
      'Zola is built for the couple planning their own wedding: free wedding website, registry, RSVP, guest list, budget tracker. The Special Wedding is built for the professional planner running multiple weddings, contracting vendors, billing clients, and orchestrating day-of operations.',
    heroSnapshot: [
      'Zola is consumer-side: a free, all-in-one toolkit for the couple themselves.',
      'The Special Wedding is planner-side: a paid SaaS for professional planners running 8-50+ weddings per year.',
      'These categories overlap on guest list and RSVP — but diverge sharply on contracting, billing, vendor CRM, team management, and day-of execution.',
    ],
    pricingSnapshot: 'Zola: free for couples; vendor advertising priced separately',
    differentiators: [
      'The Special Wedding is the planner\'s book of business: contracts, packages, invoicing, vendor CRM, team permissions, multi-wedding portfolio.',
      'Zola excels at consumer-facing wedding websites and registries — strengths The Special Wedding does not try to replicate one-for-one for the couple\'s public website.',
      'Couples who use Zola can still hire a planner who uses The Special Wedding; the two tools serve different sides of the same wedding.',
    ],
    auditNotes: [
      'Be honest that Zola is not a competitor in the planner-CRM category — the comparison exists for planners explaining the tooling delta to couples.',
      'Couples\' Zola accounts can stay; The Special Wedding\'s couple portal lives alongside, not in conflict.',
      'Zola\'s registry strength is genuine; The Special Wedding does not host registries, only links to them.',
    ],
    faq: sharedFaq,
  },
  'the-knot': {
    slug: 'the-knot',
    competitorName: 'The Knot',
    pageTitle: 'The Knot vs The Special Wedding',
    metaDescription:
      'The Knot is a consumer wedding directory with planning tools for couples. The Special Wedding is the planner-side operating system. Where they differ — and why a planner needs both.',
    heroEyebrow: 'The Knot comparison page',
    heroTitle: 'The Knot vs The Special Wedding for wedding planners',
    heroSummary:
      'The Knot is the largest consumer wedding aggregator: vendor directory, wedding website builder, planning tools, and a recently launched AI planning assistant — all aimed at couples. The Special Wedding is the platform a professional planner uses to run their book of business across many weddings.',
    heroSnapshot: [
      'The Knot is consumer-side and ad-funded: vendor advertising is the core monetization model.',
      'The Special Wedding is planner-side and subscription-funded: pro planners pay for the operating system; vendors pay separately for placement.',
      'A professional planner can hire vendors via The Knot and still need The Special Wedding for the back-office: contracts, scheduling, payments, day-of execution.',
    ],
    pricingSnapshot: 'The Knot: free for couples; vendors pay for advertising packages',
    differentiators: [
      'The Special Wedding is the planner\'s book-to-pay engine: package builder, contracts with e-sign, milestone payments, autopilot retries — none of which The Knot exposes.',
      'Vendor CRM, day-of execution, and team management are first-class; The Knot does not own these workflows.',
      'The Knot\'s AI planner serves couples; The Special Wedding\'s AI serves planners (contract drafting, pricing guidance, cash flow forecasting).',
    ],
    auditNotes: [
      'Acknowledge The Knot\'s scale honestly: it is the largest consumer wedding platform in the US.',
      'Do not position as "alternative" — position as "complementary": planners use both for different jobs.',
      'The Knot\'s 2025 AI planner launch is documented in industry coverage; do not overstate the depth before reviewing official sources.',
    ],
    faq: sharedFaq,
  },
  'planning-pod': {
    slug: 'planning-pod',
    competitorName: 'Planning Pod',
    pageTitle: 'Planning Pod vs The Special Wedding',
    metaDescription:
      'Planning Pod is event-generic software supporting weddings, galas, and corporate events. The Special Wedding is wedding-first, with couple portal, guest memories, and AI tuned for the planner running multiple weddings per year.',
    heroEyebrow: 'Planning Pod comparison page',
    heroTitle: 'Planning Pod vs The Special Wedding for wedding planners',
    heroSummary:
      'Planning Pod is the deepest event-management platform for planners running mixed event types — weddings, conferences, fundraisers. The Special Wedding is the wedding-only platform: couple portal, multicultural-multi-day support, guest memories, and AI woven through the planner\'s book-of-business workflow.',
    heroSnapshot: [
      'Planning Pod\'s strength is breadth: it supports weddings + corporate events + galas in one interface.',
      'The Special Wedding\'s strength is depth: every surface is wedding-specific (couple portal, RSVP, microsite, guest memories, day-of, multicultural-multi-day support).',
      'A planner running a 70/30 wedding/corporate split may stay with Planning Pod; a wedding-only planner gets a tighter fit on The Special Wedding.',
    ],
    pricingSnapshot: 'Planning Pod: tiers start around $19/mo, scaling with seats and event volume',
    differentiators: [
      'The Special Wedding is purpose-built for weddings — multicultural-multi-day modeling, couple portal, microsite, and guest memories are first-class.',
      'AI is wedding-shaped: contract drafting, pricing guidance, cash flow, and seating optimization — not generic event helpers.',
      'Planning Pod\'s breadth is a real advantage for planners with mixed event books; we don\'t pretend to compete there.',
    ],
    auditNotes: [
      'Be honest about Planning Pod\'s breadth — it is a real competitor in features like proposals, invoicing, and floor plans.',
      'Planning Pod\'s seating diagrams are documented; do not understate them.',
      'Pricing varies by tier and seats; the snapshot starts at the low end and scales.',
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
