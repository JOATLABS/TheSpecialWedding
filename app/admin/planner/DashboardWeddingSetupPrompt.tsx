'use client';

import clsx from 'clsx';
import ArrowRight from 'lucide-react/dist/esm/icons/arrow-right';
import CheckCircle2 from 'lucide-react/dist/esm/icons/check-circle-2';
import CircleAlert from 'lucide-react/dist/esm/icons/circle-alert';
import ListChecks from 'lucide-react/dist/esm/icons/list-checks';

import type { Wedding } from '@/types/wedding';
import {
  buildWeddingSetupSummary,
  type WeddingSetupStatus,
  type WeddingSetupTab,
} from '@/admin/weddings/setupGuide';

export interface DashboardWeddingSetupPromptWedding extends Wedding {
  progress_percentage?: number;
  days_until_wedding?: number;
}

interface DashboardWeddingSetupPromptProps {
  weddings: DashboardWeddingSetupPromptWedding[];
  canViewCoupleTab: boolean;
  setupDetailsLoaded: boolean;
  onOpenSetup: (weddingId: string, setupTab: WeddingSetupTab) => void;
}

const chipClass: Record<WeddingSetupStatus, string> = {
  complete:
    'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300',
  attention:
    'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300',
  optional:
    'border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-400',
};

export function DashboardWeddingSetupPrompt({
  weddings,
  canViewCoupleTab,
  setupDetailsLoaded,
  onOpenSetup,
}: DashboardWeddingSetupPromptProps) {
  if (weddings.length === 0) {
    return null;
  }

  if (!setupDetailsLoaded) {
    const wedding = weddings[0];

    return (
      <section
        aria-labelledby="planner-setup-prompt-heading"
        className="rounded-lg border border-wedding-gold/30 bg-white shadow-sm dark:border-wedding-gold/20 dark:bg-slate-800"
      >
        <div className="flex flex-col gap-4 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-wedding-navy text-white dark:bg-wedding-gold dark:text-slate-950">
              <ListChecks className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-wedding-rose dark:text-wedding-gold">
                Wedding setup
              </p>
              <h2
                id="planner-setup-prompt-heading"
                className="mt-1 text-lg font-bold text-wedding-navy dark:text-white"
              >
                Open {wedding.couple_names || 'this wedding'}'s setup
              </h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                Review schedule, RSVP, access, and theme from the configuration tabs.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => onOpenSetup(wedding.id, 'events')}
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-wedding-navy px-4 text-sm font-semibold text-white transition-colors hover:bg-wedding-navy/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-gold/60 lg:w-auto dark:bg-wedding-gold dark:text-slate-950 dark:hover:bg-wedding-gold/90"
          >
            Open setup
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </section>
    );
  }

  const setupRows = weddings.map((wedding) => ({
    wedding,
    summary: buildWeddingSetupSummary(wedding, {
      canViewCoupleTab,
      vendorAssignmentCount: 0,
    }),
  }));
  const target = setupRows.find((row) => row.summary.nextStep) ?? setupRows[0];
  const { wedding, summary } = target;
  const nextStep = summary.nextStep;
  const requiredSteps = summary.steps.filter((step) => step.required);

  return (
    <section
      aria-labelledby="planner-setup-prompt-heading"
      className="rounded-lg border border-wedding-gold/30 bg-white shadow-sm dark:border-wedding-gold/20 dark:bg-slate-800"
    >
      <div className="flex flex-col gap-4 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-wedding-navy text-white dark:bg-wedding-gold dark:text-slate-950">
            {nextStep ? (
              <ListChecks className="h-5 w-5" />
            ) : (
              <CheckCircle2 className="h-5 w-5" />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-wedding-rose dark:text-wedding-gold">
                Wedding setup
              </p>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600 dark:bg-slate-900 dark:text-slate-300">
                {summary.requiredComplete}/{summary.requiredTotal} essentials
              </span>
            </div>
            <h2
              id="planner-setup-prompt-heading"
              className="mt-1 text-lg font-bold text-wedding-navy dark:text-white"
            >
              {nextStep
                ? `Finish ${wedding.couple_names}'s wedding site`
                : `${wedding.couple_names}'s guest essentials are ready`}
            </h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              {nextStep
                ? `${nextStep.title}: ${nextStep.description}`
                : 'Review the setup tabs or preview the public site before launch.'}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 lg:min-w-[360px]">
          <div className="flex items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
              <div
                className="h-full rounded-full bg-wedding-gold transition-all"
                style={{ width: `${summary.progressPercent}%` }}
              />
            </div>
            <span className="w-10 text-right text-xs font-semibold text-slate-500 dark:text-slate-400">
              {summary.progressPercent}%
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {requiredSteps.map((step) => (
              <span
                key={step.id}
                className={clsx(
                  'inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-semibold',
                  chipClass[step.status],
                )}
              >
                {step.status === 'complete' ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : (
                  <CircleAlert className="h-3.5 w-3.5" />
                )}
                {step.title}
              </span>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={() => onOpenSetup(wedding.id, nextStep?.tab ?? 'events')}
          className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-wedding-navy px-4 text-sm font-semibold text-white transition-colors hover:bg-wedding-navy/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-gold/60 lg:w-auto dark:bg-wedding-gold dark:text-slate-950 dark:hover:bg-wedding-gold/90"
        >
          {nextStep ? nextStep.actionLabel : 'Review setup'}
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </section>
  );
}
