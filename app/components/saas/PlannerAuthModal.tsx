'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { PlannerAuthSection, SubscriptionPlan } from './PlannerAuthSection';
import { ThemeConfig } from '@/types/wedding';

interface PlannerAuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  mode: 'signup' | 'login';
  onModeChange: (mode: 'signup' | 'login') => void;
  theme?: ThemeConfig;
  plans: SubscriptionPlan[];
  plansLoading?: boolean;
  plansError?: string;
  plansNotice?: string;
  selectedPlan?: { id: string; name?: string } | null;
  onSelectPlan?: (plan: { id: string; name?: string }) => void;
}

export const PlannerAuthModal: React.FC<PlannerAuthModalProps> = ({
  isOpen,
  onClose,
  mode,
  onModeChange,
  theme,
  plans,
  plansLoading,
  plansError,
  plansNotice,
  selectedPlan,
  onSelectPlan,
}) => {
  const [isAnimating, setIsAnimating] = useState(false);
  const closeTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    if (isOpen) {
      setIsAnimating(true);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  const handleClose = useCallback(() => {
    setIsAnimating(false);
    if (closeTimeoutRef.current) {
      window.clearTimeout(closeTimeoutRef.current);
    }
    closeTimeoutRef.current = window.setTimeout(() => {
      onClose();
      closeTimeoutRef.current = null;
    }, 300);
  }, [onClose]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [handleClose, isOpen]);

  useEffect(() => {
    return () => {
      if (closeTimeoutRef.current) {
        window.clearTimeout(closeTimeoutRef.current);
        closeTimeoutRef.current = null;
      }
    };
  }, []);

  if (!isOpen && !isAnimating) return null;

  return (
    <div
      className={`fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center sm:p-6 transition-all duration-300 ${
        isAnimating ? 'opacity-100' : 'opacity-0'
      }`}
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        className={`absolute inset-0 bg-slate-950/85 backdrop-blur-xl transition-opacity duration-300 ${
          isAnimating ? 'opacity-100' : 'opacity-0'
        }`}
      >
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(59,130,246,0.18),transparent_55%)]" />
      </div>

      <div
        className={`relative w-full max-w-[min(100vw-1.5rem,40rem)] sm:max-w-4xl max-h-[min(100vh-1.5rem,45rem)] overflow-hidden rounded-[2.5rem] bg-white transition-all duration-500 ease-out ${
          isAnimating ? 'translate-y-0 scale-100' : 'translate-y-8 scale-[0.97]'
        } shadow-[0_60px_160px_-90px_rgba(15,23,42,0.65)] sm:overflow-visible`}
      >
        <div className="absolute inset-x-12 top-0 hidden h-1 rounded-full bg-gradient-to-r from-sky-400 via-blue-500 to-purple-500 sm:block" />
        <div className="grid h-full lg:grid-cols-[0.85fr_1.15fr]">
          <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-slate-900 via-blue-900 to-slate-800 p-9 text-white lg:flex">
            <div className="absolute inset-y-0 right-[-6rem] w-[14rem] rounded-full bg-blue-500/25 blur-3xl" />
            <div className="absolute -bottom-16 left-[-9rem] h-44 w-44 rounded-full bg-purple-500/30 blur-3xl" />
            <div className="relative space-y-5">
              <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-blue-100">
                Planner workspace
              </span>
              <h2 className="text-2xl font-semibold leading-tight">Launch in minutes with concierge onboarding</h2>
              <p className="text-sm text-slate-200">
                Personalize your studio portal, invite collaborators, and turn on automations in a guided, human-supported flow.
              </p>
            </div>
            <div className="relative space-y-5 rounded-2xl border border-white/15 bg-white/10 p-5 text-sm text-slate-100">
              <div className="flex items-center justify-between">
                <span className="font-semibold">Average setup time</span>
                <span className="text-lg font-semibold">4 days</span>
              </div>
              <div className="flex items-center justify-between text-xs text-blue-100/90">
                <span>Vendor invites</span>
                <span>Unlimited</span>
              </div>
              <div className="flex items-center justify-between text-xs text-blue-100/90">
                <span>Client portals</span>
                <span>Included</span>
              </div>
              <div className="flex items-center justify-between text-xs text-blue-100/90">
                <span>Live concierge support</span>
                <span>Yes</span>
              </div>
            </div>
          </div>

          <div className="relative max-h-[calc(100vh-4rem)] overflow-y-auto p-6 sm:max-h-none sm:p-8">
            <button
              onClick={handleClose}
              className="absolute right-6 top-6 z-10 flex h-10 w-10 items-center justify-center rounded-full border border-slate-200/80 bg-white text-slate-500 transition hover:-translate-y-[1px] hover:border-slate-300 hover:text-slate-900"
              aria-label="Close modal"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <div className="mt-6 space-y-6">
              <div className="flex flex-col gap-3 text-left">
                <div className="inline-flex items-center gap-2 self-start rounded-full border border-slate-200/80 bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-600">
                  Planner login
                  <span className="rounded-full bg-white px-2 py-0.5 text-[9px] font-semibold text-slate-500">Secure</span>
                </div>
                <h2 className="text-2xl font-semibold text-slate-900">
                  {mode === 'signup' ? 'Create your planner account' : 'Welcome back'}
                </h2>
                <p className="text-sm text-slate-500">
                  {mode === 'signup'
                    ? 'Choose a signature plan, invite collaborators, and begin managing weddings today.'
                    : 'Access your planning workspaces, vendor collaboration hub, and analytics.'}
                </p>
              </div>

              <div className="grid gap-4">
                {theme && (
                  <PlannerAuthSection
                    mode={mode}
                    onModeChange={onModeChange}
                    theme={theme}
                    plans={plans}
                    plansLoading={plansLoading}
                    plansError={plansError}
                    plansNotice={plansNotice}
                    selectedPlan={selectedPlan}
                    onSelectPlan={onSelectPlan}
                    className="shadow-none"
                  />
                )}

                <div className="rounded-2xl border border-slate-200/80 bg-slate-50 px-4 py-3 text-xs text-slate-500">
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    <svg className="h-4 w-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Concierge onboarding included
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed">
                    We guide your first import, vendor invites, and branded portal setup so your team launches confidently.
                  </p>
                </div>
              </div>

              {plansError && !plansLoading && (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {plansError}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .overflow-y-auto::-webkit-scrollbar {
          width: 8px;
        }

        .overflow-y-auto::-webkit-scrollbar-track {
          background: rgba(226, 232, 240, 0.6);
          border-radius: 4px;
        }

        .overflow-y-auto::-webkit-scrollbar-thumb {
          background: rgba(148, 163, 184, 0.7);
          border-radius: 4px;
        }

        .overflow-y-auto::-webkit-scrollbar-thumb:hover {
          background: rgba(71, 85, 105, 0.7);
        }

        @media (max-width: 640px) {
          .overflow-y-auto {
            max-height: calc(100vh - 6rem);
          }
        }
      `}</style>
    </div>
  );
};

export default PlannerAuthModal;
