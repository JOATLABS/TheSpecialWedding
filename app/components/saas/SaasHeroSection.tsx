'use client';

import React, { useCallback } from 'react';
import Link from 'next/link';

import { PlannerSignupForm } from './PlannerSignupForm';
import { SaasLogoTitle } from './SaasLogoTitle';
import { GlassCard } from '../ui/GlassCard';
import { SocialAuthButtons } from '../auth/SocialAuthButtons';

interface SaasConfig {
  hero_title: string;
  hero_subtitle: string;
  hero_description: string;
  hero_cta_primary: string;
  hero_cta_secondary: string;
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
  theme: {
    primary_color: string;
    secondary_color: string;
    background_style: 'gradient' | 'solid';
  };
  onAuthModeChange: (mode: 'signup' | 'login') => void;
  onRequestSignupFocus?: () => void;
}

interface AuthPanelProps {
  mode: 'signup' | 'login';
  onModeChange: (mode: 'signup' | 'login') => void;
  selectedPlan?: { id: string; name?: string } | null;
  theme: {
    primary_color: string;
    secondary_color: string;
  };
}

function PlannerLoginPanel({ theme }: { theme: { primary_color: string; secondary_color: string } }) {
  return (
    <div className="space-y-5">
      <SocialAuthButtons flow="login" redirectPath="/admin" />
      <div className="rounded-2xl border border-white/50 bg-white/70 p-4 text-sm text-gray-700 shadow-sm">
        <p className="font-medium text-gray-900">Prefer email access?</p>
        <p className="mt-2 text-gray-600">
          Use your verified planner credentials to continue with password or magic link.
        </p>
        <Link
          href="/admin/login"
          className="mt-3 inline-flex items-center justify-center rounded-xl border border-transparent bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-900"
        >
          Go to secure planner login
        </Link>
      </div>
      <p className="text-xs text-gray-500">
        Single sign-on keeps vendor and couple data protected with the same 2-step verification we enforce in the admin portal.
      </p>
      <p className="text-xs text-gray-500">
        Tip: save this page to your home screen for a glass-optimised mobile shortcut.
      </p>
    </div>
  );
}

export function SaasAuthPanel({ mode, onModeChange, selectedPlan, theme }: AuthPanelProps) {
  return (
    <GlassCard depth="near" blur="xl" className="flex h-full flex-col gap-6 rounded-[2.25rem] p-6 sm:p-8">
      <div className="space-y-3 text-left">
        <p className="text-xs font-semibold uppercase tracking-[0.32em] text-gray-600">Planner access</p>
        <h2 className="text-2xl font-semibold text-gray-900">
          {mode === 'signup' ? 'Launch your workspace' : 'Welcome back, planner'}
        </h2>
        <p className="text-sm text-gray-600">
          Keep budgets, forms, vendors, and couples in sync with glassmorphic controls optimised for 2025 workflows.
        </p>
      </div>

      <div className="inline-flex rounded-full bg-white/70 p-1 text-sm font-medium shadow-inner">
        <button
          type="button"
          onClick={() => onModeChange('signup')}
          className={`flex-1 rounded-full px-4 py-2 transition ${
            mode === 'signup'
              ? 'bg-gray-900 text-white shadow'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Sign up
        </button>
        <button
          type="button"
          onClick={() => onModeChange('login')}
          className={`flex-1 rounded-full px-4 py-2 transition ${
            mode === 'login'
              ? 'bg-gray-900 text-white shadow'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Log in
        </button>
      </div>

      {selectedPlan && (
        <div className="rounded-2xl border border-white/55 bg-white/70 p-4 text-sm text-gray-700 shadow-sm">
          <p className="font-semibold text-gray-900">Selected plan</p>
          <p className="mt-1 text-gray-600">
            {selectedPlan.name ?? selectedPlan.id}
          </p>
          <p className="mt-2 text-xs text-gray-500">
            We&apos;ll pre-fill this during onboarding so you can start your trial instantly.
          </p>
        </div>
      )}

      {mode === 'signup' ? (
        <PlannerSignupForm
          theme={theme}
          selectedPlanId={selectedPlan?.id ?? undefined}
          selectedPlanLabel={selectedPlan?.name}
          variant="panel"
        />
      ) : (
        <PlannerLoginPanel theme={theme} />
      )}
    </GlassCard>
  );
}

export const SaasHeroSection: React.FC<SaasHeroSectionProps> = ({
  config,
  theme,
  onAuthModeChange,
  onRequestSignupFocus,
}) => {
  const handlePrimaryCta = useCallback(() => {
    onAuthModeChange('signup');
    if (onRequestSignupFocus) {
      onRequestSignupFocus();
      return;
    }
    if (typeof document !== 'undefined') {
      const panel = document.getElementById('saas-auth-panel');
      panel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [onAuthModeChange, onRequestSignupFocus]);

  const handleSecondaryCta = useCallback(() => {
    if (config.demo_url && typeof window !== 'undefined') {
      window.open(config.demo_url, '_blank');
      return;
    }
    handlePrimaryCta();
  }, [config.demo_url, handlePrimaryCta]);

  return (
    <section className="relative isolate overflow-hidden bg-gradient-to-br from-[#f6f3ff] via-[#eef7ff] to-[#f9fcff] py-16 sm:py-20 xl:py-24">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-[-12rem] h-[26rem] bg-gradient-to-b from-white/60 via-white/10 to-transparent"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-32 top-10 h-72 w-72 rounded-full bg-[#ffdce5]/30 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-40 bottom-0 h-80 w-80 rounded-full bg-[#c8e6ff]/35 blur-3xl"
      />

      <div className="relative mx-auto flex w-full max-w-[1440px] flex-col gap-12 px-4 sm:px-6 lg:px-10 xl:px-12">
        <div className="max-w-3xl space-y-8 text-left xl:max-w-4xl">
          <SaasLogoTitle theme={theme} />

          <div className="space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.4em] text-gray-600 shadow-sm">
              2025 Ready
            </span>
            {config.hero_subtitle && (
              <p className="text-sm font-medium uppercase tracking-[0.28em] text-gray-500">
                {config.hero_subtitle}
              </p>
            )}
            <h1 className="text-4xl font-semibold leading-tight text-gray-900 sm:text-5xl xl:text-[3.35rem]">
              {config.hero_title}
            </h1>
            <p className="text-lg text-gray-700 sm:text-xl">
              {config.hero_description}
            </p>
            <div className="flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={handlePrimaryCta}
                className="inline-flex items-center justify-center rounded-full px-8 py-3 text-base font-semibold text-white shadow-lg transition hover:shadow-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                style={{ backgroundColor: theme.primary_color }}
              >
                {config.hero_cta_primary}
              </button>
              <button
                type="button"
                onClick={handleSecondaryCta}
                className="inline-flex items-center justify-center rounded-full border border-gray-300 bg-white/80 px-6 py-3 text-base font-semibold text-gray-800 shadow transition hover:bg-white"
              >
                {config.hero_cta_secondary}
              </button>
            </div>
          </div>

          {config.trust_indicators?.length > 0 && (
            <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600">
              {config.trust_indicators.map((indicator, index) => (
                <span
                  key={indicator}
                  className="inline-flex items-center gap-2 rounded-full border border-white/80 bg-white/70 px-4 py-2 shadow-sm"
                >
                  <span
                    className={`h-2 w-2 rounded-full ${
                      index % 3 === 0 ? 'bg-emerald-400' : index % 3 === 1 ? 'bg-blue-400' : 'bg-violet-400'
                    }`}
                  />
                  {indicator}
                </span>
              ))}
            </div>
          )}
        </div>

        {config.statistics_enabled && Array.isArray(config.statistics) && config.statistics.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {config.statistics.map((statistic) => (
              <GlassCard
                key={statistic.label}
                depth="near"
                blur="lg"
                className="flex flex-col gap-2 rounded-3xl border border-white/50 bg-white/70 p-5 text-left shadow-lg"
              >
                <span className="text-sm font-medium uppercase tracking-[0.24em] text-gray-500">{statistic.label}</span>
                <span className="text-3xl font-semibold text-gray-900">{statistic.value}</span>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

export default SaasHeroSection;
