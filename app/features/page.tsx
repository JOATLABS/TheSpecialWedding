'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { PUBLIC_LOGIN_PATH } from '@/seo/crawlPolicy';
import SaasNav from '../components/saas/SaasNav';
import BreadcrumbSchema from '../components/seo/BreadcrumbSchema';
import { MARKETING_FEATURES } from '../data/marketingFeatures';

/* ═══════════════════════════════════════════════════════════
   Feature data
   ═══════════════════════════════════════════════════════════ */
const features = MARKETING_FEATURES;

/**
 * Three-state comparison:
 *  true      = Confirmed: feature exists and is documented
 *  'adjacent' = Adjacent: related capability exists but not a 1:1 match
 *  false     = Not found in reviewed sources
 */
type FeatureState = boolean | 'adjacent';

type ComparisonRow = {
  feature: string;
  you: FeatureState;
  honeybook: FeatureState;
  aislePlanner: FeatureState;
  planningPod: FeatureState;
};

/* Values aligned with /compare evidence.ts research (April 6, 2026 audit) */
const comparison: ComparisonRow[] = [
  { feature: 'Guest Management & RSVPs', you: true, honeybook: 'adjacent', aislePlanner: true, planningPod: true },
  { feature: 'Client Portal / Couple Portal', you: true, honeybook: 'adjacent', aislePlanner: 'adjacent', planningPod: false },
  { feature: 'Built-In Wedding Microsite', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'SMS & Email Reminders', you: true, honeybook: 'adjacent', aislePlanner: 'adjacent', planningPod: true },
  { feature: 'Real-Time Push Notifications', you: true, honeybook: 'adjacent', aislePlanner: false, planningPod: false },
  { feature: 'Inbound Email Threading', you: true, honeybook: true, aislePlanner: false, planningPod: false },
  { feature: 'Seating Charts', you: true, honeybook: false, aislePlanner: true, planningPod: true },
  { feature: 'AI Contract Generation & E-Sign', you: true, honeybook: 'adjacent', aislePlanner: 'adjacent', planningPod: false },
  { feature: 'Service Packages', you: true, honeybook: 'adjacent', aislePlanner: false, planningPod: false },
  { feature: 'AI Cash Flow Predictions', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'Budget Management', you: true, honeybook: 'adjacent', aislePlanner: true, planningPod: true },
  { feature: 'Photo Gallery & Guest QR Uploads', you: true, honeybook: false, aislePlanner: 'adjacent', planningPod: false },
  { feature: 'Vendor / Contact CRM', you: true, honeybook: 'adjacent', aislePlanner: 'adjacent', planningPod: true },
  { feature: 'Public Vendor Directory', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'Contract Vendor Portal (Token-Based)', you: true, honeybook: 'adjacent', aislePlanner: false, planningPod: false },
  { feature: 'Vendor Advertising Portal', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'AI Quote Comparison', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'Couple-Maintained FAQs', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'Meeting Scheduler', you: true, honeybook: true, aislePlanner: 'adjacent', planningPod: 'adjacent' },
  { feature: 'Custom Forms & Intake', you: true, honeybook: 'adjacent', aislePlanner: 'adjacent', planningPod: true },
  { feature: 'Calendar Sync', you: true, honeybook: 'adjacent', aislePlanner: true, planningPod: false },
  { feature: 'CSV / Google Sheets Guest Import', you: true, honeybook: false, aislePlanner: true, planningPod: true },
  { feature: 'OTP Guest Access', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'Team Management & Permissions', you: true, honeybook: 'adjacent', aislePlanner: 'adjacent', planningPod: false },
  { feature: 'Invoicing & Online Payments', you: true, honeybook: 'adjacent', aislePlanner: 'adjacent', planningPod: true },
  { feature: 'Enterprise Scaling', you: true, honeybook: 'adjacent', aislePlanner: false, planningPod: false },
  { feature: 'In-App Support & Knowledge Base', you: true, honeybook: 'adjacent', aislePlanner: 'adjacent', planningPod: 'adjacent' },
  { feature: 'Day-of / Onsite Check-In', you: true, honeybook: false, aislePlanner: false, planningPod: true },
];

function FeatureCell({ value }: { value: FeatureState }) {
  if (value === true) return <span className="text-emerald-400 text-base">✓</span>;
  if (value === 'adjacent') return <span className="text-amber-400/70 text-xs font-medium" title="Adjacent capability — not a 1:1 match">~</span>;
  return <span className="text-slate-600">—</span>;
}

/* ═══════════════════════════════════════════════════════════
   Page
   ═══════════════════════════════════════════════════════════ */

export default function FeaturesPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Features', href: '/features' },
        ]}
      />
      {/* ── Hero ── */}
      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-50"
          style={{
            background:
              'radial-gradient(800px 500px at 20% -10%, rgba(212,165,165,0.3), transparent 70%), radial-gradient(1000px 600px at 85% -10%, rgba(232,196,106,0.2), transparent 65%)',
          }}
        />
        <div className="relative mx-auto max-w-5xl px-6 pt-32 pb-12 text-center sm:px-10">
          <p className="text-[11px] uppercase tracking-[0.5em] text-wedding-rose/80 mb-4">
            Why The Special Wedding
          </p>
          <h1 className="text-3xl font-semibold text-white sm:text-4xl md:text-5xl leading-tight">
            Every planning surface.<br />One platform.
          </h1>
          <p className="mt-5 text-base text-slate-300 max-w-2xl mx-auto">
            The planner dashboard, wedding configuration, microsite publishing, gallery management, event timelines, guest pipeline, planner communications, vendor directory, contract canvas, forms, payments, knowledge base, and team controls are designed to work together instead of fighting each other.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <a
              href="#pricing"
              className="rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-wedding-rose/30 transition hover:bg-wedding-blush"
            >
              {/* SYNC-WITH-SEED: trial_days */}
              Start 30-day trial
            </a>
            <Link
              href="/resources/blog"
              className="rounded-full border border-white/20 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/40"
            >
              Read the blog
            </Link>
          </div>
        </div>
      </section>

      {/* ── Feature Grid ── */}
      <section className="mx-auto max-w-6xl px-6 py-12 sm:px-10">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <article
              key={f.title}
              className="group rounded-2xl border border-white/8 bg-white/[0.03] p-7 transition hover:border-wedding-rose/30"
            >
              <div className="relative mb-5 aspect-[16/10] overflow-hidden rounded-2xl border border-white/10 bg-slate-900/70">
                <Image
                  src={f.image}
                  alt={`${f.title} — ${f.tagline}`}
                  fill
                  sizes="(min-width: 1024px) 30vw, (min-width: 640px) 45vw, 90vw"
                  className="object-cover object-top transition duration-500 group-hover:scale-[1.02]"
                />
              </div>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-wedding-rose/10 text-xl">
                    {f.icon}
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.25em] text-slate-500">{f.category}</p>
                    <h3 className="mt-1 text-base font-semibold text-white">{f.title}</h3>
                  </div>
                </div>
                {f.ai && (
                  <span className="rounded-full border border-wedding-rose/30 bg-wedding-rose/15 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-wedding-rose">
                    AI
                  </span>
                )}
              </div>
              <p className="mt-4 text-sm font-medium text-slate-300">{f.tagline}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{f.description}</p>
              {f.blogSlug && (
                <Link
                  href={`/resources/blog/${f.blogSlug}`}
                  className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-wedding-rose transition hover:text-wedding-blush"
                >
                  Read the story
                  <span aria-hidden="true">→</span>
                </Link>
              )}
            </article>
          ))}
        </div>
      </section>

      {/* ── Comparison Table ── */}
      <section className="mx-auto max-w-5xl px-6 py-16 sm:px-10">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-semibold text-white sm:text-3xl">How we compare</h2>
          <p className="mt-3 text-base text-slate-400">
            The Special Wedding vs the tools you&apos;re probably juggling right now.
          </p>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-white/8 bg-white/[0.02]">
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-white/8">
                <th className="text-left px-5 py-4 text-xs uppercase tracking-[0.2em] text-slate-500 font-semibold">Feature</th>
                <th className="text-center px-4 py-4 text-xs uppercase tracking-[0.2em] text-wedding-rose font-semibold">Us</th>
                <th className="text-center px-4 py-4 text-xs uppercase tracking-[0.2em] text-slate-500 font-semibold">HoneyBook</th>
                <th className="text-center px-4 py-4 text-xs uppercase tracking-[0.2em] text-slate-500 font-semibold">Aisle Planner</th>
                <th className="text-center px-4 py-4 text-xs uppercase tracking-[0.2em] text-slate-500 font-semibold">Planning Pod</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((row) => (
                <tr key={row.feature} className="border-b border-white/5 hover:bg-white/[0.02]">
                  <td className="px-5 py-3.5 text-sm text-slate-300">{row.feature}</td>
                  <td className="text-center px-4 py-3.5"><FeatureCell value={row.you} /></td>
                  <td className="text-center px-4 py-3.5"><FeatureCell value={row.honeybook} /></td>
                  <td className="text-center px-4 py-3.5"><FeatureCell value={row.aislePlanner} /></td>
                  <td className="text-center px-4 py-3.5"><FeatureCell value={row.planningPod} /></td>
                </tr>
              ))}
              {/* Pricing row */}
              <tr className="border-t border-white/10">
                <td className="px-5 py-4 text-sm font-semibold text-white">Starting price</td>
                <td className="text-center px-4 py-4 text-sm font-semibold text-wedding-rose">$0/mo<span className="block text-[10px] text-slate-500">(Solo — 1 wedding free)</span></td>
                <td className="text-center px-4 py-4 text-sm text-slate-400">$29/mo<span className="block text-[10px] text-slate-500">(billed annually)</span></td>
                <td className="text-center px-4 py-4 text-sm text-slate-400">$49.99/mo</td>
                <td className="text-center px-4 py-4 text-sm text-slate-400">$149/mo</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-xs leading-relaxed text-slate-500">
          ✓ = confirmed &nbsp; ~ = adjacent capability &nbsp; — = not found. Pricing and feature statuses reflect publicly documented capabilities as of April 2026. For source-backed detail on each row, see the <Link href="/compare" className="underline hover:text-slate-300">full comparison pages</Link>.
        </p>
      </section>

      {/* ── CTA ── */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-t from-transparent via-wedding-rose/[0.04] to-transparent" />
        <div className="relative mx-auto max-w-3xl px-6 py-20 text-center sm:px-10">
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">
            Replace 10+ subscriptions with one platform.
          </h2>
          <p className="mt-4 text-base text-slate-300">
            {/* SYNC-WITH-SEED: trial_days */}
            Start a 30-day free trial today — no credit card required.
          </p>
          <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              href={PUBLIC_LOGIN_PATH}
              className="rounded-full bg-white px-6 py-3 text-base font-semibold text-slate-900 transition hover:bg-slate-100"
            >
              Get started free
            </Link>
            <a
              href="mailto:hello@thespecialwedding.io?subject=I'd like a demo of The Special Wedding"
              className="rounded-full border border-white/20 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/40"
            >
              Request a demo
            </a>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-slate-950 border-t border-white/5">
        <div className="mx-auto max-w-6xl px-6 py-6">
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
            <p className="text-xs text-slate-500">© {new Date().getFullYear()} The Special Wedding. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <a href="mailto:hello@thespecialwedding.io" className="text-xs text-slate-500 transition hover:text-slate-300">Contact</a>
              <p className="text-xs text-slate-500">
                Built by{' '}
                <a href="https://joatlabs.dev" target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white">
                  JOATLABS LLC
                </a>
              </p>
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}
