import type { CompetitorSlug } from './data';

/**
 * Confidence level for a comparison evidence row.
 * - **High** — claim is directly backed by a reviewed source
 * - **Medium** — claim is inferred or partially backed
 * - **Low** — claim could not be verified in the reviewed source set
 */
export type EvidenceConfidence = 'High' | 'Medium' | 'Low';

export type CompareEvidenceSource = {
  code: string;
  label: string;
  url: string;
};

export type CompareEvidenceRow = {
  feature: string;
  confidence: EvidenceConfidence;
  note: string;
  sourceCodes: string[];
};

export type CompareEvidenceSet = {
  sources: CompareEvidenceSource[];
  rows: CompareEvidenceRow[];
};

const HONEYBOOK_SOURCES: CompareEvidenceSource[] = [
  { code: 'HB1', label: 'HoneyBook pricing', url: 'https://www.honeybook.com/pricing' },
  { code: 'HB2', label: 'HoneyBook client portal / smart files', url: 'https://help.honeybook.com/en/articles/4394789-set-a-custom-domain-for-your-client-portal-and-smart-files' },
  { code: 'HB3', label: 'HoneyBook contact workspace', url: 'https://help.honeybook.com/en/articles/7942562-find-and-use-the-contact-workspace' },
  { code: 'HB4', label: 'HoneyBook communication, scheduling, automations', url: 'https://help.honeybook.com/en/articles/2209147-communicating-through-honeybook' },
  { code: 'HB5', label: 'HoneyBook event planner page', url: 'https://www.honeybook.com/software-for-event-planners' },
  { code: 'HB6', label: 'HoneyBook invoice/payment page', url: 'https://www.honeybook.com/free-invoice-maker' },
  { code: 'HB7', label: 'HoneyBook meeting slots in email', url: 'https://help.honeybook.com/en/articles/9944552-embed-meeting-slots-in-your-emails' },
];

const AISLE_PLANNER_SOURCES: CompareEvidenceSource[] = [
  { code: 'AP1', label: 'Aisle Planner pricing', url: 'https://www.aisleplanner.com/pricing' },
  { code: 'AP2', label: 'Aisle Planner guest list download', url: 'https://help.aisleplanner.com/en/articles/2130230-downloading-your-guest-list' },
  { code: 'AP3', label: 'Aisle Planner layout canvas seating', url: 'https://help.aisleplanner.com/en/articles/2887342-viewing-guest-names-seat-numbers-meal-selections-on-your-layout-canvas' },
  { code: 'AP4', label: 'Aisle Planner wedding website / QR RSVP', url: 'https://help.aisleplanner.com/en/articles/2013039-how-to-create-an-event-or-wedding-website-in-aisle-planner' },
  { code: 'AP5', label: 'Aisle Planner calendar sync', url: 'https://help.aisleplanner.com/en/articles/10375834-ap-connect' },
  { code: 'AP6', label: 'Aisle Planner integrated account calendar', url: 'https://help.aisleplanner.com/en/articles/11786770-ap-connect-integrated-account-calendar' },
  { code: 'AP7', label: 'Aisle Planner lead contact forms', url: 'https://help.aisleplanner.com/en/articles/2210385-setting-up-your-lead-contact-form' },
  { code: 'AP8', label: 'Aisle Planner contract / proposal lifecycle', url: 'https://help.aisleplanner.com/en/articles/3128743-voiding-a-proposal-or-contract' },
  { code: 'AP9', label: 'Aisle Planner platform fees / online payments', url: 'https://help.aisleplanner.com/en/articles/3706461-platform-fees-offsetting-service-related-costs' },
];

const EVIDENCE_BY_COMPETITOR: Record<CompetitorSlug, CompareEvidenceSet> = {
  honeybook: {
    sources: HONEYBOOK_SOURCES,
    rows: [
      { feature: 'Guest Management & RSVPs', confidence: 'High', note: 'Adjacent: contact/workspace management exists, but no explicit guest manager or RSVP workflow.', sourceCodes: ['HB3', 'HB4'] },
      { feature: 'Client Portal / Couple Portal', confidence: 'High', note: 'Adjacent: client portal, smart files, and payments exist, but not a wedding-specific couple portal.', sourceCodes: ['HB2', 'HB3', 'HB4'] },
      { feature: 'SMS & Email Reminders', confidence: 'Medium', note: 'Adjacent: SMS reminders and automations exist, but fallback behavior is not source-backed.', sourceCodes: ['HB1', 'HB4'] },
      { feature: 'Seating Charts', confidence: 'High', note: 'Not found in the reviewed HoneyBook source set.', sourceCodes: ['HB1', 'HB5'] },
      { feature: 'AI Contract Generation & E-Sign', confidence: 'Medium', note: 'Adjacent: contracts/e-sign and HoneyBook AI exist, but no explicit AI contract generator was documented.', sourceCodes: ['HB1', 'HB5'] },
      { feature: 'Service Packages', confidence: 'Medium', note: 'Adjacent: AI and proposal flows exist, but no explicit package builder was documented.', sourceCodes: ['HB1', 'HB5'] },
      { feature: 'AI Cash Flow Predictions', confidence: 'Medium', note: 'Not found: finance tools exist, but explicit predictive cash-flow tooling was not documented.', sourceCodes: ['HB1', 'HB6'] },
      { feature: 'Budget Management', confidence: 'Medium', note: 'Adjacent: finances and reporting exist, but explicit budgeting/forecasting were not documented.', sourceCodes: ['HB1', 'HB6'] },
      { feature: 'Photo Gallery & Guest QR Uploads', confidence: 'Medium', note: 'Not found in the reviewed HoneyBook source set.', sourceCodes: ['HB1'] },
      { feature: 'Vendor / Contact CRM', confidence: 'Medium', note: 'Adjacent: contact workspace plus payment tooling exists, but not a wedding-vendor CRM as such.', sourceCodes: ['HB3', 'HB6'] },
      { feature: 'Custom Forms & Intake', confidence: 'High', note: 'Adjacent: forms, questionnaires, and reports exist, but analytics depth varies by workflow.', sourceCodes: ['HB1', 'HB4'] },
      { feature: 'Calendar Sync', confidence: 'High', note: 'Adjacent: scheduling exists, but explicit Google sync was not shown in the reviewed sources.', sourceCodes: ['HB1', 'HB7'] },
      { feature: 'Team Management & Permissions', confidence: 'High', note: 'Adjacent: team tiers exist, but the reviewed sources did not show granular 12+ permissions.', sourceCodes: ['HB1'] },
      { feature: 'Invoicing & Online Payments', confidence: 'High', note: 'Adjacent: invoicing and payments are explicit, but Stripe is not named on the reviewed pages.', sourceCodes: ['HB1', 'HB6'] },
      { feature: 'Multi-Tenant Agency Tier', confidence: 'Medium', note: 'Adjacent: teams and multiple collaborators exist, but not a clearly branded agency tier.', sourceCodes: ['HB1'] },
      { feature: 'Vendor Advertising Portal', confidence: 'High', note: 'Not found in the reviewed HoneyBook source set.', sourceCodes: ['HB1', 'HB5'] },
      { feature: 'Day-of / Onsite Check-In', confidence: 'Medium', note: 'Not found in the reviewed HoneyBook source set.', sourceCodes: ['HB1'] },
    ],
  },
  'aisle-planner': {
    sources: AISLE_PLANNER_SOURCES,
    rows: [
      { feature: 'Guest Management & RSVPs', confidence: 'High', note: 'Confirmed: guest list, RSVP summary, seating, and meal-selection workflows are documented.', sourceCodes: ['AP2', 'AP3'] },
      { feature: 'Client Portal / Couple Portal', confidence: 'High', note: 'Adjacent: client-facing project and website workflows exist, but not the same couple-portal model.', sourceCodes: ['AP1', 'AP4'] },
      { feature: 'SMS & Email Reminders', confidence: 'Medium', note: 'Adjacent: automated email responses and reminders exist, but explicit SMS evidence was not found.', sourceCodes: ['AP1', 'AP5', 'AP6'] },
      { feature: 'Seating Charts', confidence: 'High', note: 'Confirmed for seating and layout canvas workflows; AI suggestions were not documented.', sourceCodes: ['AP3'] },
      { feature: 'AI Contract Generation & E-Sign', confidence: 'Medium', note: 'Adjacent: contract and proposal lifecycle exists, but AI contract generation was not documented.', sourceCodes: ['AP1', 'AP8'] },
      { feature: 'Service Packages', confidence: 'Medium', note: 'Not found in the reviewed Aisle Planner source set.', sourceCodes: ['AP1', 'AP7'] },
      { feature: 'AI Cash Flow Predictions', confidence: 'Medium', note: 'Not found in the reviewed Aisle Planner source set.', sourceCodes: ['AP1', 'AP9'] },
      { feature: 'Budget Management', confidence: 'Medium', note: 'Confirmed for budget management; forecasting depth was not explicit in the reviewed docs.', sourceCodes: ['AP1', 'AP2', 'AP3'] },
      { feature: 'Photo Gallery & Guest QR Uploads', confidence: 'Medium', note: 'Adjacent: wedding website and QR RSVP are documented, but guest photo uploads were not explicit.', sourceCodes: ['AP4'] },
      { feature: 'Vendor / Contact CRM', confidence: 'Medium', note: 'Adjacent: vendor/contact and payment workflows are documented, though broader than a strict CRM label.', sourceCodes: ['AP1', 'AP9'] },
      { feature: 'Custom Forms & Intake', confidence: 'High', note: 'Adjacent: lead contact forms and questionnaires are documented; analytics depth varies by workflow.', sourceCodes: ['AP1', 'AP7'] },
      { feature: 'Calendar Sync', confidence: 'High', note: 'Confirmed: external calendar syncing with Google, Outlook, and Apple is documented.', sourceCodes: ['AP5', 'AP6'] },
      { feature: 'Team Management & Permissions', confidence: 'High', note: 'Adjacent: unlimited users and collaboration settings exist, but not the same permission granularity.', sourceCodes: ['AP1'] },
      { feature: 'Invoicing & Online Payments', confidence: 'High', note: 'Adjacent: invoicing and online payments are explicit, but Stripe is not named on the reviewed pages.', sourceCodes: ['AP1', 'AP9'] },
      { feature: 'Multi-Tenant Agency Tier', confidence: 'Medium', note: 'Not found in the reviewed Aisle Planner source set.', sourceCodes: ['AP1'] },
      { feature: 'Vendor Advertising Portal', confidence: 'High', note: 'Not found in the reviewed Aisle Planner source set.', sourceCodes: ['AP1'] },
      { feature: 'Day-of / Onsite Check-In', confidence: 'Medium', note: 'Not found: QR RSVP access exists, but not a dedicated check-in workflow.', sourceCodes: ['AP4'] },
    ],
  },
};

export function getCompareEvidence(slug: CompetitorSlug): CompareEvidenceSet {
  return EVIDENCE_BY_COMPETITOR[slug];
}

/* ------------------------------------------------------------------ *
 * Build-time validation: keep evidence rows in sync with comparison  *
 * rows. A mismatch here means a feature was added to one file but    *
 * not the other — TypeScript will surface this as a compile error.   *
 * ------------------------------------------------------------------ */
import { comparisonRows, getCompareSupportedSlugs } from './data';

const _comparisonFeatures = new Set(comparisonRows.map((r) => r.feature));

for (const slug of getCompareSupportedSlugs()) {
  const evidence = EVIDENCE_BY_COMPETITOR[slug];
  const evidenceFeatures = new Set(evidence.rows.map((r) => r.feature));

  Array.from(_comparisonFeatures).forEach((feature) => {
    if (!evidenceFeatures.has(feature)) {
      throw new Error(
        `[compare/evidence] Missing evidence row for "${feature}" in competitor "${slug}". ` +
        `Add an entry to EVIDENCE_BY_COMPETITOR['${slug}'].rows.`
      );
    }
  });

  Array.from(evidenceFeatures).forEach((feature) => {
    if (!_comparisonFeatures.has(feature)) {
      throw new Error(
        `[compare/evidence] Evidence row "${feature}" in competitor "${slug}" has no matching comparison row. ` +
        `Either add it to comparisonRows in data.ts or remove the evidence entry.`
      );
    }
  });
}
