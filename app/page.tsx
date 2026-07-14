"use client";

import Link from "next/link";
import { FeatureShowcase } from "./components/landing-page/FeatureShowcase.client";
import { PhaseOneHeroProof } from "./components/landing-page/PhaseOneHeroProof";
import { PricingSignupSection } from "./components/landing-page/PricingSignupSection.client";
import HomepageTemplatesBand from "./components/saas/HomepageTemplatesBand";
import MarketingFooter from "./components/saas/MarketingFooter";
import SaasNav from "./components/saas/SaasNav";
import { FEATURE_DEMO_VIDEOS, HERO_DEMO_VIDEO, toPublicDemoVideo } from "./data/demoVideos";
import { serializeJsonLd } from "./seo/jsonLd";
import type { ThemeConfig } from "./types/wedding";

export type PricingTier = {
  id: string;
  name: string;
  price: string;
  period: string;
  features: string[];
  cta: string;
  popular?: boolean;
  savings?: string;
};

const defaultTheme: ThemeConfig = {
  primary_color: "#D4A5A5",
  secondary_color: "#E8C46A",
  accent_color: "#FFE4D6",
  background_style: "gradient",
  font_style: "elegant",
};

// IMPORTANT: keep in sync with scripts/seed_subscription_plans.py and
// app/api/subscription_management.py::seed_default_subscription_plans.
// The client-side <PricingSignupSection> fetches /public/subscription-plans
// and swaps this fallback out after ~800ms, but server-rendered HTML uses
// THIS array — which means crawlers, social share previews, and the
// first-paint flash all read from here. Stale values here = stale SEO.
const fallbackPricing: PricingTier[] = [
  {
    id: "plan_solo",
    name: "Solo",
    price: "$0",
    period: "/month",
    features: [
      "1 wedding to try us out",
      "Guest list & RSVP system",
      "Branded wedding website",
      "Basic timeline builder",
      "1GB guest memories storage",
    ],
    cta: "Start free",
  },
  {
    id: "plan_boutique",
    name: "Boutique",
    price: "$49",
    period: "/month",
    features: [
      "Unlimited weddings",
      "Unlimited guests",
      "Vendor management",
      "Seating orchestration",
      "300 AI credits/month",
      "25GB guest memories storage",
    ],
    cta: "Choose Boutique",
  },
  {
    id: "plan_signature",
    name: "Signature",
    price: "$149",
    period: "/month",
    features: [
      "Unlimited weddings",
      "Unlimited guests",
      "Team collaboration (5 staff seats)",
      "Vendor-collaboration workspaces",
      "Planner storefront on a shareable platform URL",
      "Optional custom domain",
      "1,500 AI credits/month",
      "100GB guest memories storage",
    ],
    cta: "Choose Signature",
    popular: true,
    savings: "Most popular",
  },
  {
    id: "plan_enterprise",
    name: "Enterprise",
    price: "$399",
    period: "/month",
    features: [
      "Unlimited weddings",
      "Unlimited guests",
      "20 staff seats",
      "Planner storefront on a shareable platform URL",
      "Optional custom domain",
      "5,000 AI credits/month",
      "500GB guest memories storage",
      "Support-assisted launch planning",
    ],
    cta: "Choose Enterprise",
  },
];

const faqs = [
  {
    question: "Can we bring over existing weddings?",
    answer:
      "Yes. You can import guests, vendors, notes, tasks, and timelines from existing planning files, then invite couples when the workspace is ready.",
  },
  {
    question: "Does the couple see the same dashboard?",
    answer:
      "Couples get a guided portal with the pieces you choose to share. Planner operations, internal notes, and team workflows stay private.",
  },
  {
    question: "Can this support a team?",
    answer:
      "Yes. Roles, handoffs, dashboards, and shared planning workflows are designed for studios with multiple planners and assistants.",
  },
  {
    question: "What happens after the free wedding?",
    answer:
      "Your data stays intact. You can select a paid plan, pause new wedding intake, or export the core workspace data before deciding.",
  },
];

const faqPageJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: faqs.map((faq) => ({
    '@type': 'Question',
    name: faq.question,
    acceptedAnswer: {
      '@type': 'Answer',
      text: faq.answer,
    },
  })),
};

function SectionBridge({ label }: { label: string }) {
  return (
    <div className="pointer-events-none flex items-center justify-center py-8 sm:py-10" aria-hidden="true">
      <div className="h-px w-16 bg-gradient-to-r from-transparent via-slate-400 to-transparent" />
      <span className="mx-4 text-[11px] font-semibold uppercase tracking-[0.5em] text-slate-300">{label}</span>
      <div className="h-px w-16 bg-gradient-to-r from-transparent via-slate-400 to-transparent" />
    </div>
  );
}

export default function HomePage() {
  const heroDemo = toPublicDemoVideo(HERO_DEMO_VIDEO);
  const featureDemosByFeatureId = Object.fromEntries(
    FEATURE_DEMO_VIDEOS.map((demo) => [demo.featureId, toPublicDemoVideo(demo)]),
  );

  return (
    <main className="min-h-screen overflow-x-hidden bg-slate-950 text-white">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(faqPageJsonLd) }}
      />
      <SaasNav />

      <section className="relative isolate overflow-hidden bg-slate-950 px-5 pb-20 pt-32 sm:px-8 sm:pb-24 sm:pt-36 lg:px-12 lg:pb-28">
        <div
          className="absolute inset-0 -z-10 bg-[radial-gradient(900px_620px_at_12%_10%,rgba(212,165,165,0.2),transparent_68%),radial-gradient(900px_620px_at_90%_18%,rgba(232,196,106,0.12),transparent_68%)]"
          aria-hidden="true"
        />
        <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[minmax(0,0.78fr)_minmax(520px,1.22fr)] lg:gap-14">
          <div className="max-w-xl">
            <h1 className="text-5xl font-semibold leading-[0.98] tracking-[-0.035em] text-white sm:text-6xl lg:text-7xl">
              The connected operating system built specifically for wedding planners.
            </h1>
            <p className="mt-7 text-lg leading-8 text-slate-300 sm:text-xl">
              Replace scattered spreadsheets, messages, documents, and timelines with one planner-owned workspace that keeps couples, guests, vendors, and teams aligned.
            </p>
            <div className="mt-9 flex flex-col gap-4 sm:flex-row sm:items-center">
              <Link
                href="/#pricing"
                className="inline-flex min-h-12 items-center justify-center rounded-full bg-wedding-rose px-7 py-3 text-base font-semibold text-slate-950 shadow-lg shadow-wedding-rose/20 transition hover:bg-wedding-blush focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-wedding-rose"
              >
                Start one wedding free
              </Link>
              <Link
                href="/#showcase"
                className="inline-flex min-h-12 items-center justify-center rounded-full border border-white/20 px-7 py-3 text-base font-semibold text-white transition hover:border-white/40 hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
              >
                See the connected workspace
              </Link>
            </div>
          </div>
          <PhaseOneHeroProof demo={heroDemo} />
        </div>
      </section>

      <HomepageTemplatesBand />

      <SectionBridge label="See what's inside" />

      <section id="showcase" className="scroll-mt-28 bg-slate-950 px-5 py-8 sm:px-8 sm:py-10 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="mb-6 max-w-4xl sm:mb-10">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">Planner outcomes</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-normal text-white sm:mt-4 sm:text-5xl">
                See how one connected record changes the work.
              </h2>
              <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300 sm:text-lg">
                These are the four operating outcomes a systems-minded planner should be able to verify before signing up—not another disconnected feature list.
              </p>
            </div>
          </div>
          <FeatureShowcase demoVideosByFeatureId={featureDemosByFeatureId} />
        </div>
      </section>

      <SectionBridge label="Find your fit" />

      <PricingSignupSection pricing={fallbackPricing} theme={defaultTheme} />

      <SectionBridge label="Why this exists" />

      <section className="bg-slate-950 px-6 py-16 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-8 rounded-3xl border border-white/10 bg-white/[0.035] p-7 sm:p-10 lg:grid-cols-[0.82fr_1.18fr] lg:items-center">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">Founder perspective</p>
            <h2 className="mt-4 text-3xl font-semibold leading-tight text-white sm:text-4xl">
              Built by a systems engineer who watched the gaps fail a real wedding.
            </h2>
          </div>
          <div>
            <p className="text-base leading-8 text-slate-300">
              The Special Wedding began when JOAT Labs founder Emmanuel Akinwale watched his own planning experience fracture across spreadsheets, contracts, budget files, and email threads. Industrial engineering taught him the tools were not failing independently—the handoffs between them were.
            </p>
            <p className="mt-5 border-l-2 border-wedding-rose/70 pl-4 text-base font-semibold leading-7 text-slate-100">
              The tools are not the problem. The gaps between them are.
            </p>
          </div>
        </div>
      </section>

      <SectionBridge label="Still exploring" />

      <section className="bg-slate-950 px-6 py-16 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.75fr_1.25fr]">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-rose-200">Questions</p>
            <h2 className="mt-4 text-4xl font-semibold tracking-normal text-white">The details planners ask before switching.</h2>
          </div>
          <div className="grid gap-4">
            {faqs.map((faq) => (
              <article key={faq.question} className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
                <h3 className="text-lg font-semibold text-white">{faq.question}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-300">{faq.answer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
