'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import {
  CalendarSelectionPick,
  completeCalendarCallback,
  ProviderCallbackCalendar,
  ProviderCallbackResponse,
  selectCalendars,
} from '@/services/calendarApi';
import CalendarPickerModal from './CalendarPickerModal';

// Aurinko OAuth codes are single-use. React 18 dev StrictMode double-
// invokes effects, which would POST the same code twice — the second
// attempt returns 410 Gone and clobbers the success state from the
// first call. This module-level cache survives the simulated remount
// and lets us short-circuit duplicate attempts. Stores per-tab only;
// hard reloads start fresh which is fine because the code in the URL
// would already be redeemed (and Aurinko would 410 — caught below).
const inflightOrCompletedCodes = new Map<
  string,
  Promise<Awaited<ReturnType<typeof completeCalendarCallback>>>
>();

type CallbackStatus = 'loading' | 'picker' | 'success' | 'error';

export default function CalendarCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token, isLoading } = useAdmin();
  const [status, setStatus] = useState<CallbackStatus>('loading');
  const [message, setMessage] = useState('Processing your calendar connection...');
  // Picker payload from the OAuth callback step. We pass it down to the
  // CalendarPickerModal which collects the planner's picks and calls
  // back into ``handleSelection`` (Option B commit).
  const [pickerPayload, setPickerPayload] = useState<{
    draftId: string;
    accountEmail: string | null;
    accountName: string | null;
    provider: string | null;
    calendars: ProviderCallbackCalendar[];
    redirectTo: string | null;
  } | null>(null);
  const [pickerSubmitting, setPickerSubmitting] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);

  const completeRedirect = useCallback(
    (target?: string | null) => {
      window.setTimeout(() => {
        router.push(target || '/admin/planner/calendar');
      }, 800);
    },
    [router]
  );

  const handleSelection = useCallback(
    async (picks: CalendarSelectionPick[]) => {
      if (!token || !pickerPayload) return;
      setPickerSubmitting(true);
      setPickerError(null);
      try {
        const result: ProviderCallbackResponse = await selectCalendars(
          token,
          pickerPayload.draftId,
          picks
        );
        if (!result.connected) {
          throw new Error(result.message || 'Failed to save calendar selection.');
        }
        setStatus('success');
        const created = result.connections_created ?? 0;
        setMessage(
          created === 0
            ? 'Connection skipped. You can pick calendars later from settings.'
            : `Connected ${created} calendar${created === 1 ? '' : 's'}. Redirecting…`
        );
        completeRedirect(result.redirect_to ?? pickerPayload.redirectTo);
      } catch (err) {
        setPickerError(
          err instanceof Error
            ? err.message
            : 'Could not save your calendar selection. Please retry.'
        );
      } finally {
        setPickerSubmitting(false);
      }
    },
    [completeRedirect, pickerPayload, token]
  );

  const handleSkip = useCallback(() => {
    // "Skip for now" is the empty-picks path. We still POST so the
    // backend deletes the draft cleanly; the TTL fallback is only for
    // crash paths.
    void handleSelection([]);
  }, [handleSelection]);

  useEffect(() => {
    if (isLoading) return;

    let cancelled = false;

    const run = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const error = searchParams.get('error');

      if (error) {
        setStatus('error');
        setMessage(
          error === 'access_denied'
            ? 'You cancelled the calendar authorization.'
            : `Calendar authorization failed: ${error}`
        );
        return;
      }

      if (!code || !state) {
        setStatus('error');
        setMessage('Missing authorization code or state parameter.');
        return;
      }

      if (!token) {
        setStatus('error');
        setMessage('Your admin session is missing. Sign in again and restart the calendar connection.');
        return;
      }

      try {
        // Dedupe by code — StrictMode in dev mounts this effect twice.
        // Without this, both invocations POST to /provider/callback with
        // the same single-use Aurinko code; the second hit returns 410
        // and overwrites the first's success in the UI. Sharing the
        // in-flight Promise means both effect runs observe the SAME
        // resolution, so the second one cannot 410-clobber the first.
        let exchange = inflightOrCompletedCodes.get(code);
        if (!exchange) {
          exchange = completeCalendarCallback(token, code, state);
          inflightOrCompletedCodes.set(code, exchange);
        }
        const result = await exchange;

        if (cancelled) return;

        // Option B: backend returns ``needs_selection`` instead of
        // creating rows immediately. Render the picker modal.
        if (result.needs_selection && result.draft_id) {
          setPickerPayload({
            draftId: result.draft_id,
            accountEmail: result.account_email ?? null,
            accountName: result.account_name ?? null,
            provider: result.provider ?? null,
            calendars: result.calendars ?? [],
            redirectTo: result.redirect_to ?? null,
          });
          setStatus('picker');
          setMessage(result.message);
          return;
        }

        // Legacy / failure paths.
        if (result.connected) {
          setStatus('success');
          setMessage('Calendar connected successfully. Redirecting…');
          completeRedirect(result.redirect_to ?? null);
          return;
        }

        setStatus('error');
        setMessage(String(result.message || 'Failed to connect your calendar.'));
      } catch (err) {
        if (cancelled) return;
        setStatus('error');
        setMessage(err instanceof Error ? err.message : 'An unexpected error occurred.');
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [completeRedirect, isLoading, router, searchParams, token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      {/* Picker modal overlays the page when the backend returns the
          deferred-creation payload. The card below stays in the
          background as visual context. */}
      {status === 'picker' && pickerPayload && (
        <CalendarPickerModal
          draftId={pickerPayload.draftId}
          accountEmail={pickerPayload.accountEmail}
          accountName={pickerPayload.accountName}
          provider={pickerPayload.provider}
          calendars={pickerPayload.calendars}
          submitting={pickerSubmitting}
          errorMessage={pickerError}
          onSubmit={handleSelection}
          onSkip={handleSkip}
        />
      )}

      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="mb-6 flex justify-center">
          {(status === 'loading' || status === 'picker') && (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900 dark:border-slate-600 dark:border-t-slate-100" />
            </div>
          )}
          {status === 'success' && (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200">
              <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          )}
          {status === 'error' && (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-200">
              <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
          )}
        </div>

        <h1 className="text-center text-xl font-semibold text-slate-900 dark:text-slate-100">
          {status === 'loading' && 'Connecting your calendar'}
          {status === 'picker' && 'Pick your calendars to continue'}
          {status === 'success' && 'Calendar Connected'}
          {status === 'error' && 'Connection Failed'}
        </h1>

        <p className="mt-3 text-center text-sm leading-6 text-slate-500 dark:text-slate-400">{message}</p>

        {status === 'success' && (
          <p className="mt-4 text-center text-xs text-slate-400 dark:text-slate-500">Redirecting to the calendar workspace...</p>
        )}

        {status === 'error' && (
          <div className="mt-6 space-y-3">
            <button
              onClick={() => router.push('/admin/planner/calendar')}
              className="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200"
            >
              Return to planner calendar
            </button>
            <button
              onClick={() => window.location.reload()}
              className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Try again
            </button>
          </div>
        )}

        <p className="mt-6 text-center text-xs text-slate-500 dark:text-slate-400">
          Need help? Visit{' '}
          <a href="/support" className="font-medium text-slate-900 underline dark:text-slate-100">
            public support
          </a>
          .
        </p>
      </div>
    </div>
  );
}
