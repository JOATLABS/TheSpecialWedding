import Link from "next/link";
import Image from "next/image";
import { DeferredHomeEffects } from "./components/landing-page/DeferredHomeEffects.client";
import { FeatureShowcase } from "./components/landing-page/FeatureShowcase.client";
import { PricingSignupSection } from "./components/landing-page/PricingSignupSection.client";
import HomepageTemplatesBand from "./components/saas/HomepageTemplatesBand";
import SaasNav from "./components/saas/SaasNav";
import type { ThemeConfig } from "./types/wedding";

type Testimonial = {
  name: string;
  role: string;
  quote: string;
  result: string;
};

export type PricingTier = {
  id: string;
  name: string;
  tagline: string;
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

const fallbackPricing: PricingTier[] = [
  {
    id: "plan_boutique",
    name: "Boutique",
    tagline: "For solo planners onboarding their first weddings.",
    price: "$29",
    period: "/month",
    features: ["Up to 3 weddings", "150 guests per wedding", "Guest and RSVP manager", "100 AI credits/month"],
    cta: "Start Boutique",
  },
  {
    id: "plan_signature",
    name: "Signature",
    tagline: "For planners managing a growing calendar.",
    price: "$59",
    period: "/month",
    features: ["Up to 10 weddings", "350 guests per wedding", "Vendor collaboration", "300 AI credits/month"],
    cta: "Choose Signature",
    popular: true,
    savings: "Most popular",
  },
  {
    id: "plan_enterprise",
    name: "Enterprise",
    tagline: "For teams that need scale, support, and control.",
    price: "$149",
    period: "/month",
    features: ["Unlimited weddings", "Unlimited guests", "10 staff seats", "Dedicated support"],
    cta: "Go Enterprise",
  },
];

const testimonials: Testimonial[] = [
  {
    name: "Arielle Morgan",
    role: "Owner, Linen & Light Events",
    quote: "We stopped chasing spreadsheets and started running the studio from one place.",
    result: "18 hours saved each week",
  },
  {
    name: "Maya Chen",
    role: "Lead Planner, Atelier June",
    quote: "Couples see progress without asking for updates, and our team always knows what changed.",
    result: "42% faster vendor follow-up",
  },
  {
    name: "Noah Rivera",
    role: "Operations Director, Vow & Venue",
    quote: "It gave our planners a repeatable operating system without making the experience feel generic.",
    result: "3x more weddings per planner",
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
    question: "What happens after the trial?",
    answer:
      "Your data stays intact. You can select a plan, pause new wedding intake, or export the core workspace data before deciding.",
  },
];

const metrics = [
  { label: "Planner hours reclaimed", value: "18/wk" },
  { label: "Vendor follow-up lift", value: "42%" },
  { label: "Guest workflows automated", value: "11" },
];

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
  const year = new Date().getFullYear();

  return (
    <main className="min-h-screen overflow-x-hidden bg-slate-950 text-white">
      <SaasNav />

      <section className="relative isolate min-h-[92vh] overflow-hidden px-6 pt-28 sm:px-8 lg:px-12">
        <DeferredHomeEffects />
        <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-black/80 to-transparent" aria-hidden="true" />
        <div className="relative z-10 mx-auto grid max-w-7xl gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div className="max-w-3xl">
            <p className="mb-5 inline-flex rounded-full border border-rose-300/30 bg-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-rose-100">
              Wedding planning OS
            </p>
            <h1 className="text-5xl font-semibold leading-[0.95] tracking-normal text-white sm:text-6xl lg:text-7xl">
              Plan every wedding from one calm command center.
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-slate-200 sm:text-xl">
              Replace scattered spreadsheets, messages, documents, and timelines with a planner workspace that keeps couples, vendors, and teams in sync.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link
                href="#pricing"
                className="inline-flex items-center justify-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-950 shadow-xl shadow-rose-950/20 transition hover:-translate-y-0.5 hover:bg-rose-50"
              >
                Start 30-day trial
              </Link>
              <Link
                href="#showcase"
                className="inline-flex items-center justify-center rounded-full border border-white/25 px-6 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/10"
              >
                See the workspace
              </Link>
            </div>
            <dl className="mt-12 grid max-w-2xl grid-cols-3 gap-4 border-t border-white/10 pt-6">
              {metrics.map((metric) => (
                <div key={metric.label}>
                  <dt className="text-[11px] uppercase tracking-[0.24em] text-slate-400">{metric.label}</dt>
                  <dd className="mt-2 text-2xl font-semibold text-white">{metric.value}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="relative">
            <div className="absolute -inset-6 rounded-[2rem] bg-gradient-to-br from-wedding-rose/25 via-sky-300/10 to-wedding-gold/20 blur-3xl" aria-hidden="true" />
            <div className="relative overflow-hidden rounded-2xl border border-white/15 bg-white/[0.08] p-2 shadow-2xl shadow-black/40 backdrop-blur">
              <div className="flex items-center gap-2 border-b border-white/10 px-3 py-2" aria-hidden="true">
                <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-yellow-400/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-green-400/70" />
              </div>
              <div className="relative aspect-[16/10] rounded-b-xl bg-[#071020]">
                <Image
                  src="/dashboard.webp"
                  alt="The Special Wedding planner dashboard showing live wedding metrics, workflow insights, and planning tools"
                  fill
                  sizes="(min-width: 1280px) 604px, (min-width: 1024px) 46vw, calc(100vw - 48px)"
                  className="object-contain object-top"
                  priority
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      <HomepageTemplatesBand />

      <SectionBridge label="See what's inside" />

      <section id="showcase" className="scroll-mt-28 bg-slate-950 px-5 py-8 sm:px-8 sm:py-10 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="mb-6 grid gap-4 sm:mb-10 sm:gap-6 lg:grid-cols-[0.7fr_0.3fr] lg:items-end">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-wedding-rose">Planner workflow</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-normal text-white sm:mt-4 sm:text-5xl">
                See the actual workspace before you sign up.
              </h2>
            </div>
            <p className="max-w-md text-sm leading-6 text-slate-300 sm:leading-7 lg:justify-self-end">
              Featured planner workflows shown with real product screenshots so planners can inspect website setup, guest operations, communications, vendors, payments, and team controls before signing up.
            </p>
          </div>
          <FeatureShowcase />
        </div>
      </section>

      <SectionBridge label="Find your fit" />

      <PricingSignupSection pricing={fallbackPricing} theme={defaultTheme} />

      <SectionBridge label="What planners say" />

      <section className="bg-slate-950 px-6 py-16 sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-3">
          {testimonials.map((testimonial) => (
            <article key={testimonial.name} className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
              <p className="text-sm leading-7 text-slate-200">"{testimonial.quote}"</p>
              <div className="mt-6 border-t border-white/10 pt-5">
                <p className="font-semibold text-white">{testimonial.name}</p>
                <p className="text-sm text-slate-400">{testimonial.role}</p>
                <p className="mt-3 text-sm font-semibold text-emerald-200">{testimonial.result}</p>
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

      <footer className="border-t border-white/10 bg-black px-6 py-10 text-sm text-slate-400 sm:px-8 lg:px-12">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p>&copy; {year} The Special Wedding. All rights reserved.</p>
          <div className="flex flex-wrap gap-5">
            <Link href="/resources?tab=templates" className="hover:text-white">
              Free templates
            </Link>
            <Link href="/privacy" className="hover:text-white">
              Privacy
            </Link>
            <Link href="/terms" className="hover:text-white">
              Terms
            </Link>
            <Link href="/login" className="hover:text-white">
              Login
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
