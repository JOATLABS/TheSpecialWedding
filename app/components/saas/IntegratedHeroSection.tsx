'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
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
    hero_headline?: string;
    hero_subheadline?: string;
    hero_problem_statement?: string;
    hero_solution_statement?: string;
    hero_cta_primary: string;
    hero_cta_secondary: string;
    demo_url?: string;
    primary_color?: string;
    statistics?: Statistic[];
    features?: Feature[];
  };
  plans: SubscriptionPlan[];
  onAuthModalOpen: () => void;
  className?: string;
}

export const IntegratedHeroSection: React.FC<IntegratedHeroSectionProps> = ({
  config,
  plans,
  onAuthModalOpen,
  className,
}) => {
  const sectionRef = useRef<HTMLElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [visibleStats, setVisibleStats] = useState(false);
  const [visibleFeatures, setVisibleFeatures] = useState<Set<number>>(new Set());

  // Track scroll progress through hero section
  useEffect(() => {
    const handleScroll = () => {
      if (!sectionRef.current) return;

      const rect = sectionRef.current.getBoundingClientRect();
      const sectionHeight = rect.height;
      const viewportHeight = window.innerHeight;

      // Calculate how far through the section we've scrolled
      const scrolled = Math.max(0, -rect.top);
      const total = sectionHeight - viewportHeight;
      const progress = Math.min(Math.max(scrolled / total, 0), 1);

      setScrollProgress(progress);

      // Trigger stats visibility
      if (progress > 0.15 && !visibleStats) {
        setVisibleStats(true);
      }

      // Trigger feature cards visibility based on scroll
      const featureStartProgress = 0.35;
      if (progress > featureStartProgress) {
        const featureProgress = (progress - featureStartProgress) / 0.3;
        const visibleCount = Math.floor(featureProgress * 6);
        const indices = [];
        for (let i = 0; i < visibleCount; i++) {
          indices.push(i);
        }
        setVisibleFeatures(new Set(indices));
      }
    };

    window.addEventListener('scroll', handleScroll);
    handleScroll(); // Initial check

    return () => window.removeEventListener('scroll', handleScroll);
  }, [visibleStats]);

  const topFeatures = config.features?.slice(0, 6) || [];
  const stats = config.statistics || [];
  const featuredPlan = plans.find(p => p.is_featured) || plans[0];

  // Calculate phase visibility with NO OVERLAP - gaps between phases
  const getPhaseOpacity = (phase: 1 | 2 | 3 | 4) => {
    switch (phase) {
      case 1: // 0-22% scroll, fade out 18-22%
        if (scrollProgress <= 0.18) return 1;
        if (scrollProgress <= 0.22) return 1 - ((scrollProgress - 0.18) / 0.04);
        return 0;

      case 2: // 28-48% scroll, fade in 28-32%, fade out 44-48%
        if (scrollProgress < 0.28) return 0;
        if (scrollProgress <= 0.32) return (scrollProgress - 0.28) / 0.04;
        if (scrollProgress <= 0.44) return 1;
        if (scrollProgress <= 0.48) return 1 - ((scrollProgress - 0.44) / 0.04);
        return 0;

      case 3: // 54-74% scroll, fade in 54-58%, fade out 70-74%
        if (scrollProgress < 0.54) return 0;
        if (scrollProgress <= 0.58) return (scrollProgress - 0.54) / 0.04;
        if (scrollProgress <= 0.70) return 1;
        if (scrollProgress <= 0.74) return 1 - ((scrollProgress - 0.70) / 0.04);
        return 0;

      case 4: // 80-100% scroll, fade in 80-84%
        if (scrollProgress < 0.80) return 0;
        if (scrollProgress <= 0.84) return (scrollProgress - 0.80) / 0.04;
        return 1;

      default:
        return 0;
    }
  };

  const getPhaseZIndex = (phase: 1 | 2 | 3 | 4) => {
    const currentPhase =
      scrollProgress <= 0.22 ? 1 :
      scrollProgress <= 0.48 ? 2 :
      scrollProgress <= 0.74 ? 3 : 4;
    return phase === currentPhase ? 20 : 10;
  };

  return (
    <section
      ref={sectionRef}
      className={`relative min-h-[300vh] w-full bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 ${
        className ?? ''
      }`}
    >
      {/* Sticky container that stays in viewport */}
      <div className="sticky top-0 min-h-screen w-full flex items-center justify-center">
        {/* Dynamic gradient orbs that move with scroll */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute right-0 top-0 h-[600px] w-[600px] rounded-full bg-blue-600/20 blur-3xl"
          style={{
            transform: `translate(${scrollProgress * 100}px, ${scrollProgress * -50}px) scale(${1 + scrollProgress * 0.5})`,
            transition: 'transform 0.3s ease-out',
          }}
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute bottom-0 left-0 h-[500px] w-[500px] rounded-full bg-purple-600/10 blur-3xl"
          style={{
            transform: `translate(${scrollProgress * -100}px, ${scrollProgress * 50}px) scale(${1 + scrollProgress * 0.3})`,
            transition: 'transform 0.3s ease-out',
          }}
        />

        {/* Phase container - centered content */}
        <div className="relative w-full max-w-7xl px-6">
          {/* Phase 1: Initial hero (0-22% scroll) - Clean fade out */}
          <div
            className="absolute inset-0 flex items-center justify-center"
            style={{
              opacity: getPhaseOpacity(1),
              transform: `translateY(${scrollProgress * -50}px) scale(${1 - scrollProgress * 0.1})`,
              zIndex: getPhaseZIndex(1),
              transition: 'opacity 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94), transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
              pointerEvents: getPhaseOpacity(1) > 0 ? 'auto' : 'none',
            }}
          >
            <div className="grid gap-16 lg:grid-cols-2 lg:items-center lg:gap-24">
              {/* Left: Copy */}
              <div className="space-y-8 text-center lg:text-left">
                {config.hero_subheadline && (
                  <div className="inline-block rounded-full bg-blue-500/10 px-4 py-2 text-sm font-medium text-blue-400 ring-1 ring-blue-500/20">
                    {config.hero_subheadline}
                  </div>
                )}

                <h1 className="text-5xl font-bold leading-tight text-white lg:text-6xl xl:text-7xl">
                  {config.hero_headline || 'Manage 10+ Weddings Simultaneously'}
                </h1>

                {config.hero_problem_statement && (
                  <p className="text-lg text-slate-300 lg:text-xl">
                    {config.hero_problem_statement}
                  </p>
                )}

                {config.hero_solution_statement && (
                  <p className="text-lg font-medium text-white lg:text-xl">
                    {config.hero_solution_statement}
                  </p>
                )}

                <div className="flex flex-col gap-4 sm:flex-row">
                  <button
                    type="button"
                    onClick={onAuthModalOpen}
                    className="group relative inline-flex items-center justify-center overflow-hidden rounded-lg bg-blue-600 px-8 py-4 text-base font-semibold text-white shadow-lg transition-all hover:bg-blue-700 hover:shadow-xl hover:shadow-blue-500/50"
                  >
                    <span className="relative z-10">{config.hero_cta_primary}</span>
                    <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-purple-600 opacity-0 transition-opacity group-hover:opacity-100" />
                  </button>

                  <button
                    type="button"
                    onClick={() => config.demo_url && window.open(config.demo_url, '_blank')}
                    className="inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-800/50 px-8 py-4 text-base font-semibold text-white backdrop-blur-sm transition-all hover:bg-slate-700/50 hover:border-slate-600"
                  >
                    {config.hero_cta_secondary}
                  </button>
                </div>

                <div className="flex items-center gap-6 text-sm text-slate-400">
                  <div className="flex items-center gap-2">
                    <svg className="h-5 w-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    <span>Free 30-day trial</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <svg className="h-5 w-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    <span>No credit card required</span>
                  </div>
                </div>
              </div>

              {/* Right: Elegant Wedding Visualization */}
              <div className="relative h-[600px] w-full">
                <ElegantWeddingHero />
              </div>
            </div>
          </div>

          {/* Phase 2: Stats section (28-48% scroll) - NO OVERLAP */}
          <div
            className="absolute inset-0 flex items-center justify-center"
            style={{
              opacity: getPhaseOpacity(2),
              transform: `translateY(${Math.max(0, (0.32 - scrollProgress) * 150)}px) scale(${0.95 + (getPhaseOpacity(2) * 0.05)})`,
              zIndex: getPhaseZIndex(2),
              transition: 'opacity 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94), transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
              pointerEvents: getPhaseOpacity(2) > 0 ? 'auto' : 'none',
            }}
          >
            <div className="mx-auto max-w-6xl px-6">
              <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-slate-800/50 to-slate-900/50 p-12 backdrop-blur-xl">
                <h3 className="mb-12 text-center text-3xl font-bold text-white">
                  Trusted by Wedding Professionals Worldwide
                </h3>
                <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
                  {stats.map((stat, index) => (
                    <div
                      key={index}
                      className="text-center transition-all duration-500"
                      style={{
                        opacity: visibleStats ? 1 : 0,
                        transform: visibleStats ? 'translateY(0)' : 'translateY(20px)',
                        transitionDelay: `${index * 150}ms`,
                      }}
                    >
                      <div className="mb-2 text-5xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                        {stat.value}
                      </div>
                      <div className="text-sm text-slate-400">{stat.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Phase 3: Feature preview cards (54-74% scroll) - NO OVERLAP */}
          <div
            className="absolute inset-0 flex items-center justify-center"
            style={{
              opacity: getPhaseOpacity(3),
              transform: `scale(${0.92 + (getPhaseOpacity(3) * 0.08)})`,
              zIndex: getPhaseZIndex(3),
              transition: 'opacity 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94), transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
              pointerEvents: getPhaseOpacity(3) > 0 ? 'auto' : 'none',
            }}
          >
            <div className="mx-auto max-w-6xl px-6">
              <h3 className="mb-8 text-center text-3xl font-bold text-white">
                Everything You Need in One Platform
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {topFeatures.map((feature, index) => {
                  const isVisible = visibleFeatures.has(index);
                  return (
                    <div
                      key={index}
                      className="group rounded-2xl border border-white/10 bg-slate-800/30 p-6 backdrop-blur-sm transition-all duration-500 hover:bg-slate-800/50 hover:border-blue-500/30"
                      style={{
                        opacity: isVisible ? 1 : 0,
                        transform: isVisible ? 'translateY(0) scale(1)' : 'translateY(30px) scale(0.9)',
                        transitionDelay: `${(index % 3) * 100}ms`,
                      }}
                    >
                      <div className="mb-3 text-3xl">{feature.icon || '✨'}</div>
                      <h4 className="mb-2 font-semibold text-white">{feature.title}</h4>
                      <p className="text-sm text-slate-400">{feature.description}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Phase 4: Pricing preview (80-100% scroll) - NO OVERLAP */}
          {featuredPlan && (
            <div
              className="absolute inset-0 flex items-center justify-center"
              style={{
                opacity: getPhaseOpacity(4),
                transform: `translateY(${Math.max(0, (0.84 - scrollProgress) * 100)}px) scale(${0.9 + (getPhaseOpacity(4) * 0.1)})`,
                zIndex: getPhaseZIndex(4),
                transition: 'opacity 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94), transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
                filter: `brightness(${1 + (getPhaseOpacity(4) * 0.2)})`,
              }}
            >
              <div className="mx-auto max-w-2xl px-6">
                <div className="rounded-3xl border border-purple-500/30 bg-gradient-to-br from-blue-500/10 to-purple-500/10 p-8 text-center backdrop-blur-xl">
                  <div className="mb-2 inline-block rounded-full bg-blue-500/20 px-3 py-1 text-xs font-bold text-blue-400">
                    MOST POPULAR
                  </div>
                  <h3 className="mb-2 text-3xl font-bold text-white">{featuredPlan.name}</h3>
                  <p className="mb-6 text-slate-400">{featuredPlan.description}</p>
                  <div className="mb-6 flex items-baseline justify-center gap-2">
                    <span className="text-5xl font-bold text-white">${featuredPlan.price_monthly}</span>
                    <span className="text-slate-400">/month</span>
                  </div>
                  <button
                    onClick={onAuthModalOpen}
                    className="mx-auto inline-flex items-center justify-center rounded-lg bg-gradient-to-r from-blue-500 to-purple-500 px-8 py-3 font-semibold text-white shadow-lg shadow-blue-500/30 transition-all hover:scale-105 hover:shadow-xl hover:shadow-blue-500/50"
                  >
                    Start Free Trial
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};

export default IntegratedHeroSection;
