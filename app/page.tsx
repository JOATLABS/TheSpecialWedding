"use client";
import {
  UserGroupIcon,
  EnvelopeIcon,
  CalendarDaysIcon,
  PhotoIcon,
  BellAlertIcon,
  QrCodeIcon,
  MapPinIcon,
  RectangleGroupIcon,
  CheckBadgeIcon,
} from "@heroicons/react/24/outline";
import RosePetals from "./components/ui/RosePetals";
import React from "react";

type Feature = {
  title: string;
  description: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
};

type Metric = { label: string; value: string; subtext: string };

type Testimonial = { quote: string; name: string; role: string };

type PricingTier = {
  name: string;
  price: string;
  cadence: string;
  badge?: string;
  features: string[];
  cta: string;
  emphasized?: boolean;
};

const features: Feature[] = [
  {
    title: "Guest Lists & Segmentation",
    description:
      "Import guests, manage households and plus‑ones, and segment by role or RSVP state.",
    icon: UserGroupIcon,
  },
  {
    title: "Digital Invitations",
    description:
      "Send branded email invites with personalized links and track opens and bounces.",
    icon: EnvelopeIcon,
  },
  {
    title: "RSVP Tracking",
    description:
      "Real‑time RSVP collection with meal choices, allergies, and attendance updates.",
    icon: CheckBadgeIcon,
  },
  {
    title: "Seating & Tables",
    description:
      "Arrange tables effortlessly and export seating charts for coordinators and vendors.",
    icon: RectangleGroupIcon,
  },
  {
    title: "Timeline & Tasks",
    description:
      "Plan ceremonies and receptions with to‑dos, reminders, and a shared day‑of schedule.",
    icon: CalendarDaysIcon,
  },
  {
    title: "Gallery & Sharing",
    description:
      "Collect and curate photos from guests; publish a beautiful gallery for attendees.",
    icon: PhotoIcon,
  },
  {
    title: "Check‑in & QR",
    description:
      "Approve arrivals with QR codes and live counts so lines move quickly at the venue.",
    icon: QrCodeIcon,
  },
  {
    title: "Maps & Directions",
    description:
      "Share venue maps, parking, and hotel blocks with smart directions for guests.",
    icon: MapPinIcon,
  },
  {
    title: "Reminders & Messaging",
    description:
      "Automated email reminders for RSVP deadlines, travel, and timeline changes.",
    icon: BellAlertIcon,
  },
];

const metrics: Metric[] = [
  { label: "Guests managed", value: "10k+", subtext: "across active weddings" },
  { label: "RSVP rate", value: "92%", subtext: "average response in 7 days" },
  { label: "Check‑in time", value: "<3s", subtext: "scan‑to‑confirm per guest" },
  { label: "On‑time reminders", value: "99.9%", subtext: "delivery reliability" },
];

const testimonials: Testimonial[] = [
  {
    quote:
      "Guest management, invitations, and seating finally live in one place. Our planners saved hours every week.",
    name: "Event Operations Lead",
    role: "Premier Venue Group",
  },
  {
    quote:
      "QR check‑in made our ceremony start on time with zero bottlenecks. The live counts were invaluable.",
    name: "Coordinator",
    role: "Coastal Weddings",
  },
];

const pricing: PricingTier[] = [
  {
    name: "Starter",
    price: "$29",
    cadence: "per wedding / month",
    features: [
      "Guest list & RSVP",
      "Email invitations",
      "Timeline & tasks",
      "Basic gallery",
    ],
    cta: "Get Started",
  },
  {
    name: "Professional",
    price: "$54",
    cadence: "per wedding / month",
    badge: "Popular",
    features: [
      "Seating planner",
      "QR check‑in",
      "Vendor exports",
      "Priority support",
    ],
    cta: "Upgrade",
    emphasized: true,
  },
  {
    name: "Agency",
    price: "Custom",
    cadence: "multi‑wedding, multi‑tenant",
    features: [
      "Admin console",
      "SSO & roles",
      "Custom domains",
      "White‑labeling",
    ],
    cta: "Contact Sales",
  },
];

const partners = ["Stripe", "Zoom", "Google", "Mapbox"];

export default function HomePage() {
  return (
    <main className="bg-slate-950 text-white">
      {/* HERO */}
      <section className="relative overflow-hidden bg-gradient-to-b from-wedding-navy via-slate-900 to-slate-950">
        <RosePetals count={28} />
        <div className="absolute inset-0 opacity-40" style={{
          background:
            "radial-gradient(1200px 600px at 20% -10%, rgba(212,165,165,0.35), transparent), radial-gradient(900px 500px at 80% 10%, rgba(232,196,106,0.25), transparent)",
        }} />
        <div className="relative mx-auto max-w-7xl px-6 pb-24 pt-36 sm:px-10 lg:px-16 lg:pb-32">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-sm backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-wedding-rose" />
                Wedding Planner SaaS
              </div>
              <h1 className="mt-6 text-4xl font-semibold leading-tight sm:text-5xl md:text-6xl">
                Plan, invite, and celebrate—beautifully coordinated in one platform.
              </h1>
              <p className="mt-6 text-lg text-slate-200 sm:max-w-xl">
                A multi‑tenant workspace for planners and couples to run guest lists, invitations, RSVPs, seating, timelines, reminders, and day‑of check‑ins.
              </p>
              <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
                <a
                  href="#pricing"
                  className="flex items-center justify-center rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg transition hover:bg-wedding-blush"
                >
                  View Pricing
                </a>
                <a
                  href="/admin/login"
                  className="flex items-center justify-center rounded-full border border-white/30 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/50"
                >
                  Admin Login
                </a>
              </div>
              <div className="mt-12 flex flex-wrap items-center gap-x-8 gap-y-4 text-sm text-slate-300/90">
                <span className="text-xs text-slate-300/70">Trusted by modern planners:</span>
                {partners.map((p) => (
                  <span key={p}>{p}</span>
                ))}
              </div>
            </div>
            <div className="relative">
              <div className="relative rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl shadow-2xl">
                <div className="text-sm text-slate-200">Wedding Day Timeline</div>
                <ol className="mt-4 space-y-3 text-slate-200">
                  <li className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    2:00 PM — Guest arrivals and QR check‑in
                  </li>
                  <li className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    3:00 PM — Ceremony begins
                  </li>
                  <li className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    5:30 PM — Dinner seating and toasts
                  </li>
                  <li className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    7:00 PM — First dance and open gallery link
                  </li>
                </ol>
                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
                    <p className="font-medium text-white">Live RSVP</p>
                    <p className="mt-2 text-xs text-slate-300">Real‑time responses and dietary notes.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
                    <p className="font-medium text-white">Smart Reminders</p>
                    <p className="mt-2 text-xs text-slate-300">Automated emails before key milestones.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="platform" className="relative mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-16">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-wedding-rose/40 to-transparent" />
        <h2 className="text-3xl font-semibold text-white sm:text-4xl">Everything planners need, in one place.</h2>
        <p className="mt-4 max-w-2xl text-base text-slate-200">
          Built specifically for wedding workflows—from invite to last dance. Mobile‑first and accessible across the board.
        </p>
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="group rounded-3xl border border-white/10 bg-white/5 p-6 transition hover:border-wedding-rose/60 hover:bg-wedding-rose/10">
              <div className="flex items-center justify-between text-sm text-slate-200">
                <f.icon className="h-6 w-6 text-wedding-rose" />
                <span className="text-xs uppercase tracking-widest text-wedding-rose/80">Included</span>
              </div>
              <h3 className="mt-4 text-lg font-semibold text-white">{f.title}</h3>
              <p className="mt-3 text-sm text-slate-200">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* METRICS + INFO */}
      <section className="relative bg-slate-900/60">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
        <div className="mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-16">
          <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
            <div className="rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-xl">
              <h3 className="text-xl font-semibold text-white">Operational clarity for every event.</h3>
              <p className="mt-3 text-sm text-slate-200">
                Live dashboards show RSVP velocity, arrival counts, and guest engagement across all weddings in your workspace.
              </p>
              <div className="mt-6 grid grid-cols-2 gap-4 text-center text-sm text-slate-200">
                {metrics.map((m) => (
                  <div key={m.label} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                    <p className="text-2xl font-semibold text-white">{m.value}</p>
                    <p className="mt-1 text-xs uppercase tracking-widest text-slate-300">{m.label}</p>
                    <p className="mt-2 text-[11px] text-slate-400">{m.subtext}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-xl">
              <h3 className="text-xl font-semibold text-white">Planners and venues love the flow.</h3>
              <div className="mt-6 grid gap-6">
                {testimonials.map((t) => (
                  <blockquote key={t.name} className="rounded-2xl border border-white/10 bg-white/5 p-5 text-slate-200">
                    <p className="text-base text-white">“{t.quote}”</p>
                    <p className="mt-4 text-xs font-semibold uppercase tracking-widest text-wedding-rose">{t.name}</p>
                    <p className="mt-1 text-[11px] uppercase tracking-[0.3em] text-slate-300">{t.role}</p>
                  </blockquote>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="pricing" className="relative bg-slate-950">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-wedding-rose/40 to-transparent" />
        <div className="mx-auto max-w-6xl px-6 py-20 sm:px-10 lg:px-12">
          <div className="text-center">
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">Simple pricing for every celebration.</h2>
            <p className="mt-4 text-base text-slate-200">
              Start small and scale to multiple weddings with agency controls and white‑label options.
            </p>
          </div>
          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {pricing.map((tier) => (
              <div
                key={tier.name}
                className={`relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-8 text-slate-200 backdrop-blur-xl transition hover:border-wedding-rose/60 ${
                  tier.emphasized ? "shadow-[0_20px_80px_rgba(212,165,165,0.35)]" : ""
                }`}
              >
                {tier.badge ? (
                  <div className="absolute right-6 top-6 inline-flex items-center gap-2 rounded-full border border-wedding-rose/40 bg-wedding-rose/20 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-wedding-rose-100">
                    {tier.badge}
                  </div>
                ) : null}
                <h3 className="text-xl font-semibold text-white">{tier.name}</h3>
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="text-4xl font-semibold text-white">{tier.price}</span>
                  <span className="text-xs uppercase tracking-[0.3em] text-slate-300">{tier.cadence}</span>
                </div>
                <ul className="mt-6 space-y-3 text-sm text-slate-200">
                  {tier.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-3">
                      <span className="h-1.5 w-1.5 rounded-full bg-wedding-rose" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <a
                  href="/admin/login"
                  className={`mt-8 flex items-center justify-center rounded-full px-5 py-3 text-sm font-semibold uppercase tracking-widest transition ${
                    tier.emphasized
                      ? "bg-wedding-rose text-slate-900 shadow-lg hover:bg-wedding-blush"
                      : "border border-white/20 text-white hover:border-white/40"
                  }`}
                >
                  {tier.cta}
                </a>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section id="cta" className="relative overflow-hidden bg-gradient-to-b from-slate-900 via-wedding-navy to-slate-950">
        <div className="relative mx-auto max-w-4xl px-6 py-24 text-center sm:px-10">
          <h2 className="text-4xl font-semibold text-white sm:text-5xl">Bring every detail together.</h2>
          <p className="mt-6 text-base text-slate-200">
            Manage invitations, RSVPs, seating, and day‑of execution with clarity and calm.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href="/admin/login"
              className="flex items-center justify-center rounded-full bg-white px-6 py-3 text-base font-semibold text-slate-900 transition hover:bg-slate-100"
            >
              Launch Console
            </a>
            <a
              href="mailto:hello@weddingwebapp.ai"
              className="flex items-center justify-center rounded-full border border-white/20 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/40"
            >
              Request a Demo
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/10 bg-slate-950/95">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-8 text-sm text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Wedding WebApp. Multi‑tenant wedding planner platform.</p>
          <nav className="flex flex-wrap items-center gap-6 text-xs uppercase tracking-[0.3em]">
            <a href="#platform" className="hover:text-white">Platform</a>
            <a href="#pricing" className="hover:text-white">Pricing</a>
            <a href="/admin/login" className="hover:text-white">Admin Login</a>
          </nav>
        </div>
      </footer>
    </main>
  );
}
