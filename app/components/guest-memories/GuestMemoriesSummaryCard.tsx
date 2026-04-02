'use client';

import { Images } from 'lucide-react';

type SummaryAccent = 'indigo' | 'emerald' | 'rose' | 'amber' | 'slate';

interface GuestMemoriesSummaryCardProps {
  icon: typeof Images;
  title: string;
  value: string;
  subtitle: string;
  accent: SummaryAccent;
}

const accentClasses: Record<SummaryAccent, string> = {
  indigo: 'text-indigo-500 bg-indigo-100 dark:bg-indigo-950/40',
  emerald: 'text-emerald-500 bg-emerald-100 dark:bg-emerald-950/40',
  rose: 'text-rose-500 bg-rose-100 dark:bg-rose-950/40',
  amber: 'text-amber-500 bg-amber-100 dark:bg-amber-950/40',
  slate: 'text-slate-500 bg-slate-100 dark:bg-slate-700',
};

export default function GuestMemoriesSummaryCard({
  icon: Icon,
  title,
  value,
  subtitle,
  accent,
}: GuestMemoriesSummaryCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className={`inline-flex h-10 w-10 items-center justify-center rounded-2xl ${accentClasses[accent]}`}>
        <Icon className="h-5 w-5" />
      </div>
      <p className="mt-4 text-sm font-medium text-slate-500 dark:text-slate-400">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-white">{value}</p>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>
    </div>
  );
}
