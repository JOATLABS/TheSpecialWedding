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
  CheckCircle,
  Megaphone,
  Zap
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
    title: 'Welcome to Planner HQ',
    description: 'Your dashboard now brings together wedding health, couple collaboration, AI guidance, and operations tooling in one place. This tour highlights the fastest way to work through it.',
    icon: <Sparkles className="w-12 h-12 text-purple-500" />,
    features: [
      'See portfolio-wide activity without bouncing between modules',
      'Guide couples through their own shared portal experience',
      'Manage payments, forms, contracts, and messaging from connected tools',
      'Use AI insights to surface the next best action for each wedding',
    ]
  },
  {
    id: 'dashboard',
    title: 'Your Dashboard Pulse',
    description: 'The planner dashboard is the command surface for the workday. It shows summary stats, quick-launch actions, AI insights, progress tracking, and the recent activity stream side by side.',
    icon: <LayoutDashboard className="w-12 h-12 text-blue-500" />,
    features: [
      'Review guest, RSVP, and wedding totals at a glance',
      'Jump straight into guests, reminders, and gallery uploads',
      'Read AI insights for the selected wedding without leaving the dashboard',
      'Track wedding progress and recent activity from one screen',
    ]
  },
  {
    id: 'weddings',
    title: 'Wedding Operations',
    description: 'Every wedding still has its own workspace, but the dashboard now makes it easier to jump into the ones that need attention and manage them as a portfolio instead of isolated records.',
    icon: <Heart className="w-12 h-12 text-pink-500" />,
    features: [
      'Open the right wedding directly from the dashboard list',
      'Monitor progress percentages and days remaining per couple',
      'Launch each wedding website or workspace in one click',
      'Keep event details, venues, and RSVP context connected to the same record',
    ]
  },
  {
    id: 'couples',
    title: 'Couple Collaboration',
    description: 'The platform now gives couples their own portal for forms, payments, updates, FAQ content, registry links, and day-of context, so you stop managing approvals through fragmented messages.',
    icon: <Users className="w-12 h-12 text-green-500" />,
    features: [
      'Share a guided dashboard with each couple',
      'Keep forms, FAQs, registry links, and updates in one portal',
      'Let couples review payment status without extra follow-up',
      'Reduce back-and-forth by keeping the couple experience wired to your data',
    ]
  },
  {
    id: 'inbox',
    title: 'Messaging & Activity',
    description: 'Planner communication now lives in a cleaner workflow. The split-panel inbox and recent activity stream make it easier to see what changed, who needs a response, and what was already handled.',
    icon: <Mail className="w-12 h-12 text-indigo-500" />,
    features: [
      'Reply to couples from a dedicated inbox instead of scattered threads',
      'Track unread message counts across the platform',
      'Review project activity without digging through wedding records',
      'Keep updates, notes, and communication attached to the right account',
    ]
  },
  {
    id: 'business',
    title: 'Packages, Contracts & Payments',
    description: 'Business workflows are now more connected, from AI-assisted packages and contracts to payment schedules couples can review inside their portal.',
    icon: <DollarSign className="w-12 h-12 text-yellow-500" />,
    features: [
      'Create and preview service packages from the planner workspace',
      'Generate polished contracts with AI-assisted drafting',
      'Track payments, balances, and billing milestones in one place',
      'Give couples visibility into what is due without extra admin work',
    ]
  },
  {
    id: 'support',
    title: 'Team Readiness & Support',
    description: 'As your studio grows, the platform now supports tighter internal coordination through team access controls, knowledge base content, and operational visibility.',
    icon: <HelpCircle className="w-12 h-12 text-cyan-500" />,
    features: [
      'Assign planners only to the weddings they should touch',
      'Use the knowledge base to reduce repeated training and support requests',
      'Spot opportunities and activity from the dashboard without context switching',
      'Keep the whole team working from the same source of truth',
    ]
  },
  {
    id: 'vendor-network',
    title: 'Grow Through Your Vendor Network',
    description: 'The platform is also a vendor marketplace. Source from the public directory, invite vendors into token-based contract workspaces, or let advertising vendors bring leads directly to your inbox — all without a separate subscription.',
    icon: <Megaphone className="w-12 h-12 text-rose-500" />,
    features: [
      'Browse photographers, venues, and caterers in the public vendor directory',
      'Invite contract vendors into token-based workspaces for signatures, deliverables, and payments',
      'Compare quotes side by side with AI-assisted summaries',
      'Receive CPL leads from advertising vendors directly in the planner inbox',
    ]
  },
  {
    id: 'real-time',
    title: 'Everyone Stays in Sync, Automatically',
    description: 'Changes you save push live to the couple portal the second they happen. Inbound emails thread against the right couple. Every write is captured in the activity audit log. Planning stops being email tag.',
    icon: <Zap className="w-12 h-12 text-amber-500" />,
    features: [
      'Server-sent events update the couple portal in real time — no refresh needed',
      'Forwarded vendor and guest emails auto-thread into the right couple inbox',
      'See every change to a wedding in the activity audit log, filterable by team member',
      'Team members share one real-time workspace instead of status-update emails',
    ]
  },
  {
    id: 'ready',
    title: 'You\'re Ready',
    description: 'Start each day from the planner dashboard. It is now the fastest path to wedding triage, couple communication, financial follow-up, and team coordination.',
    icon: <CheckCircle className="w-12 h-12 text-green-500" />,
    features: [
      'Review AI insights before jumping into detail pages',
      'Use the inbox and activity feed as your operational heartbeat',
      'Drive couples back into the portal for forms, approvals, and updates',
      'Keep weddings moving forward from one connected system',
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
