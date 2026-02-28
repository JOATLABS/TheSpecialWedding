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
  Mail,
  DollarSign,
  HelpCircle,
  Sparkles,
  CheckCircle
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
    title: 'Welcome to The Special Wedding!',
    description: 'Your all-in-one platform for managing weddings. Let\'s take a quick tour of the key features that will help you deliver exceptional wedding experiences.',
    icon: <Sparkles className="w-12 h-12 text-purple-500" />,
    features: [
      'Manage multiple weddings from one dashboard',
      'Streamline guest communication',
      'Track budgets and vendors',
      'AI-powered assistance'
    ]
  },
  {
    id: 'dashboard',
    title: 'Your Dashboard',
    description: 'Your command center for all wedding operations. Get a bird\'s-eye view of everything happening across your weddings.',
    icon: <LayoutDashboard className="w-12 h-12 text-blue-500" />,
    features: [
      'View RSVP statistics at a glance',
      'Track wedding progress and timelines',
      'Access AI-powered insights',
      'Quick actions for common tasks'
    ]
  },
  {
    id: 'weddings',
    title: 'Wedding Management',
    description: 'Create and manage weddings with ease. Each wedding gets its own dedicated space with customizable settings.',
    icon: <Heart className="w-12 h-12 text-pink-500" />,
    features: [
      'Create multi-event weddings',
      'Customize wedding websites',
      'Manage event details and venues',
      'Generate unique guest URLs'
    ]
  },
  {
    id: 'guests',
    title: 'Guest Management',
    description: 'Keep track of every guest, their preferences, and their RSVP status. Import guests in bulk or add them one by one.',
    icon: <Users className="w-12 h-12 text-green-500" />,
    features: [
      'Add guests individually or import in bulk',
      'Organize guests into groups',
      'Manage plus-ones and dietary preferences',
      'Track attendance for multiple events'
    ]
  },
  {
    id: 'rsvp',
    title: 'RSVP & Invitations',
    description: 'Send beautiful invitations via SMS or email and track responses in real-time. Automate reminders to increase response rates.',
    icon: <Mail className="w-12 h-12 text-indigo-500" />,
    features: [
      'Send SMS & email invitations',
      'Track RSVP responses instantly',
      'Schedule automated reminders',
      'View delivery and read status'
    ]
  },
  {
    id: 'budget',
    title: 'Budget Tracking',
    description: 'Keep wedding finances under control. Track expenses, payments, and get AI-powered budget recommendations.',
    icon: <DollarSign className="w-12 h-12 text-yellow-500" />,
    features: [
      'Set and track budgets by category',
      'Record payments and expenses',
      'Get AI budget insights',
      'Generate financial reports'
    ]
  },
  {
    id: 'support',
    title: 'Help & Support',
    description: 'You\'re never alone! Access our Knowledge Base for guides and FAQs, or create a support ticket if you need personalized help.',
    icon: <HelpCircle className="w-12 h-12 text-cyan-500" />,
    features: [
      'Browse Knowledge Base articles',
      'Create support tickets',
      'Contribute your own guides',
      'Get email notifications on updates'
    ]
  },
  {
    id: 'ready',
    title: 'You\'re All Set!',
    description: 'You now know the basics. Start by creating your first wedding or explore the dashboard to get familiar with the platform.',
    icon: <CheckCircle className="w-12 h-12 text-green-500" />,
    features: [
      'Create your first wedding',
      'Import your guest list',
      'Send out invitations',
      'Track everything in one place'
    ]
  }
];

export default function OnboardingModal({ isOpen, onClose, onComplete }: OnboardingModalProps) {
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
        <div className="p-8">
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
          <p className="text-center text-gray-600 dark:text-gray-400 mb-8 max-w-lg mx-auto">
            {step.description}
          </p>

          {/* Features */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-8">
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
          <div className="flex justify-center gap-2 mb-8">
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
