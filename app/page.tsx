"use client";

import {
  BellAlertIcon,
  CalendarDaysIcon,
  CheckBadgeIcon,
  EnvelopeIcon,
  MapPinIcon,
  PhotoIcon,
  QrCodeIcon,
  RectangleGroupIcon,
  SparklesIcon,
  UserGroupIcon,
} from "@heroicons/react/24/outline";
import React, { useState, useEffect } from "react";
import Link from "next/link";

import HeroAurora from "./components/ui/HeroAurora";
import HeroCanvas from "./components/ui/HeroCanvas";
import PetalCanvas from "./components/ui/PetalCanvas";
import { SignupModal } from "./components/saas/SignupModal";
import { ThemeConfig } from "./types/wedding";

type Feature = {
  title: string;
  description: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  category: string;
};

type Metric = {
  label: string;
  value: string;
  subtext: string;
};

type WorkflowStage = {
  title: string;
  subtitle: string;
  bullets: string[];
};

type Suite = {
  title: string;
  description: string;
  stat: string;
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

const features: Feature[] = [
  {
    title: "Guest lists & households",
    description: "Unify invites, plus‑ones, and households with filters for VIPs, vendors, and families.",
    icon: UserGroupIcon,
    category: "Planning",
  },
  {
    title: "Signature invitations",
    description: "Send branded email invitations, track bounces, and personalize every RSVP link.",
    icon: EnvelopeIcon,
    category: "Engagement",
  },
  {
    title: "Wedding websites",
    description: "Launch a stunning site for every celebration—custom domains, schedules, travel, and galleries.",
    icon: SparklesIcon,
    category: "Experience",
  },
  {
    title: "RSVP & meal selections",
    description: "Capture attendance, meal preferences, allergies, and notes in real time.",
    icon: CheckBadgeIcon,
    category: "Engagement",
  },
  {
    title: "Seating orchestration",
    description: "Drag-and-drop tables, respect family groupings, and export final charts instantly.",
    icon: RectangleGroupIcon,
    category: "Planning",
  },
  {
    title: "Ceremony & reception timeline",
    description: "Publish schedules for planners, vendors, and couples with role-based visibility.",
    icon: CalendarDaysIcon,
    category: "Execution",
  },
  {
    title: "Moments gallery",
    description: "Collect guest photos, curate galleries, and share highlights after the celebration.",
    icon: PhotoIcon,
    category: "Celebration",
  },
  {
    title: "Smart reminders",
    description: "Automate nudges for RSVP deadlines, travel updates, and day-of changes.",
    icon: BellAlertIcon,
    category: "Communication",
  },
  {
    title: "Touchless check-in",
    description: "Scan QR codes, monitor arrivals, and keep lines moving with live capacity counts.",
    icon: QrCodeIcon,
    category: "Execution",
  },
  {
    title: "Maps & travel",
    description: "Share venues, shuttles, and hotel blocks with smart directions for every guest.",
    icon: MapPinIcon,
    category: "Communication",
  },
];

const metrics: Metric[] = [
  { label: "Guest records", value: "48k", subtext: "managed across active weddings" },
  { label: "Average RSVP window", value: "5 days", subtext: "to reach 90% response" },
  { label: "Check-in speed", value: "2.8s", subtext: "median scan-to-confirm time" },
  { label: "Automation reliability", value: "99.9%", subtext: "delivery across reminders" },
];

const workflow: WorkflowStage[] = [
  {
    title: "Design the experience",
    subtitle: "Collaborative planning canvas",
    bullets: [
      "Launch weddings in minutes with reusable templates",
      "Assign visibility by planner, couple, or vendor team",
      "Model budgets, seating, and timelines side by side",
    ],
  },
  {
    title: "Invite & delight",
    subtitle: "Intelligent guest journeys",
    bullets: [
      "Personalized wedding websites with per-wedding slugs",
      "Automated reminders that adapt to RSVP behavior",
      "Guest portal with travel guidance and gallery teasers",
    ],
  },
  {
    title: "Execute flawlessly",
    subtitle: "Day-of command center",
    bullets: [
      "Touchless check-in with live headcounts and alerts",
      "Role-based run of show for coordinators and crew",
      "Instant galleries and thank-you follow ups post event",
    ],
  },
];

const suites: Suite[] = [
  {
    title: "Multi-tenant oversight",
    description: "Serve every planner, partner, or franchise in isolated workspaces with shared brand standards.",
    stat: "Scale to 100+ concurrent weddings with centralized governance.",
  },
  {
    title: "Vendor collaboration",
    description: "Loop photographers, caterers, and venues into dedicated timelines and file exchanges.",
    stat: "Reduce coordination rounds by 68% through unified updates.",
  },
  {
    title: "Insights & compliance",
    description: "Audit-ready exports cover guest consent, messaging logs, and accessibility notes.",
    stat: "SOC 2 aligned infrastructure keeps client data secure.",
  },
];

const testimonials: Testimonial[] = [
  {
    quote:
      "The Special Wedding gives our planners and couples a shared language. Every guest touchpoint feels intentional and elegant.",
    name: "Maya Glenn",
    role: "Director of Events, Aurora Collective",
  },
  {
    quote:
      "Check-in lines disappeared. The live dashboards let us choreograph the day like a performance instead of fighting fires.",
    name: "Elias Romero",
    role: "Lead Coordinator, Harbor & Bloom",
  },
];

// Fallback pricing if API fails
const fallbackPricing: PricingTier[] = [
  {
    name: "Boutique",
    price: "$29",
    cadence: "per wedding / month",
    features: [
      "Guest & RSVP manager",
      "Email invitations",
      "Wedding website",
      "Timeline builder",
    ],
    cta: "Start planning",
  },
  {
    name: "Signature",
    price: "$59",
    cadence: "per wedding / month",
    badge: "Popular",
    features: [
      "Seating orchestration",
      "QR check-in & live counts",
      "Automated reminders",
      "Vendor collaboration",
    ],
    cta: "Upgrade to Signature",
    emphasized: true,
  },
  {
    name: "Agency",
    price: "Custom",
    cadence: "multi-tenant deployments",
    features: [
      "Dedicated success architect",
      "Custom domains & branding",
      "SSO + role provisioning",
      "Compliance reporting",
    ],
    cta: "Talk with sales",
  },
];

// Agency tier (always hardcoded - contact sales only)
const agencyTier: PricingTier = {
  name: "Agency",
  price: "Custom",
  cadence: "multi-tenant deployments",
  features: [
    "Dedicated success architect",
    "Custom domains & branding",
    "SSO + role provisioning",
    "Compliance reporting",
  ],
  cta: "Talk with sales",
};

const faqs: FAQ[] = [
  {
    question: "Can I manage multiple weddings at once?",
    answer:
      "Yes. Workspaces let you run simultaneous weddings, each with their own permissions, branding, and analytics while maintaining agency-wide oversight.",
  },
  {
    question: "How do couples collaborate with planners?",
    answer:
      "Invite couples to a curated dashboard where they approve guest lists, monitor RSVPs, and review timelines without seeing internal notes.",
  },
  {
    question: "Is there support on the wedding day?",
    answer:
      "Signature and Agency plans include live chat with our success team plus on-call escalation for critical day-of moments.",
  },
  {
    question: "What’s next for messaging?",
    answer:
      "We are crafting a dedicated messaging studio that centralizes vendor, couple, and planner conversations with payment, contract, and budget context—launching soon.",
  },
];

const partners = ["Stripe", "Mailgun", "Mapbox", "Slack", "Zoom"];

// Default theme for the signup modal
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

export default function HomePage() {
  const [isSignupModalOpen, setIsSignupModalOpen] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string | undefined>();
  const [apiPlans, setApiPlans] = useState<ApiPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);

  // Fetch subscription plans from API
  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/public/subscription-plans`);
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

  const handlePricingCTAClick = (planId: string) => {
    // Handle Agency plan - open mailto instead of signup modal
    if (planId === 'agency') {
      window.location.href = 'mailto:sales@thespecialwedding.com?subject=Agency Plan Inquiry';
      return;
    }
    setSelectedPlanId(planId);
    setIsSignupModalOpen(true);
  };

  // Map API plans to PricingTier format and add Agency tier
  const pricing: PricingTier[] = React.useMemo(() => {
    if (plansLoading || apiPlans.length === 0) {
      return fallbackPricing;
    }

    const apiTiers: PricingTier[] = apiPlans.map((plan) => ({
      name: plan.name,
      price: `$${plan.price_monthly}`,
      cadence: "per wedding / month",
      features: plan.features_list || [],
      cta: plan.name === "Boutique" ? "Start planning" : `Upgrade to ${plan.name}`,
      badge: plan.is_featured ? "Popular" : undefined,
      emphasized: plan.is_featured,
    }));

    // Add Agency tier at the end
    return [...apiTiers, agencyTier];
  }, [apiPlans, plansLoading]);

  return (
    <main className="bg-slate-950 text-white">
      {/* HERO */}
      <section className="relative overflow-hidden bg-gradient-to-b from-[#0b1120] via-slate-950 to-slate-950">
        <HeroCanvas />
        <HeroAurora />
        <PetalCanvas count={64} />
        <div
          className="absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(900px 600px at 15% -10%, rgba(212,165,165,0.45), transparent 70%), radial-gradient(1200px 700px at 90% -10%, rgba(232,196,106,0.35), transparent 65%)",
          }}
        />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'160\' height=\'160\' viewBox=\'0 0 40 40\'%3E%3Cg fill=%27none%27 stroke=%27rgba(255,255,255,0.06)%27 stroke-width=%270.5%27%3E%3Cpath d=%27M0 0h40v40H0z%27/%3E%3Cpath d=%27M0 20h40M20 0v40%27/%3E%3C/g%3E%3C/svg%3E')] opacity-40" />
        <div className="relative mx-auto max-w-7xl px-6 pb-32 pt-40 sm:px-10 lg:px-16">
          <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_1fr]">
            <div className="relative">
              <div className="absolute -left-16 top-10 hidden h-60 w-60 rounded-full bg-wedding-rose/25 blur-3xl lg:block" />
              <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-1.5 text-sm uppercase tracking-[0.3em] backdrop-blur">
                The Special Wedding
              </div>
              <h1 className="mt-8 text-4xl font-semibold leading-tight text-white sm:text-5xl md:text-6xl">
                A stage-set platform where every wedding feels like a cinematic premiere.
              </h1>
              <p className="mt-6 text-lg text-slate-200 sm:max-w-xl">
                Sculpt invitations, RSVP journeys, wedding websites, seating, timelines, and on-site orchestration—woven together with romantic motion and intelligent automation.
              </p>
              <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
                <a
                  href="#pricing"
                  className="flex items-center justify-center rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-wedding-rose/40 transition hover:bg-wedding-blush"
                >
                  Explore pricing
                </a>
                <Link
                  href="/admin/login"
                  className="flex items-center justify-center rounded-full border border-white/30 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/60"
                >
                  Launch console
                </Link>
              </div>
              <div className="mt-14 flex flex-wrap items-center gap-x-8 gap-y-4 text-sm text-slate-300/90">
                <span className="text-xs uppercase tracking-[0.3em] text-slate-300/60">Trusted partners</span>
                {partners.map((partner) => (
                  <span key={partner}>{partner}</span>
                ))}
              </div>
            </div>
            <div className="relative">
              <div className="absolute inset-0 -translate-x-10 translate-y-12 rounded-[3rem] bg-wedding-rose/25 blur-3xl" />
              <div className="relative grid gap-6 rounded-[2.8rem] border border-white/15 bg-white/10 p-8 backdrop-blur-3xl shadow-[0_40px_140px_rgba(11,17,32,0.7)]">
                <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-white/15 via-white/5 to-transparent p-6 shadow-inner">
                  <p className="text-sm uppercase tracking-[0.3em] text-slate-300">Wedding overview</p>
                  <div className="mt-4 grid gap-4 text-slate-200 sm:grid-cols-3">
                    <div>
                      <p className="text-xs text-slate-300">Guests confirmed</p>
                      <p className="text-2xl font-semibold text-white">182</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-300">VIP arrivals</p>
                      <p className="text-2xl font-semibold text-white">17</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-300">Reminders queued</p>
                      <p className="text-2xl font-semibold text-white">5</p>
                    </div>
                  </div>
                </div>
                <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/10 p-5">
                  <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-wedding-rose/20 blur-3xl" />
                  <h3 className="text-sm font-semibold text-white">Ceremony timeline</h3>
                  <ul className="mt-3 space-y-2 text-xs text-slate-200">
                    <li className="flex items-start gap-3">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-wedding-rose" />
                      2:00 PM Guest arrivals & prosecco welcome
                    </li>
                    <li className="flex items-start gap-3">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-wedding-rose" />
                      3:00 PM Garden ceremony begins
                    </li>
                    <li className="flex items-start gap-3">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-wedding-rose" />
                      4:15 PM Sunset portraits & lounge hour
                    </li>
                  </ul>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-3xl border border-white/10 bg-white/10 p-5">
                    <h3 className="text-sm font-semibold text-white">Seating snapshot</h3>
                    <ul className="mt-3 space-y-2 text-xs text-slate-200">
                      <li>18 tables finalized</li>
                      <li>Allergies flagged for 12 guests</li>
                      <li>Vendor meals confirmed</li>
                    </ul>
                  </div>
                  <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-wedding-rose/25 via-transparent to-slate-900/40 p-5">
                    <h3 className="text-sm font-semibold text-white">Wedding website</h3>
                    <p className="mt-3 text-xs text-slate-200">
                      Share the per-wedding link with travel guides, RSVP, and gallery teasers—auto-updated from your workspace.
                    </p>
                  </div>
                </div>
                <div className="rounded-3xl border border-white/10 bg-white/10 p-6">
                  <p className="text-sm font-semibold text-white">Messaging studio (coming soon)</p>
                  <p className="mt-3 text-xs text-slate-200">
                    Centralize vendor and couple conversations with synced payments, contracts, and budgets in one timeline.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURE MOSAIC */}
      <section className="relative mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-16">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-wedding-rose/40 to-transparent" />
        <div className="grid gap-12 lg:grid-cols-[0.45fr_1fr]">
          <div>
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">A suite tailored for planners who obsess over detail.</h2>
            <p className="mt-4 text-base text-slate-200">
              The Special Wedding unites every workflow—from first guest upload to final thank-you—in a harmonized, mobile-first interface.
            </p>
            <div className="mt-8 space-y-6">
              {suites.map((suite) => (
                <div key={suite.title} className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
                  <p className="text-xs uppercase tracking-[0.3em] text-wedding-rose">{suite.title}</p>
                  <h3 className="mt-3 text-lg font-semibold text-white">{suite.description}</h3>
                  <p className="mt-3 text-sm text-slate-200">{suite.stat}</p>
                </div>
              ))}
              <div className="rounded-3xl border border-wedding-rose/40 bg-wedding-rose/15 p-6 backdrop-blur-xl">
                <p className="text-xs uppercase tracking-[0.3em] text-wedding-rose">On the horizon</p>
                <h3 className="mt-3 text-lg font-semibold text-white">Messaging studio</h3>
                <p className="mt-3 text-sm text-slate-200">
                  A dedicated dashboard for planner, couple, and vendor conversations with searchable history, shared assets, and hooks into payments, contracts, and budgets. Joining the platform soon.
                </p>
              </div>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-6 transition hover:border-wedding-rose/60 hover:bg-wedding-rose/10"
              >
                <div className="flex items-center justify-between text-sm text-slate-200">
                  <div className="flex items-center gap-2 text-wedding-rose">
                    <feature.icon className="h-6 w-6" aria-hidden="true" />
                    <span className="text-xs uppercase tracking-[0.3em] text-wedding-rose/80">{feature.category}</span>
                  </div>
                  <span className="text-xs uppercase tracking-[0.3em] text-slate-400 group-hover:text-wedding-rose/80">Included</span>
                </div>
                <h3 className="mt-4 text-lg font-semibold text-white">{feature.title}</h3>
                <p className="mt-3 text-sm text-slate-200">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* WORKFLOW */}
      <section className="relative bg-slate-900/60">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
        <div className="mx-auto max-w-6xl px-6 py-20 sm:px-10 lg:px-12">
          <div className="text-center">
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">From planning to celebration, choreographed in three acts.</h2>
            <p className="mt-4 text-base text-slate-200">
              Guide couples and vendors through a curated journey that keeps everyone aligned and inspired.
            </p>
          </div>
          <div className="mt-12 grid gap-8 lg:grid-cols-3">
            {workflow.map((stage, idx) => (
              <div key={stage.title} className="relative rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-xl">
                <div className="absolute -top-8 left-8 h-14 w-14 rounded-full bg-wedding-rose/30 backdrop-blur">
                  <div className="flex h-full items-center justify-center text-lg font-semibold text-white">0{idx + 1}</div>
                </div>
                <p className="text-xs uppercase tracking-[0.3em] text-wedding-rose">{stage.subtitle}</p>
                <h3 className="mt-4 text-xl font-semibold text-white">{stage.title}</h3>
                <ul className="mt-5 space-y-3 text-sm text-slate-200">
                  {stage.bullets.map((item) => (
                    <li key={item} className="flex gap-3">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-wedding-rose" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* METRICS & TESTIMONIALS */}
      <section className="relative mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-16">
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[2.5rem] border border-white/10 bg-white/5 p-10 backdrop-blur-xl">
            <h3 className="text-2xl font-semibold text-white">Operational clarity you can feel.</h3>
            <p className="mt-3 text-sm text-slate-200">
              Live dashboards surface RSVP velocity, seating readiness, task completion, and check-in momentum across every wedding under your care.
            </p>
            <div className="mt-8 grid gap-5 sm:grid-cols-2">
              {metrics.map((metric) => (
                <div key={metric.label} className="rounded-3xl border border-white/10 bg-white/10 p-6 text-center text-slate-200">
                  <p className="text-3xl font-semibold text-white">{metric.value}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.3em] text-slate-400">{metric.label}</p>
                  <p className="mt-2 text-[11px] text-slate-300">{metric.subtext}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-6">
            {testimonials.map((testimonial) => (
              <blockquote key={testimonial.name} className="rounded-[2rem] border border-white/10 bg-white/5 p-8 backdrop-blur-xl">
                <p className="text-lg text-white">“{testimonial.quote}”</p>
                <p className="mt-6 text-xs font-semibold uppercase tracking-[0.3em] text-wedding-rose">{testimonial.name}</p>
                <p className="mt-1 text-[11px] uppercase tracking-[0.4em] text-slate-300">{testimonial.role}</p>
              </blockquote>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="pricing" className="relative bg-gradient-to-b from-slate-900 via-[#101826] to-slate-950">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-wedding-rose/40 to-transparent" />
        <div className="relative mx-auto max-w-6xl px-6 py-20 sm:px-10 lg:px-12">
          <div className="text-center">
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">Pricing for every celebration cadence.</h2>
            <p className="mt-4 text-base text-slate-200">
              Choose the plan that matches your roster. Scale up or down as your season unfolds.
            </p>
          </div>
          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {pricing.map((tier) => (
              <div
                key={tier.name}
                className={`relative overflow-hidden rounded-[2.2rem] border border-white/10 bg-white/5 p-9 text-slate-200 backdrop-blur-xl transition hover:border-wedding-rose/60 ${
                  tier.emphasized ? "shadow-[0_35px_120px_rgba(212,165,165,0.3)]" : ""
                }`}
              >
                {tier.badge ? (
                  <div className="absolute right-8 top-8 inline-flex items-center gap-2 rounded-full border border-wedding-rose/40 bg-wedding-rose/20 px-4 py-1 text-xs font-semibold uppercase tracking-[0.4em] text-wedding-rose">
                    {tier.badge}
                  </div>
                ) : null}
                <h3 className="text-xl font-semibold text-white">{tier.name}</h3>
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="text-4xl font-semibold text-white">{tier.price}</span>
                  <span className="text-xs uppercase tracking-[0.4em] text-slate-400">{tier.cadence}</span>
                </div>
                <ul className="mt-6 space-y-3 text-sm text-slate-200">
                  {tier.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-3">
                      <span className="h-1.5 w-1.5 rounded-full bg-wedding-rose" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => handlePricingCTAClick(tier.name.toLowerCase())}
                  className={`mt-9 flex items-center justify-center rounded-full px-5 py-3 text-sm font-semibold uppercase tracking-[0.3em] transition ${
                    tier.emphasized
                      ? "bg-wedding-rose text-slate-900 shadow-lg hover:bg-wedding-blush"
                      : "border border-white/20 text-white hover:border-white/40"
                  }`}
                >
                  {tier.cta}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="relative mx-auto max-w-5xl px-6 py-20 sm:px-10">
        <div className="text-center">
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">Frequently asked questions</h2>
          <p className="mt-4 text-base text-slate-200">
            Everything you need to know about working with The Special Wedding.
          </p>
        </div>
        <dl className="mt-10 space-y-6">
          {faqs.map((faq) => (
            <div key={faq.question} className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
              <dt className="text-lg font-semibold text-white">{faq.question}</dt>
              <dd className="mt-3 text-sm text-slate-200">{faq.answer}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* CTA */}
      <section id="cta" className="relative overflow-hidden bg-gradient-to-b from-slate-950 via-wedding-navy to-slate-950">
        <div className="absolute inset-0 opacity-60" style={{ background: "radial-gradient(circle at 50% 0%, rgba(212,165,165,0.35), transparent 65%)" }} />
        <div className="relative mx-auto max-w-4xl px-6 py-24 text-center sm:px-10">
          <h2 className="text-4xl font-semibold text-white sm:text-5xl">Create memories that feel effortless from the first hello.</h2>
          <p className="mt-6 text-base text-slate-200">
            Give every planner, partner, and couple a stage worthy of their story with The Special Wedding.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="/admin/login"
              className="flex items-center justify-center rounded-full bg-white px-6 py-3 text-base font-semibold text-slate-900 transition hover:bg-slate-100"
            >
              Launch console
            </Link>
            <a
              href="mailto:hello@weddingwebapp.ai"
              className="flex items-center justify-center rounded-full border border-white/20 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/40"
            >
              Request a guided tour
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/10 bg-slate-950/90">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-8 text-sm text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} The Special Wedding. Multi-tenant wedding planner platform.</p>
          <nav className="flex flex-wrap items-center gap-6 text-xs uppercase tracking-[0.3em]">
            <a href="#platform" className="hover:text-white">Platform</a>
            <a href="#pricing" className="hover:text-white">Pricing</a>
            <Link href="/admin/login" className="hover:text-white">Admin login</Link>
          </nav>
        </div>
      </footer>

      {/* Signup Modal */}
      <SignupModal
        isOpen={isSignupModalOpen}
        onClose={() => setIsSignupModalOpen(false)}
        selectedPlanId={selectedPlanId}
        theme={defaultTheme}
      />
    </main>
  );
}
