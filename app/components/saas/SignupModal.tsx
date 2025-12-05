'use client';

import React from 'react';

import { PlannerAuthSection } from './PlannerAuthSection';
import { ThemeConfig } from '@/types/wedding';

interface SignupModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedPlanId?: string;
  theme: ThemeConfig;
}

export const SignupModal: React.FC<SignupModalProps> = ({ isOpen, onClose, selectedPlanId, theme }) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-5xl rounded-3xl border border-white/20 bg-white/95 shadow-2xl backdrop-blur-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-6 top-6 z-10 rounded-full bg-white/80 p-2 text-slate-600 shadow-lg transition-all hover:bg-white hover:text-slate-900 hover:shadow-xl"
          aria-label="Close sign up dialog"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Content */}
        <div className="grid lg:grid-cols-[1fr_1.2fr]">
          {/* Left side - Hero/Info */}
          <div className="hidden lg:flex flex-col justify-center rounded-l-3xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-12 text-white">
            <div className="space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-sm backdrop-blur">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-wedding-rose opacity-75"></span>
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-wedding-rose"></span>
                </span>
                Join 2,000+ wedding planners
              </div>

              <h2 className="text-4xl font-bold leading-tight">
                Launch your workspace in minutes
              </h2>

              <p className="text-lg text-slate-300">
                Everything you need to manage weddings, delight couples, and scale your business—all in one elegant platform.
              </p>

              <div className="space-y-4 pt-4">
                {[
                  { icon: '✓', text: 'Free 14-day trial, no credit card required' },
                  { icon: '✓', text: 'Collaborate with your team & couples' },
                  { icon: '✓', text: 'Manage up to 500 guests per wedding' },
                  { icon: '✓', text: 'Premium support & onboarding included' }
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center gap-3">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-wedding-rose/20 text-sm font-semibold text-wedding-rose">
                      {item.icon}
                    </span>
                    <span className="text-slate-200">{item.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right side - Form */}
          <div className="max-h-[85vh] overflow-y-auto rounded-r-3xl p-8 lg:p-12">
            <PlannerAuthSection
              defaultMode="signup"
              layout="modal"
              theme={theme}
              selectedPlan={selectedPlanId ? { id: selectedPlanId } : undefined}
              onSignupSuccess={onClose}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignupModal;
