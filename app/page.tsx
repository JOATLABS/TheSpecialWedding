"use client";

import { getApiBaseUrl } from '@/utils/env';
import React, { startTransition, useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";


import HeroAurora from "./components/ui/HeroAurora";
import HeroCanvas from "./components/ui/HeroCanvas";
import PetalCanvas from "./components/ui/PetalCanvas";
import InfiniteScrollWrapper from "./components/ui/InfiniteScrollWrapper";
import { SignupModal } from "./components/saas/SignupModal";
import SaasNav from "./components/saas/SaasNav";
import { MARKETING_FEATURES } from "./data/marketingFeatures";
import { ThemeConfig } from "./types/wedding";

/* ═══════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════ */

type Testimonial = {
  quote: string;
  name: string;
  role: string;
};

type PricingTier = {
  name: string;
  price: string;
  cadence: string;
  trialDays?: number;
  badge?: string;
  features: string[];
  cta: string;
  emphasized?: boolean;
};

type FAQ = {
  question: string;
  answer: string;
};

/* ═══════════════════════════════════════════════════════════
   Feature showcase data — hardcoded for performance
   18 features mapped to real dashboard screenshots
   ═══════════════════════════════════════════════════════════ */

const showcaseFeatures = MARKETING_FEATURES;

/* ═══════════════════════════════════════════════════════════
   Metrics + Replacements (hardcoded for speed)
   ═══════════════════════════════════════════════════════════ */

const metrics = [
  { value: "48k+", label: "Guests managed" },
  { value: "5 days", label: "Avg. RSVP turnaround" },
  { value: "18", label: "Tools in one platform" },
  { value: "99.9%", label: "Uptime" },
];

const replacements = [
  "HoneyBook", "Aisle Planner", "Zola", "Google Sheets",
  "DocuSign", "Canva", "QuickBooks", "Trello",
  "Typeform", "Mailchimp",
];

/* ═══════════════════════════════════════════════════════════
   FAQs (hardcoded for speed)
   ═══════════════════════════════════════════════════════════ */

const faqs: FAQ[] = [
  {
    question: "Can I manage multiple weddings at once?",
    answer: "Yes. Each wedding gets its own workspace with separate guest lists, budgets, seating, vendors, and branding — all managed from a single dashboard with portfolio-level analytics.",
  },
  {
    question: "What do my couples see?",
    answer: "Every couple gets their own Couple Portal with a personalized dashboard, timeline, payment history, form submissions, an inbox to message you directly, photo memories, gift registry, and FAQs — no app download needed.",
  },
  {
    question: "How does the AI help me run my business?",
    answer: "AI is woven into contracts (clause generation), Service Packages (pricing suggestions), reminders (tone-aware message drafting), budgets (spend forecasting), payments (cash flow predictions), and seating (conflict resolution) — saving hours of manual work every week.",
  },
  {
    question: "Can I send RSVPs and reminders via SMS?",
    answer: "Yes. Send RSVP invitations and follow-up reminders via SMS (Twilio or Telnyx) or email (Resend), with automatic fallback if SMS fails, delivery tracking, and AI-drafted messages in formal, friendly, or casual tones.",
  },
  {
    question: "Can vendors collaborate in the platform?",
    answer: "Yes. Invite photographers, caterers, and venues into dedicated workspaces with role-based access to timelines, contracts, deliverables, and file exchanges.",
  },
  {
    question: "Is there support on the wedding day?",
    answer: "Signature and Enterprise plans include live chat with our success team plus on-call escalation for critical day-of moments.",
  },
];

/* ═══════════════════════════════════════════════════════════
   Fallback pricing (if API fails)
   ═══════════════════════════════════════════════════════════ */

const fallbackPricing: PricingTier[] = [
  {
    name: "Boutique",
    price: "$29",
    cadence: "per wedding / month",
    trialDays: 30,
    features: [
      "Up to 3 weddings",
      "150 guests per wedding",
      "Guest & RSVP manager",
      "Email invitations",
      "Wedding website",
      "Timeline builder",
      "100 AI credits/month",
    ],
    cta: "Start 30-day trial",
  },
  {
    name: "Signature",
    price: "$59",
    cadence: "per wedding / month",
    trialDays: 30,
    badge: "Popular",
    features: [
      "Up to 10 weddings",
      "350 guests per wedding",
      "Everything in Boutique",
      "Seating orchestration",
      "Guest memories QR uploads",
      "Automated reminders",
      "Vendor collaboration",
      "300 AI credits/month",
      "Priority support",
    ],
    cta: "Start 30-day trial",
    emphasized: true,
  },
  {
    name: "Enterprise",
    price: "$149",
    cadence: "per wedding / month",
    trialDays: 30,
    features: [
      "Unlimited weddings",
      "Unlimited guests",
      "Everything in Signature",
      "White-label branding",
      "API access",
      "1000 AI credits/month",
      "10 staff seats",
      "Dedicated support",
      "Custom integrations",
    ],
    cta: "Start 30-day trial",
  },
];

const defaultTheme: ThemeConfig = {
  primary_color: "#D4A5A5",
  secondary_color: "#E8C46A",
  accent_color: "#FFE4D6",
  background_style: "gradient",
  font_style: "elegant",
};

interface ApiPlan {
  _id: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  trial_days?: number;
  features_list?: string[];
  is_featured: boolean;
  sort_order: number;
}

/* ═══════════════════════════════════════════════════════════
   Feature Showcase — Interactive Image Carousel
   Merges feature list + dashboard images into ONE section
   ═══════════════════════════════════════════════════════════ */

function FeatureShowcase({ isClone }: { isClone: boolean }) {
  const [activeIdx, setActiveIdx] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-cycle through features every 4 seconds
  const startAutoPlay = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(() => {
      setActiveIdx((prev) => (prev + 1) % showcaseFeatures.length);
    }, 4000);
  }, []);

  useEffect(() => {
    if (!isClone) startAutoPlay();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isClone, startAutoPlay]);

  const handleFeatureClick = (idx: number) => {
    setActiveIdx(idx);
    startAutoPlay(); // restart timer on manual click
  };

  const active = showcaseFeatures[activeIdx];

  return (
    <section className="relative mx-auto max-w-7xl px-6 py-16 sm:px-10 lg:px-16">
      <div className="text-center mb-12">
        <p className="text-xs uppercase tracking-[0.5em] text-wedding-rose/80 mb-4">{showcaseFeatures.length} tools in one platform</p>
        <h2 className="text-3xl font-semibold text-white sm:text-4xl">
          Your wedding planning command center.
        </h2>
        <p className="mt-4 max-w-2xl mx-auto text-base text-slate-300">
          Dashboards, inbox, couple portals, payments, forms, and more. Explore the platform through real product screens below.
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-[320px_1fr] items-start">
        {/* Feature list — left column (hidden on mobile, shown on lg+) */}
        <div className="hidden lg:flex flex-col gap-1 max-h-[540px] overflow-y-auto pr-2 scrollbar-thin">
          {showcaseFeatures.map((feature, idx) => (
            <button
              key={feature.id}
              type="button"
              onClick={() => handleFeatureClick(idx)}
              className={`group text-left rounded-xl px-4 py-3 transition-all duration-300 ${
                idx === activeIdx
                  ? "bg-wedding-rose/15 border border-wedding-rose/40 shadow-lg shadow-wedding-rose/10"
                  : "border border-transparent hover:bg-white/5"
              }`}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`text-[10px] uppercase tracking-[0.3em] px-2 py-0.5 rounded-full ${
                    idx === activeIdx
                      ? "bg-wedding-rose/25 text-wedding-rose"
                      : "bg-white/5 text-slate-500"
                  }`}
                >
                  {feature.category}
                </span>
              </div>
              <h3
                className={`mt-1.5 text-sm font-semibold transition-colors ${
                  idx === activeIdx ? "text-white" : "text-slate-400 group-hover:text-slate-200"
                }`}
              >
                {feature.title}
              </h3>
              {idx === activeIdx && (
                <>
                  <p className="mt-1 text-xs text-slate-300 leading-relaxed animate-fade-in">
                    {feature.tagline}
                  </p>
                  {feature.blogSlug && (
                    <Link
                      href={`/resources/blog/${feature.blogSlug}`}
                      className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-semibold text-wedding-rose transition hover:text-wedding-blush animate-fade-in"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Read the story
                      <span aria-hidden="true">→</span>
                    </Link>
                  )}
                </>
              )}
            </button>
          ))}
        </div>

        {/* Mobile: active feature label above image */}
        <div className="lg:hidden text-center mb-2">
          <span className="text-[10px] uppercase tracking-[0.3em] px-2.5 py-1 rounded-full bg-wedding-rose/20 text-wedding-rose">
            {active.category}
          </span>
          <h3 className="mt-2 text-lg font-semibold text-white">{active.title}</h3>
          <p className="mt-1 text-sm text-slate-300">{active.tagline}</p>
          {active.blogSlug && (
            <Link
              href={`/resources/blog/${active.blogSlug}`}
              className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-wedding-rose transition hover:text-wedding-blush"
            >
              Read the story
              <span aria-hidden="true">→</span>
            </Link>
          )}
        </div>

        {/* Dashboard image — right column */}
        <div className="relative">
          <div className="absolute -inset-4 rounded-3xl bg-gradient-to-br from-wedding-rose/10 via-transparent to-wedding-gold/10 blur-2xl opacity-60" />
          <div className="relative rounded-2xl border border-white/10 bg-white/5 p-2 backdrop-blur-sm shadow-[0_30px_100px_rgba(11,17,32,0.5)]">
            {/* Browser chrome */}
            <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10">
              <span className="h-2.5 w-2.5 rounded-full bg-red-400/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-yellow-400/60" />
              <span className="h-2.5 w-2.5 rounded-full bg-green-400/60" />
            </div>
            {/* Image container with smooth transition */}
            <div className="relative aspect-[16/10] overflow-hidden rounded-b-xl bg-slate-900">
              {showcaseFeatures.map((feature, idx) => (
                <div
                  key={feature.id}
                  className={`absolute inset-0 transition-opacity duration-500 ${
                    idx === activeIdx ? "opacity-100 z-10" : "opacity-0 z-0"
                  }`}
                >
                  <img
                    src={feature.image}
                    alt={`${feature.title} — ${feature.tagline}`}
                    className="absolute inset-0 w-full h-full object-cover object-top"
                    loading={idx < 3 ? "eager" : "lazy"}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Progress dots */}
          <div className="flex justify-center gap-1.5 mt-4">
            {showcaseFeatures.map((_, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleFeatureClick(idx)}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  idx === activeIdx
                    ? "w-6 bg-wedding-rose"
                    : "w-1.5 bg-white/20 hover:bg-white/40"
                }`}
                aria-label={`View feature ${idx + 1}`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════
   Section bridges
   ═══════════════════════════════════════════════════════════ */

function SectionBridge({ text }: { text: string }) {
  return (
    <div className="mx-auto max-w-7xl px-6 py-8 text-center sm:px-10 lg:px-16">
      <p className="text-[11px] uppercase tracking-[0.5em] text-slate-400/50">{text}</p>
    </div>
  );
}

function ScrollHint() {
  return (
    <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 text-slate-400/60">
      <span className="text-[10px] uppercase tracking-[0.4em]">Scroll to explore</span>
      <svg className="h-5 w-5 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Landing page content
   ═══════════════════════════════════════════════════════════ */

function LandingContent({
  isClone,
  pricing,
  testimonials,
  onPricingClick,
}: {
  isClone: boolean;
  pricing: PricingTier[];
  testimonials: Testimonial[];
  onPricingClick: (planId: string) => void;
}) {
  return (
    <>
      {/* ── HERO ────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-gradient-to-b from-[#0b1120] via-slate-950 to-slate-950">
        {!isClone && <HeroCanvas />}
        {/* PetalCanvas moved to main level for full-page coverage */}
        <HeroAurora />

        <div
          className="absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(900px 600px at 15% -10%, rgba(212,165,165,0.45), transparent 70%), radial-gradient(1200px 700px at 90% -10%, rgba(232,196,106,0.35), transparent 65%)",
          }}
        />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'160\' height=\'160\' viewBox=\'0 0 40 40\'%3E%3Cg fill=%27none%27 stroke=%27rgba(255,255,255,0.06)%27 stroke-width=%270.5%27%3E%3Cpath d=%27M0 0h40v40H0z%27/%3E%3Cpath d=%27M0 20h40M20 0v40%27/%3E%3C/g%3E%3C/svg%3E')] opacity-40" />

        <div className="relative mx-auto max-w-7xl px-6 pb-24 pt-36 sm:px-10 lg:px-16">
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-1.5 text-sm uppercase tracking-[0.3em] backdrop-blur">
              The Special Wedding
            </div>

            <h1 className="mt-8 text-4xl font-semibold leading-tight text-white sm:text-5xl md:text-6xl">
              Wedding planning software built for professional planners.
            </h1>

            <p className="mt-6 text-lg text-slate-200 max-w-2xl mx-auto">
              The all-in-one wedding planner CRM for guest management, seating, vendor contracts, budgets, payments, and a live couple portal — replacing HoneyBook, Aisle Planner, and Squarespace in one workspace.
            </p>

            {/* Replacement pills */}
            <div className="mt-8 flex flex-wrap justify-center gap-2">
              {replacements.map((name) => (
                <span
                  key={name}
                  className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-400"
                >
                  <span className="text-wedding-rose">✕</span>
                  {name}
                </span>
              ))}
            </div>

            <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-center">
              {!isClone ? (
                <a
                  href="#pricing"
                  className="flex items-center justify-center rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-wedding-rose/40 transition hover:bg-wedding-blush"
                >
                  Start 30-day trial
                </a>
              ) : (
                <span className="flex items-center justify-center rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-wedding-rose/40">
                  Start 30-day trial
                </span>
              )}
              {!isClone ? (
                <Link
                  href="/admin/login"
                  className="flex items-center justify-center rounded-full border border-white/30 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/60"
                >
                  Sign in to dashboard
                </Link>
              ) : (
                <span className="flex items-center justify-center rounded-full border border-white/30 px-6 py-3 text-base font-semibold text-white backdrop-blur">
                  Sign in to dashboard
                </span>
              )}
            </div>

            {/* Metrics strip */}
            <div className="mt-14 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {metrics.map((m) => (
                <div key={m.label} className="text-center">
                  <p className="text-2xl font-semibold text-white">{m.value}</p>
                  <p className="mt-1 text-[11px] uppercase tracking-[0.3em] text-slate-400">{m.label}</p>
                </div>
              ))}
            </div>
            <p className="mt-5 text-[11px] uppercase tracking-[0.28em] text-slate-500">
              As of April 2026. Metrics are directional snapshots from current product and marketing data.
            </p>
          </div>
        </div>

        {!isClone && <ScrollHint />}
      </section>

      {/* ── bridge: Hero → Features ── */}
      <SectionBridge text="See what's inside" />

      {/* ── FEATURE SHOWCASE (images + features in one section) ── */}
      <FeatureShowcase isClone={isClone} />

      {/* ── bridge: Features → Pricing ── */}
      <SectionBridge text="Find your fit" />

      {/* ── PRICING (admin-configurable via API) ────────── */}
      <section id={isClone ? undefined : "pricing"} className="relative bg-gradient-to-b from-slate-900 via-[#101826] to-slate-950">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-wedding-rose/40 to-transparent" />
        <div className="relative mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-12">
          <div className="text-center">
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">Plans that scale with every celebration.</h2>
            <p className="mt-4 text-base text-slate-200">
              Choose the plan that matches your roster. Scale up or down as your season unfolds.
            </p>
          </div>
          {/* Flex-wrap so any number of cards stay centered */}
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            {pricing.map((tier) => (
              <div
                key={tier.name}
                className={`relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 px-4 py-4 sm:px-5 sm:py-5 lg:px-6 lg:py-7 text-slate-200 backdrop-blur-xl transition hover:border-wedding-rose/60 w-full sm:w-[calc(50%-0.5rem)] lg:w-[280px] ${
                  tier.emphasized ? "shadow-[0_35px_120px_rgba(212,165,165,0.3)]" : ""
                }`}
              >
                {tier.badge ? (
                  <div className="absolute right-4 top-4 lg:right-5 lg:top-6 inline-flex items-center gap-1.5 rounded-full border border-wedding-rose/40 bg-wedding-rose/20 px-3 py-0.5 text-[10px] font-semibold uppercase tracking-[0.3em] text-wedding-rose">
                    {tier.badge}
                  </div>
                ) : null}
                {/* Mobile: horizontal layout — content left, button right */}
                {/* Desktop: vertical column with button pinned to bottom via mt-auto */}
                <div className="flex items-center gap-4 lg:flex-col lg:items-stretch lg:h-full">
                  {/* Left: plan info + features */}
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-semibold text-white">{tier.name}</h3>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className="text-2xl sm:text-3xl font-semibold text-white">{tier.price}</span>
                      <span className="text-[10px] uppercase tracking-[0.3em] text-slate-400">{tier.cadence}</span>
                    </div>
                    {tier.trialDays ? (
                      <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.2em] text-wedding-rose">
                        {tier.trialDays}-day free trial · no card required
                      </p>
                    ) : null}
                    <ul className="mt-2 space-y-0.5 text-sm text-slate-200">
                      {tier.features.map((feature) => (
                        <li key={feature} className="flex items-center gap-2">
                          <span className="h-1.5 w-1.5 rounded-full bg-wedding-rose flex-shrink-0" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                  </div>
                  {/* Right on mobile, bottom-center on desktop — mt-auto pushes to bottom */}
                  <button
                    type="button"
                    onClick={() => onPricingClick(tier.name.toLowerCase())}
                    className={`flex-shrink-0 lg:mt-auto lg:pt-4 lg:mx-auto rounded-full px-5 py-2 text-[11px] font-semibold uppercase tracking-[0.15em] whitespace-nowrap transition ${
                      tier.emphasized
                        ? "bg-wedding-rose text-slate-900 shadow-lg hover:bg-wedding-blush"
                        : "border border-white/20 text-white hover:border-white/40"
                    }`}
                  >
                    {tier.cta}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── bridge: Pricing → Testimonials ── */}
      <SectionBridge text="What planners say" />

      {/* ── TESTIMONIALS (admin-configurable) ── */}
      {testimonials.length > 0 && (
        <section className="relative mx-auto max-w-5xl px-6 py-16 sm:px-10">
          <div className="grid gap-6 md:grid-cols-2">
            {testimonials.map((t) => (
              <blockquote key={t.name} className="rounded-[2rem] border border-white/10 bg-white/5 p-8 backdrop-blur-xl" suppressHydrationWarning>
                <p className="text-lg text-white" suppressHydrationWarning>&ldquo;{t.quote}&rdquo;</p>
                <p className="mt-6 text-xs font-semibold uppercase tracking-[0.3em] text-wedding-rose">{t.name}</p>
                <p className="mt-1 text-[11px] uppercase tracking-[0.4em] text-slate-300">{t.role}</p>
              </blockquote>
            ))}
          </div>
        </section>
      )}

      {/* ── bridge: Testimonials → FAQ ── */}
      <SectionBridge text="Still exploring?" />

      {/* ── FAQ (hardcoded for speed) ── */}
      <section className="relative mx-auto max-w-5xl px-6 py-16 sm:px-10">
        <div className="text-center">
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">Frequently asked questions</h2>
        </div>
        <dl className="mt-10 space-y-4">
          {faqs.map((faq) => (
            <div key={faq.question} className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
              <dt className="text-lg font-semibold text-white">{faq.question}</dt>
              <dd className="mt-3 text-sm text-slate-200">{faq.answer}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* ── CTA ── */}
      <section id={isClone ? undefined : "cta"} className="relative overflow-hidden bg-gradient-to-b from-slate-950 via-wedding-navy to-slate-950">
        <div className="absolute inset-0 opacity-60" style={{ background: "radial-gradient(circle at 50% 0%, rgba(212,165,165,0.35), transparent 65%)" }} />
        <div className="relative mx-auto max-w-4xl px-6 py-24 text-center sm:px-10">
          <h2 className="text-4xl font-semibold text-white sm:text-5xl">
            Stop juggling tools. Start planning weddings.
          </h2>
          <p className="mt-6 text-base text-slate-200">
            Join planners who replaced 10+ subscriptions with one platform. Start a 30-day free trial today — no credit card required.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            {!isClone ? (
              <Link
                href="/admin/login"
                className="flex items-center justify-center rounded-full bg-white px-6 py-3 text-base font-semibold text-slate-900 transition hover:bg-slate-100"
              >
                Get started free
              </Link>
            ) : (
              <span className="flex items-center justify-center rounded-full bg-white px-6 py-3 text-base font-semibold text-slate-900">
                Get started free
              </span>
            )}
            {!isClone ? (
              <a
                href="mailto:hello@thespecialwedding.io?subject=I'd like a demo of The Special Wedding"
                className="flex items-center justify-center rounded-full border border-white/20 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/40"
              >
                Request a demo
              </a>
            ) : (
              <span className="flex items-center justify-center rounded-full border border-white/20 px-6 py-3 text-base font-semibold text-white backdrop-blur">
                Request a demo
              </span>
            )}
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-slate-950 border-t border-white/5">
        <div className="mx-auto max-w-6xl px-6 py-10">
          {/* Compare-to row — high commercial intent ("X alternative" SEO) */}
          <div className="mb-8 grid gap-6 sm:grid-cols-2 md:grid-cols-4">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Compare</h3>
              <ul className="mt-3 space-y-2 text-xs text-slate-500">
                {!isClone ? (
                  <>
                    <li><Link href="/compare/honeybook" className="transition hover:text-white">vs HoneyBook</Link></li>
                    <li><Link href="/compare/aisle-planner" className="transition hover:text-white">vs Aisle Planner</Link></li>
                    <li><Link href="/compare/dubsado" className="transition hover:text-white">vs Dubsado</Link></li>
                    <li><Link href="/compare/zola" className="transition hover:text-white">vs Zola</Link></li>
                    <li><Link href="/compare/the-knot" className="transition hover:text-white">vs The Knot</Link></li>
                    <li><Link href="/compare/planning-pod" className="transition hover:text-white">vs Planning Pod</Link></li>
                    <li><Link href="/compare" className="transition hover:text-white">All comparisons →</Link></li>
                  </>
                ) : (
                  <>
                    <li><span>vs HoneyBook</span></li>
                    <li><span>vs Aisle Planner</span></li>
                    <li><span>vs Dubsado</span></li>
                    <li><span>vs Zola</span></li>
                    <li><span>vs The Knot</span></li>
                    <li><span>vs Planning Pod</span></li>
                  </>
                )}
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Product</h3>
              <ul className="mt-3 space-y-2 text-xs text-slate-500">
                {!isClone ? (
                  <>
                    <li><Link href="/features" className="transition hover:text-white">Features</Link></li>
                    <li><Link href="/vendors" className="transition hover:text-white">Vendor directory</Link></li>
                    <li><Link href="/admin/login" className="transition hover:text-white">Sign in</Link></li>
                  </>
                ) : (
                  <>
                    <li><span>Features</span></li>
                    <li><span>Vendor directory</span></li>
                    <li><span>Sign in</span></li>
                  </>
                )}
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Resources</h3>
              <ul className="mt-3 space-y-2 text-xs text-slate-500">
                {!isClone ? (
                  <>
                    <li><Link href="/resources" className="transition hover:text-white">Blog</Link></li>
                    <li><Link href="/support" className="transition hover:text-white">Support</Link></li>
                    <li><a href="mailto:hello@thespecialwedding.io" className="transition hover:text-white">Contact</a></li>
                  </>
                ) : (
                  <>
                    <li><span>Blog</span></li>
                    <li><span>Support</span></li>
                    <li><span>Contact</span></li>
                  </>
                )}
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Legal</h3>
              <ul className="mt-3 space-y-2 text-xs text-slate-500">
                {!isClone ? (
                  <>
                    <li><Link href="/privacy" className="transition hover:text-white">Privacy</Link></li>
                    <li><Link href="/terms" className="transition hover:text-white">Terms</Link></li>
                  </>
                ) : (
                  <>
                    <li><span>Privacy</span></li>
                    <li><span>Terms</span></li>
                  </>
                )}
              </ul>
            </div>
          </div>

          <div className="flex flex-col items-center gap-3 border-t border-white/5 pt-6 sm:flex-row sm:justify-between">
            <p className="text-xs text-slate-500">
              © {new Date().getFullYear()} The Special Wedding. All rights reserved.
            </p>
            <p className="text-xs text-slate-500">
              Built by{' '}
              {!isClone ? (
                <a href="https://joatlabs.dev" target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white">
                  JOATLABS LLC
                </a>
              ) : (
                <span className="text-slate-400">JOATLABS LLC</span>
              )}
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════
   Page component
   ═══════════════════════════════════════════════════════════ */

const fallbackTestimonials: Testimonial[] = [
  {
    quote: "I used to juggle Google Sheets for guests, QuickBooks for budgets, and DocuSign for contracts — all disconnected. Now my 240-person guest list, seating chart, and budget tracker live in one place. Last Saturday I reassigned three tables in the seating orchestrator ten minutes before doors opened and the live headcount updated instantly at check-in.",
    name: "Maya Glenn",
    role: "Director of Events, Aurora Collective",
  },
  {
    quote: "Building a service package with AI-suggested pricing took me ten minutes instead of a full afternoon of market research. I sent the quote through the contract canvas with e-sign the same day, and the client’s milestone payment hit my dashboard before dinner. The entire book-to-pay cycle that used to take me a week now happens in a single session.",
    name: "Elias Romero",
    role: "Lead Coordinator, Harbor & Bloom",
  },
  {
    quote: "Coordinating twelve vendors across two venues was a nightmare of group texts and missed emails. Now every florist, caterer, and photographer has role-based access to the timeline, uploads deliverables to the gallery, and signs off on contracts inside the platform. The automated reminders alone saved me from three near-disasters last season.",
    name: "Priya Chandran",
    role: "Senior Planner, Verdant Celebrations",
  },
  {
    quote: "We run fifteen weddings a month and the planning calendar synced with Google Calendar keeps my team sane. I set up intake forms for new couples in the forms canvas, the RSVP reminders go out automatically by SMS and email, and every wedding has its own branded configuration so clients feel like they have a dedicated app. The knowledge base even onboards our junior planners faster than I can.",
    name: "Tomás Vega",
    role: "Founder, Día Perfecto Weddings",
  },
];

export default function HomePage() {
  const [isSignupModalOpen, setIsSignupModalOpen] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string | undefined>();
  const [apiPlans, setApiPlans] = useState<ApiPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [testimonials, setTestimonials] = useState<Testimonial[]>(fallbackTestimonials);
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    setHasHydrated(true);
  }, []);

  // Wait until after hydration before refreshing marketing data so SSR markup
  // and the first client render stay byte-for-byte identical.
  useEffect(() => {
    if (!hasHydrated) {
      return;
    }

    let cancelled = false;
    const frame = window.requestAnimationFrame(() => {
      void fetchPlans();
    });

    const fetchPlans = async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/public/subscription-plans`);
        if (response.ok) {
          const data = await response.json();
          if (!cancelled) {
            startTransition(() => {
              setApiPlans([...data].sort((a: ApiPlan, b: ApiPlan) => a.sort_order - b.sort_order));
            });
          }
        }
      } catch (error) {
        console.error('Failed to fetch subscription plans:', error);
      } finally {
        if (!cancelled) {
          setPlansLoading(false);
        }
      }
    };

    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
    };
  }, [hasHydrated]);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }

    let cancelled = false;
    const frame = window.requestAnimationFrame(() => {
      void fetchTestimonials();
    });

    const fetchTestimonials = async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/saas/public/testimonials`);
        if (response.ok) {
          const data = await response.json();
          if (!cancelled && data.length > 0) {
            startTransition(() => {
              setTestimonials(
                data.map((t: any) => ({
                  quote: t.quote,
                  name: t.name,
                  role: [t.role, t.company].filter(Boolean).join(', '),
                }))
              );
            });
          }
        }
      } catch (error) {
        console.error('Failed to fetch testimonials:', error);
        // Fallback testimonials are already set as initial state
      }
    };

    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
    };
  }, [hasHydrated]);

  const handlePricingCTAClick = (planId: string) => {
    setSelectedPlanId(planId);
    setIsSignupModalOpen(true);
  };

  const pricing: PricingTier[] = React.useMemo(() => {
    if (plansLoading || apiPlans.length === 0) {
      return fallbackPricing;
    }

    const apiTiers: PricingTier[] = apiPlans.map((plan) => ({
      name: plan.name,
      price: `$${plan.price_monthly}`,
      cadence: "per wedding / month",
      trialDays: plan.trial_days || undefined,
      features: plan.features_list || [],
      cta: plan.trial_days ? `Start ${plan.trial_days}-day trial` : `Start with ${plan.name}`,
      badge: plan.is_featured ? "Popular" : undefined,
      emphasized: plan.is_featured,
    }));

    return apiTiers;
  }, [apiPlans, plansLoading]);

  return (
    <main className="bg-slate-950 text-white relative">
      <SaasNav />
      <PetalCanvas count={64} />
      <InfiniteScrollWrapper>
        {(isClone) => (
          <LandingContent
            isClone={isClone}
            pricing={pricing}
            testimonials={testimonials}
            onPricingClick={isClone ? () => {} : handlePricingCTAClick}
          />
        )}
      </InfiniteScrollWrapper>

      <SignupModal
        isOpen={isSignupModalOpen}
        onClose={() => setIsSignupModalOpen(false)}
        selectedPlanId={selectedPlanId}
        theme={defaultTheme}
      />
    </main>
  );
}
