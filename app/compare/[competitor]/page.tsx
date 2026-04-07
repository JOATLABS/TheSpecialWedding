import type { Metadata } from 'next';
import Link from 'next/link';
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  ShieldAlert,
  Sparkles,
  Target,
} from 'lucide-react';
import {
  COMPARE_AUDIT_QUALIFIER,
  COMPARE_AUDIT_STAMP,
  comparisonRows,
  getCompareBreadcrumbs,
  getComparePageData,
  getCompareSupportedSlugs,
} from '../data';
import { getCompareEvidence } from '../evidence';

type PageParams = {
  params: Promise<{
    competitor: string;
  }>;
};

const compareBaseUrl = 'https://thespecialwedding.io/compare';

function buildBreadcrumbJsonLd(competitorName?: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: getCompareBreadcrumbs(competitorName).map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.href ? `https://thespecialwedding.io${item.href}` : undefined,
    })),
  };
}

function buildFaqJsonLd(faq: Array<{ question: string; answer: string }>) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faq.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: item.answer,
      },
    })),
  };
}

function buildWebPageJsonLd(title: string, description: string, canonical: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name: title,
    description,
    url: canonical,
    isPartOf: {
      '@type': 'WebSite',
      name: 'The Special Wedding',
      url: 'https://thespecialwedding.io',
    },
  };
}

function SupportedPage({
  competitor,
  title,
  description,
}: {
  competitor: NonNullable<ReturnType<typeof getComparePageData>>;
  title: string;
  description: string;
}) {
  const rows = comparisonRows;
  const competitorColumn = competitor.slug === 'honeybook' ? 'honeybook' : 'aislePlanner';
  const evidence = getCompareEvidence(competitor.slug);
  const evidenceLookup = new Map(evidence.rows.map((row) => [row.feature, row]));
  const confidenceClasses = {
    High: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-100',
    Medium: 'border-amber-400/20 bg-amber-500/10 text-amber-100',
  } as const;

  return (
    <main>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify([
            buildWebPageJsonLd(title, description, `${compareBaseUrl}/${competitor.slug}`),
            buildBreadcrumbJsonLd(competitor.competitorName),
            buildFaqJsonLd(competitor.faq),
          ]),
        }}
      />

      <section className="relative overflow-hidden border-b border-white/5">
        <div
          className="absolute inset-0 opacity-60"
          style={{
            background:
              'radial-gradient(900px 500px at 20% 0%, rgba(212,165,165,0.22), transparent 68%), radial-gradient(800px 500px at 80% 10%, rgba(232,196,106,0.16), transparent 70%)',
          }}
        />
        <div className="relative mx-auto max-w-7xl px-6 pt-28 pb-14 sm:px-10 lg:px-16">
          <div className="max-w-5xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-wedding-rose/30 bg-white/5 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.35em] text-wedding-rose">
              <Sparkles size={12} />
              {competitor.heroEyebrow}
            </div>

            <h1 className="mt-6 max-w-4xl text-4xl font-semibold leading-tight text-white sm:text-5xl lg:text-6xl">
              {competitor.heroTitle}
            </h1>

            <p className="mt-5 max-w-3xl text-lg leading-relaxed text-slate-300">
              {competitor.heroSummary}
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/features"
                className="inline-flex items-center gap-2 rounded-full bg-wedding-rose px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-wedding-blush"
              >
                Read the feature matrix
                <ArrowRight size={16} />
              </Link>
              <Link
                href="/resources"
                className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white transition hover:border-white/30 hover:bg-white/5"
              >
                Open the resources hub
                <BookOpen size={16} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-14 sm:px-10 lg:grid-cols-[1.35fr_0.85fr] lg:px-16">
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            {competitor.heroSnapshot.map((item) => (
              <div
                key={item}
                className="rounded-2xl border border-white/8 bg-white/[0.03] p-5 shadow-lg shadow-black/10"
              >
                <CheckCircle2 className="text-emerald-300" size={18} />
                <p className="mt-3 text-sm leading-relaxed text-slate-300">{item}</p>
              </div>
            ))}
          </div>

          <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.35em] text-wedding-rose">
              <Target size={14} />
              What this page is for
            </div>
            <p className="mt-4 text-sm leading-relaxed text-slate-300">
              This comparison page is deliberately narrow: it targets planners searching for a direct alternative to {competitor.competitorName}. The copy stays anchored to official competitor sources reviewed on {COMPARE_AUDIT_STAMP} and leaves room for later source-backed updates.
            </p>
          </div>
        </div>

        <aside className="rounded-3xl border border-wedding-gold/20 bg-wedding-gold/5 p-6">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.35em] text-wedding-gold">
            <ShieldAlert size={14} />
            Source review
          </div>
          <p className="mt-4 text-2xl font-semibold text-white">{COMPARE_AUDIT_QUALIFIER}</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">
            {COMPARE_AUDIT_STAMP} is the explicit review date used across the matrix and footnotes.
          </p>

          <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/60 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Pricing snapshot</p>
            <p className="mt-2 text-lg font-semibold text-white">{competitor.pricingSnapshot}</p>
            <p className="mt-2 text-sm text-slate-400">
              Verify this against the live vendor pricing page before publishing externally.
            </p>
          </div>

          <div className="mt-5 space-y-3">
            {competitor.differentiators.map((item) => (
              <div key={item} className="flex gap-3">
                <span className="mt-1 h-2.5 w-2.5 rounded-full bg-wedding-rose" />
                <p className="text-sm leading-relaxed text-slate-300">{item}</p>
              </div>
            ))}
          </div>
        </aside>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-14 sm:px-10 lg:px-16">
        <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-6 sm:p-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Feature matrix</p>
              <h2 className="mt-3 text-2xl font-semibold text-white sm:text-3xl">
                April 2026 comparison snapshot
              </h2>
            </div>
            <p className="max-w-xl text-sm leading-relaxed text-slate-400">
              Each row is written from vendor pricing pages and help-doc sources reviewed on {COMPARE_AUDIT_STAMP}. Use the wording deliberately: some rows are exact matches, and others are adjacent capabilities rather than one-to-one equivalents.
            </p>
          </div>

          <div className="mt-8 overflow-x-auto rounded-2xl border border-white/8">
            <table className="min-w-[860px] w-full border-collapse">
              <thead>
                <tr className="border-b border-white/8 bg-white/[0.03]">
                  <th className="px-5 py-4 text-left text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
                    Feature
                  </th>
                  <th className="px-5 py-4 text-left text-xs font-semibold uppercase tracking-[0.25em] text-wedding-rose">
                    The Special Wedding
                  </th>
                  <th className="px-5 py-4 text-left text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
                    {competitor.competitorName}
                  </th>
                  <th className="px-5 py-4 text-left text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
                    Audit note
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.feature} className="border-b border-white/5">
                    <td className="px-5 py-4 align-top text-sm font-medium text-white">
                      {row.feature}
                    </td>
                    <td className="px-5 py-4 align-top text-sm leading-relaxed text-slate-300">
                      {row.specialWedding}
                    </td>
                    <td className="px-5 py-4 align-top text-sm leading-relaxed text-slate-300">
                      {row[competitorColumn]}
                    </td>
                    <td className="px-5 py-4 align-top text-sm leading-relaxed text-slate-400">
                      Treat this as a sourced snapshot, not a permanent truth. Re-check live docs before external use.
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-4 text-xs uppercase tracking-[0.25em] text-slate-500">
            Footnote: all rows are tied to a documented source review and labeled {COMPARE_AUDIT_QUALIFIER}.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-14 sm:px-10 lg:px-16">
        <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-6 sm:p-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Evidence and confidence</p>
              <h2 className="mt-3 text-2xl font-semibold text-white sm:text-3xl">
                Row-by-row source ledger
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
              This section inlines the confidence call and the official source URLs used for the current competitor so the public compare page stays traceable back to the research snapshot.
            </p>
          </div>

          <div className="mt-8 overflow-x-auto rounded-2xl border border-white/8">
            <table className="min-w-[920px] w-full border-collapse">
              <thead>
                <tr className="border-b border-white/8 bg-white/[0.03]">
                  <th className="px-5 py-4 text-left text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
                    Feature
                  </th>
                  <th className="px-5 py-4 text-left text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
                    Confidence
                  </th>
                  <th className="px-5 py-4 text-left text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
                    Official sources
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const evidenceRow = evidenceLookup.get(row.feature);

                  return (
                    <tr key={`${row.feature}-evidence`} className="border-b border-white/5">
                      <td className="px-5 py-4 align-top">
                        <p className="text-sm font-medium text-white">{row.feature}</p>
                        <p className="mt-2 text-sm leading-relaxed text-slate-400">
                          {evidenceRow?.note ?? 'No source note was captured for this row in the current research snapshot.'}
                        </p>
                      </td>
                      <td className="px-5 py-4 align-top">
                        {evidenceRow ? (
                          <span
                            className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${confidenceClasses[evidenceRow.confidence]}`}
                          >
                            {evidenceRow.confidence}
                          </span>
                        ) : (
                          <span className="text-sm text-slate-500">N/A</span>
                        )}
                      </td>
                      <td className="px-5 py-4 align-top">
                        {evidenceRow?.sourceCodes?.length ? (
                          <div className="flex flex-wrap gap-2">
                            {evidenceRow.sourceCodes.map((sourceCode) => {
                              const source = evidence.sources.find((entry) => entry.code === sourceCode);
                              if (!source) {
                                return null;
                              }

                              return (
                                <a
                                  key={source.code}
                                  href={source.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-slate-950/60 px-3 py-1.5 text-xs text-slate-200 transition hover:border-white/20 hover:bg-slate-900"
                                >
                                  <span className="font-semibold text-white">{source.code}</span>
                                  <span>{source.label}</span>
                                  <ExternalLink size={12} />
                                </a>
                              );
                            })}
                          </div>
                        ) : (
                          <span className="text-sm text-slate-500">No source links captured.</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {evidence.sources.map((source) => (
              <a
                key={source.code}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-2xl border border-white/8 bg-slate-950/50 p-4 transition hover:border-white/15 hover:bg-slate-900/60"
              >
                <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{source.code}</p>
                <p className="mt-2 text-sm font-semibold text-white">{source.label}</p>
                <p className="mt-2 text-xs text-slate-400">{source.url}</p>
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 pb-14 sm:px-10 lg:grid-cols-[1fr_0.9fr] lg:px-16">
        <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-6 sm:p-8">
          <p className="text-xs uppercase tracking-[0.35em] text-slate-500">What to verify next</p>
          <h2 className="mt-3 text-2xl font-semibold text-white">Sourced update slot</h2>
          <div className="mt-6 space-y-4">
            {competitor.auditNotes.map((note) => (
              <div key={note} className="rounded-2xl border border-white/8 bg-slate-950/50 p-4">
                <p className="text-sm leading-relaxed text-slate-300">{note}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-6 sm:p-8">
          <p className="text-xs uppercase tracking-[0.35em] text-slate-500">FAQ</p>
          <h2 className="mt-3 text-2xl font-semibold text-white">Questions planners usually ask</h2>
          <dl className="mt-6 space-y-4">
            {competitor.faq.map((item) => (
              <div key={item.question} className="rounded-2xl border border-white/8 bg-slate-950/50 p-4">
                <dt className="text-sm font-semibold text-white">{item.question}</dt>
                <dd className="mt-2 text-sm leading-relaxed text-slate-300">{item.answer}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className="border-t border-white/5 bg-slate-950/70">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-12 sm:px-10 lg:flex-row lg:items-center lg:justify-between lg:px-16">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Next step</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">
              Compare the product, then read the supporting content.
            </h2>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/features"
              className="inline-flex items-center gap-2 rounded-full bg-wedding-rose px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-wedding-blush"
            >
              Open features
              <ArrowRight size={16} />
            </Link>
            <Link
              href="/resources"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white transition hover:border-white/30 hover:bg-white/5"
            >
              Browse resources
              <ExternalLink size={16} />
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}

function UnsupportedPage({
  competitor,
}: {
  competitor: string;
}) {
  return (
    <main className="mx-auto max-w-5xl px-6 pb-16 pt-28 sm:px-10 lg:px-16">
      <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-8">
        <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Comparison page coming soon</p>
        <h1 className="mt-4 text-4xl font-semibold text-white">
          We do not have a published compare page for “{competitor}” yet.
        </h1>
        <p className="mt-4 max-w-3xl text-base leading-relaxed text-slate-300">
          The route is still graceful: you can use the two supported comparison pages below, or jump into the feature and resources content that backs the comparison story.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/compare/honeybook"
            className="inline-flex items-center gap-2 rounded-full bg-wedding-rose px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-wedding-blush"
          >
            HoneyBook comparison
            <ArrowRight size={16} />
          </Link>
          <Link
            href="/compare/aisle-planner"
            className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white transition hover:border-white/30 hover:bg-white/5"
          >
            Aisle Planner comparison
          </Link>
        </div>
      </div>
    </main>
  );
}

export async function generateStaticParams() {
  return getCompareSupportedSlugs().map((competitor) => ({ competitor }));
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { competitor } = await params;
  const pageData = getComparePageData(competitor);

  if (!pageData) {
    return {
      title: 'Compare The Special Wedding',
      description:
        'Wedding planner comparison pages for HoneyBook and Aisle Planner, updated against official competitor sources reviewed on April 6, 2026.',
      robots: {
        index: false,
        follow: true,
      },
      alternates: {
        canonical: '/compare',
      },
    };
  }

  const canonicalUrl = `${compareBaseUrl}/${pageData.slug}`;

  return {
    title: `${pageData.pageTitle} | The Special Wedding`,
    description: pageData.metaDescription,
    alternates: {
      canonical: `/compare/${pageData.slug}`,
    },
    openGraph: {
      title: pageData.pageTitle,
      description: pageData.metaDescription,
      url: canonicalUrl,
      type: 'article',
      images: [
        {
          url: '/og-image.png',
          width: 1200,
          height: 630,
          alt: pageData.pageTitle,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      site: '@thespecialwedding',
      title: pageData.pageTitle,
      description: pageData.metaDescription,
      images: ['/og-image.png'],
    },
  };
}

export default async function CompareCompetitorPage({ params }: PageParams) {
  const { competitor } = await params;
  const pageData = getComparePageData(competitor);

  if (!pageData) {
    return <UnsupportedPage competitor={competitor} />;
  }

  return (
    <>
      <SupportedPage
        competitor={pageData}
        title={`${pageData.pageTitle} | The Special Wedding`}
        description={pageData.metaDescription}
      />
    </>
  );
}
