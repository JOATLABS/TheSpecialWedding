/**
 * Canonical client-side manifest of the 9 free marketing templates.
 *
 * Exported from one place so the public templates page, the blog
 * "Related templates" card, and any future surface (homepage band,
 * resources hub tile, etc.) all reference identical names + copy.
 *
 * This mirrors a curated subset of `FORM_TEMPLATES` in
 * `app/services/form_template_catalog.py`. The Python catalog is the
 * source of truth for the underlying form; this manifest is the
 * source of truth for marketing copy.
 *
 * Adding a template: add its row here AND in the Python catalog. The
 * `id` must match the Python catalog `id` so deep links to
 * `/resources/templates#<id>` work.
 */
export interface MarketingTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  fieldCount: number;
}

export const MARKETING_TEMPLATES: MarketingTemplate[] = [
  {
    id: 'couple_intake',
    name: 'Couple Intake Questionnaire',
    description:
      'Capture everything you need from a new couple in one go: names, vision, guest count, budget range, must-haves, and traditions to honour.',
    category: 'Intake',
    fieldCount: 17,
  },
  {
    id: 'order_of_events',
    name: 'Wedding Day Order of Events',
    description:
      'The minute-by-minute timeline shared with the couple, MC, and every vendor — ceremony milestones, reception flow, and song cues.',
    category: 'Timeline',
    fieldCount: 18,
  },
  {
    id: 'guest_dietary_access',
    name: 'Guest Dietary & Access Survey',
    description:
      'Send to every confirmed guest 60 days out. Captures dietary needs, allergies, accessibility, and child-seat counts.',
    category: 'Guest',
    fieldCount: 9,
  },
  {
    id: 'vendor_onboarding',
    name: 'Vendor Onboarding Brief',
    description:
      'The packet every newly-contracted vendor fills out — legal info, day-of contact, COI upload, setup / breakdown windows.',
    category: 'Vendor',
    fieldCount: 14,
  },
  {
    id: 'photo_video_shot_list',
    name: 'Photographer & Videographer Shot List',
    description:
      'The single source of truth for what the couple wants captured — family combinations, must-have moments, getting-ready locations.',
    category: 'Creative',
    fieldCount: 10,
  },
  {
    id: 'bridal_party_logistics',
    name: 'Wedding Party Logistics',
    description:
      'One form per member of the wedding party — hair / makeup slots, attire pickup, transport groups, after-party RSVPs.',
    category: 'Bridal Party',
    fieldCount: 9,
  },
  {
    id: 'vendor_performance_review',
    name: 'Vendor Performance Review',
    description:
      "Planner-internal review of each vendor after the wedding — feeds your own rolodex with would-rebook flags and notes.",
    category: 'Vendor',
    fieldCount: 11,
  },
  {
    id: 'engagement_session_brief',
    name: 'Engagement Session Brief',
    description:
      'Quick form for the couple to scope the engagement shoot — locations, outfits, vibe, must-include shots.',
    category: 'Creative',
    fieldCount: 8,
  },
  {
    id: 'day_of_emergency_contacts',
    name: 'Day-Of Emergency Contact Sheet',
    description:
      'One short form per critical contact. Combine the responses into the single laminated sheet on every vendor’s clipboard.',
    category: 'Timeline',
    fieldCount: 8,
  },
];

export function getMarketingTemplate(id: string): MarketingTemplate | undefined {
  return MARKETING_TEMPLATES.find((t) => t.id === id);
}

export function getMarketingTemplates(ids: readonly string[]): MarketingTemplate[] {
  return ids
    .map((id) => getMarketingTemplate(id))
    .filter((t): t is MarketingTemplate => Boolean(t));
}
