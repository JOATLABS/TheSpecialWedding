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
        className={`relative w-full max-w-[min(100vw-1.5rem,42rem)] sm:max-w-5xl max-h-[min(100vh-1.5rem,46rem)] overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/95 transition-all duration-500 ease-out ${
          isAnimating ? 'translate-y-0 scale-100' : 'translate-y-8 scale-[0.97]'
        } shadow-[0_80px_160px_-80px_rgba(15,23,42,0.65)] sm:overflow-visible`}
      >
        <div className="absolute inset-x-12 top-0 hidden h-1 rounded-full bg-gradient-to-r from-sky-400 via-blue-500 to-purple-500 sm:block" />
        <div className="grid h-full lg:grid-cols-[0.82fr_1.18fr]">
          <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-slate-950 via-indigo-900 to-slate-900 p-10 text-white lg:flex">
            <div className="planner-modal-backdrop" aria-hidden="true">
              <div className="planner-modal-ring planner-modal-ring--primary" />
              <div className="planner-modal-ring planner-modal-ring--secondary" />
              <div className="planner-modal-orb planner-modal-orb--top" />
              <div className="planner-modal-orb planner-modal-orb--bottom" />
              <div className="planner-modal-petal planner-modal-petal--one" />
              <div className="planner-modal-petal planner-modal-petal--two" />
            </div>
            <div className="relative space-y-5">
              <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-blue-100">
                Planner concierge
              </span>
              <h2 className="text-2xl font-semibold leading-tight">Launch in minutes with a dedicated guide</h2>
              <p className="text-sm text-slate-200/90">
                Personalize your studio portal, align collaborators, and automate reminders with curated workflows for luxury weddings.
              </p>
            </div>
            <div className="relative space-y-5 rounded-3xl border border-white/15 bg-white/10 p-5 text-sm text-slate-100 shadow-[0_24px_60px_-40px_rgba(59,130,246,0.65)]">
              <div className="flex items-center justify-between">
                <span className="font-semibold">Average setup time</span>
                <span className="text-lg font-semibold">4 days</span>
              </div>
              <div className="grid gap-3 text-xs text-blue-100/90">
                <div className="flex items-center justify-between">
                  <span>Vendor invites</span>
                  <span>Unlimited</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Client portals</span>
                  <span>Included</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Concierge walkthrough</span>
                  <span>Yes</span>
                </div>
              </div>
            </div>
          </div>

          <div className="relative max-h-[calc(100vh-4rem)] overflow-y-auto bg-white/98 p-6 sm:max-h-none sm:p-8">
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
                <div className="inline-flex items-center gap-2 self-start rounded-full border border-slate-200/80 bg-slate-100 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-600">
                  Planner access
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

              <div className="rounded-2xl border border-slate-200/70 bg-slate-50/90 p-5 text-sm text-slate-600 shadow-sm lg:hidden">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 via-sky-400 to-purple-500 text-base font-semibold text-white">SW</div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Concierge onboarding</p>
                    <p className="text-xs text-slate-500">Average setup time 4 days with a live specialist.</p>
                  </div>
                </div>
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

        .planner-modal-backdrop {
          position: absolute;
          inset: 0;
          pointer-events: none;
          overflow: hidden;
        }

        .planner-modal-ring {
          position: absolute;
          border-radius: 9999px;
          border: 1.5px solid rgba(255, 255, 255, 0.35);
          opacity: 0.7;
          animation: planner-ring-drift 20s ease-in-out infinite;
        }

        .planner-modal-ring--primary {
          width: 360px;
          height: 360px;
          top: -160px;
          right: -140px;
          border-color: rgba(191, 219, 254, 0.6);
        }

        .planner-modal-ring--secondary {
          width: 240px;
          height: 240px;
          bottom: -140px;
          left: -120px;
          border-color: rgba(224, 231, 255, 0.45);
          animation-delay: 1.5s;
        }

        .planner-modal-orb {
          position: absolute;
          border-radius: 9999px;
          background: radial-gradient(circle at 30% 30%, rgba(96, 165, 250, 0.6), transparent 70%);
          filter: blur(0.5px);
          animation: planner-orb-float 16s ease-in-out infinite;
        }

        .planner-modal-orb--top {
          width: 160px;
          height: 160px;
          top: 12%;
          left: 12%;
        }

        .planner-modal-orb--bottom {
          width: 140px;
          height: 140px;
          bottom: 15%;
          right: 18%;
          animation-delay: 1.8s;
        }

        .planner-modal-petal {
          position: absolute;
          width: 54px;
          height: 54px;
          opacity: 0.75;
          background: radial-gradient(circle, rgba(254, 215, 226, 0.65), transparent 70%);
          animation: planner-petal-fall 14s ease-in-out infinite;
        }

        .planner-modal-petal--one {
          top: -10px;
          right: 35%;
        }

        .planner-modal-petal--two {
          bottom: 8%;
          left: 28%;
          animation-delay: 2.5s;
        }

        @keyframes planner-ring-drift {
          0%,
          100% {
            transform: translate3d(0, 0, 0) rotate(0deg);
          }
          50% {
            transform: translate3d(18px, 12px, 0) rotate(8deg);
          }
        }

        @keyframes planner-orb-float {
          0%,
          100% {
            transform: translate3d(0, 0, 0);
            opacity: 0.75;
          }
          50% {
            transform: translate3d(0, -22px, 0);
            opacity: 1;
          }
        }

        @keyframes planner-petal-fall {
          0%,
          100% {
            transform: translate3d(0, 0, 0) rotate(0deg);
            opacity: 0.45;
          }
          50% {
            transform: translate3d(-10px, 18px, 0) rotate(12deg);
            opacity: 0.85;
          }
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
