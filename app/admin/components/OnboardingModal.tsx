'use client';

import React, { useState, useEffect } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import {
  X,
  ChevronRight,
  ChevronLeft,
  LayoutDashboard,
  Heart,
  Users,
  Sparkles,
  CheckCircle,
} from 'lucide-react';

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
}

interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  features: string[];
}

const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'welcome',
    title: 'Start With The Wedding Setup Prompt',
    description: 'Your dashboard now points you to the next guest-facing setup step for each wedding, then drops you into the exact configuration tab that needs attention.',
    icon: <Sparkles className="w-12 h-12 text-purple-500" />,
    features: [
      'See which wedding still needs schedule, RSVP, access, or theme work',
      'Use one action to continue setup from the dashboard',
      'Keep optional tabs visible without blocking launch readiness',
      'Preview the couple site once the essentials are ready',
    ]
  },
  {
    id: 'site-essentials',
    title: 'Finish The Guest Essentials',
    description: 'The setup checklist focuses first on the information guests need before the wedding website should be shared.',
    icon: <Heart className="w-12 h-12 text-pink-500" />,
    features: [
      'Schedule: date, time, venue, address, and attire',
      'RSVP: guest-facing copy and help handoff',
      'Access: public, private, or password-protected visibility',
      'Theme: colors and typography for the public page',
    ]
  },
  {
    id: 'optional-content',
    title: 'Add The Experience Layers',
    description: 'Once the essentials are stable, the same configuration page walks you through the content that makes the site feel complete.',
    icon: <Users className="w-12 h-12 text-green-500" />,
    features: [
      'Vendors: assigned partners, contracts, quotes, and payments',
      'Registry: gift links guests can open from the site',
      'FAQ: travel, hotel, dress code, and guest questions',
      'Story: couple story, photos, and wedding party',
    ]
  },
  {
    id: 'dashboard',
    title: 'Run The Wedding From The Dashboard',
    description: 'The setup prompt stays small so the dashboard can still work as your daily command surface for guests, communications, and activity.',
    icon: <LayoutDashboard className="w-12 h-12 text-blue-500" />,
    features: [
      'Review portfolio stats without losing the setup context',
      'Jump into guests, reminders, and gallery uploads from quick actions',
      'Use recent activity and AI insights after the public site is configured',
      'Open each wedding workspace or public site from the same list',
    ]
  },
  {
    id: 'ready',
    title: 'You Know What To Do Next',
    description: 'Start from the dashboard, follow the next setup action, save the wedding, and come back when you want the broader operational view.',
    icon: <CheckCircle className="w-12 h-12 text-green-500" />,
    features: [
      'The setup prompt stays visible after this tour is dismissed',
      'The configuration page keeps the checklist above the tabs',
      'Required essentials show amber until they are ready',
      'Ready essentials show green so you can move on confidently',
    ]
  }
];

export default function OnboardingModal({ isOpen, onComplete }: OnboardingModalProps) {
  const { apiRequest } = useAdmin();
  const [currentStep, setCurrentStep] = useState(0);
  const [completing, setCompleting] = useState(false);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const handleNext = () => {
    if (currentStep < ONBOARDING_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = async () => {
    await completeOnboarding(false);
  };

  const handleComplete = async () => {
    await completeOnboarding(true);
  };

  const completeOnboarding = async (completed: boolean) => {
    try {
      setCompleting(true);

      // Get list of completed steps
      const stepsCompleted = ONBOARDING_STEPS
        .slice(0, completed ? ONBOARDING_STEPS.length : currentStep + 1)
        .map(step => step.id);

      await apiRequest('/profile/onboarding', 'PUT', {
        completed: true, // Always mark as completed (whether finished or skipped)
        steps_completed: stepsCompleted
      });

      onComplete();
    } catch (error) {
      console.error('Error completing onboarding:', error);
      // Still close on error - don't block the user
      onComplete();
    } finally {
      setCompleting(false);
    }
  };

  if (!isOpen) return null;

  const step = ONBOARDING_STEPS[currentStep];
  const isLastStep = currentStep === ONBOARDING_STEPS.length - 1;
  const isFirstStep = currentStep === 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm"
        onClick={handleSkip}
      />

      {/* Modal */}
      <div
        className="relative bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={handleSkip}
          className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors z-10"
          aria-label="Skip tour"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Content */}
        <div className="p-5 sm:p-8">
          {/* Icon */}
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-2xl">
              {step.icon}
            </div>
          </div>

          {/* Title */}
          <h2 className="text-2xl font-bold text-center text-gray-900 dark:text-gray-100 mb-4">
            {step.title}
          </h2>

          {/* Description */}
          <p className="text-center text-gray-600 dark:text-gray-400 mb-6 max-w-lg mx-auto">
            {step.description}
          </p>

          {/* Features */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
            {step.features.map((feature, index) => (
              <div
                key={index}
                className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-slate-700/50 rounded-lg"
              >
                <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                <span className="text-sm text-gray-700 dark:text-gray-300">{feature}</span>
              </div>
            ))}
          </div>

          {/* Progress Dots */}
          <div className="flex justify-center gap-2 mb-6">
            {ONBOARDING_STEPS.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentStep(index)}
                className={`w-2.5 h-2.5 rounded-full transition-all ${
                  index === currentStep
                    ? 'bg-blue-600 w-6'
                    : index < currentStep
                    ? 'bg-blue-300 dark:bg-blue-700'
                    : 'bg-gray-300 dark:bg-gray-600'
                }`}
                aria-label={`Go to step ${index + 1}`}
              />
            ))}
          </div>

          {/* Navigation Buttons */}
          <div className="flex items-center justify-between">
            {/* Skip/Previous */}
            <div>
              {isFirstStep ? (
                <button
                  onClick={handleSkip}
                  disabled={completing}
                  className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
                >
                  Skip Tour
                </button>
              ) : (
                <button
                  onClick={handlePrevious}
                  disabled={completing}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-slate-700 rounded-lg hover:bg-gray-200 dark:hover:bg-slate-600 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Previous
                </button>
              )}
            </div>

            {/* Step Counter */}
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {currentStep + 1} of {ONBOARDING_STEPS.length}
            </span>

            {/* Next/Complete */}
            {isLastStep ? (
              <button
                onClick={handleComplete}
                disabled={completing}
                className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 transition-all shadow-lg shadow-blue-500/25"
              >
                {completing ? 'Finishing...' : 'Get Started'}
                <Sparkles className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleNext}
                disabled={completing}
                className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
