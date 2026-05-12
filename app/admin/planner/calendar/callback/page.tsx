'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { completeGoogleCalendarCallback } from '@/services/calendarApi';

export default function GoogleCalendarCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token, isLoading } = useAdmin();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Processing your calendar connection...');

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
        const result = await completeGoogleCalendarCallback(token, code, state);

        if (cancelled) return;

        const connected = Boolean(result.connected);
        if (connected) {
          setStatus('success');
          setMessage('Calendar connected successfully. Redirecting to the planner calendar...');
          window.setTimeout(() => {
            router.push('/admin/planner/calendar');
          }, 1500);
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
  }, [isLoading, router, searchParams, token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="mb-6 flex justify-center">
          {status === 'loading' && (
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
