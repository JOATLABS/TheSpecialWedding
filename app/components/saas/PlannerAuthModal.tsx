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
        className={`relative w-full sm:w-auto max-w-[min(100vw-2rem,34rem)] sm:max-w-lg max-h-[calc(100vh-2rem)] overflow-y-auto rounded-2xl transition-all duration-500 ease-out ${
          isAnimating ? 'scale-100 translate-y-0' : 'scale-95 translate-y-8'
        }`}
      >
        {/* Glassmorphic container with gradient border */}
        <div className="relative rounded-3xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 p-[1px] shadow-2xl">
          <div className="relative rounded-3xl bg-slate-900/95 backdrop-blur-2xl">
            {/* Close button */}
            <button
              onClick={handleClose}
              className="absolute right-4 top-4 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-slate-800/70 text-slate-300 transition-all duration-200 hover:bg-slate-700 hover:text-white"
              aria-label="Close modal"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            {/* Animated gradient orb */}
            <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/30 rounded-full blur-3xl animate-pulse" />
            <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-purple-500/30 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />

            {/* Auth section */}
            <div className="relative p-8">
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
