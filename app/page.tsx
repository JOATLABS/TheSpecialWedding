type Feature = {
  title: string;
  description: string;
  highlight: string;
  icon: string;
};

type Metric = {
  label: string;
  value: string;
  subtext: string;
};

type UseCase = {
  title: string;
  description: string;
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

const features: Feature[] = [
  {
    title: "Adaptive Workflows",
    description: "Automate decisions with generative AI agents that respond instantly to customer signals across every touchpoint.",
    highlight: "Designed with mobile-first breakpoints so every interaction feels intentional.",
    icon: "⚡️",
  },
  {
    title: "Crystal Analytics",
    description: "Zoom into revenue, sentiment, and retention with pixel-perfect dashboards backed by secure data pipelines.",
    highlight: "Visual density inspired by high-fidelity dashboards for clarity at a glance.",
    icon: "📊",
  },
  {
    title: "Multiplayer Collaboration",
    description: "Get approvals, leave annotations, and ship campaigns with real-time co-editing and audit trails.",
    highlight: "Optimized for distributed teams syncing across time zones in the same canvas.",
    icon: "🤝",
  },
  {
    title: "AI Guardrails",
    description: "Protect customer privacy with automated compliance checks, redaction, and consent-aware messaging.",
    highlight: "Enterprise-grade policies shipped out-of-the-box with adaptive alerting.",
    icon: "🛡️",
  },
  {
    title: "Omni-channel Delivery",
    description: "Compose journeys once and publish to web, mobile, voice, and AR surfaces while staying on brand.",
    highlight: "Experience parity across landscape and portrait experiences by design.",
    icon: "🌐",
  },
  {
    title: "No-Code Extensions",
    description: "Bring your data, embed your logic, and extend with serverless actions without touching production APIs.",
    highlight: "Builder kits and SDKs so teams ship safely in hours, not quarters.",
    icon: "🧩",
  },
];

const metrics: Metric[] = [
  { label: "Activation lift", value: "+38%", subtext: "after automation launch" },
  { label: "Real-time decisions", value: "<120ms", subtext: "median orchestration latency" },
  { label: "Global teams", value: "62", subtext: "shipping on the same canvas" },
  { label: "Annual savings", value: "$4.7M", subtext: "average cost avoided" },
];

const useCases: UseCase[] = [
  {
    title: "Product Growth",
    description: "Trigger hyper-personal onboarding with predictive scoring, adaptive in-app tours, and instant paywall tests.",
  },
  {
    title: "Revenue Intelligence",
    description: "Forecast pipeline, route leads, and arm sellers with next-best actions synthesized from every dataset.",
  },
  {
    title: "Customer Care",
    description: "Resolve complex intents with multimodal AI copilots that surface answers, actions, and empathy in a single view.",
  },
  {
    title: "Ops Automation",
    description: "Run finance, logistics, and compliance on autopilot with AI agents that learn from every approval cycle.",
  },
];

const testimonials: Testimonial[] = [
  {
    quote: "Our launch velocity tripled. What used to be quarterly experiments now ship weekly with guardrails built in.",
    name: "Selena Rivers",
    role: "VP Growth, Meridian Labs",
  },
  {
    quote: "The experience parity across devices is unmatched. Designers iterate once and ship everywhere effortlessly.",
    name: "Hideki Watanabe",
    role: "Head of Product Design, NovaFleet",
  },
  {
    quote: "We replaced six disconnected tools with one luminous hub that keeps marketing, sales, and ops aligned.",
    name: "Jamie Ortega",
    role: "COO, SignalNorth",
  },
];

const pricing: PricingTier[] = [
  {
    name: "Starter",
    price: "$38",
    cadence: "per seat / month",
    features: [
      "Realtime dashboards",
      "Playbooks for growth teams",
      "Email + in-app channels",
      "SOC 2 Type II compliance",
    ],
    cta: "Start building",
  },
  {
    name: "AI Edge",
    price: "$54",
    cadence: "per seat / month",
    badge: "Popular",
    features: [
      "Predictive orchestration",
      "Unlimited AI copilots",
      "Revenue intelligence module",
      "Premium support, 1 hour SLA",
    ],
    cta: "Upgrade to AI Edge",
    emphasized: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    cadence: "tailored programs",
    features: [
      "Private cloud deployment",
      "Dedicated solutions architect",
      "24/7 compliance concierge",
      "On-site enablement",
    ],
    cta: "Talk to sales",
  },
];

const integrations = ["Mapbox", "Linktree", "Wirepas", "Sileon", "Letter", "Hippo", "Bloomreach"];

export default function HomePage() {
  return (
    <main className="bg-slate-950 text-white">
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <img
            src="https://cdn.builder.io/api/v1/image/assets%2F773f428d9fc94d15bfc15e9730159245%2F82f0228d717e4cff9049fe5ef2563b75?format=webp&width=1600"
            alt="Ambient neon tunnel"
            className="h-full w-full object-cover opacity-80"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-slate-950/70 via-slate-900/60 to-cyan-500/30" />
        </div>
        <div className="relative mx-auto max-w-7xl px-6 pb-24 pt-36 sm:px-10 lg:px-16 lg:pb-32">
          <div className="flex flex-col gap-12 lg:flex-row lg:items-center">
            <div className="max-w-2xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-2 text-sm backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-cyan-300" />
                Crafted for the Future of SaaS
              </div>
              <h1 className="mt-6 text-4xl font-semibold leading-tight sm:text-5xl md:text-6xl">
                Speed meets elegance for teams scaling intelligent experiences.
              </h1>
              <p className="mt-6 text-lg text-slate-200 sm:max-w-xl">
                Build luminous customer journeys with adaptive AI, glassmorphic visuals, and orchestrated workflows that feel handcrafted on every device.
              </p>
              <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
                <a
                  href="#pricing"
                  className="flex items-center justify-center rounded-full bg-cyan-400 px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-cyan-400/50 transition hover:bg-cyan-300"
                >
                  Start Your Journey
                </a>
                <a
                  href="#platform"
                  className="flex items-center justify-center rounded-full border border-white/20 px-6 py-3 text-base font-semibold text-white backdrop-blur transition hover:border-white/40"
                >
                  Explore the Platform
                </a>
              </div>
            </div>
            <div className="relative flex-1">
              <div className="absolute inset-0 -m-6 rounded-3xl bg-cyan-400/20 blur-3xl" />
              <div className="relative rounded-3xl border border-white/10 bg-white/10 p-8 backdrop-blur-xl shadow-2xl">
                <div className="flex items-center justify-between text-sm text-slate-200">
                  <span>AI Breakpoints Synopsis</span>
                  <span>v3.2</span>
                </div>
                <img
                  src="https://cdn.builder.io/api/v1/image/assets%2F773f428d9fc94d15bfc15e9730159245%2Febf3e12a670f41aca2792ba112036484?format=webp&width=800"
                  alt="Responsive breakpoint preview"
                  className="mt-6 w-full rounded-2xl border border-white/10"
                />
                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
                    <p className="font-medium text-white">Glasmorphic Cards</p>
                    <p className="mt-2 text-xs text-slate-300">Powered by AI layouts that glow with depth and precision.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
                    <p className="font-medium text-white">Neural Animations</p>
                    <p className="mt-2 text-xs text-slate-300">Adaptive parallax effects keep focus on outcomes, not noise.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="mt-16 flex flex-wrap items-center gap-x-10 gap-y-6 text-sm uppercase tracking-[0.2em] text-slate-300/80">
            <span className="text-xs text-slate-300/60">Trusted by teams who move fast:</span>
            {integrations.map((brand) => (
              <span key={brand} className="text-slate-200/80">
                {brand}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section id="platform" className="relative mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-16">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent" />
        <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <div className="rounded-4xl relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-white/10 via-white/5 to-transparent p-8 backdrop-blur-xl">
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">Compose intelligent journeys in minutes.</h2>
            <p className="mt-4 text-base text-slate-200">
              Combine data, content, and AI into a single command center. Build with intent using modular sections, test variations instantly, and orchestrate outcomes with serverless precision.
            </p>
            <div className="mt-8 grid gap-5 sm:grid-cols-2">
              {features.map((feature) => (
                <div key={feature.title} className="group rounded-3xl border border-white/10 bg-white/5 p-6 transition hover:border-cyan-300/60 hover:bg-cyan-300/10">
                  <div className="flex items-center justify-between text-sm text-slate-200">
                    <span className="text-xl">{feature.icon}</span>
                    <span className="text-xs uppercase tracking-widest text-cyan-200/80">Live</span>
                  </div>
                  <h3 className="mt-4 text-lg font-semibold text-white">{feature.title}</h3>
                  <p className="mt-3 text-sm text-slate-200">{feature.description}</p>
                  <p className="mt-4 text-xs font-medium text-cyan-200">{feature.highlight}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-6">
            <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
              <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/10 via-slate-900/0 to-slate-950/60" />
              <div className="relative">
                <h3 className="text-xl font-semibold text-white">Metrics that glow with clarity.</h3>
                <p className="mt-3 text-sm text-slate-200">
                  Every interaction syncs in real-time for precise attribution and proactive insights across your funnel.
                </p>
                <div className="mt-6 grid grid-cols-2 gap-4 text-center text-sm text-slate-200">
                  {metrics.map((metric) => (
                    <div key={metric.label} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                      <p className="text-2xl font-semibold text-white">{metric.value}</p>
                      <p className="mt-1 text-xs uppercase tracking-widest text-slate-300">{metric.label}</p>
                      <p className="mt-2 text-[11px] text-slate-400">{metric.subtext}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
              <img
                src="https://cdn.builder.io/api/v1/image/assets%2F773f428d9fc94d15bfc15e9730159245%2F46e9bb43fa634acda2652ea2b31124e8?format=webp&width=800"
                alt="Glass card interface"
                className="absolute inset-0 h-full w-full object-cover opacity-70"
              />
              <div className="absolute inset-0 bg-gradient-to-br from-slate-950/70 via-slate-900/20 to-cyan-500/20" />
              <div className="relative">
                <h3 className="text-xl font-semibold text-white">Showcase brilliance with living surfaces.</h3>
                <p className="mt-3 text-sm text-slate-200">
                  Deploy shimmering UI kits across marketing, product, and onboarding so every pixel feels premium.
                </p>
                <ul className="mt-6 space-y-3 text-sm text-slate-200">
                  <li className="flex items-center gap-3">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                    Gradient-aware theming adapts to your brand palette.
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                    Live previews keep stakeholders aligned without exporting comps.
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                    Device parity ensures clarity from 480px through 1440px breakpoints.
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="relative bg-slate-900/60">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
        <div className="mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-16">
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">Where luminous teams create impact.</h2>
          <p className="mt-4 max-w-2xl text-base text-slate-200">
            Curated journeys backed by intelligent automation unlock new frontiers for every department. Choose a starting point and tailor it without limits.
          </p>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {useCases.map((useCase) => (
              <div key={useCase.title} className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl transition hover:border-cyan-300/60 hover:bg-cyan-300/10">
                <div className="absolute inset-0 bg-gradient-to-br from-transparent via-slate-900/0 to-slate-900/40" />
                <div className="relative">
                  <h3 className="text-lg font-semibold text-white">{useCase.title}</h3>
                  <p className="mt-3 text-sm text-slate-200">{useCase.description}</p>
                  <button className="mt-6 inline-flex items-center gap-2 rounded-full border border-white/20 px-4 py-2 text-xs font-semibold uppercase tracking-widest text-white transition group-hover:border-cyan-300/60">
                    Explore playbook
                    <span className="text-base">→</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative">
        <div className="absolute inset-0">
          <img
            src="https://cdn.builder.io/api/v1/image/assets%2F773f428d9fc94d15bfc15e9730159245%2Fca1a3ca2a28642b182d58f32f08d7d83?format=webp&width=1600"
            alt="Dimensional AI landscape"
            className="h-full w-full object-cover opacity-80"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-slate-950/85 via-slate-900/50 to-cyan-600/40" />
        </div>
        <div className="relative mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-16">
          <div className="grid gap-10 lg:grid-cols-[1.2fr_1fr]">
            <div>
              <h2 className="text-3xl font-semibold text-white sm:text-4xl">Celebrated by teams who demand brilliance.</h2>
              <p className="mt-4 max-w-xl text-base text-slate-200">
                From fintech pioneers to creative studios, leaders choose us to deliver cinematic experiences that remain grounded in measurable outcomes.
              </p>
              <div className="mt-10 grid gap-6 sm:grid-cols-2">
                {testimonials.map((testimonial) => (
                  <div key={testimonial.name} className="rounded-3xl border border-white/10 bg-white/10 p-6 text-sm text-slate-200 backdrop-blur-xl">
                    <p className="text-base text-white">“{testimonial.quote}”</p>
                    <p className="mt-4 text-xs font-semibold uppercase tracking-widest text-cyan-200">{testimonial.name}</p>
                    <p className="mt-1 text-[11px] uppercase tracking-[0.3em] text-slate-300">{testimonial.role}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
              <img
                src="https://cdn.builder.io/api/v1/image/assets%2F773f428d9fc94d15bfc15e9730159245%2Fe8e6ac062d884c2dbd49b0f9e75b1adb?format=webp&width=1200"
                alt="High-speed product interface"
                className="absolute inset-0 h-full w-full object-cover opacity-60"
              />
              <div className="absolute inset-0 bg-gradient-to-br from-slate-950/70 via-slate-900/40 to-transparent" />
              <div className="relative">
                <h3 className="text-xl font-semibold text-white">Cinematic onboarding that feels alive.</h3>
                <p className="mt-3 text-sm text-slate-200">
                  Layered motion design with neural depth of field keeps focus on the journey, not the UI.
                </p>
                <ul className="mt-6 space-y-3 text-sm text-slate-200">
                  <li className="flex items-center gap-3">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                    Auto-personalized hero sections and preview states.
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                    Interactive gallery feeds sourced from live data.
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                    Accessibility-first to ensure brilliance for every visitor.
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="pricing" className="relative bg-slate-950">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent" />
        <div className="mx-auto max-w-6xl px-6 py-20 sm:px-10 lg:px-12">
          <div className="text-center">
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">Choose the arc that fits your velocity.</h2>
            <p className="mt-4 text-base text-slate-200">
              Pricing that scales with your canvas. Switch anytime and keep momentum with seamless upgrades.
            </p>
          </div>
          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {pricing.map((tier) => (
              <div
                key={tier.name}
                className={`relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-8 text-slate-200 backdrop-blur-xl transition hover:border-cyan-300/60 ${
                  tier.emphasized ? "shadow-[0_20px_80px_rgba(16,212,250,0.35)]" : ""
                }`}
              >
                {tier.badge ? (
                  <div className="absolute right-6 top-6 inline-flex items-center gap-2 rounded-full border border-cyan-200/40 bg-cyan-200/20 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-cyan-100">
                    <span className="text-base">★</span>
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
                      <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <a
                  href="#cta"
                  className={`mt-8 flex items-center justify-center rounded-full px-5 py-3 text-sm font-semibold uppercase tracking-widest transition ${
                    tier.emphasized
                      ? "bg-cyan-400 text-slate-900 shadow-lg shadow-cyan-400/50 hover:bg-cyan-300"
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

      <section id="cta" className="relative overflow-hidden">
        <div className="absolute inset-0">
          <img
            src="https://cdn.builder.io/api/v1/image/assets%2F773f428d9fc94d15bfc15e9730159245%2F02da24b6d1084452a37389463a80ef4d?format=webp&width=1600"
            alt="Futuristic gradient horizon"
            className="h-full w-full object-cover opacity-70"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-slate-950/90 via-slate-900/70 to-cyan-500/30" />
        </div>
        <div className="relative mx-auto max-w-4xl px-6 py-24 text-center sm:px-10">
          <h2 className="text-4xl font-semibold text-white sm:text-5xl">Step inside the luminous era of software.</h2>
          <p className="mt-6 text-base text-slate-200">
            Orchestrate campaigns, insights, and experiences that feel alive on every surface. It begins with a single click.
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
              Request Guided Tour
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/10 bg-slate-950/95">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-8 text-sm text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Wedding WebApp. Crafted for luminous SaaS teams.</p>
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
