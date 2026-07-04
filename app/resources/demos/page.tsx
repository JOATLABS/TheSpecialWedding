import type { Metadata } from 'next';
import Link from 'next/link';

import DemoVideoLauncher from '@/components/saas/DemoVideoLauncher';
import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import {
  DEMO_VIDEO_PLAYLIST,
  FEATURE_DEMO_VIDEOS,
  HERO_DEMO_VIDEO,
  getDemoVideoStatusLabel,
} from '@/data/demoVideos';
import { PUBLIC_LOGIN_PATH } from '@/seo/crawlPolicy';
import { serializeJsonLd } from '@/seo/jsonLd';

import SaasNav from '../../components/saas/SaasNav';

const DEMOS_PATH = '/resources/demos';
const DEMOS_URL = `https://thespecialwedding.io${DEMOS_PATH}`;

export const metadata: Metadata = {
  title: 'Product Demo Library | The Special Wedding',
  description:
    'Watch the product demo library for The Special Wedding, from the planner dashboard to couple portal, microsite, guests, seating, vendors, contracts, and team workflows.',
  alternates: {
    canonical: DEMOS_PATH,
  },
  openGraph: {
    title: 'The Special Wedding Product Demo Library',
    description:
      'A proof-first walkthrough library for professional wedding planners evaluating The Special Wedding.',
    url: DEMOS_URL,
    siteName: 'The Special Wedding',
    type: 'website',
  },
  robots: {
    index: true,
    follow: true,
  },
};

const demosJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'CollectionPage',
  '@id': DEMOS_URL,
  url: DEMOS_URL,
  name: 'The Special Wedding Product Demo Library',
  description:
    'Product demo videos showing the major planner, couple, guest, vendor, and team workflows inside The Special Wedding.',
  hasPart: DEMO_VIDEO_PLAYLIST.map((demo) => ({
    '@type': 'CreativeWork',
    name: demo.title,
    description: demo.audience,
    url: `${DEMOS_URL}#${demo.id}`,
  })),
};

function statusClass(status: string): string {
  if (status === 'published') return 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200';
  if (status === 'recording') return 'border-amber-300/30 bg-amber-300/10 text-amber-100';
  return 'border-wedding-rose/30 bg-wedding-rose/10 text-wedding-rose';
}

export default function ProductDemosPage() {
  const phaseOne = FEATURE_DEMO_VIDEOS.filter((demo) => demo.priority === 'phase-one');
  const phaseTwo = FEATURE_DEMO_VIDEOS.filter((demo) => demo.priority === 'phase-two');

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Resources', href: '/resources/blog' },
          { name: 'Product Demos', href: DEMOS_PATH },
        ]}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(demosJsonLd) }}
      />

      <section className="relative overflow-hidden border-b border-white/10 bg-slate-950 px-6 pb-12 pt-32 sm:px-10">
        <div className="relative mx-auto max-w-5xl text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.5em] text-wedding-rose/80">
            Product proof library
          </p>
          <h1 className="mt-4 text-3xl font-semibold leading-tight text-white sm:text-4xl md:text-5xl">
            Real walkthroughs of the planner operating system.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-slate-300">
            Watch the recorded product walkthroughs across planner, couple, guest, vendor, payment, seating, and team workflows.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <DemoVideoLauncher
              demo={HERO_DEMO_VIDEO}
              label="Watch 2-minute walkthrough"
              variant="outline"
            />
            <Link
              href={PUBLIC_LOGIN_PATH}
              className="rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100"
            >
              Start with one wedding free
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-10 sm:px-10">
        <div
          id={HERO_DEMO_VIDEO.id}
          className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 sm:p-8"
        >
          <div className="grid gap-6 lg:grid-cols-[0.78fr_0.22fr] lg:items-start">
            <div>
              <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${statusClass(HERO_DEMO_VIDEO.status)}`}>
                {getDemoVideoStatusLabel(HERO_DEMO_VIDEO.status)}
              </span>
              <h2 className="mt-4 text-2xl font-semibold text-white">{HERO_DEMO_VIDEO.title}</h2>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">{HERO_DEMO_VIDEO.audience}</p>
              <ol className="mt-5 grid gap-3 md:grid-cols-2">
                {HERO_DEMO_VIDEO.script.map((step) => (
                  <li key={`${step.timestamp}-${step.action}`} className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
                    <p className="text-xs font-semibold text-wedding-rose">{step.timestamp}</p>
                    <p className="mt-1 text-sm font-semibold text-white">{step.action}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-400">{step.voiceover}</p>
                  </li>
                ))}
              </ol>
            </div>
            <div className="space-y-3">
              <DemoVideoLauncher demo={HERO_DEMO_VIDEO} label="Watch full walkthrough" variant="outline" />
              <Link
                href="/features"
                className="inline-flex w-full items-center justify-center rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-white transition hover:border-wedding-rose/50 hover:text-wedding-rose"
              >
                Browse features
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-10 sm:px-10">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">
              Phase one
            </p>
            <h2 className="mt-3 text-3xl font-semibold text-white">Highest-conversion clips</h2>
          </div>
          <p className="max-w-md text-sm leading-6 text-slate-400">
            These seven demos prove the buyer journey fastest, from first planner login to guest, vendor, and couple proof.
          </p>
        </div>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {phaseOne.map((demo) => (
            <article
              key={demo.id}
              id={demo.id}
              className="scroll-mt-28 rounded-2xl border border-white/10 bg-white/[0.04] p-5"
            >
              <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${statusClass(demo.status)}`}>
                {getDemoVideoStatusLabel(demo.status)}
              </span>
              <h3 className="mt-4 text-xl font-semibold text-white">{demo.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">{demo.audience}</p>
              <p className="mt-4 text-xs uppercase tracking-[0.22em] text-slate-500">Primary route</p>
              <p className="mt-1 font-mono text-xs text-slate-300">{demo.routePlan[0]}</p>
              <div className="mt-5">
                <DemoVideoLauncher demo={demo} />
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-10 sm:px-10">
        <div className="mb-6">
          <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">
            Phase two
          </p>
          <h2 className="mt-3 text-3xl font-semibold text-white">Remaining feature clips</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {phaseTwo.map((demo) => (
            <article
              key={demo.id}
              id={demo.id}
              className="scroll-mt-28 rounded-2xl border border-white/10 bg-white/[0.035] p-5"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${statusClass(demo.status)}`}>
                    {getDemoVideoStatusLabel(demo.status)}
                  </span>
                  <h3 className="mt-4 text-lg font-semibold text-white">{demo.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{demo.audience}</p>
                </div>
                <DemoVideoLauncher demo={demo} />
              </div>
            </article>
          ))}
        </div>
      </section>

      <footer className="border-t border-white/10 px-6 py-10 text-center text-sm text-slate-500">
        <Link href="/resources/templates" className="font-semibold text-slate-300 transition hover:text-white">
          Download the free templates
        </Link>
        <span className="mx-2">or</span>
        <Link href="#planner-command-center-walkthrough" className="font-semibold text-slate-300 transition hover:text-white">
          return to the hero walkthrough
        </Link>
      </footer>
    </main>
  );
}
