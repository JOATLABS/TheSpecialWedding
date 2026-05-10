'use client';

/**
 * Shared email-gated template-download modal.
 *
 * Used by:
 * - The homepage "starter pack" lead-magnet band (templateId="starter_pack").
 * - The Resources templates-tab per-template cards.
 *
 * Submits to POST {API}/public/marketing/template-download. The backend
 * is idempotent on (email, template_id) so the success-state's "Resend"
 * button can re-POST the same lead without making the user re-enter
 * anything. Handles 429 / 4xx / network errors gracefully.
 *
 * The component owns no business logic — it's a thin form + a couple of
 * fetches. UTM context is either supplied by the caller (homepage band
 * forwards `utm_source: 'homepage_band'` etc.) or read once from
 * window.location.search at mount time.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';

export interface TemplateDownloadModalUtm {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
}

export interface TemplateDownloadModalProps {
  open: boolean;
  onClose: () => void;
  /** Value POSTed to the server (real template id or "starter_pack"). */
  templateId: string;
  /** Modal title — short, action-oriented. */
  headline: string;
  /** Single-paragraph description below the title. */
  subhead: string;
  /** Optional override for the success message; defaults to the API's. */
  successMessage?: string;
  /**
   * Optional UTM context to forward. If omitted the component falls
   * back to reading utm_source / utm_medium / utm_campaign from
   * window.location.search.
   */
  utm?: TemplateDownloadModalUtm;
  /** Surface-aware styling. Defaults to 'light'. */
  surface?: 'light' | 'dark';
  /** Optional data-testid prefix to make Playwright assertions unambiguous. */
  testIdPrefix?: string;
}

function readUtmFromUrl(): TemplateDownloadModalUtm {
  if (typeof window === 'undefined') return {};
  const params = new URLSearchParams(window.location.search);
  const out: TemplateDownloadModalUtm = {};
  for (const key of ['utm_source', 'utm_medium', 'utm_campaign'] as const) {
    const value = params.get(key);
    if (value) out[key] = value.slice(0, 120);
  }
  return out;
}

function isValidEmail(value: string): boolean {
  // Lightweight client-side gate; the server uses Pydantic EmailStr
  // (https://pydantic.dev/docs/validation/latest/concepts/validators/)
  // for the authoritative check.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

interface SubmissionPayload {
  templateId: string;
  email: string;
  name?: string;
}

export default function TemplateDownloadModal({
  open,
  onClose,
  templateId,
  headline,
  subhead,
  successMessage,
  utm,
  surface = 'light',
  testIdPrefix = 'template-download',
}: TemplateDownloadModalProps) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  // Capture the most recent submission so the "Resend" button can re-POST
  // without re-prompting the user. Server is idempotent on (email,
  // template_id) — repeats increment download_count and re-send the email.
  const [lastSubmission, setLastSubmission] = useState<SubmissionPayload | null>(null);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  const fallbackUtm = useMemo(readUtmFromUrl, []);
  const effectiveUtm = utm ?? fallbackUtm;

  // Reset transient form state every time the modal opens — avoids
  // stale errors / success leaking across attempts.
  useEffect(() => {
    if (open) {
      setError(null);
      setSuccess(null);
      setResent(false);
    }
  }, [open]);

  const dispatchDownload = async (
    targetTemplateId: string,
    targetEmail: string,
    targetName?: string,
  ) => {
    const res = await fetch(
      `${getApiBaseUrl()}/public/marketing/template-download`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: targetTemplateId,
          email: targetEmail,
          name: targetName || undefined,
          ...effectiveUtm,
        }),
      },
    );
    if (res.status === 429) {
      throw new Error(
        'Too many requests right now. Please try again in a few minutes.',
      );
    }
    if (!res.ok) {
      // Some error responses are HTML (CDN/edge/error pages) and not
      // JSON. Log the parse failure so the silent fallback message
      // doesn't hide real backend regressions.
      const data = await res.json().catch((parseErr: unknown) => {
        if (typeof console !== 'undefined') {
          console.warn(
            '[TemplateDownloadModal] non-JSON error response from /public/marketing/template-download',
            { status: res.status, parseErr },
          );
        }
        return {} as Record<string, unknown>;
      });
      throw new Error(
        (data && ((data as { detail?: string }).detail ||
          (data as { message?: string }).message)) ||
          'Something went wrong. Please try again.',
      );
    }
    return res.json();
  };

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!isValidEmail(email)) {
      setError('Please enter a valid email address.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const data = await dispatchDownload(templateId, email, name);
      setSuccess(
        successMessage ||
          data.message ||
          'Check your inbox — the template is on its way.',
      );
      setLastSubmission({ templateId, email, name });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Network error. Please try again.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  const onResend = async () => {
    if (!lastSubmission || resending) return;
    setResending(true);
    setError(null);
    try {
      await dispatchDownload(
        lastSubmission.templateId,
        lastSubmission.email,
        lastSubmission.name,
      );
      setResent(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Network error. Please try again.',
      );
    } finally {
      setResending(false);
    }
  };

  if (!open) return null;

  // Surface-aware tokens. The modal panel itself is always light for
  // contrast on the form fields; the *backdrop* changes by surface so
  // the dialog feels native to its host page.
  const backdrop =
    surface === 'dark'
      ? 'bg-slate-950/70 backdrop-blur-sm'
      : 'bg-[#1a1a1a]/40';

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center px-4 ${backdrop}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="template-download-title"
      data-testid={`${testIdPrefix}-modal`}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
        <h2
          id="template-download-title"
          className="font-serif text-2xl text-[#1a1a1a] mb-1"
        >
          {headline}
        </h2>
        <p className="text-sm text-[#555] mb-5">{subhead}</p>

        {success ? (
          <div className="space-y-3">
            <div
              className="rounded-lg bg-emerald-50 text-emerald-900 px-4 py-3 text-sm"
              data-testid={`${testIdPrefix}-success`}
            >
              {success}
            </div>
            <div className="flex items-center justify-between text-xs text-[#555]">
              <span>
                {resent
                  ? 'Sent again — please check your spam folder too.'
                  : "Didn't receive it?"}
              </span>
              <button
                type="button"
                onClick={onResend}
                disabled={resending || !lastSubmission}
                data-testid={`${testIdPrefix}-resend`}
                className="rounded-full border border-[#d6cfc1] bg-white px-3 py-1 text-xs font-medium text-[#1a1a1a] hover:bg-[#f5efe5] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {resending ? 'Resending…' : resent ? 'Resend again' : 'Resend'}
              </button>
            </div>
            {error && (
              <p className="text-sm text-red-600" role="alert">
                {error}
              </p>
            )}
            <button
              type="button"
              onClick={onClose}
              className="text-xs text-[#9a8f82] hover:text-[#6b5d4f] underline"
            >
              Close
            </button>
          </div>
        ) : (
          <form
            onSubmit={onSubmit}
            className="space-y-4"
            data-testid={`${testIdPrefix}-form`}
          >
            <div>
              <label
                htmlFor={`${testIdPrefix}-name-input`}
                className="block text-xs font-medium text-[#444] mb-1"
              >
                Your name (optional)
              </label>
              <input
                id={`${testIdPrefix}-name-input`}
                type="text"
                value={name}
                maxLength={120}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border border-[#d6cfc1] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#6b5d4f]/40"
                placeholder="Jamie Planner"
              />
            </div>
            <div>
              <label
                htmlFor={`${testIdPrefix}-email-input`}
                className="block text-xs font-medium text-[#444] mb-1"
              >
                Email
              </label>
              <input
                id={`${testIdPrefix}-email-input`}
                type="email"
                required
                value={email}
                maxLength={254}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-[#d6cfc1] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#6b5d4f]/40"
                placeholder="you@yourplannerco.com"
                data-testid={`${testIdPrefix}-email`}
              />
            </div>

            {error && (
              <p className="text-sm text-red-600" role="alert">
                {error}
              </p>
            )}

            <div className="flex items-center justify-between pt-1">
              <button
                type="button"
                onClick={onClose}
                className="text-sm text-[#9a8f82] hover:text-[#6b5d4f]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !email}
                data-testid={`${testIdPrefix}-submit`}
                className="rounded-full bg-[#6b5d4f] text-white px-5 py-2 text-sm font-medium hover:bg-[#574a3e] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {submitting ? 'Sending…' : 'Email me the PDF'}
              </button>
            </div>
            <p className="text-xs text-[#9a8f82]">
              By downloading you agree to receive this template plus an
              occasional product update. Unsubscribe in one click.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
