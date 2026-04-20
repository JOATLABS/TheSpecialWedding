'use client';

import React from 'react';
import { Lock, Mail, LogOut } from 'lucide-react';
import { useAdmin } from '@/contexts/AdminContext';

/**
 * TeamMemberSubscriptionBlocked
 *
 * Rendered by AdminRouteGuard when a team member's parent planner has a blocked
 * subscription (past_due / unpaid / cancelled / suspended / expired / pending_*).
 *
 * The backend tags the team member's profile with:
 *   - _subscription_blocked: true
 *   - _subscription_block_reason: "Your team's subscription requires attention
 *     (status: <...>). Please contact your planner at <email> to restore access."
 *
 * Why this component exists:
 *   Previously the team member's dashboard rendered normally, every gated
 *   feature endpoint returned 402, and failed-fetch errors leaked into the
 *   console + inline UI ("Failed to fetch dashboard data"). That is not OK in
 *   production.
 *
 *   This shell short-circuits rendering of the full dashboard and its network
 *   calls — it performs zero data fetches of its own.
 */
export default function TeamMemberSubscriptionBlocked() {
  const { userProfile, logout } = useAdmin();

  const ud = userProfile?.user_data || {};
  const reason =
    ud._subscription_block_reason ||
    (userProfile as any)?._subscription_block_reason ||
    "Your team's subscription requires attention. Please contact your planner to restore access.";

  const ownerEmail = userProfile?.team_owner_email || ud.team_owner_email;

  return (
    <div className="min-h-screen flex items-center justify-center bg-light-bg dark:bg-dark-bg px-4 py-12">
      <div className="w-full max-w-lg">
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-xl overflow-hidden">
          <div className="bg-slate-900 dark:bg-slate-950 text-amber-300 px-6 py-4 flex items-center gap-3">
            <Lock size={20} className="shrink-0" />
            <h1 className="text-base font-semibold tracking-wide">
              Team access paused
            </h1>
          </div>

          <div className="px-6 py-6 space-y-5">
            <p className="text-slate-700 dark:text-slate-200 leading-relaxed">
              {reason}
            </p>

            {ownerEmail ? (
              <div className="rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-700 px-4 py-3 flex items-start gap-3">
                <Mail
                  size={18}
                  className="text-slate-500 dark:text-slate-400 mt-0.5 shrink-0"
                />
                <div className="text-sm">
                  <div className="text-slate-500 dark:text-slate-400">
                    Contact your planner
                  </div>
                  <a
                    href={`mailto:${ownerEmail}`}
                    className="text-slate-900 dark:text-slate-100 font-medium break-all hover:underline"
                  >
                    {ownerEmail}
                  </a>
                </div>
              </div>
            ) : null}

            <div className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Once your planner restores the subscription, sign in again and
              your access to the workspace will resume automatically. No data
              has been lost.
            </div>

            <div className="pt-2 flex items-center justify-end">
              <button
                type="button"
                onClick={() =>
                  logout({
                    message: 'Signed out.',
                    redirectTo: '/admin/login',
                    showToast: true,
                  })
                }
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white transition-colors"
              >
                <LogOut size={16} />
                Sign out
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
