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

import type { Metadata } from 'next';

import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';

import { MARKETING_TEMPLATES } from './manifest';
import TemplatesClient from './TemplatesClient';

const SITE_ORIGIN = 'https://thespecialwedding.io';
const PAGE_PATH = '/resources/templates';
const PAGE_URL = `${SITE_ORIGIN}${PAGE_PATH}`;
const PAGE_DESCRIPTION =
  'Nine production-ready form templates for wedding planners — couple intake, order of events, vendor onboarding, dietary surveys, shot lists. Download as PDF, free.';
const PAGE_TITLE = 'Free Wedding Planner Templates — The Special Wedding';

// Static manifest moved to ./manifest so other surfaces (blog "Related
// templates" card, future homepage / resources tiles) can import the
// canonical names + descriptions without duplicating copy.

// Full Next.js Metadata API per
// https://nextjs.org/docs/app/api-reference/functions/generate-metadata —
// metadataBase + alternates.canonical resolve relative URLs in the
// rendered head, openGraph + twitter give social-share previews,
// robots is permissive by inheritance from the root layout.
export const metadata: Metadata = {
  metadataBase: new URL(SITE_ORIGIN),
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: {
    canonical: PAGE_PATH,
  },
  openGraph: {
    type: 'website',
    url: PAGE_URL,
    title: PAGE_TITLE,
    description: PAGE_DESCRIPTION,
    siteName: 'The Special Wedding',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Free wedding planner template library',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@thespecialwedding',
    title: PAGE_TITLE,
    description: PAGE_DESCRIPTION,
    images: ['/og-image.png'],
  },
};

export default function PublicTemplatesPage() {
  // schema.org ItemList (https://schema.org/ItemList) surfaces the 9
  // templates as a single rich-result-eligible list per
  // https://developers.google.com/search/docs/appearance/structured-data.
  // Each template links to its anchor on this page so search snippets
  // can deep-link into the catalog.
  const itemListJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: 'Free Wedding Planner Templates',
    description: PAGE_DESCRIPTION,
    itemListOrder: 'https://schema.org/ItemListOrderAscending',
    numberOfItems: MARKETING_TEMPLATES.length,
    itemListElement: MARKETING_TEMPLATES.map((template, idx) => ({
      '@type': 'ListItem',
      position: idx + 1,
      name: template.name,
      description: template.description,
      url: `${PAGE_URL}#${template.id}`,
    })),
  };
  return (
    <main className="min-h-screen bg-[#fbf9f6] py-16 sm:py-24">
      {/*
       * Structured data: ItemList for the 9 templates +
       * BreadcrumbList for the Home → Resources → Free Templates
       * trail. Both surface as Google Rich Results when the page is
       * indexed (validated against
       * https://developers.google.com/search/docs/appearance/structured-data).
       */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListJsonLd) }}
      />
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Resources', href: '/resources' },
          { name: 'Free Templates', href: PAGE_PATH },
        ]}
      />
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
