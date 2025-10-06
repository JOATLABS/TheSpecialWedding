'use client';

import React, { useCallback } from 'react';
import Link from 'next/link';

import { SaasLogoTitle } from './SaasLogoTitle';
import { GlassCard } from '../ui/GlassCard';
import { ThemeConfig } from '@/types/wedding';

interface SaasConfig {
  hero_title: string;
  hero_subtitle: string;
  hero_description: string;
  hero_cta_primary: string;
  hero_cta_secondary: string;
  contact_cta_label?: string;
  contact_url?: string;
  trust_indicators: string[];
  statistics: Array<{
    label: string;
    value: string;
  }>;
  statistics_enabled: boolean;
  demo_url?: string;
  primary_color: string;
  secondary_color: string;
}

interface SaasHeroSectionProps {
  config: SaasConfig;
  theme: ThemeConfig;
  onAuthModeChange: (mode: 'signup' | 'login') => void;
  onRequestSignupFocus?: () => void;
  onContactClick?: () => void;
  className?: string;
}

const indicatorAccent = ['bg-emerald-400', 'bg-sky-400', 'bg-violet-400'];

export const SaasHeroSection: React.FC<SaasHeroSectionProps> = ({
  config,
  theme,
  onAuthModeChange,
  onRequestSignupFocus,
  onContactClick,
  className,
}) => {
  const handlePrimaryCta = useCallback(() => {
    onAuthModeChange('signup');
    if (onRequestSignupFocus) {
      onRequestSignupFocus();
      return;
    }
    if (typeof document !== 'undefined') {
      document.getElementById('planner-auth-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [onAuthModeChange, onRequestSignupFocus]);

  const handleSecondaryCta = useCallback(() => {
    if (config.demo_url && typeof window !== 'undefined') {
      window.open(config.demo_url, '_blank', 'noopener');
      return;
    }
    handlePrimaryCta();
  }, [config.demo_url, handlePrimaryCta]);

  const handleContactCta = useCallback(() => {
    if (onContactClick) {
      onContactClick();
      return;
    }

    const fallbackContact = process.env.NEXT_PUBLIC_CONTACT_URL || 'mailto:sales@specialwedding.com';
    const target = config.contact_url || fallbackContact;

    if (!target) {
      return;
    }

    const isHttp = target.startsWith('http://') || target.startsWith('https://');

    if (typeof window !== 'undefined') {
      if (isHttp) {
        window.open(target, '_blank', 'noopener');
        return;
      }

      window.location.href = target;
    }
  }, [config.contact_url, onContactClick]);

  return (
    <section
      className={`relative isolate w-full bg-gradient-to-br from-[#f6f3ff] via-[#eef7ff] to-[#f9fcff] px-4 py-12 sm:px-6 sm:py-16 lg:px-8 xl:px-12 ${
        className ?? ''
      }`}
    >
      <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-[-10rem] h-[22rem] bg-gradient-to-b from-white/70 via-white/10 to-transparent" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-40 top-16 h-72 w-72 rounded-full bg-[#ffdce5]/35 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -left-32 bottom-0 h-80 w-80 rounded-full bg-[#c8e6ff]/35 blur-3xl" />

      <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-12 lg:gap-16">
        <div className="space-y-10">
          <SaasLogoTitle theme={theme} />

          <div className="space-y-7 text-left">
            {config.hero_subtitle && (
              <p className="text-[0.75rem] font-semibold uppercase tracking-[0.28em] text-slate-500 sm:text-xs">
                {config.hero_subtitle}
              </p>
            )}

            <h1 className="font-semibold leading-tight text-slate-900" style={{ fontSize: 'clamp(2.6rem, 4.8vw, 3.6rem)' }}>
              {config.hero_title}
            </h1>

            <p className="max-w-3xl text-base text-slate-600 sm:text-lg">
              {config.hero_description}
            </p>

            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
              <button
                type="button"
                onClick={handlePrimaryCta}
                className="inline-flex items-center justify-center rounded-full px-8 py-3 text-sm font-semibold text-white shadow-lg transition hover:shadow-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                style={{ backgroundColor: theme.primary_color }}
              >
                {config.hero_cta_primary}
              </button>
              <button
                type="button"
                onClick={handleSecondaryCta}
                className="inline-flex items-center justify-center rounded-full border border-slate-200 bg-white/80 px-7 py-3 text-sm font-semibold text-slate-900 shadow transition hover:bg-white"
              >
                {config.hero_cta_secondary}
              </button>
              <button
                type="button"
                onClick={handleContactCta}
                className="inline-flex items-center justify-center rounded-full border border-transparent bg-white/70 px-6 py-3 text-sm font-semibold text-slate-900 shadow transition hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
              >
                {config.contact_cta_label ?? 'Contact sales'}
              </button>
            </div>

            {Array.isArray(config.trust_indicators) && config.trust_indicators.length > 0 && (
              <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
                {config.trust_indicators.map((indicator, index) => (
                  <span
                    key={indicator}
                    className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/75 px-4 py-2 shadow-sm"
                  >
                    <span className={`h-2 w-2 rounded-full ${indicatorAccent[index % indicatorAccent.length]}`} aria-hidden="true" />
                    {indicator}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {config.statistics_enabled && Array.isArray(config.statistics) && config.statistics.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {config.statistics.map((statistic) => (
              <GlassCard
                key={statistic.label}
                depth="near"
                blur="lg"
                className="flex flex-col gap-2 rounded-3xl border border-white/60 bg-white/85 p-5 text-left shadow-lg"
              >
                <span className="text-xs font-medium uppercase tracking-[0.26em] text-slate-500">{statistic.label}</span>
                <span className="text-3xl font-semibold text-slate-900">{statistic.value}</span>
              </GlassCard>
            ))}
          </div>
        )}

        <div className="rounded-3xl border border-white/60 bg-white/70 px-6 py-4 text-sm text-slate-600 shadow-sm sm:px-8">
          <p>
            Prefer to talk first?{' '}
            <Link
              href={config.contact_url || process.env.NEXT_PUBLIC_CONTACT_URL || 'mailto:sales@specialwedding.com'}
              className="font-semibold text-slate-900 underline decoration-slate-300 underline-offset-4 hover:decoration-slate-500"
            >
              Connect with our team
            </Link>{' '}
            to map out your onboarding plan.
          </p>
        </div>
      </div>
    </section>
  );
};

export default SaasHeroSection;
