'use client';

import React, { useState, useEffect } from 'react';
import { PlannerAuthSection, SubscriptionPlan } from './PlannerAuthSection';

interface PlannerAuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  mode: 'signup' | 'login';
  onModeChange: (mode: 'signup' | 'login') => void;
  theme?: {
    primary_color?: string;
    secondary_color?: string;
    accent_color?: string;
    background_style?: string;
    font_style?: string;
  };
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

  const handleClose = () => {
    setIsAnimating(false);
    setTimeout(onClose, 300); // Wait for animation to complete
  };

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  if (!isOpen && !isAnimating) return null;

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-300 ${
        isAnimating ? 'opacity-100' : 'opacity-0'
      }`}
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      {/* Backdrop with blur */}
      <div
        className={`absolute inset-0 bg-slate-950/80 backdrop-blur-xl transition-opacity duration-300 ${
          isAnimating ? 'opacity-100' : 'opacity-0'
        }`}
      />

      {/* Modal content */}
      <div
        className={`relative max-w-lg w-full max-h-[90vh] overflow-y-auto transition-all duration-500 ease-out ${
          isAnimating ? 'scale-100 translate-y-0' : 'scale-95 translate-y-8'
        }`}
      >
        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute -top-12 right-0 z-10 p-2 rounded-full bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-700/50 transition-all duration-200 backdrop-blur-sm"
          aria-label="Close modal"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Glassmorphic container with gradient border */}
        <div className="relative rounded-3xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 p-[1px] shadow-2xl">
          <div className="relative rounded-3xl bg-slate-900/95 backdrop-blur-2xl">
            {/* Animated gradient orb */}
            <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/30 rounded-full blur-3xl animate-pulse" />
            <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-purple-500/30 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />

            {/* Auth section */}
            <div className="relative p-8">
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

              {plansError && !plansLoading && (
                <div className="mt-4 rounded-xl border border-red-200/80 bg-red-50/10 px-4 py-3 text-sm text-red-400 backdrop-blur">
                  {plansError}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        /* Custom scrollbar for modal */
        .overflow-y-auto::-webkit-scrollbar {
          width: 8px;
        }

        .overflow-y-auto::-webkit-scrollbar-track {
          background: rgba(30, 41, 59, 0.3);
          border-radius: 4px;
        }

        .overflow-y-auto::-webkit-scrollbar-thumb {
          background: rgba(100, 116, 139, 0.5);
          border-radius: 4px;
        }

        .overflow-y-auto::-webkit-scrollbar-thumb:hover {
          background: rgba(148, 163, 184, 0.7);
        }
      `}</style>
    </div>
  );
};

export default PlannerAuthModal;
