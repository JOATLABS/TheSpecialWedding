'use client';

// Compact single-row metrics bar that replaces the 4-card grid at the
// top of /admin/planner/calendar. Mockup ref: View 1 "metric strip".
//
// Design intent:
//   * Single ~36 px row, not a ~140 px 4-card grid → 4× less viewport
//     real estate for the same information density.
//   * Gold-dot accent for non-zero values (brand wedding-gold token),
//     muted slate dot for zeros. Lets the planner scan for live
//     activity at a glance.
//   * No interactivity — pure read-only summary. Click-through to
//     deeper breakdowns happens elsewhere (right rail tabs, filters).

import React from 'react';

export interface MetricStripValues {
  internalMeetings: number;
  sharedCalendars: number;
  busyFreeImports: number;
  visibleItems: number;
}

interface MetricStripProps {
  values: MetricStripValues;
  /** Right-aligned context label, e.g. the visible month/year. */
  context?: string;
}

interface MetricPillProps {
  label: string;
  value: number;
}

function MetricPill({ label, value }: MetricPillProps) {
  const hot = value > 0;
  return (
    <span className="inline-flex items-center gap-2 text-[13px]">
      <span
        className={
          hot
            ? 'inline-block h-1.5 w-1.5 rounded-full bg-wedding-gold shadow-[0_0_0_3px_rgba(233,196,106,0.18)]'
            : 'inline-block h-1.5 w-1.5 rounded-full bg-slate-400 dark:bg-slate-600'
        }
      />
      <span
        className={
          hot
            ? 'font-semibold text-slate-900 dark:text-slate-100'
            : 'text-slate-500 dark:text-slate-400'
        }
      >
        {value}
      </span>
      <span className="text-slate-500 dark:text-slate-400">{label}</span>
    </span>
  );
}

export default function MetricStrip({ values, context }: MetricStripProps) {
  return (
    <div
      role="region"
      aria-label="Calendar summary metrics"
      className="rounded-xl border border-slate-200 bg-white/80 px-5 py-2.5 backdrop-blur-sm dark:border-slate-700 dark:bg-slate-800/60"
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <MetricPill label="internal meetings" value={values.internalMeetings} />
        <span className="text-slate-300 dark:text-slate-600">·</span>
        <MetricPill label="shared" value={values.sharedCalendars} />
        <span className="text-slate-300 dark:text-slate-600">·</span>
        <MetricPill label="imports" value={values.busyFreeImports} />
        <span className="text-slate-300 dark:text-slate-600">·</span>
        <MetricPill label="visible items" value={values.visibleItems} />
        {context && (
          <span className="ml-auto font-elegant italic text-xs text-slate-500 dark:text-slate-400">
            {context}
          </span>
        )}
      </div>
    </div>
  );
}
