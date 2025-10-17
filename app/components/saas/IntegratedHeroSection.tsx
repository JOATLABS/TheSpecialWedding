'use client';

import React, { useMemo } from 'react';
import ElegantWeddingHero from './ElegantWeddingHero';

interface Feature {
  title: string;
  description: string;
  icon?: string;
  status: 'available' | 'coming_soon';
}

interface Statistic {
  label: string;
  value: string;
}

interface SubscriptionPlan {
  _id: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  is_featured?: boolean;
}

interface IntegratedHeroSectionProps {
  config: {
    hero_title?: string;
    hero_headline?: string;
    hero_subheadline?: string;
    hero_problem_statement?: string;
    hero_solution_statement?: string;
    hero_description?: string;
    hero_cta_primary: string;
    hero_cta_secondary: string;
    demo_url?: string;
    primary_color?: string;
    statistics?: Statistic[];
    features?: Feature[];
    trust_indicators?: string[];
    statistics_enabled?: boolean;
    features_enabled?: boolean;
  };
  plans: SubscriptionPlan[];
  onAuthModalOpen: () => void;
  className?: string;
}

const primaryLinks = [
  { href: '#features', label: 'Features' },
  { href: '#workflow', label: 'Workflow' },
  { href: '#pricing', label: 'Pricing' },
  { href: '#testimonials', label: 'Stories' },
];

export const IntegratedHeroSection: React.FC<IntegratedHeroSectionProps> = ({
  config,
  plans,
  onAuthModalOpen,
  className,
}) => {
  const statistics = config.statistics_enabled === false ? [] : config.statistics?.slice(0, 3) ?? [];
  const trustIndicators = config.trust_indicators?.slice(0, 4) ?? [
    'Free 30-day trial',
    'No credit card required',
    'Cancel anytime',
    'Personalized onboarding',
  ];

  const primaryFeatureCallouts = useMemo(() => {
    if (config.features_enabled === false) {
      return [] as Feature[];
    }

    return (config.features ?? [])
      .filter((feature) => feature.status === 'available')
      .slice(0, 3);
  }, [config.features, config.features_enabled]);

  const featuredPlan = useMemo(() => {
    if (!plans || plans.length === 0) {
      return undefined;
    }

    return plans.find((plan) => plan.is_featured) ?? plans[0];
  }, [plans]);

  const heroTitle = config.hero_headline ?? config.hero_title ?? 'Craft iconic celebrations without the chaos';
  const heroDescription =
    config.hero_solution_statement ??
    config.hero_description ??
    'Streamline proposals, guest management, vendors, and beautifully branded experiences in one collaborative hub purpose-built for wedding planners.';

  return (
    <section className={`relative isolate overflow-hidden bg-slate-950 text-slate-100 ${className ?? ''}`}>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.18),transparent_55%)]" />
      <div className="pointer-events-none absolute -top-52 right-[-14rem] h-[30rem] w-[30rem] rounded-full bg-violet-500/30 blur-3xl" />
      <div className="pointer-events-none absolute bottom-[-10rem] left-[-12rem] h-[26rem] w-[26rem] rounded-full bg-sky-400/25 blur-3xl" />

      <div className="relative mx-auto flex w-full max-w-7xl flex-col gap-14 px-4 pb-28 pt-8 sm:px-6 lg:px-8 lg:pb-36 lg:pt-16">
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-full border border-white/10 bg-white/5 px-5 py-3 backdrop-blur-xl">
          <div className="flex items-center gap-3 text-sm font-semibold text-white sm:text-base">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-400 via-sky-400 to-purple-500 text-base font-bold text-slate-950">
              SW
            </span>
            <div className="flex flex-col text-left">
              <span>Special Wedding Platform</span>
              <span className="text-[10px] font-medium uppercase tracking-[0.35em] text-blue-100">Planner OS</span>
            </div>
          </div>
          <nav className="hidden items-center gap-6 text-sm text-slate-200 md:flex">
            {primaryLinks.map((link) => (
              <a key={link.href} href={link.href} className="transition hover:text-white">
                {link.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => config.demo_url && window.open(config.demo_url, '_blank')}
              className="hidden rounded-full border border-white/25 px-5 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-white/70 transition hover:border-white hover:text-white lg:inline-flex"
            >
              Watch tour
            </button>
            <button
              type="button"
              onClick={onAuthModalOpen}
              className="inline-flex items-center justify-center rounded-full bg-white px-5 py-2 text-sm font-semibold text-slate-900 transition hover:-translate-y-px hover:shadow-[0_18px_45px_-25px_rgba(15,23,42,0.45)]"
            >
              Book a demo
            </button>
          </div>
        </header>

        <div className="grid gap-14 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:items-center">
          <div className="space-y-10 text-center lg:text-left">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.35em] text-blue-100">
              {config.hero_subheadline ?? 'Built for elite planning studios'}
              <span className="hidden rounded-full bg-white/10 px-2 py-0.5 text-[9px] font-semibold text-white/80 sm:inline-flex">Beta 2.1</span>
            </div>
            <div className="space-y-6">
              <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl lg:text-6xl">{heroTitle}</h1>
              <p className="mx-auto max-w-2xl text-base leading-relaxed text-slate-200 sm:text-lg lg:mx-0">{heroDescription}</p>
              {config.hero_problem_statement && (
                <p className="text-xs font-semibold uppercase tracking-[0.4em] text-blue-100/80">{config.hero_problem_statement}</p>
              )}
            </div>

            <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-start">
              <button
                type="button"
                onClick={onAuthModalOpen}
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-blue-500 via-sky-400 to-purple-500 px-8 py-3 text-base font-semibold text-white shadow-[0_22px_60px_-30px_rgba(56,189,248,0.9)] transition hover:translate-y-[-1px] hover:shadow-[0_32px_80px_-40px_rgba(59,130,246,0.95)] sm:w-auto"
              >
                {config.hero_cta_primary}
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
              </button>
              <button
                type="button"
                onClick={() => config.demo_url && window.open(config.demo_url, '_blank')}
                className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-white/20 bg-white/10 px-8 py-3 text-base font-semibold text-white/90 transition hover:border-white hover:text-white sm:w-auto"
              >
                {config.hero_cta_secondary}
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-4.586-2.659A1 1 0 008 9.342v5.316a1 1 0 001.166.974l4.586-0.918A1 1 0 0015 13.724v-2.448a1 1 0 00-0.248-0.108z" />
                </svg>
              </button>
            </div>

            <div className="flex flex-col gap-4 text-left sm:flex-row sm:items-center sm:text-left">
              <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-slate-200 sm:justify-start">
                {trustIndicators.map((indicator) => (
                  <div key={indicator} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1">
                    <svg className="h-4 w-4 text-emerald-300" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 10-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span>{indicator}</span>
                  </div>
                ))}
              </div>
            </div>

            {statistics.length > 0 && (
              <div className="grid gap-4 rounded-3xl border border-white/15 bg-white/5 p-5 text-left backdrop-blur">
                <div className="flex items-center justify-between text-xs uppercase tracking-[0.4em] text-blue-100/80">
                  <span>Planner impact</span>
                  <span>Live dashboards</span>
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  {statistics.map((stat) => (
                    <div key={stat.label} className="rounded-2xl bg-white/10 p-4">
                      <p className="text-2xl font-semibold text-white sm:text-3xl">{stat.value}</p>
                      <p className="mt-1 text-[11px] uppercase tracking-[0.3em] text-blue-100/70">{stat.label}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="relative flex justify-center lg:justify-end">
            <div className="absolute inset-y-[-4rem] right-[-6rem] w-[18rem] rounded-full bg-white/10 blur-3xl" />
            <div className="relative w-full max-w-lg rounded-[3rem] border border-white/10 bg-white/10 p-6 shadow-[0_80px_180px_-90px_rgba(56,189,248,0.8)] backdrop-blur-xl sm:p-8">
              <div className="rounded-[2.5rem] border border-white/20 bg-slate-950/80 p-5 shadow-[0_24px_80px_-60px_rgba(59,130,246,0.8)]">
                <ElegantWeddingHero />
              </div>
              <div className="mt-6 grid gap-4 rounded-2xl border border-white/15 bg-white/10 p-5 text-sm text-white">
                <div className="flex items-center justify-between text-xs uppercase tracking-[0.35em] text-blue-100/80">
                  <span>Featured plan</span>
                  <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-[10px] font-semibold text-white/80">Best for studios</span>
                </div>
                <div className="space-y-3">
                  <div>
                    <p className="text-lg font-semibold text-white">{featuredPlan?.name ?? 'Studio Growth'}</p>
                    <p className="text-xs text-blue-100/80">
                      {featuredPlan?.description ?? 'Everything you need for 10 active weddings with concierge support.'}
                    </p>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-semibold text-white">${featuredPlan?.price_monthly ?? 179}</span>
                    <span className="text-[11px] uppercase tracking-[0.3em] text-blue-100/70">per planner / month</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onAuthModalOpen}
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-900 transition hover:-translate-y-px hover:bg-blue-50"
                >
                  Compare plans
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>

              {primaryFeatureCallouts.length > 0 && (
                <div className="mt-4 grid gap-3 text-xs text-white/85">
                  {primaryFeatureCallouts.map((feature) => (
                    <div key={feature.title} className="flex items-start gap-3 rounded-2xl border border-white/15 bg-white/5 p-3">
                      <div className="mt-1 inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-400/15 text-emerald-200">
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-white">{feature.title}</p>
                        <p className="text-[11px] leading-relaxed text-blue-100/80">{feature.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-4 text-center sm:grid-cols-2 lg:grid-cols-4">
          {['Aura Events', 'Luxe Weddings', 'Crescent & Co.', 'Gala Society'].map((brand) => (
            <div
              key={brand}
              className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs font-semibold uppercase tracking-[0.4em] text-white/70 backdrop-blur"
            >
              {brand}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default IntegratedHeroSection;
