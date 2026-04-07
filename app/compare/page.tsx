import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowRight, FileText, Sparkles } from 'lucide-react';
import { comparePageData, COMPARE_AUDIT_QUALIFIER, COMPARE_AUDIT_STAMP } from './data';

export const metadata: Metadata = {
  title: 'Compare The Special Wedding',
  description:
    `Start here for comparison pages that position The Special Wedding against HoneyBook and Aisle Planner using official competitor sources reviewed on ${COMPARE_AUDIT_STAMP}.`,
  alternates: {
    canonical: '/compare',
  },
  openGraph: {
    title: 'Compare The Special Wedding',
    description:
      'Start here for comparison pages that position The Special Wedding against HoneyBook and Aisle Planner.',
    url: 'https://thespecialwedding.io/compare',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Compare The Special Wedding',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@thespecialwedding',
    title: 'Compare The Special Wedding',
    description:
      'Start here for comparison pages that position The Special Wedding against HoneyBook and Aisle Planner.',
    images: ['/og-image.png'],
  },
};

export default function CompareIndexPage() {
  const pages = Object.values(comparePageData);

  return (
    <main className="mx-auto max-w-7xl px-6 pb-16 pt-28 sm:px-10 lg:px-16">
      <section className="max-w-4xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-wedding-rose/30 bg-white/5 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.35em] text-wedding-rose">
          <Sparkles size={12} />
          Comparison hub
        </div>
        <h1 className="mt-6 text-4xl font-semibold leading-tight text-white sm:text-5xl">
          Compare The Special Wedding against the tools planners are already searching for.
        </h1>
        <p className="mt-5 max-w-3xl text-lg leading-relaxed text-slate-300">
          These pages are written from official competitor pricing and help-doc sources reviewed on {COMPARE_AUDIT_STAMP}, so the comparison story stays explicit about what is confirmed, adjacent, or still missing.
        </p>
      </section>

      <section className="mt-12 grid gap-6 md:grid-cols-2">
        {pages.map((page) => (
          <article
            key={page.slug}
            className="rounded-3xl border border-white/8 bg-white/[0.03] p-6 shadow-lg shadow-black/10"
          >
            <p className="text-xs uppercase tracking-[0.35em] text-slate-500">
              {page.heroEyebrow}
            </p>
            <h2 className="mt-3 text-2xl font-semibold text-white">{page.pageTitle}</h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-300">{page.heroSummary}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full border border-white/10 bg-slate-950/60 px-3 py-1 text-xs text-slate-300">
                {page.pricingSnapshot}
              </span>
              <span className="rounded-full border border-white/10 bg-slate-950/60 px-3 py-1 text-xs text-slate-300">
                {COMPARE_AUDIT_QUALIFIER}
              </span>
            </div>
            <Link
              href={`/compare/${page.slug}`}
              className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-wedding-rose transition hover:text-wedding-blush"
            >
              Open comparison page
              <ArrowRight size={16} />
            </Link>
          </article>
        ))}
      </section>

      <section className="mt-12 rounded-3xl border border-white/8 bg-white/[0.03] p-6 sm:p-8">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
          <FileText size={14} />
          Update slot
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-300">
          This hub is intentionally narrow. The route structure is ready for future source-backed refreshes without rewriting the comparison pages from scratch.
        </p>
      </section>
    </main>
  );
}
