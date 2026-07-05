import type { Metadata } from 'next';
import Link from 'next/link';

import DemoVideoLauncher from '@/components/saas/DemoVideoLauncher';
import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import {
  FEATURE_DEMO_VIDEOS,
  HERO_DEMO_VIDEO,
  type DemoVideo,
} from '@/data/demoVideos';
import { PUBLIC_LOGIN_PATH } from '@/seo/crawlPolicy';
import { serializeJsonLd } from '@/seo/jsonLd';

import SaasNav from '../../components/saas/SaasNav';

const DEMOS_PATH = '/resources/demos';
const DEMOS_URL = `https://thespecialwedding.io${DEMOS_PATH}`;
const TEMPLATES_PATH = '/resources/templates';

type FeatureDemo = DemoVideo & { featureId: string };

const CORE_PROOF_FEATURE_IDS = [
  'dashboard',
  'couple-portal',
  'wedding-website',
  'guest-management',
  'seating-orchestrator',
  'book-the-client',
  'vendor-network',
] as const;

const CORE_PROOF_DEMOS = CORE_PROOF_FEATURE_IDS.map((featureId) =>
  FEATURE_DEMO_VIDEOS.find((demo) => demo.featureId === featureId),
).filter((demo): demo is FeatureDemo => Boolean(demo));

const SUPPORTING_DEMOS = FEATURE_DEMO_VIDEOS.filter(
  (demo) => !CORE_PROOF_FEATURE_IDS.some((featureId) => featureId === demo.featureId),
);

const proofCopyByFeatureId: Record<(typeof CORE_PROOF_FEATURE_IDS)[number], string> = {
  dashboard:
    'A planner starts the day from one operating table instead of sweeping email, spreadsheets, and payment tabs.',
  'couple-portal':
    'Couples get calm self-service, so routine questions stop turning into midnight text threads.',
  'wedding-website':
    'The public wedding site reads from the same plan the planner manages, so schedule and RSVP details do not drift.',
  'guest-management':
    'Guest details flow into reminders, catering counts, seating, and exports without another reconciliation pass.',
  'seating-orchestrator':
    'Seating stays tied to the room, households, meal context, and the final day-of artifact.',
  'book-the-client':
    'Scope, signatures, payments, and vendor context stay attached to the wedding record.',
  'vendor-network':
    'Discovery, private CRM notes, contracts, files, and vendor performance live in one planner-owned system.',
};

const positioningCards = [
  {
    title: 'Connection over tools',
    body: 'The walkthroughs show what happens when the gaps between HoneyBook, Aisle Planner, Excel, email, and PDFs disappear.',
  },
  {
    title: 'Couple experience compounds',
    body: 'The planner system becomes the couple experience: portal, website, RSVP, memories, and updates all stay calm and current.',
  },
  {
    title: 'Boundaries by design',
    body: 'The right workspace protects the planner from late-night follow-up, scope creep, and fragmented client communication.',
  },
] as const;

const evaluationPaths = [
  {
    title: 'I need to see the workspace first',
    body: 'Start with the two-minute walkthrough, then watch Morning View and Guest Management.',
  },
  {
    title: 'I care about client experience',
    body: 'Watch the Couple Portal and Microsite clips to see how planner organization becomes visible calm.',
  },
  {
    title: 'I am comparing tools',
    body: 'Watch Vendor CRM, Contracts, Budget, and Seating to see the workflows generic CRMs do not own.',
  },
] as const;

export const metadata: Metadata = {
  title: 'Wedding Planner OS Walkthrough | The Special Wedding',
  description:
    'Watch business-outcome walkthroughs of The Special Wedding: one connected operating system for serious wedding planners replacing disconnected tools, spreadsheets, email, contracts, and client portals.',
  alternates: {
    canonical: DEMOS_PATH,
  },
  openGraph: {
    title: 'Watch The Special Wedding Planner OS in Action',
    description:
      'Real product walkthroughs for serious wedding planners who want one connected workspace instead of disconnected tools.',
    url: DEMOS_URL,
    siteName: 'The Special Wedding',
    type: 'website',
  },
  robots: {
    index: true,
    follow: true,
  },
};

function absoluteUrl(path?: string): string | undefined {
  if (!path) return undefined;
  if (/^https?:\/\//.test(path)) return path;
  return `https://thespecialwedding.io${path}`;
}

function isoDuration(totalSeconds: number): string {
  const seconds = Math.max(1, Math.round(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes === 0) return `PT${remainingSeconds}S`;
  if (remainingSeconds === 0) return `PT${minutes}M`;
  return `PT${minutes}M${remainingSeconds}S`;
}

const publishedDemos = [HERO_DEMO_VIDEO, ...CORE_PROOF_DEMOS, ...SUPPORTING_DEMOS].filter(
  (demo) => demo.assetUrl,
);

const demosJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'CollectionPage',
  '@id': DEMOS_URL,
  url: DEMOS_URL,
  name: 'The Special Wedding Planner OS Walkthroughs',
  description:
    'Business-outcome product walkthroughs showing how serious wedding planners replace disconnected tools with one connected workspace.',
  audience: {
    '@type': 'Audience',
    audienceType: 'Professional wedding planners',
  },
  hasPart: publishedDemos.map((demo) => ({
    '@type': 'VideoObject',
    name: demo.title,
    description: demo.audience,
    duration: isoDuration(demo.durationSeconds),
    uploadDate: demo.recordedAt,
    thumbnailUrl: absoluteUrl(demo.thumbnailUrl),
    contentUrl: absoluteUrl(demo.assetUrl),
    url: `${DEMOS_URL}#${demo.id}`,
  })),
};

export default function ProductDemosPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Resources', href: '/resources/blog' },
          { name: 'Planner OS Walkthroughs', href: DEMOS_PATH },
        ]}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(demosJsonLd) }}
      />

      <section className="relative overflow-hidden border-b border-white/10 bg-slate-950 px-6 pb-14 pt-32 sm:px-10">
        <div className="absolute inset-x-0 top-0 h-56 bg-[radial-gradient(circle_at_top,_rgba(224,160,166,0.16),_transparent_60%)]" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-6xl gap-10 lg:grid-cols-[0.58fr_0.42fr] lg:items-center">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.48em] text-wedding-rose/85">
              Planner operating proof
            </p>
            <h1 className="mt-5 max-w-3xl text-4xl font-semibold leading-tight text-white sm:text-5xl">
              See how one connected workspace removes the chaos between tools.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300">
              These are real product walkthroughs for professional wedding planners. They are framed around business outcomes: fewer scattered systems, calmer couples, cleaner vendor handoffs, and a planner workspace that protects time.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <DemoVideoLauncher
                demo={HERO_DEMO_VIDEO}
                label="Watch 2-minute walkthrough"
                variant="outline"
              />
              <Link
                href={PUBLIC_LOGIN_PATH}
                className="inline-flex items-center justify-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100"
              >
                Start with one wedding free
              </Link>
              <Link
                href={TEMPLATES_PATH}
                className="inline-flex items-center justify-center rounded-full border border-white/15 px-6 py-3 text-sm font-semibold text-white transition hover:border-wedding-rose/50 hover:text-wedding-rose"
              >
                Get free templates
              </Link>
            </div>
            <p className="mt-5 text-sm leading-6 text-slate-500">
              Built for planners, not engaged-couple browsing. No trend reels. No generic SaaS tour.
            </p>
          </div>

          <div
            id={HERO_DEMO_VIDEO.id}
            className="rounded-3xl border border-white/10 bg-white/[0.04] p-4 shadow-2xl shadow-black/30"
          >
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-black">
              <video
                className="aspect-video w-full bg-black object-cover"
                controls
                playsInline
                preload="metadata"
                poster={HERO_DEMO_VIDEO.thumbnailUrl}
              >
                <source src={HERO_DEMO_VIDEO.assetUrl} type="video/mp4" />
              </video>
            </div>
            <div className="p-2 pt-5">
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-wedding-rose">
                Two-minute evaluation path
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-white">{HERO_DEMO_VIDEO.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">{HERO_DEMO_VIDEO.audience}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-12 sm:px-10">
        <div className="grid gap-4 md:grid-cols-3">
          {positioningCards.map((card) => (
            <article key={card.title} className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
              <h2 className="text-xl font-semibold text-white">{card.title}</h2>
              <p className="mt-3 text-sm leading-6 text-slate-300">{card.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-8 sm:px-10">
        <div className="mb-7 grid gap-4 lg:grid-cols-[0.56fr_0.44fr] lg:items-end">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">
              Core workflow proof
            </p>
            <h2 className="mt-3 text-3xl font-semibold text-white">
              Watch the parts of the system that make disconnection disappear.
            </h2>
          </div>
          <p className="text-sm leading-6 text-slate-400">
            Each clip shows a planner outcome, not a feature checklist. The through-line is simple: one source of truth feeding the planner, couple, guest, vendor, and payment surfaces.
          </p>
        </div>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {CORE_PROOF_DEMOS.map((demo) => (
            <article
              key={demo.id}
              id={demo.id}
              className="scroll-mt-28 rounded-2xl border border-white/10 bg-white/[0.04] p-5"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-wedding-rose">
                Business outcome
              </p>
              <h3 className="mt-3 text-xl font-semibold text-white">{demo.title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                {proofCopyByFeatureId[demo.featureId as (typeof CORE_PROOF_FEATURE_IDS)[number]]}
              </p>
              <p className="mt-4 text-sm leading-6 text-slate-500">{demo.audience}</p>
              <div className="mt-5">
                <DemoVideoLauncher demo={demo} label="Watch proof clip" />
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-10 sm:px-10">
        <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-6 sm:p-8">
          <div className="grid gap-8 lg:grid-cols-[0.38fr_0.62fr]">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">
                Choose the proof path
              </p>
              <h2 className="mt-3 text-3xl font-semibold text-white">Different concerns, same operating system.</h2>
              <p className="mt-4 text-sm leading-6 text-slate-400">
                A serious planner should not have to decode a feature grid. Start with the concern that matters most, then watch the workspace answer it.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              {evaluationPaths.map((path) => (
                <article key={path.title} className="rounded-2xl border border-white/10 bg-slate-950/60 p-5">
                  <h3 className="text-base font-semibold text-white">{path.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-400">{path.body}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-8 sm:px-10">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">
              More workflow moments
            </p>
            <h2 className="mt-3 text-3xl font-semibold text-white">Deeper proof when a planner wants to inspect the system.</h2>
          </div>
          <Link
            href={TEMPLATES_PATH}
            className="inline-flex items-center justify-center rounded-full border border-white/15 px-5 py-2 text-sm font-semibold text-white transition hover:border-wedding-rose/50 hover:text-wedding-rose"
          >
            Download the planner templates
          </Link>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {SUPPORTING_DEMOS.map((demo) => (
            <article
              key={demo.id}
              id={demo.id}
              className="scroll-mt-28 rounded-2xl border border-white/10 bg-white/[0.035] p-5"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-white">{demo.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{demo.audience}</p>
                </div>
                <DemoVideoLauncher demo={demo} label="Watch clip" />
              </div>
            </article>
          ))}
        </div>
      </section>

      <footer className="border-t border-white/10 px-6 py-10 text-center text-sm text-slate-500">
        <Link href={TEMPLATES_PATH} className="font-semibold text-slate-300 transition hover:text-white">
          Download the free templates
        </Link>
        <span className="mx-2">or</span>
        <Link href={PUBLIC_LOGIN_PATH} className="font-semibold text-slate-300 transition hover:text-white">
          start one wedding free
        </Link>
      </footer>
    </main>
  );
}
