'use client';

import React, { useMemo } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Clock, XCircle } from 'lucide-react';

export default function TrialBanner() {
  const { userProfile } = useAdmin();
  const router = useRouter();

  const bannerState = useMemo(() => {
    if (!userProfile) return null;

    // Support both data paths: user_data (full profile) and top-level fields
    const ud = userProfile.user_data || {};
    const status = ud.subscription_status || userProfile.subscription_status;
    const trialEnd = ud.trial_end_date || userProfile.trial_end_date;

    if (!status) return null;

    // Show banner for expired/blocked users
    if (status === 'expired' || status === 'cancelled' || status === 'suspended' || status === 'pending_payment') {
      return {
        type: 'expired' as const,
        message: ud._subscription_block_reason || 'Your subscription needs attention.',
        urgent: true,
      };
    }

    // Show countdown banner for trial users within 3 days of expiration
    if (status === 'trial' && trialEnd) {
      const endDate = new Date(trialEnd);
      const now = new Date();
      const daysLeft = Math.ceil((endDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

      if (daysLeft <= 0) {
        return {
          type: 'expired' as const,
          message: 'Your free trial has ended. Upgrade now to keep your data.',
          urgent: true,
        };
      }

      if (daysLeft <= 3) {
        return {
          type: 'warning' as const,
          message: `Your free trial ends in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}. Upgrade now to avoid losing access.`,
          urgent: daysLeft <= 1,
        };
      }
    }

    return null;
  }, [userProfile]);

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
