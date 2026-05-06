'use client';

/**
 * Phase C client component: catalog cards + email-gated download modal.
 *
 * Each card opens a single-field form (email + optional name). On
 * submit we POST to /public/marketing/template-download with any UTM
 * params lifted from the current URL so the lead row carries
 * attribution. The endpoint records the lead and emails the PDF.
 *
 * Lean choices
 * - No new client deps; uses native <dialog>-style fixed overlay,
 *   plain fetch, and small useState for form state.
 * - Modal closes on success after a 2.5 s confirmation so the user
 *   sees the "check your inbox" message before it disappears.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';

interface TemplateCard {
  id: string;
  name: string;
  description: string;
  category: string;
  fieldCount: number;
}

interface TemplatesClientProps {
  templates: TemplateCard[];
}

interface UtmContext {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
}

function readUtmFromUrl(): UtmContext {
  if (typeof window === 'undefined') return {};
  const params = new URLSearchParams(window.location.search);
  const out: UtmContext = {};
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

export default function TemplatesClient({ templates }: TemplatesClientProps) {
  const [active, setActive] = useState<TemplateCard | null>(null);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  // Batch 13 / R9: capture the most recent submission payload so the
  // success state's "Resend" button can re-POST the same lead without
  // making the user re-enter anything. Server is idempotent — repeats
  // increment download_count and re-send the email.
  const [lastSubmission, setLastSubmission] = useState<
    { templateId: string; email: string; name?: string } | null
  >(null);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  const utm = useMemo(readUtmFromUrl, []);

  // Reset transient form state every time the modal opens for a different
  // template — avoids stale errors leaking across attempts.
  useEffect(() => {
    if (active) {
      setError(null);
      setSuccess(null);
      setResent(false);
    }
  }, [active]);

  const dispatchDownload = async (
    templateId: string,
    targetEmail: string,
    targetName?: string,
  ) => {
    const res = await fetch(
      `${getApiBaseUrl()}/public/marketing/template-download`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: templateId,
          email: targetEmail,
          name: targetName || undefined,
          ...utm,
        }),
      },
    );
    if (res.status === 429) {
      throw new Error(
        'Too many requests right now. Please try again in a few minutes.',
      );
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(
        (data && (data.detail || data.message)) ||
          'Something went wrong. Please try again.',
      );
    }
    return res.json();
  };

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!active) return;
    if (!isValidEmail(email)) {
      setError('Please enter a valid email address.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const data = await dispatchDownload(active.id, email, name);
      setSuccess(
        data.message ||
          'Check your inbox — the template is on its way.',
      );
      setLastSubmission({ templateId: active.id, email, name });
      // Don't auto-close: the user should see the Resend link.
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error. Please try again.');
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
      setError(err instanceof Error ? err.message : 'Network error. Please try again.');
    } finally {
      setResending(false);
    }
  };

  return (
    <>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {templates.map((template) => (
          <article
            key={template.id}
            id={template.id}
            className="bg-white rounded-2xl shadow-sm border border-[#eee5d8] p-6 flex flex-col scroll-mt-24"
          >
            <div className="text-xs font-semibold uppercase tracking-wider text-[#9a8f82] mb-2">
              {template.category}
            </div>
            <h3 className="font-serif text-xl text-[#1a1a1a] mb-2 leading-snug">
              {template.name}
            </h3>
            <p className="text-sm text-[#555] mb-4 flex-grow">
              {template.description}
            </p>
            <div className="text-xs text-[#9a8f82] mb-4">
              {template.fieldCount} fields · A4 PDF
            </div>
            <button
              type="button"
              onClick={() => setActive(template)}
              className="self-start rounded-full bg-[#6b5d4f] text-white px-5 py-2 text-sm font-medium hover:bg-[#574a3e] transition-colors"
            >
              Download as PDF
            </button>
          </article>
        ))}
      </div>

      {active && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#1a1a1a]/40 px-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="template-download-title"
          onClick={(event) => {
            if (event.target === event.currentTarget) setActive(null);
          }}
        >
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h2
              id="template-download-title"
              className="font-serif text-2xl text-[#1a1a1a] mb-1"
            >
              {active.name}
            </h2>
            <p className="text-sm text-[#555] mb-5">
              Drop your email and we'll send the PDF straight to your inbox.
            </p>

            {success ? (
              <div className="space-y-3">
                <div className="rounded-lg bg-emerald-50 text-emerald-900 px-4 py-3 text-sm">
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
                    data-testid="marketing-resend"
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
                  onClick={() => setActive(null)}
                  className="text-xs text-[#9a8f82] hover:text-[#6b5d4f] underline"
                >
                  Close
                </button>
              </div>
            ) : (
              <form onSubmit={onSubmit} className="space-y-4">
                <div>
                  <label
                    htmlFor="dl-name"
                    className="block text-xs font-medium text-[#444] mb-1"
                  >
                    Your name (optional)
                  </label>
                  <input
                    id="dl-name"
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
                    htmlFor="dl-email"
                    className="block text-xs font-medium text-[#444] mb-1"
                  >
                    Email
                  </label>
                  <input
                    id="dl-email"
                    type="email"
                    required
                    value={email}
                    maxLength={254}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-lg border border-[#d6cfc1] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#6b5d4f]/40"
                    placeholder="you@yourplannerco.com"
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
                    onClick={() => setActive(null)}
                    className="text-sm text-[#9a8f82] hover:text-[#6b5d4f]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting || !email}
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
      )}
    </>
  );
}
