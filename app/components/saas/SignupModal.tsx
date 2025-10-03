'use client';

import React from 'react';

import { GlassCard } from '../ui/GlassCard';
import { PlannerSignupForm } from './PlannerSignupForm';
import { ThemeConfig } from '@/types/wedding';
import { SocialAuthButtons } from '../auth/SocialAuthButtons';

interface SignupModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedPlanId?: string;
  theme: ThemeConfig;
}

export const SignupModal: React.FC<SignupModalProps> = ({ isOpen, onClose, selectedPlanId, theme }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <GlassCard theme={theme} className="max-h-[90vh] w-full max-w-md overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Create Your Account</h2>
          <button
            onClick={onClose}
            className="text-gray-400 transition-colors hover:text-gray-600"
            aria-label="Close sign up dialog"
          >
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p className="mb-6 text-gray-600">
          Join thousands of wedding planners who trust Special Wedding for their business.
        </p>

        <PlannerSignupForm theme={theme} selectedPlanId={selectedPlanId} onDismiss={onClose} variant="modal" />
      </GlassCard>
    </div>
  );
};

export default SignupModal;
