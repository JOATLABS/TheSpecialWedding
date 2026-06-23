'use client';

import clsx from 'clsx';
import ArrowRight from 'lucide-react/dist/esm/icons/arrow-right';
import CheckCircle2 from 'lucide-react/dist/esm/icons/check-circle-2';
import CircleDashed from 'lucide-react/dist/esm/icons/circle-dashed';

import type { Wedding } from '@/types/wedding';

import {
  buildWeddingSetupSummary,
  type WeddingSetupStatus,
  type WeddingSetupTab,
} from '../setupGuide';

interface WeddingSetupGuideProps {
  wedding: Wedding;
  activeTab: WeddingSetupTab;
  canViewCoupleTab: boolean;
  vendorAssignmentCount?: number | null;
  onSelectTab: (tab: WeddingSetupTab) => void;
}

const statusDotClass: Record<WeddingSetupStatus, string> = {
  complete: 'bg-emerald-500',
  attention: 'bg-amber-500',
  optional: 'bg-slate-300 dark:bg-slate-600',
};

const statusTextClass: Record<WeddingSetupStatus, string> = {
  complete: 'text-emerald-700 dark:text-emerald-300',
  attention: 'text-amber-700 dark:text-amber-300',
  optional: 'text-slate-500 dark:text-slate-400',
};

export function WeddingSetupGuide({
  wedding,
  activeTab,
  canViewCoupleTab,
  vendorAssignmentCount,
  onSelectTab,
}: WeddingSetupGuideProps) {
  const summary = buildWeddingSetupSummary(wedding, {
    canViewCoupleTab,
    vendorAssignmentCount,
  });
  const nextStep = summary.nextStep;

  return (
    <section
      aria-labelledby="wedding-setup-guide-heading"
      className="mb-4 rounded-xl border border-gray-200 bg-white px-4 py-4 shadow-sm dark:border-slate-700 dark:bg-slate-800 sm:px-5"
    >
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0 xl:max-w-md">
          <div className="flex flex-wrap items-center gap-3">
            <h2
              id="wedding-setup-guide-heading"
              className="text-base font-bold text-wedding-navy dark:text-gray-100"
            >
              Setup checklist
            </h2>
            <span className="rounded-full bg-wedding-navy px-2.5 py-1 text-xs font-semibold text-white dark:bg-wedding-gold dark:text-slate-950">
              {summary.requiredComplete}/{summary.requiredTotal} essentials
            </span>
          </div>
          <div className="mt-3 flex items-center gap-3">
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
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {nextStep
              ? `Next: ${nextStep.title}`
              : 'Guest-facing essentials are ready.'}
          </p>
        </div>

        <div className="flex flex-col gap-3 xl:min-w-0 xl:flex-1 xl:items-end">
          <div className="flex gap-2 overflow-x-auto pb-1 xl:max-w-full">
            {summary.steps.map((step) => {
              const selected = activeTab === step.tab;
              const complete = step.status === 'complete';

              return (
                <button
                  key={step.id}
                  type="button"
                  onClick={() => onSelectTab(step.tab)}
                  className={clsx(
                    'inline-flex h-10 shrink-0 items-center gap-2 rounded-full border px-3 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-gold/50',
                    selected
                      ? 'border-wedding-gold bg-wedding-gold/10 text-wedding-navy dark:border-wedding-gold/70 dark:text-wedding-gold'
                      : 'border-gray-200 bg-white text-slate-700 hover:border-wedding-gold/60 hover:bg-wedding-gold/5 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-200 dark:hover:border-wedding-gold/60',
                  )}
                  aria-current={selected ? 'step' : undefined}
                  title={`${step.title}: ${step.statusLabel}`}
                >
                  {complete ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                  ) : (
                    <span
                      aria-hidden="true"
                      className={clsx(
                        'h-2.5 w-2.5 rounded-full',
                        statusDotClass[step.status],
                      )}
                    />
                  )}
                  <span>{step.title}</span>
                  <span
                    className={clsx(
                      'hidden text-xs font-medium sm:inline',
                      statusTextClass[step.status],
                    )}
                  >
                    {step.statusLabel}
                  </span>
                </button>
              );
            })}
          </div>

          {nextStep ? (
            <button
              type="button"
              onClick={() => onSelectTab(nextStep.tab)}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-wedding-navy px-4 text-sm font-semibold text-white transition-colors hover:bg-wedding-navy/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-gold/60 sm:w-auto dark:bg-wedding-gold dark:text-slate-950 dark:hover:bg-wedding-gold/90"
            >
              {nextStep.actionLabel}
              <ArrowRight className="h-4 w-4" />
            </button>
          ) : (
            <a
              href={`/${wedding.slug}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-wedding-navy px-4 text-sm font-semibold text-white transition-colors hover:bg-wedding-navy/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-gold/60 sm:w-auto dark:bg-wedding-gold dark:text-slate-950 dark:hover:bg-wedding-gold/90"
            >
              Preview site
              <ArrowRight className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>
    </section>
  );
}
