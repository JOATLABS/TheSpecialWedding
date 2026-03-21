'use client';

import React from 'react';
import Link from 'next/link';

/* ═══════════════════════════════════════════════════════════
   Feature data
   ═══════════════════════════════════════════════════════════ */

const features = [
  {
    icon: '👥',
    title: 'Guest Management',
    desc: 'RSVPs, plus-ones, groups, dietary needs \u2014 one live view for 200+ guests across multiple events.',
    ai: false,
  },
  {
    icon: '🪑',
    title: 'Seating Orchestrator',
    desc: 'Drag-and-drop seating across sections and tables. Constraints, group rules, and real-time headcounts.',
    ai: false,
  },
  {
    icon: '📝',
    title: 'Contract Canvas',
    desc: 'AI-generated clauses, placeholders, and e-sign \u2014 build contracts from scratch or templates.',
    ai: true,
  },
  {
    icon: '💰',
    title: 'Budget Tracker',
    desc: 'Track every dollar with category breakdowns. AI cash flow predictions tell you when payments are due.',
    ai: true,
  },
  {
    icon: '🤝',
    title: 'Vendor CRM',
    desc: 'Contracts, payments, and communication for every vendor in one hub. Role-based access for collaboration.',
    ai: false,
  },
  {
    icon: '🏷️',
    title: 'Service Packages',
    desc: 'Build bookable tiers with AI pricing suggestions. Send professional proposals with one click.',
    ai: true,
  },
  {
    icon: '📅',
    title: 'Planning Calendar',
    desc: 'Tasks, deadlines, and Google Calendar sync. Assign to team members with due dates and reminders.',
    ai: false,
  },
  {
    icon: '💳',
    title: 'Payment Management',
    desc: 'Incoming and outgoing payments, Stripe integration, forecasts, and AI cash flow predictions.',
    ai: true,
  },
  {
    icon: '📨',
    title: 'Reminders & Invites',
    desc: 'SMS and email \u2014 event reminders, RSVP nudges, custom messages. Automated or manual.',
    ai: false,
  },
  {
    icon: '📸',
    title: 'Photo Gallery',
    desc: 'Upload, organize, and share wedding photos with clients. Privacy controls per gallery.',
    ai: false,
  },
  {
    icon: '📋',
    title: 'Forms Canvas',
    desc: 'Drag-and-drop intake forms, questionnaires, and feedback. AI-assisted field suggestions.',
    ai: true,
  },
  {
    icon: '⚙️',
    title: 'Wedding Configuration',
    desc: 'Events, privacy, RSVP settings, branding \u2014 all customizable per wedding, per client.',
    ai: false,
  },
];

type ComparisonRow = {
  feature: string;
  you: boolean;
  honeybook: boolean;
  aislePlanner: boolean;
  planningPod: boolean;
};

const comparison: ComparisonRow[] = [
  { feature: 'Guest Management & RSVPs', you: true, honeybook: false, aislePlanner: true, planningPod: true },
  { feature: 'Seating Charts', you: true, honeybook: false, aislePlanner: false, planningPod: true },
  { feature: 'AI Pricing Suggestions', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'AI Contract Generation', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'AI Cash Flow Predictions', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'Vendor Collaboration', you: true, honeybook: false, aislePlanner: true, planningPod: false },
  { feature: 'Contracts & E-Sign', you: true, honeybook: true, aislePlanner: true, planningPod: true },
  { feature: 'Invoicing & Payments', you: true, honeybook: true, aislePlanner: true, planningPod: true },
  { feature: 'Multi-Tenant Agency Tier', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'Touchless Day-of Check-in', you: true, honeybook: false, aislePlanner: false, planningPod: false },
  { feature: 'Custom Forms Builder', you: true, honeybook: true, aislePlanner: false, planningPod: true },
  { feature: 'Photo Gallery', you: true, honeybook: false, aislePlanner: true, planningPod: false },
];

/* ═══════════════════════════════════════════════════════════
   Page
   ═══════════════════════════════════════════════════════════ */

export default function FeaturesPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
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
            13 tools. One platform.<br />Zero tool juggling.
          </h1>
          <p className="mt-5 text-base text-slate-300 max-w-2xl mx-auto">
            Everything a professional wedding planner needs to manage guests, vendors, budgets, contracts, and day-of execution \u2014 with AI that actually saves time.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <a
              href="#pricing"
              className="rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-wedding-rose/30 transition hover:bg-wedding-blush"
            >
              Start your free trial
            </a>
            <Link
              href="/resources"
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
            <div
              key={f.title}
              className="group rounded-2xl border border-white/8 bg-white/[0.03] p-7 transition hover:border-wedding-rose/30"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-wedding-rose/10 text-xl">
                  {f.icon}
                </div>
                {f.ai && (
                  <span className="rounded-full bg-wedding-rose/15 border border-wedding-rose/30 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-wedding-rose">
                    AI
                  </span>
                )}
              </div>
              <h3 className="mt-4 text-base font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-sm text-slate-400 leading-relaxed">{f.desc}</p>
            </div>
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
                  <td className="text-center px-4 py-3.5">
                    {row.you ? (
                      <span className="text-emerald-400 text-base">✓</span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="text-center px-4 py-3.5">
                    {row.honeybook ? (
                      <span className="text-emerald-400/60 text-base">✓</span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="text-center px-4 py-3.5">
                    {row.aislePlanner ? (
                      <span className="text-emerald-400/60 text-base">✓</span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="text-center px-4 py-3.5">
                    {row.planningPod ? (
                      <span className="text-emerald-400/60 text-base">✓</span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                </tr>
              ))}
              {/* Pricing row */}
              <tr className="border-t border-white/10">
                <td className="px-5 py-4 text-sm font-semibold text-white">Starting price</td>
                <td className="text-center px-4 py-4 text-sm font-semibold text-wedding-rose">$29/mo</td>
                <td className="text-center px-4 py-4 text-sm text-slate-400">$19/mo</td>
                <td className="text-center px-4 py-4 text-sm text-slate-400">$39/mo</td>
                <td className="text-center px-4 py-4 text-sm text-slate-400">$20/mo</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-t from-transparent via-wedding-rose/[0.04] to-transparent" />
        <div className="relative mx-auto max-w-3xl px-6 py-20 text-center sm:px-10">
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">
            Replace 8+ subscriptions with one platform.
          </h2>
          <p className="mt-4 text-base text-slate-300">
            Start your free trial \u2014 no credit card required.
          </p>
          <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              href="/admin/login"
              className="rounded-full bg-white px-6 py-3 text-base font-semibold text-slate-900 transition hover:bg-slate-100"
            >
              Start free trial
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
        <div className="mx-auto max-w-6xl px-6 py-10">
          <nav className="flex flex-wrap justify-center gap-x-8 gap-y-3 mb-8">
            <Link href="/" className="text-sm text-slate-400 transition hover:text-white">Home</Link>
            <Link href="/resources" className="text-sm text-slate-400 transition hover:text-white">Resources</Link>
            <Link href="/vendors" className="text-sm text-slate-400 transition hover:text-white">Vendor directory</Link>
            <Link href="/admin/login" className="text-sm text-slate-400 transition hover:text-white">Sign in</Link>
            <a href="mailto:hello@thespecialwedding.io" className="text-sm text-slate-400 transition hover:text-white">Contact</a>
          </nav>
          <div className="h-px bg-white/5 mb-6" />
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
            <p className="text-xs text-slate-500">© {new Date().getFullYear()} The Special Wedding. All rights reserved.</p>
            <p className="text-xs text-slate-500">
              Built by{' '}
              <a href="https://joatlabs.dev" target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white">
                JOATLABS LLC
              </a>
              {' '}© 2026
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
