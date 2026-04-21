'use client';

import React, { useEffect, useState } from 'react';
import {
  X,
  ChevronRight,
  ChevronLeft,
  LayoutDashboard,
  Calendar,
  ClipboardList,
  CreditCard,
  MessageCircle,
  Gift,
  Sparkles,
  BellRing,
  CheckCircle,
} from 'lucide-react';
import { coupleFetch } from '@/couple/lib/auth';

interface CoupleOnboardingModalProps {
  isOpen: boolean;
  onComplete: () => void;
}

interface CoupleOnboardingStep {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  features: string[];
}

const COUPLE_ONBOARDING_STEPS: CoupleOnboardingStep[] = [
  {
    id: 'welcome',
    title: 'Welcome to Your Wedding Portal',
    description: 'This is your shared home base for everything your planner wants you to see, review, and respond to as the day gets closer.',
    icon: <Sparkles className="w-12 h-12 text-rose-500" />,
    features: [
      'See the latest plan without chasing email threads',
      'Track your guest and budget snapshot at a glance',
      'Reply to your planner from one shared inbox',
      'Keep every important detail in one secure place',
    ],
  },
  {
    id: 'dashboard',
    title: 'Your Dashboard',
    description: 'The dashboard surfaces the biggest things you need right now, from countdown and guest status to planner contact details and budget progress.',
    icon: <LayoutDashboard className="w-12 h-12 text-blue-500" />,
    features: [
      'Countdown to the wedding day',
      'Guest RSVP totals and pending responses',
      'Budget snapshot with remaining balance',
      'Planner contact details when you need help fast',
    ],
  },
  {
    id: 'timeline',
    title: 'Timeline & Event Notes',
    description: 'Each event keeps its own date, venue details, and note threads so you and your planner stay aligned on the run of show.',
    icon: <Calendar className="w-12 h-12 text-violet-500" />,
    features: [
      'Review each ceremony, reception, or rehearsal event',
      'Add notes directly to an event or timeline item',
      'See timing, attire, and location details in context',
      'Keep planner feedback attached to the right moment',
    ],
  },
  {
    id: 'forms',
    title: 'Forms & Requests',
    description: 'When your planner needs answers, documents, or selections, they show up here with clear status so you know what is still outstanding.',
    icon: <ClipboardList className="w-12 h-12 text-emerald-500" />,
    features: [
      'Complete shared questionnaires and intake forms',
      'See which forms are pending versus submitted',
      'Update answers later when plans change',
      'Keep all submitted information tied to your wedding record',
    ],
  },
  {
    id: 'payments',
    title: 'Contracts & Payments',
    description: 'Your contract summary and payment schedule are available in the portal so you can check status, upcoming due dates, and what remains outstanding.',
    icon: <CreditCard className="w-12 h-12 text-amber-500" />,
    features: [
      'Review your package and contract status',
      'Track paid, scheduled, and remaining payments',
      'Know what is due next without asking your planner',
      'Keep billing context connected to the rest of the plan',
    ],
  },
  {
    id: 'messages',
    title: 'Messages & Planner Updates',
    description: 'Use the portal inbox instead of scattered texts and emails. Messages, milestone updates, and planner announcements stay in one running conversation.',
    icon: <MessageCircle className="w-12 h-12 text-indigo-500" />,
    features: [
      'Send questions directly to your planner',
      'Read milestone updates and project announcements',
      'Track unread activity in one place',
      'Keep wedding communication attached to the right account',
    ],
  },
  {
    id: 'self-serve',
    title: 'Your Registry, FAQs & Check-Ins',
    description: 'Stop being the bottleneck for routine guest questions. Maintain your registry, FAQs, and planner check-ins right in the portal — and every update flows to your public wedding microsite automatically.',
    icon: <Gift className="w-12 h-12 text-pink-500" />,
    features: [
      'Add and update registry URLs from any of your favorite sites',
      'Maintain a FAQ list guests see on your wedding microsite',
      'Book planner check-ins without the back-and-forth texting',
      'Every change syncs to the public wedding site in real time',
    ],
  },
  {
    id: 'stay-informed',
    title: 'Get Pinged, Not Pestered',
    description: 'Real-time push notifications let you know the moment something changes — RSVPs, payments, vendor updates, messages. Plus a memory wall where guests can upload photos during the event.',
    icon: <BellRing className="w-12 h-12 text-cyan-500" />,
    features: [
      'Enable push notifications for messages, payments, and milestones',
      'See updates in the portal live — no refresh, no "did you see my email"',
      'Let guests upload photos during the reception via a QR memory wall',
      'Review guest memories privately before they appear in the public gallery',
    ],
  },
  {
    id: 'ready',
    title: 'You\'re Ready',
    description: 'Use the portal as your source of truth. The more you keep conversations, forms, and approvals here, the smoother the final weeks become.',
    icon: <CheckCircle className="w-12 h-12 text-green-500" />,
    features: [
      'Open the dashboard whenever plans shift',
      'Check the inbox before sending a text or email',
      'Complete forms as soon as they appear',
      'Keep notifications on so you never miss a change',
    ],
  },
];

export default function CoupleOnboardingModal({ isOpen, onComplete }: CoupleOnboardingModalProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [completing, setCompleting] = useState(false);

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

  const completeOnboarding = async (completed: boolean) => {
    try {
      setCompleting(true);
      const stepsCompleted = COUPLE_ONBOARDING_STEPS
        .slice(0, completed ? COUPLE_ONBOARDING_STEPS.length : currentStep + 1)
        .map((step) => step.id);

      await coupleFetch('/couple/profile/onboarding', {
        method: 'PUT',
        body: JSON.stringify({
          completed: true,
          steps_completed: stepsCompleted,
        }),
      });
    } catch (error) {
      console.error('Error completing couple onboarding:', error);
    } finally {
      setCompleting(false);
      onComplete();
    }
  };

  if (!isOpen) {
    return null;
  }

  const step = COUPLE_ONBOARDING_STEPS[currentStep];
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === COUPLE_ONBOARDING_STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => completeOnboarding(false)} />

      <div
        className="relative w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-slate-800"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          onClick={() => completeOnboarding(false)}
          className="absolute top-4 right-4 z-10 p-2 text-gray-400 transition-colors hover:text-gray-600 dark:hover:text-gray-300"
          aria-label="Skip portal tour"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-8">
          <div className="mb-6 flex justify-center">
            <div className="rounded-2xl bg-gradient-to-br from-rose-50 to-sky-50 p-4 dark:from-rose-900/20 dark:to-sky-900/20">
              {step.icon}
            </div>
          </div>

          <h2 className="mb-4 text-center text-2xl font-bold text-gray-900 dark:text-gray-100">
            {step.title}
          </h2>

          <p className="mx-auto mb-8 max-w-lg text-center text-gray-600 dark:text-gray-400">
            {step.description}
          </p>

          <div className="mb-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {step.features.map((feature) => (
              <div
                key={feature}
                className="flex items-start gap-3 rounded-lg bg-gray-50 p-3 dark:bg-slate-700/50"
              >
                <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-500" />
                <span className="text-sm text-gray-700 dark:text-gray-300">{feature}</span>
              </div>
            ))}
          </div>

          <div className="mb-8 flex justify-center gap-2">
            {COUPLE_ONBOARDING_STEPS.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentStep(index)}
                className={`h-2.5 rounded-full transition-all ${
                  index === currentStep
                    ? 'w-6 bg-rose-500'
                    : index < currentStep
                      ? 'w-2.5 bg-rose-200 dark:bg-rose-700'
                      : 'w-2.5 bg-gray-300 dark:bg-gray-600'
                }`}
                aria-label={`Go to portal step ${index + 1}`}
              />
            ))}
          </div>

          <div className="flex items-center justify-between">
            <div>
              {isFirstStep ? (
                <button
                  onClick={() => completeOnboarding(false)}
                  disabled={completing}
                  className="px-4 py-2 text-sm text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  Skip Tour
                </button>
              ) : (
                <button
                  onClick={() => setCurrentStep((stepIndex) => stepIndex - 1)}
                  disabled={completing}
                  className="inline-flex items-center gap-2 rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200 dark:bg-slate-700 dark:text-gray-300 dark:hover:bg-slate-600"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Previous
                </button>
              )}
            </div>

            <span className="text-sm text-gray-500 dark:text-gray-400">
              {currentStep + 1} of {COUPLE_ONBOARDING_STEPS.length}
            </span>

            {isLastStep ? (
              <button
                onClick={() => completeOnboarding(true)}
                disabled={completing}
                className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-rose-500 to-indigo-500 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-rose-500/25 transition-all hover:from-rose-600 hover:to-indigo-600 disabled:opacity-50"
              >
                {completing ? 'Finishing...' : 'Open My Portal'}
                <Sparkles className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={() => setCurrentStep((stepIndex) => stepIndex + 1)}
                disabled={completing}
                className="inline-flex items-center gap-2 rounded-lg bg-rose-500 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-rose-600"
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
