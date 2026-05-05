/**
 * Phase C: Public marketing surface for the form template catalog.
 *
 * Server component — renders one card per template with name, description,
 * field count and a "Download as PDF" CTA. The CTA opens a client-side
 * email-gate modal (TemplatesClient) which posts to
 * ``POST /public/marketing/template-download``; the API records the lead
 * + UTM and dispatches the PDF by email.
 *
 * The catalog list is fetched server-side from
 * ``GET /admin/form-templates`` ... actually that endpoint is
 * planner-auth gated, so we hit ``GET /public/form-templates`` if it
 * exists, or render the list from a small static manifest committed
 * alongside the catalog.  The simplest answer: hit the same
 * ``/public/form-templates/{id}/preview.pdf`` endpoint per card for
 * the actual download — and use a small static manifest of names +
 * descriptions for the cards. That keeps this page fully static-
 * renderable without leaking auth surface.
 */

import TemplatesClient from './TemplatesClient';

// Small static manifest mirroring the python catalog.  Kept in sync by
// hand; the catalog test suite (test_form_template_catalog.py) is the
// source of truth — if a template is added there but not here, the
// marketing page simply doesn't surface it (acceptable: marketing is
// curated, not auto-populated).
const MARKETING_TEMPLATES: Array<{
  id: string;
  name: string;
  description: string;
  category: string;
  fieldCount: number;
}> = [
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

export const metadata = {
  title: 'Free Wedding Planner Templates — The Special Wedding',
  description:
    'Nine production-ready form templates for wedding planners — couple intake, order of events, vendor onboarding, dietary surveys, shot lists. Download as PDF, free.',
};

export default function PublicTemplatesPage() {
  return (
    <main className="min-h-screen bg-[#fbf9f6] py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <header className="text-center mb-12 sm:mb-16">
          <p className="text-sm font-medium uppercase tracking-wider text-[#6b5d4f] mb-3">
            Free for wedding planners
          </p>
          <h1 className="font-serif text-4xl sm:text-5xl text-[#1a1a1a] leading-tight">
            Templates we'd actually use ourselves.
          </h1>
          <p className="mt-5 max-w-2xl mx-auto text-lg text-[#555]">
            Nine production-ready form templates spanning the full planning
            lifecycle — couple intake to day-of emergency contacts. Download
            any as a printable PDF.
          </p>
          <p className="mt-3 text-sm text-[#9a8f82]">
            Each download lands in your inbox. No fluff.
          </p>
        </header>

        <TemplatesClient templates={MARKETING_TEMPLATES} />

        <footer className="mt-20 text-center">
          <p className="text-sm text-[#9a8f82]">
            Want to use these <em>live</em> with your couples — link
            distribution, response tracking, reminders?{' '}
            <a
              href="/saas?utm_source=template_marketing&utm_medium=footer"
              className="text-[#6b5d4f] font-semibold underline"
            >
              Start a free trial
            </a>
            {' '}— every template you've downloaded loads automatically.
          </p>
        </footer>
      </div>
    </main>
  );
}
