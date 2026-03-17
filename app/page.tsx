"use client";

import { getApiBaseUrl } from '@/utils/env';
import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";


import HeroAurora from "./components/ui/HeroAurora";
import HeroCanvas from "./components/ui/HeroCanvas";
import PetalCanvas from "./components/ui/PetalCanvas";
import InfiniteScrollWrapper from "./components/ui/InfiniteScrollWrapper";
import { SignupModal } from "./components/saas/SignupModal";
import { ThemeConfig } from "./types/wedding";

/* ═══════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════ */

type ShowcaseFeature = {
  id: string;
  title: string;
  tagline: string;
  image: string;
  category: string;
};

type Testimonial = {
  quote: string;
  name: string;
  role: string;
};

type PricingTier = {
  name: string;
  price: string;
  cadence: string;
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
   13 features mapped to real dashboard screenshots
   ═══════════════════════════════════════════════════════════ */

const showcaseFeatures: ShowcaseFeature[] = [
  {
    id: "guests",
    title: "Guest Management",
    tagline: "242 guests, RSVPs, plus-ones, groups — one live view.",
    image: "/guest_management.png",
    category: "Planning",
  },
  {
    id: "calendar",
    title: "Planning Calendar",
    tagline: "Tasks, deadlines, and Google Calendar sync built in.",
    image: "/calendar_management.png",
    category: "Planning",
  },
  {
    id: "budget",
    title: "Budget Tracker",
    tagline: "Track every dollar — $80k budget, $55k remaining, zero guesswork.",
    image: "/budget_management_dark_mode.png",
    category: "Finance",
  },
  {
    id: "seating",
    title: "Seating Orchestrator",
    tagline: "Drag guests to tables. 240 seated across 5 sections, 10 tables.",
    image: "/seating.png",
    category: "Planning",
  },
  {
    id: "packages",
    title: "Service Packages",
    tagline: "Build bookable tiers with AI pricing suggestions.",
    image: "/create_package_flow_with_ai_pricing_suggestion.png",
    category: "Business",
  },
  {
    id: "vendor",
    title: "Vendor Management",
    tagline: "CRM, contracts, and payments — every vendor in one hub.",
    image: "/vendor_management.png",
    category: "Business",
  },
  {
    id: "contracts",
    title: "Contract Canvas",
    tagline: "AI-generated clauses, placeholders, and e-sign — built from scratch.",
    image: "/contract_canvas.png",
    category: "Business",
  },
  {
    id: "payments",
    title: "Payment Management",
    tagline: "Incoming, outgoing, forecasts — with AI cash flow predictions.",
    image: "/payment_management.png",
    category: "Finance",
  },
  {
    id: "gallery",
    title: "Photo Gallery",
    tagline: "Upload, organize, and share wedding photos with clients.",
    image: "/gallery_management.png",
    category: "Experience",
  },
  {
    id: "forms",
    title: "Forms Canvas",
    tagline: "Drag-and-drop intake forms, questionnaires, and feedback — AI-assisted.",
    image: "/forms_canvas.png",
    category: "Experience",
  },
  {
    id: "reminders",
    title: "Reminders & Invites",
    tagline: "SMS and email — event reminders, RSVP nudges, custom messages.",
    image: "/reminders.png",
    category: "Communication",
  },
  {
    id: "config",
    title: "Wedding Configuration",
    tagline: "Events, privacy, RSVP settings, branding — all customizable per wedding.",
    image: "/wedding_config1.png",
    category: "Setup",
  },
  {
    id: "support",
    title: "Knowledge Base",
    tagline: "Guides, tutorials, and troubleshooting — searchable and categorized.",
    image: "/knowledgebase.png",
    category: "Support",
  },
];

/* ═══════════════════════════════════════════════════════════
   Metrics + Replacements (hardcoded for speed)
   ═══════════════════════════════════════════════════════════ */

const metrics = [
  { value: "48k+", label: "Guests managed" },
  { value: "5 days", label: "Avg. RSVP turnaround" },
  { value: "13", label: "Tools in one platform" },
  { value: "99.9%", label: "Uptime" },
];

const replacements = [
  "HoneyBook", "Aisle Planner", "Zola", "Google Sheets",
  "DocuSign", "Canva", "QuickBooks", "Trello",
];

/* ═══════════════════════════════════════════════════════════
   FAQs (hardcoded for speed)
   ═══════════════════════════════════════════════════════════ */

const faqs: FAQ[] = [
  {
    question: "Can I manage multiple weddings at once?",
    answer: "Yes. Each wedding gets its own workspace with separate guest lists, budgets, seating, and branding — all managed from a single dashboard.",
  },
  {
    question: "Is there support on the wedding day?",
    answer: "Signature and Agency plans include live chat with our success team plus on-call escalation for critical day-of moments.",
  },
  {
    question: "How does AI pricing suggestions work?",
    answer: "When creating service packages, our AI analyzes your market, services, and costs to suggest competitive pricing tiers — saving you hours of research.",
  },
  {
    question: "Can vendors collaborate in the platform?",
    answer: "Yes. Invite photographers, caterers, and venues into dedicated workspaces with role-based access to timelines, contracts, and file exchanges.",
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
    features: ["Guest & RSVP manager", "Email invitations", "Wedding website", "Timeline builder"],
    cta: "Start your free trial",
  },
  {
    name: "Signature",
    price: "$59",
    cadence: "per wedding / month",
    badge: "Popular",
    features: ["Seating orchestration", "AI pricing suggestions", "Automated reminders", "Vendor collaboration"],
    cta: "Start your free trial",
    emphasized: true,
  },
  {
    name: "Agency",
    price: "Custom",
    cadence: "multi-tenant deployments",
    features: ["Dedicated success architect", "Custom domains & branding", "SSO + role provisioning", "Compliance reporting"],
    cta: "Talk with sales",
  },
];

const agencyTier: PricingTier = {
  name: "Agency",
  price: "Custom",
  cadence: "multi-tenant deployments",
  features: ["Dedicated success architect", "Custom domains & branding", "SSO + role provisioning", "Compliance reporting"],
  cta: "Talk with sales",
};

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
        <p className="text-xs uppercase tracking-[0.5em] text-wedding-rose/80 mb-4">Every tool a planner needs</p>
        <h2 className="text-3xl font-semibold text-white sm:text-4xl">
          See what&apos;s inside your command center.
        </h2>
        <p className="mt-4 max-w-2xl mx-auto text-base text-slate-300">
          13 tools that replace scattered subscriptions. Click any feature — see the real dashboard.
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
                <p className="mt-1 text-xs text-slate-300 leading-relaxed animate-fade-in">
                  {feature.tagline}
                </p>
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
              <span className="ml-3 text-[10px] text-slate-500 font-mono">
                thespecialwedding.io/dashboard/{active.id}
              </span>
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
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={feature.image}
                    alt={`${feature.title} dashboard`}
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
              Every tool a planner needs. Finally, in one place.
            </h1>

            <p className="mt-6 text-lg text-slate-200 max-w-2xl mx-auto">
              Guest management, budgets, contracts, vendor CRM, seating, payments, forms, reminders, and day-of execution — woven into one elegant workspace.
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
                  Start your free trial
                </a>
              ) : (
                <span className="flex items-center justify-center rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-wedding-rose/40">
                  Start your free trial
                </span>
              )}
              {!isClone ? (
                <Link
                  href="/admin/login"
                  className="flex items-center justify-center rounded-full border border-white/30 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/60"
                >
                  Launch console
                </Link>
              ) : (
                <span className="flex items-center justify-center rounded-full border border-white/30 px-6 py-3 text-base font-semibold text-white backdrop-blur">
                  Launch console
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
          {/* Horizontal scroll on mobile/tablet, single row on desktop */}
          <div className="mt-10 grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-4">
            {pricing.map((tier) => (
              <div
                key={tier.name}
                className={`relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 px-4 py-4 sm:px-5 sm:py-5 lg:px-6 lg:py-7 text-slate-200 backdrop-blur-xl transition hover:border-wedding-rose/60 ${
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
              <blockquote key={t.name} className="rounded-[2rem] border border-white/10 bg-white/5 p-8 backdrop-blur-xl">
                <p className="text-lg text-white">&ldquo;{t.quote}&rdquo;</p>
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
            Stop stitching tools together. Start planning weddings.
          </h2>
          <p className="mt-6 text-base text-slate-200">
            Join planners who replaced 8+ subscriptions with one platform.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            {!isClone ? (
              <Link
                href="/admin/login"
                className="flex items-center justify-center rounded-full bg-white px-6 py-3 text-base font-semibold text-slate-900 transition hover:bg-slate-100"
              >
                Start your free trial
              </Link>
            ) : (
              <span className="flex items-center justify-center rounded-full bg-white px-6 py-3 text-base font-semibold text-slate-900">
                Start your free trial
              </span>
            )}
            {!isClone ? (
              <a
                href="mailto:hello@thespecialwedding.io"
                className="flex items-center justify-center rounded-full border border-white/20 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/40"
              >
                See it in action
              </a>
            ) : (
              <span className="flex items-center justify-center rounded-full border border-white/20 px-6 py-3 text-base font-semibold text-white backdrop-blur">
                See it in action
              </span>
            )}
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-slate-950">
        <div className="mx-auto max-w-6xl px-6 py-6 text-center">
          <p className="text-xs text-slate-500">
            © {new Date().getFullYear()} The Special Wedding. Built for planners who obsess over detail.
          </p>
        </div>
      </footer>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════
   Page component
   ═══════════════════════════════════════════════════════════ */

export default function HomePage() {
  const [isSignupModalOpen, setIsSignupModalOpen] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string | undefined>();
  const [apiPlans, setApiPlans] = useState<ApiPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [testimonials, setTestimonials] = useState<Testimonial[]>([
    {
      quote: "The Special Wedding replaced five subscriptions overnight. Every guest touchpoint feels intentional now.",
      name: "Maya Glenn",
      role: "Director of Events, Aurora Collective",
    },
    {
      quote: "I built a full service package with AI-suggested pricing in under ten minutes. My clients saw the quote the same afternoon.",
      name: "Elias Romero",
      role: "Lead Coordinator, Harbor & Bloom",
    },
  ]);

  // Fetch subscription plans from API (admin-configurable)
  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/public/subscription-plans`);
        if (response.ok) {
          const data = await response.json();
          setApiPlans(data.sort((a: ApiPlan, b: ApiPlan) => a.sort_order - b.sort_order));
        }
      } catch (error) {
        console.error('Failed to fetch subscription plans:', error);
      } finally {
        setPlansLoading(false);
      }
    };
    fetchPlans();
  }, []);

  // TODO: Fetch testimonials from API when endpoint exists
  // useEffect(() => { fetchTestimonials(); }, []);

  const handlePricingCTAClick = (planId: string) => {
    if (planId === 'agency') {
      window.location.href = 'mailto:sales@thespecialwedding.com?subject=Agency Plan Inquiry';
      return;
    }
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
      features: plan.features_list || [],
      cta: "Start your free trial",
      badge: plan.is_featured ? "Popular" : undefined,
      emphasized: plan.is_featured,
    }));

    return [...apiTiers, agencyTier];
  }, [apiPlans, plansLoading]);

  return (
    <main className="bg-slate-950 text-white relative">
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
