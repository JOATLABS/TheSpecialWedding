'use client';

import React, { useCallback } from 'react';
import Image from 'next/image';

interface ModernHeroSectionProps {
  config: {
    hero_headline?: string;
    hero_subheadline?: string;
    hero_problem_statement?: string;
    hero_solution_statement?: string;
    hero_cta_primary: string;
    hero_cta_secondary: string;
    hero_screenshot_primary?: string;
    demo_url?: string;
    primary_color?: string;
  };
  onAuthModeChange: (mode: 'signup' | 'login') => void;
  onRequestSignupFocus?: () => void;
  className?: string;
}

export const ModernHeroSection: React.FC<ModernHeroSectionProps> = ({
  config,
  onAuthModeChange,
  onRequestSignupFocus,
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

  return (
    <section
      className={`relative min-h-screen w-full bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 px-6 py-20 lg:py-32 ${
        className ?? ''
      }`}
    >
      {/* Gradient orbs for depth - like Streamline */}
      <div aria-hidden="true" className="pointer-events-none absolute right-0 top-0 h-[600px] w-[600px] rounded-full bg-blue-600/20 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute bottom-0 left-0 h-[500px] w-[500px] rounded-full bg-purple-600/10 blur-3xl" />

      <div className="relative mx-auto grid max-w-7xl gap-12 lg:grid-cols-2 lg:items-center lg:gap-16">
        {/* Left: Copy */}
        <div className="space-y-8">
          {/* Subheadline - who is this for */}
          {config.hero_subheadline && (
            <div className="inline-block rounded-full bg-blue-500/10 px-4 py-2 text-sm font-medium text-blue-400 ring-1 ring-blue-500/20">
              {config.hero_subheadline}
            </div>
          )}

          {/* Main headline - benefit driven */}
          <h1 className="text-5xl font-bold leading-tight text-white lg:text-6xl xl:text-7xl">
            {config.hero_headline || 'Manage 10+ Weddings Simultaneously'}
          </h1>

          {/* Problem statement */}
          {config.hero_problem_statement && (
            <p className="text-lg text-slate-300 lg:text-xl">
              {config.hero_problem_statement}
            </p>
          )}

          {/* Solution statement */}
          {config.hero_solution_statement && (
            <p className="text-lg font-medium text-white lg:text-xl">
              {config.hero_solution_statement}
            </p>
          )}

          {/* CTAs */}
          <div className="flex flex-col gap-4 sm:flex-row">
            <button
              type="button"
              onClick={handlePrimaryCta}
              className="group relative inline-flex items-center justify-center overflow-hidden rounded-lg bg-blue-600 px-8 py-4 text-base font-semibold text-white shadow-lg transition-all hover:bg-blue-700 hover:shadow-xl hover:shadow-blue-500/50"
            >
              <span className="relative z-10">{config.hero_cta_primary}</span>
              <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-purple-600 opacity-0 transition-opacity group-hover:opacity-100" />
            </button>

            <button
              type="button"
              onClick={handleSecondaryCta}
              className="inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-800/50 px-8 py-4 text-base font-semibold text-white backdrop-blur-sm transition-all hover:bg-slate-700/50 hover:border-slate-600"
            >
              {config.hero_cta_secondary}
            </button>
          </div>

          {/* Trust indicators - minimal and modern */}
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

        {/* Right: Product Screenshot */}
        <div className="relative">
          {config.hero_screenshot_primary ? (
            <div className="relative rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 p-1 shadow-2xl shadow-blue-500/20">
              <div className="relative overflow-hidden rounded-xl">
                <Image
                  src={config.hero_screenshot_primary}
                  alt="Product Screenshot"
                  width={800}
                  height={600}
                  className="w-full"
                  priority
                />
              </div>
            </div>
          ) : (
            // Placeholder mockup when no screenshot provided
            <div className="relative rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 p-1 shadow-2xl shadow-blue-500/20">
              <div className="relative overflow-hidden rounded-xl bg-slate-900 p-8">
                <div className="space-y-4">
                  {/* Mock browser chrome */}
                  <div className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded-full bg-red-500" />
                    <div className="h-3 w-3 rounded-full bg-yellow-500" />
                    <div className="h-3 w-3 rounded-full bg-green-500" />
                  </div>

                  {/* Mock dashboard content */}
                  <div className="space-y-3">
                    <div className="h-12 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 opacity-90" />
                    <div className="grid grid-cols-3 gap-3">
                      <div className="h-24 rounded-lg bg-slate-800/50 backdrop-blur" />
                      <div className="h-24 rounded-lg bg-slate-800/50 backdrop-blur" />
                      <div className="h-24 rounded-lg bg-slate-800/50 backdrop-blur" />
                    </div>
                    <div className="h-32 rounded-lg bg-slate-800/50 backdrop-blur" />
                  </div>

                  {/* Glow effect */}
                  <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/10 to-purple-500/10 blur-2xl" />
                </div>
              </div>
            </div>
          )}

          {/* Floating accent element - like Maxima's 3D effect */}
          <div className="absolute -right-4 -top-4 h-24 w-24 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 opacity-20 blur-2xl" />
          <div className="absolute -bottom-4 -left-4 h-32 w-32 rounded-full bg-gradient-to-tr from-purple-500 to-pink-600 opacity-20 blur-2xl" />
        </div>
      </div>
    </section>
  );
};

export default ModernHeroSection;
