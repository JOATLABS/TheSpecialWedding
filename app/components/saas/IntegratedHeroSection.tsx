'use client';

import React, { useCallback, useMemo } from 'react';
import ElegantWeddingHero from './ElegantWeddingHero';
import { umamiTrack } from '@/utils/umami';

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
  trial_days?: number;
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
    hero_cta_secondary?: string;
    demo_url?: string;
    primary_color?: string;
    statistics?: Statistic[];
    features?: Feature[];
    trust_indicators?: string[];
    statistics_enabled?: boolean;
    features_enabled?: boolean;
    show_product_demo?: boolean;
    demo_video_url?: string;
    hero_screenshot_primary?: string;
    show_decorative_logo?: boolean;
  };
  plans: SubscriptionPlan[];
  onAuthModalOpen: () => void;
  className?: string;
  animationSpeedMs?: number;
  themeColors?: {
    primary: string;
    secondary: string;
  };
  useTheming?: boolean;
  hero_image_position?: 'left' | 'right';
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
  animationSpeedMs = 400,
  themeColors = { primary: "#1e3a5f", secondary: "#d4af37" },
  useTheming = false,
  hero_image_position,
}) => {
  // Umami: wrap the auth-modal open callback so every hero CTA fires
  // `hero_cta_clicked` with a `location` discriminator before opening the
  // modal. Lets the funnel report show which surface drives intent.
  const openAuthFrom = useCallback(
    (location: 'header_book_demo' | 'hero_primary' | 'featured_plan_card') => () => {
      umamiTrack('hero_cta_clicked', { location });
      onAuthModalOpen();
    },
    [onAuthModalOpen],
  );

  const statistics = config.statistics_enabled === false ? [] : (Array.isArray(config.statistics) ? config.statistics : []).slice(0, 3);
  const trustIndicators = (Array.isArray(config.trust_indicators) ? config.trust_indicators : []).slice(0, 3).length > 0
    ? (Array.isArray(config.trust_indicators) ? config.trust_indicators : []).slice(0, 3)
    // SYNC-WITH-SEED: trial_days — update when SEED_VERSION bumps paid trial length
    : ['Free 30-day trial', 'No credit card required', 'Cancel anytime'];
  const primaryFeatureCallouts = useMemo(() => {
    if (config.features_enabled === false) {
      return [] as Feature[];
    }
    const features = Array.isArray(config.features) ? config.features : [];
    return features
      .filter((feature) => feature.status === 'available')
      .slice(0, 3);
  }, [config.features, config.features_enabled]);

  const featuredPlan = useMemo(() => {
    const plansArray = Array.isArray(plans) ? plans : [];
    if (plansArray.length === 0) {
      return undefined;
    }
    return plansArray.find((plan) => plan.is_featured) ?? plansArray[0];
  }, [plans]);

  const transitionStyle: React.CSSProperties = { transitionDuration: `${animationSpeedMs}ms` };
  const hasMedia =
    (config.show_product_demo && config.demo_url) ||
    (!!config.hero_screenshot_primary);
  const mediaFirst = (hero_image_position ?? (config as any).hero_image_position) === 'left';
  const showDecorative = config.show_decorative_logo !== false;
  const gradientStyle: React.CSSProperties = useTheming
    ? { background: `linear-gradient(135deg, ${themeColors.primary} 0%, ${themeColors.secondary} 80%)` }
    : {};

  return (
    <section
      className={`relative overflow-hidden bg-slate-950 text-slate-100 ${className ?? ''}`}
      style={gradientStyle}
    >
      {showDecorative && (
        <>
          <div className="pointer-events-none absolute -top-48 left-1/2 h-[34rem] w-[34rem] -translate-x-1/2 rounded-full bg-blue-500/25 blur-3xl" />
          <div className="pointer-events-none absolute bottom-[-12rem] right-[-6rem] h-[28rem] w-[28rem] rounded-full bg-purple-500/30 blur-3xl" />
          <div className="pointer-events-none absolute top-1/3 left-[-8rem] hidden h-[24rem] w-[24rem] rounded-full bg-cyan-400/20 blur-3xl lg:block" />
        </>
      )}

      <div className="relative mx-auto flex w-full max-w-7xl flex-col gap-16 px-4 pb-28 pt-10 sm:px-6 lg:px-8 lg:pb-36 lg:pt-16">
        <header className="flex flex-wrap items-center justify-between gap-6 rounded-full border border-white/15 bg-white/[0.04] px-6 py-4 backdrop-blur-xl">
          <div className="flex items-center gap-3 text-lg font-semibold tracking-tight text-white">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-400/80 to-purple-500/70 text-base font-bold text-slate-950">
              SW
            </span>
            <span>Special Wedding Platform</span>
          </div>
          <nav className="hidden items-center gap-6 text-sm text-slate-200 md:flex">
            {primaryLinks.map((link) => (
              <a key={link.href} href={link.href} className="transition hover:text-white" style={transitionStyle}>
                {link.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <a
              href="#features"
              className="hidden rounded-full border border-white/25 px-5 py-2 text-sm font-semibold text-white/80 transition hover:border-white hover:text-white lg:inline-flex"
              style={transitionStyle}
            >
              Explore features
            </a>
            <button
              type="button"
              onClick={openAuthFrom('header_book_demo')}
              className="inline-flex items-center justify-center rounded-full bg-white px-5 py-2 text-sm font-semibold text-slate-900 transition hover:shadow-lg"
              style={transitionStyle}
            >
              Book a demo
            </button>
          </div>
        </header>

        <div className="grid gap-16 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:items-center">
          <div className={`space-y-10 text-center lg:text-left ${mediaFirst ? 'lg:order-2' : ''}`}>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs font-medium uppercase tracking-[0.3em] text-blue-100">
              {config.hero_subheadline ?? 'Built for elite planning studios'}
            </div>
            <div className="space-y-6">
              <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl lg:text-6xl">
                {config.hero_headline ?? config.hero_title ?? 'Craft iconic celebrations without the chaos'}
              </h1>
              <p className="mx-auto max-w-2xl text-base leading-relaxed text-slate-200 sm:text-lg lg:mx-0">
                {config.hero_solution_statement ??
                  config.hero_description ??
                  'Streamline proposals, guest management, vendors, and beautifully branded experiences in one collaborative hub purpose-built for wedding planners.'}
              </p>
              {config.hero_problem_statement && (
                <p className="text-sm font-medium uppercase tracking-[0.35em] text-blue-200/80">
                  {config.hero_problem_statement}
                </p>
              )}
            </div>

            <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-start">
              <button
                type="button"
                onClick={openAuthFrom('hero_primary')}
                className="inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-blue-500 via-sky-400 to-purple-500 px-8 py-3 text-base font-semibold text-white shadow-[0_20px_45px_-20px_rgba(59,130,246,0.8)] transition hover:translate-y-[-1px] hover:shadow-[0_30px_60px_-30px_rgba(56,189,248,0.9)] sm:w-auto"
                style={transitionStyle}
              >
                {config.hero_cta_primary}
              </button>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-4 text-xs text-slate-200 sm:justify-start">
              {trustIndicators.map((indicator) => (
                <div key={indicator} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1">
                  <svg className="h-4 w-4 text-emerald-300" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>{indicator}</span>
                </div>
              ))}
            </div>

            {statistics.length > 0 && (
              <div className="grid w-full gap-4 rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur lg:max-w-xl">
                {statistics.map((stat) => (
                  <div
                    key={stat.label}
                    className="flex items-center justify-between rounded-xl bg-white/[0.02] px-4 py-3 text-left transition"
                    style={transitionStyle}
                  >
                    <div>
                      <p className="text-2xl font-semibold text-white">{stat.value}</p>
                      <p className="text-xs uppercase tracking-[0.35em] text-blue-100/80">{stat.label}</p>
                    </div>
                    <div className="text-[11px] text-slate-300">
                      Always-on insights
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className={`relative ${mediaFirst ? 'lg:order-1' : ''}`}>
            <div className="absolute inset-0 -translate-y-12 rounded-[3rem] bg-gradient-to-br from-blue-400/30 via-purple-500/20 to-sky-400/20 blur-3xl" />
            <div className="relative grid gap-6 rounded-[3rem] border border-white/15 bg-white/[0.06] p-6 shadow-[0_60px_160px_-80px_rgba(56,189,248,0.75)] backdrop-blur-xl lg:p-8">
              <div className="rounded-[2.5rem] border border-white/15 bg-slate-950/70 p-5 shadow-[0_20px_80px_-50px_rgba(59,130,246,0.9)] transition" style={transitionStyle}>
                {hasMedia ? (
                  <>
                    {config.show_product_demo && config.demo_url ? (
                      <div className="aspect-video w-full overflow-hidden rounded-2xl border border-white/10 bg-slate-900">
                        <iframe
                          title="Product demo"
                          src={config.demo_url}
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                          allowFullScreen
                          className="h-full w-full"
                        />
                      </div>
                    ) : null}
                    {!config.show_product_demo && config.hero_screenshot_primary ? (
                      <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900">
                        <img
                          src={config.hero_screenshot_primary}
                          alt="Product screenshot"
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                      </div>
                    ) : null}
                  </>
                ) : (
                  <ElegantWeddingHero />
                )}
              </div>
              {featuredPlan && (
                <div className="rounded-3xl border border-white/15 bg-slate-950/60 p-6 text-left transition" style={transitionStyle}>
                  <div className="flex items-center justify-between text-sm text-blue-100/80">
                    <span className="inline-flex items-center gap-2 font-semibold">
                      Featured Plan
                      <span className="inline-flex items-center rounded-full bg-blue-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.25em] text-blue-100">
                        {featuredPlan.is_featured ? 'Recommended' : 'Popular'}
                      </span>
                    </span>
                    <span className="text-white">${featuredPlan.price_monthly}/mo</span>
                  </div>
                  <p className="mt-3 text-sm text-slate-200">{featuredPlan.description}</p>
                  {featuredPlan.trial_days ? (
                    <p className="mt-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-200">
                      {featuredPlan.trial_days}-day free trial · no card required
                    </p>
                  ) : null}
                  <button
                    type="button"
                    onClick={openAuthFrom('featured_plan_card')}
                    className="mt-5 inline-flex items-center justify-center rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition hover:shadow-lg"
                    style={transitionStyle}
                  >
                    Preview onboarding
                  </button>
                </div>
              )}
              {primaryFeatureCallouts.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-3">
                  {primaryFeatureCallouts.map((feature) => (
                    <article key={feature.title} className="flex flex-col gap-3 rounded-2xl border border-white/15 bg-white/[0.05] p-4 text-left transition" style={transitionStyle}>
                      <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/20 text-lg text-blue-100">
                        {feature.icon ?? '✨'}
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-white">{feature.title}</h3>
                        <p className="mt-1 text-xs text-slate-300">{feature.description}</p>
                      </div>
                      <span className="mt-auto text-[10px] uppercase tracking-[0.4em] text-blue-200/70">In platform</span>
                    </article>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default IntegratedHeroSection;
