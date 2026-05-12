'use client';

/**
 * Homepage lead-magnet band.
 *
 * Slots between the dark hero and the "See what's inside" showcase on
 * /. Renders three preview cards (curated from the same canonical
 * manifest as the Resources templates tab so copy never drifts) plus a single
 * primary CTA that opens the shared TemplateDownloadModal with
 * templateId="starter_pack". The starter-pack sentinel tells the
 * backend to attach all 9 catalog PDFs in a single Resend email.
 *
 * UTM context is forwarded explicitly so analytics can distinguish
 * homepage-sourced leads from Resources template-tab visitors.
 */

import Link from 'next/link';
import { useState } from 'react';

import {
  getMarketingTemplates,
  type MarketingTemplate,
} from '@/resources/templates/manifest';

import TemplateDownloadModal from './TemplateDownloadModal';

const FEATURED_IDS = [
  'couple_intake',
  'bridal_party_logistics',
  'vendor_onboarding',
] as const;

const BAND_UTM = {
  utm_source: 'homepage_band',
  utm_medium: 'organic',
  utm_campaign: 'starter_pack',
} as const;

export default function HomepageTemplatesBand() {
  const featured: MarketingTemplate[] = getMarketingTemplates(FEATURED_IDS);
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <section
      id="free-templates-band"
      data-testid="homepage-templates-band"
      className="bg-slate-950 px-6 py-16 sm:px-8 sm:py-20 lg:px-12"
    >
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:items-end">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-rose-200">
              Free for planners
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-normal text-white sm:text-4xl lg:text-5xl">
              9 free templates planners actually use.
            </h2>
            <p className="mt-5 max-w-xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
              Send your email, get all 9 production-ready PDFs in your inbox.
              No account needed.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                type="button"
                onClick={() => setModalOpen(true)}
                data-testid="homepage-band-cta"
                className="inline-flex items-center justify-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-950 shadow-xl shadow-rose-950/20 transition hover:-translate-y-0.5 hover:bg-rose-50"
              >
                Get all 9 templates &rarr;
              </button>
              <Link
                href="/resources?tab=templates"
                className="inline-flex items-center text-sm font-medium text-slate-300 underline-offset-4 transition hover:text-white hover:underline"
              >
                Browse all templates
              </Link>
            </div>
          </div>

          <ul className="grid gap-4 sm:grid-cols-3" aria-label="Featured templates">
            {featured.map((template) => (
              <li key={template.id}>
                <article className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur-sm transition hover:border-rose-300/30 hover:bg-white/[0.07]">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-rose-200">
                    {template.category}
                  </p>
                  <h3 className="mt-3 text-base font-semibold leading-snug text-white">
                    {template.name}
                  </h3>
                  <p className="mt-2 text-xs leading-5 text-slate-300 line-clamp-4">
                    {template.description}
                  </p>
                  <p className="mt-4 inline-flex w-fit items-center rounded-full border border-white/15 bg-black/30 px-2.5 py-1 text-[11px] font-medium text-slate-200">
                    {template.fieldCount} fields
                  </p>
                </article>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <TemplateDownloadModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        templateId="starter_pack"
        headline="Download the planner starter pack"
        subhead="Drop your email and we'll send all 9 PDFs in one go — no account, no fluff."
        utm={BAND_UTM}
        surface="dark"
        testIdPrefix="homepage-band"
      />
    </section>
  );
}
