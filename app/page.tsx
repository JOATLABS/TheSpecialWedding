"use client";

import Link from "next/link";
import { DeferredHomeEffects } from "./components/landing-page/DeferredHomeEffects.client";
import { FeatureShowcase } from "./components/landing-page/FeatureShowcase.client";
import { PricingSignupSection } from "./components/landing-page/PricingSignupSection.client";
import DemoVideoLauncher from "./components/saas/DemoVideoLauncher";
import HomepageTemplatesBand from "./components/saas/HomepageTemplatesBand";
import MarketingFooter from "./components/saas/MarketingFooter";
import SaasNav from "./components/saas/SaasNav";
import { FEATURE_DEMO_VIDEOS, HERO_DEMO_VIDEO, toPublicDemoVideo } from "./data/demoVideos";
import { serializeJsonLd } from "./seo/jsonLd";
import type { ThemeConfig } from "./types/wedding";
import HeroCardStack from "./components/HeroCardStack";

type Testimonial = {
  name: string;
  role: string;
  quote: string;
};

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

const testimonials: Testimonial[] = [
  {
    name: "Arielle Morgan",
    role: "Owner, Linen & Light Events",
    quote: "We stopped chasing spreadsheets and started running the studio from one place.",
  },
  {
    name: "Maya Chen",
    role: "Lead Planner, Atelier June",
    quote: "Couples see progress without asking for updates, and our team always knows what changed.",
  },
  {
    name: "Noah Rivera",
    role: "Operations Director, Vow & Venue",
    quote: "It gave our planners a repeatable operating system without making the experience feel generic.",
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

const metrics = [
  { label: "Hours reclaimed", value: "18/wk" },
  { label: "Follow-up lift", value: "42%" },
  { label: "Guest workflows", value: "11" },
];

const heroDashboardSizes = "(min-width: 1280px) 604px, (min-width: 1024px) 46vw, calc(100vw - 48px)";
const heroDashboardAvifSrcSet = "/dashboard-hero-768.avif 768w, /dashboard-hero-1200.avif 1200w";
const heroDashboardWebpSrcSet = "/dashboard-hero-768.webp 768w, /dashboard-hero-1200.webp 1200w";

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

      <section className="relative isolate overflow-hidden bg-slate-950" style={{ minHeight: '92vh' }}>
        {/* This hero was inspired and implemented based on the implementation at https://crazygl.com/hero/card-stack */}
        {/* Original implementation by @ybouane https://x.com/ybouane */}
        <div dangerouslySetInnerHTML={{ __html: '<!-- This hero was inspired and implemented based on the implementation at https://crazygl.com/hero/card-stack -->\n<!-- Original implementation by @ybouane https://x.com/ybouane -->' }} />
        <div style={{ '--crazygl-height': '92vh' } as React.CSSProperties}>
          <HeroCardStack
            contentType="heading"
            heading="Plan every wedding from one calm command center."
            subheading="Replace scattered spreadsheets, messages, documents, and timelines with a planner workspace that keeps couples, vendors, and teams in sync."
            screenshots={[
              "/dashboard.webp",
              "/wedding_config.webp",
              "/couple_portal_dashboard.webp",
              "/seating.webp",
              "/budget_management_dark_mode.webp",
              "/contract_canvas.webp",
              "/planner_inbox.webp",
              "/knowledgebase.webp"
            ]}
            groupOffsetX={0}
            groupOffsetY={0}
            stackOffsetX={0.06}
            stackOffsetY={0.04}
            stackOffsetZ={0.04}
            cardSize={2.4}
            screenBrightness={0.4}
            bgTop="#161a24"
            bgBottom="#06080d"
            edgeGlowColor="#56e3ff"
            contentAlign="start"
            paddingX={64}
            paddingY={48}
          />
        </div>
      </section>

      <HomepageTemplatesBand />

      <SectionBridge label="See what's inside" />

      <section id="showcase" className="scroll-mt-28 bg-slate-950 px-5 py-8 sm:px-8 sm:py-10 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="mb-6 max-w-4xl sm:mb-10">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">Planner workflow</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-normal text-white sm:mt-4 sm:text-5xl">
                See the actual workspace before you sign up.
              </h2>
            </div>
          </div>
          <FeatureShowcase demoVideosByFeatureId={featureDemosByFeatureId} />
        </div>
      </section>

      <SectionBridge label="Find your fit" />

      <PricingSignupSection pricing={fallbackPricing} theme={defaultTheme} />

      <SectionBridge label="Planner stories" />

      <section className="bg-slate-950 px-6 py-16 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-3">
          {testimonials.map((testimonial) => (
            <article key={testimonial.name} className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
              <p className="text-sm leading-7 text-slate-200">"{testimonial.quote}"</p>
              <div className="mt-6 border-t border-white/10 pt-5">
                <p className="font-semibold text-white">{testimonial.name}</p>
                <p className="text-sm text-slate-400">{testimonial.role}</p>
              </div>
            </article>
          ))}
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
