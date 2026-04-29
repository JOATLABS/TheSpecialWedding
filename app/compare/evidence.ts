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

const DUBSADO_SOURCES: CompareEvidenceSource[] = [
  { code: 'DS1', label: 'Dubsado pricing', url: 'https://www.dubsado.com/pricing' },
  { code: 'DS2', label: 'Dubsado workflow + automation', url: 'https://help.dubsado.com/hc/en-us/categories/360002073634-Workflows' },
  { code: 'DS3', label: 'Dubsado client portal', url: 'https://help.dubsado.com/hc/en-us/sections/360010036793-Client-Portal' },
  { code: 'DS4', label: 'Dubsado proposals + packages', url: 'https://help.dubsado.com/hc/en-us/sections/360011199314-Proposals' },
];

const ZOLA_SOURCES: CompareEvidenceSource[] = [
  { code: 'ZL1', label: 'Zola wedding planning tools (couple-side)', url: 'https://www.zola.com/wedding-planning' },
  { code: 'ZL2', label: 'Zola vendor marketplace', url: 'https://www.zola.com/wedding-vendors' },
  { code: 'ZL3', label: 'Zola wedding website builder', url: 'https://www.zola.com/wedding-planning/wedding-websites' },
];

const THE_KNOT_SOURCES: CompareEvidenceSource[] = [
  { code: 'TK1', label: 'The Knot wedding planning hub', url: 'https://www.theknot.com/content/wedding-planning' },
  { code: 'TK2', label: 'The Knot wedding website builder', url: 'https://www.theknot.com/wedding-websites' },
  { code: 'TK3', label: 'The Knot vendor advertising / marketplace', url: 'https://www.theknot.com/wedding-vendors' },
];

const PLANNING_POD_SOURCES: CompareEvidenceSource[] = [
  { code: 'PP1', label: 'Planning Pod pricing', url: 'https://www.planningpod.com/pricing' },
  { code: 'PP2', label: 'Planning Pod features', url: 'https://www.planningpod.com/features' },
  { code: 'PP3', label: 'Planning Pod seating + floor plans', url: 'https://www.planningpod.com/seating-arrangement-chart-software.cfm' },
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
  'dubsado': {
    sources: DUBSADO_SOURCES,
    rows: [
      { feature: 'Guest Management & RSVPs', confidence: 'Medium', note: 'Not found: client management is documented but no wedding-specific guest list / RSVP workflow.', sourceCodes: ['DS1', 'DS3'] },
      { feature: 'Client Portal / Couple Portal', confidence: 'High', note: 'Confirmed: client portal is a documented strength, branded and customizable.', sourceCodes: ['DS3'] },
      { feature: 'SMS & Email Reminders', confidence: 'Medium', note: 'Adjacent: email automation is deep, but native SMS reminders were not documented.', sourceCodes: ['DS2'] },
      { feature: 'Seating Charts', confidence: 'Medium', note: 'Not found in the reviewed Dubsado source set.', sourceCodes: ['DS1', 'DS2'] },
      { feature: 'AI Contract Generation & E-Sign', confidence: 'Medium', note: 'Adjacent: contracts and e-sign are highly customizable, but AI generation was not documented.', sourceCodes: ['DS4'] },
      { feature: 'Service Packages', confidence: 'High', note: 'Confirmed: package and proposal builders are documented with strong customization.', sourceCodes: ['DS4'] },
      { feature: 'AI Cash Flow Predictions', confidence: 'Medium', note: 'Not found: invoicing exists, but predictive cash-flow tooling was not documented.', sourceCodes: ['DS1'] },
      { feature: 'Budget Management', confidence: 'Medium', note: 'Adjacent: project totals exist; a wedding-style budget tracker was not documented.', sourceCodes: ['DS1'] },
      { feature: 'Photo Gallery & Guest QR Uploads', confidence: 'Medium', note: 'Not found in the reviewed Dubsado source set.', sourceCodes: ['DS1'] },
      { feature: 'Vendor / Contact CRM', confidence: 'Medium', note: 'Adjacent: deep contact CRM exists; wedding-vendor-specific subset was not documented.', sourceCodes: ['DS2', 'DS3'] },
      { feature: 'Custom Forms & Intake', confidence: 'High', note: 'Confirmed: forms with logic and conditional fields are documented as a strength.', sourceCodes: ['DS2', 'DS4'] },
      { feature: 'Calendar Sync', confidence: 'Medium', note: 'Confirmed: calendar with Google sync is documented in vendor-public materials.', sourceCodes: ['DS1', 'DS2'] },
      { feature: 'Team Management & Permissions', confidence: 'Medium', note: 'Adjacent: team members supported, but a granular 12+ permission model was not documented.', sourceCodes: ['DS1'] },
      { feature: 'Invoicing & Online Payments', confidence: 'High', note: 'Confirmed: Stripe + Square + PayPal documented; ACH carries an extra fee.', sourceCodes: ['DS1', 'DS4'] },
      { feature: 'Multi-Tenant Agency Tier', confidence: 'Medium', note: 'Adjacent: brand-board branding exists; a clearly branded agency tier was not documented.', sourceCodes: ['DS1'] },
      { feature: 'Vendor Advertising Portal', confidence: 'High', note: 'Not found in the reviewed Dubsado source set.', sourceCodes: ['DS1'] },
      { feature: 'Day-of / Onsite Check-In', confidence: 'Medium', note: 'Not found in the reviewed Dubsado source set.', sourceCodes: ['DS1'] },
    ],
  },
  'zola': {
    sources: ZOLA_SOURCES,
    rows: [
      { feature: 'Guest Management & RSVPs', confidence: 'High', note: 'Confirmed for couples: guest list and RSVP tools, but not a planner-side multi-wedding system.', sourceCodes: ['ZL1', 'ZL3'] },
      { feature: 'Client Portal / Couple Portal', confidence: 'High', note: 'Not applicable: Zola is the couple\'s tool; there is no separate planner portal.', sourceCodes: ['ZL1'] },
      { feature: 'SMS & Email Reminders', confidence: 'Medium', note: 'Adjacent: couple-side reminders exist; planner orchestration is not applicable.', sourceCodes: ['ZL3'] },
      { feature: 'Seating Charts', confidence: 'High', note: 'Confirmed for couples: seating chart tool exists, single-event scope.', sourceCodes: ['ZL1'] },
      { feature: 'AI Contract Generation & E-Sign', confidence: 'High', note: 'Not applicable: Zola does not produce planner contracts.', sourceCodes: ['ZL1'] },
      { feature: 'Service Packages', confidence: 'High', note: 'Not applicable: Zola does not host planner service packages.', sourceCodes: ['ZL1'] },
      { feature: 'AI Cash Flow Predictions', confidence: 'High', note: 'Not applicable.', sourceCodes: ['ZL1'] },
      { feature: 'Budget Management', confidence: 'High', note: 'Confirmed for couples: budget tracker exists; single-event, no portfolio rollup.', sourceCodes: ['ZL1'] },
      { feature: 'Photo Gallery & Guest QR Uploads', confidence: 'Medium', note: 'Adjacent: wedding website includes a photo section; QR-driven uploads not documented.', sourceCodes: ['ZL3'] },
      { feature: 'Vendor / Contact CRM', confidence: 'High', note: 'Adjacent: vendor marketplace for the couple, not a planner-side CRM.', sourceCodes: ['ZL2'] },
      { feature: 'Custom Forms & Intake', confidence: 'High', note: 'Not applicable: Zola does not provide planner intake forms.', sourceCodes: ['ZL1'] },
      { feature: 'Calendar Sync', confidence: 'Medium', note: 'Adjacent: couple-side countdown and timeline; planner calendar sync not applicable.', sourceCodes: ['ZL1'] },
      { feature: 'Team Management & Permissions', confidence: 'High', note: 'Not applicable: single-couple tool, no team or agency model.', sourceCodes: ['ZL1'] },
      { feature: 'Invoicing & Online Payments', confidence: 'High', note: 'Not applicable: Zola does not provide planner invoicing.', sourceCodes: ['ZL1'] },
      { feature: 'Multi-Tenant Agency Tier', confidence: 'High', note: 'Not applicable.', sourceCodes: ['ZL1'] },
      { feature: 'Vendor Advertising Portal', confidence: 'High', note: 'Confirmed for vendors: paid ad placement in vendor marketplace is documented.', sourceCodes: ['ZL2'] },
      { feature: 'Day-of / Onsite Check-In', confidence: 'High', note: 'Not applicable.', sourceCodes: ['ZL1'] },
    ],
  },
  'the-knot': {
    sources: THE_KNOT_SOURCES,
    rows: [
      { feature: 'Guest Management & RSVPs', confidence: 'High', note: 'Confirmed for couples: guest list and RSVP tracker on TheKnot.com, but couple-side, not planner-CRM.', sourceCodes: ['TK1', 'TK2'] },
      { feature: 'Client Portal / Couple Portal', confidence: 'High', note: 'Not applicable: The Knot is consumer-facing; planners use it for vendor-side placement, not client management.', sourceCodes: ['TK1'] },
      { feature: 'SMS & Email Reminders', confidence: 'Medium', note: 'Adjacent: couple-side reminders to guests; planner orchestration not applicable.', sourceCodes: ['TK2'] },
      { feature: 'Seating Charts', confidence: 'High', note: 'Confirmed for couples: seating chart tool exists, single-event scope.', sourceCodes: ['TK1'] },
      { feature: 'AI Contract Generation & E-Sign', confidence: 'High', note: 'Not applicable: The Knot does not produce planner contracts.', sourceCodes: ['TK1'] },
      { feature: 'Service Packages', confidence: 'High', note: 'Not applicable: The Knot does not host planner service packages.', sourceCodes: ['TK1'] },
      { feature: 'AI Cash Flow Predictions', confidence: 'High', note: 'Not applicable.', sourceCodes: ['TK1'] },
      { feature: 'Budget Management', confidence: 'High', note: 'Confirmed for couples: budget tracker exists; single-event, no portfolio rollup.', sourceCodes: ['TK1'] },
      { feature: 'Photo Gallery & Guest QR Uploads', confidence: 'Medium', note: 'Adjacent: wedding website includes photo section; QR-driven uploads not documented.', sourceCodes: ['TK2'] },
      { feature: 'Vendor / Contact CRM', confidence: 'High', note: 'Adjacent: massive vendor directory for couples; no planner-side vendor CRM.', sourceCodes: ['TK3'] },
      { feature: 'Custom Forms & Intake', confidence: 'High', note: 'Not applicable: The Knot does not provide planner intake forms.', sourceCodes: ['TK1'] },
      { feature: 'Calendar Sync', confidence: 'Medium', note: 'Adjacent: couple-side countdown; planner calendar sync not applicable.', sourceCodes: ['TK1'] },
      { feature: 'Team Management & Permissions', confidence: 'High', note: 'Not applicable: consumer-facing, no team or agency model.', sourceCodes: ['TK1'] },
      { feature: 'Invoicing & Online Payments', confidence: 'High', note: 'Not applicable: The Knot does not provide planner invoicing.', sourceCodes: ['TK1'] },
      { feature: 'Multi-Tenant Agency Tier', confidence: 'High', note: 'Not applicable.', sourceCodes: ['TK1'] },
      { feature: 'Vendor Advertising Portal', confidence: 'High', note: 'Confirmed for vendors: paid vendor directory is the core monetization model.', sourceCodes: ['TK3'] },
      { feature: 'Day-of / Onsite Check-In', confidence: 'High', note: 'Not applicable.', sourceCodes: ['TK1'] },
    ],
  },
  'planning-pod': {
    sources: PLANNING_POD_SOURCES,
    rows: [
      { feature: 'Guest Management & RSVPs', confidence: 'High', note: 'Confirmed for events generally: guest manager + RSVP tracking documented.', sourceCodes: ['PP2'] },
      { feature: 'Client Portal / Couple Portal', confidence: 'Medium', note: 'Adjacent: client-facing project access exists; positioning is event-generic, not wedding-couple-specific.', sourceCodes: ['PP2'] },
      { feature: 'SMS & Email Reminders', confidence: 'Medium', note: 'Adjacent: communication tooling exists, but SMS-as-a-product not documented.', sourceCodes: ['PP2'] },
      { feature: 'Seating Charts', confidence: 'High', note: 'Confirmed: seating diagrams and event floor plans are documented as a core feature.', sourceCodes: ['PP3'] },
      { feature: 'AI Contract Generation & E-Sign', confidence: 'Medium', note: 'Adjacent: contracts and proposals are documented; AI generation not shown.', sourceCodes: ['PP2'] },
      { feature: 'Service Packages', confidence: 'High', note: 'Confirmed: proposal builder with package templates is documented.', sourceCodes: ['PP2'] },
      { feature: 'AI Cash Flow Predictions', confidence: 'Medium', note: 'Not found in the reviewed Planning Pod source set.', sourceCodes: ['PP2'] },
      { feature: 'Budget Management', confidence: 'High', note: 'Confirmed: event budget tracking documented, generic across event types.', sourceCodes: ['PP2'] },
      { feature: 'Photo Gallery & Guest QR Uploads', confidence: 'Medium', note: 'Not found in the reviewed Planning Pod source set.', sourceCodes: ['PP2'] },
      { feature: 'Vendor / Contact CRM', confidence: 'High', note: 'Confirmed: vendor management documented, generic across event types.', sourceCodes: ['PP2'] },
      { feature: 'Custom Forms & Intake', confidence: 'High', note: 'Confirmed: form builder with proposals and questionnaires is documented.', sourceCodes: ['PP2'] },
      { feature: 'Calendar Sync', confidence: 'High', note: 'Confirmed: calendar with sync to Google, Outlook, Apple is documented.', sourceCodes: ['PP2'] },
      { feature: 'Team Management & Permissions', confidence: 'High', note: 'Confirmed: user roles with permissions, seat-based pricing tiers documented.', sourceCodes: ['PP1', 'PP2'] },
      { feature: 'Invoicing & Online Payments', confidence: 'High', note: 'Confirmed: invoicing and online payments documented as core features.', sourceCodes: ['PP2'] },
      { feature: 'Multi-Tenant Agency Tier', confidence: 'High', note: 'Confirmed: agency-style tiers exist with multi-event and multi-user support.', sourceCodes: ['PP1'] },
      { feature: 'Vendor Advertising Portal', confidence: 'High', note: 'Not found in the reviewed Planning Pod source set.', sourceCodes: ['PP2'] },
      { feature: 'Day-of / Onsite Check-In', confidence: 'Medium', note: 'Adjacent: event check-in tooling exists for events generally; not wedding-specific.', sourceCodes: ['PP2'] },
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
