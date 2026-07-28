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
// 2026-07 pricing: the free tier is retired — every plan is paid with a
// 30-day trial. Two planner tiers; yearly = monthly × 10.
const fallbackPricing: PricingTier[] = [
  {
    id: "plan_boutique",
    name: "Solo Founding",
    price: "$49",
    period: "/month",
    features: [
      "Unlimited weddings",
      "Unlimited guests",
      "Vendor management",
      "Seating orchestration",
      "Automated reminders",
      "Calendar sync (Google, Outlook)",
      "300 AI credits/month",
      "25GB guest memories storage",
      "Email support",
    ],
    cta: "Choose Solo Founding",
    popular: true,
    savings: "Founding-member rate",
  },
  {
    id: "plan_solo_standard",
    name: "Solo Standard",
    price: "$99",
    period: "/month",
    features: [
      "Unlimited weddings",
      "Unlimited guests",
      "Everything in Solo Founding",
      "750 AI credits/month",
      "50GB guest memories storage",
      "Email support",
    ],
    cta: "Choose Solo Standard",
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
    question: "What happens when my 30-day trial ends?",
    answer:
      "Your data stays intact. Keep your plan to continue without interruption, or export the core workspace data before deciding.",
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

      <section className="relative isolate overflow-hidden bg-slate-950 px-5 pb-24 pt-32 sm:px-8 sm:pb-28 sm:pt-36 lg:px-12 lg:pb-32">
        <div
          className="absolute inset-0 -z-10 bg-[radial-gradient(900px_620px_at_50%_8%,rgba(212,165,165,0.2),transparent_68%)]"
          aria-hidden="true"
        />
        <div className="mx-auto max-w-7xl">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-5xl font-semibold leading-[0.98] tracking-[-0.035em] text-white sm:text-6xl lg:text-7xl">
              One workspace. Every wedding you run.
            </h1>
            <p className="mx-auto mt-7 max-w-2xl text-lg leading-8 text-slate-300 sm:text-xl">
              Planner, couple, and guests — one connected record, with your operations kept private.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-5 sm:flex-row">
              <Link
                href="/#pricing"
                className="inline-flex min-h-12 items-center justify-center rounded-full bg-wedding-rose px-8 py-3 text-base font-semibold text-slate-950 shadow-lg shadow-wedding-rose/20 transition hover:bg-wedding-blush focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-wedding-rose"
              >
                Start your 30-day trial
              </Link>
              <Link
                href="/#showcase"
                className="text-base font-semibold text-white underline decoration-wedding-rose/70 underline-offset-4 transition hover:text-wedding-rose focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
              >
                See how it works ›
              </Link>
            </div>
          </div>
          <div className="mt-16 sm:mt-20">
            <PhaseOneHeroProof demo={heroDemo} />
          </div>
        </div>
      </section>

      <HomepageTemplatesBand />

      <section id="showcase" className="scroll-mt-28 bg-slate-950 px-5 py-20 sm:px-8 sm:py-24 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="mx-auto mb-16 max-w-3xl text-center sm:mb-20">
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">Planner outcomes</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-normal text-white sm:text-5xl">
              See how one connected record changes the work.
            </h2>
          </div>
          <FeatureShowcase demoVideosByFeatureId={featureDemosByFeatureId} />
        </div>
      </section>

      <PricingSignupSection pricing={fallbackPricing} theme={defaultTheme} />

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
