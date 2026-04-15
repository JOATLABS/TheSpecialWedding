'use client';

import React from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Clock, XCircle } from 'lucide-react';
import { getTrialBannerState } from './trialBannerState';

export default function TrialBanner() {
  const { userProfile } = useAdmin();
  const router = useRouter();

  const bannerState = getTrialBannerState(userProfile);

  if (!bannerState) return null;

  const isExpired = bannerState.type === 'expired';
  const Icon = isExpired ? XCircle : bannerState.urgent ? AlertTriangle : Clock;

  return (
    <div
      className={`w-full px-4 py-2.5 flex items-center justify-between gap-3 text-sm font-medium ${
        isExpired
          ? 'bg-slate-800 dark:bg-slate-700 text-amber-300'
          : bannerState.urgent
          ? 'bg-amber-600/90 text-white'
          : 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200'
      }`}
      role="alert"
    >
      <div className="flex items-center gap-2">
        <Icon size={16} className="shrink-0" />
        <span>{bannerState.message}</span>
      </div>
      <button
        onClick={() => router.push('/admin/planner/billing')}
        className={`shrink-0 px-4 py-1 rounded-full text-sm font-semibold transition-colors ${
          isExpired || bannerState.urgent
            ? 'bg-white text-slate-900 hover:bg-slate-100'
            : 'bg-amber-600 text-white hover:bg-amber-700'
        }`}
      >
        Upgrade Now
      </button>
    </div>
  );
}
