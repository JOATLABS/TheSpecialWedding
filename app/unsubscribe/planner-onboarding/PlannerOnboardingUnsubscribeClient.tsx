'use client';

import { useEffect, useState, useTransition } from 'react';
import Link from 'next/link';
import { getApiBaseUrl } from '@/utils/env';

type UnsubscribeStatus = {
  email: string;
  first_name?: string | null;
  already_unsubscribed: boolean;
  unsubscribed_at?: string | null;
};

type Props = {
  token: string;
};

export default function PlannerOnboardingUnsubscribeClient({ token }: Props) {
  const [status, setStatus] = useState<UnsubscribeStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      if (!token) {
        setError('This unsubscribe link is missing its token.');
        setLoading(false);
        return;
      }

      try {
        const apiBaseUrl = getApiBaseUrl();
        const response = await fetch(
          `${apiBaseUrl}/planner-onboarding/unsubscribe/status?token=${encodeURIComponent(token)}`,
          {
            cache: 'no-store',
          }
        );

        if (!response.ok) {
          throw new Error(response.status === 404 ? 'This unsubscribe link is invalid or expired.' : 'Unable to load this unsubscribe request right now.');
        }

        const payload = (await response.json()) as UnsubscribeStatus;
        if (!cancelled) {
          setStatus(payload);
        }
      } catch (fetchError) {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : 'Unable to load this unsubscribe request right now.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadStatus();

    return () => {
      cancelled = true;
    };
  }, [token]);

  function handleConfirm() {
    startTransition(async () => {
      try {
        const apiBaseUrl = getApiBaseUrl();
        const response = await fetch(`${apiBaseUrl}/planner-onboarding/unsubscribe`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ token }),
        });

        if (!response.ok) {
          throw new Error(response.status === 404 ? 'This unsubscribe link is invalid or expired.' : 'Unable to update your email preference right now.');
        }

        const payload = (await response.json()) as UnsubscribeStatus;
        setStatus(payload);
        setError(null);
      } catch (submitError) {
        setError(submitError instanceof Error ? submitError.message : 'Unable to update your email preference right now.');
      }
    });
  }

  return (
    <section className="mx-auto max-w-3xl px-6 pb-16 pt-28 sm:px-10">
      <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-8 shadow-2xl shadow-black/20">
        <p className="text-xs uppercase tracking-[0.35em] text-wedding-rose">Planner onboarding emails</p>
        <h1 className="mt-4 text-3xl font-semibold text-white sm:text-4xl">Manage this onboarding sequence</h1>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-slate-300">
          This page only affects the planner onboarding sequence. Account notices, billing messages, and security emails still go through their normal paths.
        </p>

        {loading ? (
          <div className="mt-8 rounded-2xl border border-white/8 bg-slate-950/50 p-6 text-sm text-slate-300">
            Checking this unsubscribe link…
          </div>
        ) : error ? (
          <div className="mt-8 rounded-2xl border border-red-400/20 bg-red-500/10 p-6 text-sm text-red-100">
            {error}
          </div>
        ) : status ? (
          <div className="mt-8 space-y-6">
            <div className="rounded-2xl border border-white/8 bg-slate-950/50 p-6">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Email</p>
              <p className="mt-2 text-lg font-semibold text-white">{status.email}</p>
              {status.first_name ? (
                <p className="mt-2 text-sm text-slate-400">
                  Hi {status.first_name}, this link controls the onboarding sequence for your planner account.
                </p>
              ) : null}
            </div>

            {status.already_unsubscribed ? (
              <div className="rounded-2xl border border-emerald-400/20 bg-emerald-500/10 p-6">
                <p className="text-sm font-semibold text-emerald-100">You have already been unsubscribed from the onboarding sequence.</p>
                <p className="mt-2 text-sm text-emerald-50/90">
                  No further onboarding emails will be sent to this address through this sequence.
                </p>
              </div>
            ) : (
              <div className="rounded-2xl border border-white/8 bg-white/[0.02] p-6">
                <p className="text-sm leading-relaxed text-slate-300">
                  Confirm below if you want to stop the onboarding emails that introduce the planner workflow over the first two weeks.
                </p>
                <button
                  type="button"
                  onClick={handleConfirm}
                  disabled={isPending}
                  className="mt-5 inline-flex items-center justify-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isPending ? 'Updating…' : 'Unsubscribe from onboarding emails'}
                </button>
              </div>
            )}
          </div>
        ) : null}

        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white transition hover:border-white/30 hover:bg-white/5"
          >
            Return home
          </Link>
          <Link
            href="/resources/blog"
            className="inline-flex items-center justify-center rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white transition hover:border-white/30 hover:bg-white/5"
          >
            Open resources
          </Link>
        </div>
      </div>
    </section>
  );
}
