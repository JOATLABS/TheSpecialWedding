'use client';

import { FormEvent, useId, useRef, useState } from 'react';

import { getApiBaseUrl } from '@/utils/env';
import type {
  StorefrontInquiryPayload,
  StorefrontInquiryResult,
} from './storefrontTypes';

type SubmissionState = 'idle' | 'submitting' | 'success' | 'error';

interface InquiryAttempt {
  idempotencyKey: string;
  requestFingerprint: string;
}

interface StorefrontInquiryFormProps {
  identifier: string;
  themeColor?: string;
  fetchImpl?: typeof fetch;
  createIdempotencyKey?: () => string;
}

function createInquiryIdempotencyKey(): string {
  const cryptoApi = globalThis.crypto;
  if (!cryptoApi) {
    throw new Error('Your inquiry could not be prepared securely. Refresh and try again.');
  }
  if (typeof cryptoApi.randomUUID === 'function') {
    return cryptoApi.randomUUID();
  }

  const randomBytes = new Uint8Array(16);
  cryptoApi.getRandomValues(randomBytes);
  return Array.from(randomBytes, (value) => value.toString(16).padStart(2, '0')).join('');
}

async function readErrorMessage(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown; message?: unknown };
    if (typeof body.detail === 'string' && body.detail.trim()) {
      return body.detail;
    }
    if (typeof body.message === 'string' && body.message.trim()) {
      return body.message;
    }
  } catch {
    // The status-specific fallback below remains safe for non-JSON failures.
  }
  return null;
}

export default function StorefrontInquiryForm({
  identifier,
  themeColor = '#0f172a',
  fetchImpl = fetch,
  createIdempotencyKey = createInquiryIdempotencyKey,
}: StorefrontInquiryFormProps) {
  const fieldPrefix = useId();
  const [state, setState] = useState<SubmissionState>('idle');
  const [feedback, setFeedback] = useState<string | null>(null);
  const inquiryAttemptRef = useRef<InquiryAttempt | null>(null);

  const handleFormChange = () => {
    if (state !== 'error') {
      return;
    }
    inquiryAttemptRef.current = null;
    setState('idle');
    setFeedback(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (state === 'submitting') {
      return;
    }

    const form = event.currentTarget;
    const valueOf = (fieldName: string) => {
      const control = form.elements.namedItem(fieldName) as
        | HTMLInputElement
        | HTMLTextAreaElement
        | null;
      return control?.value.trim() ?? '';
    };
    const name = valueOf('name');
    const email = valueOf('email');
    const message = valueOf('message');
    const phone = valueOf('phone');
    const weddingDate = valueOf('wedding_date');

    if (!name || !email || !message) {
      setState('error');
      setFeedback('Enter your name, email, and a message.');
      return;
    }

    setState('submitting');
    setFeedback(null);
    try {
      const payloadWithoutKey = {
        name,
        email,
        phone: phone || undefined,
        wedding_date: weddingDate || undefined,
        message,
      } satisfies Omit<StorefrontInquiryPayload, 'idempotency_key'>;
      const requestFingerprint = JSON.stringify(payloadWithoutKey);
      const previousAttempt = inquiryAttemptRef.current;
      const idempotencyKey =
        previousAttempt?.requestFingerprint === requestFingerprint
          ? previousAttempt.idempotencyKey
          : createIdempotencyKey();
      inquiryAttemptRef.current = { idempotencyKey, requestFingerprint };
      const response = await fetchImpl(
        `${getApiBaseUrl()}/api/storefront/${encodeURIComponent(identifier)}/inquiries`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...payloadWithoutKey,
            idempotency_key: idempotencyKey,
          } satisfies StorefrontInquiryPayload),
        },
      );

      if (!response.ok) {
        const serverMessage = await readErrorMessage(response);
        const messageForUser =
          response.status === 429
            ? 'Too many inquiries were sent recently. Please wait a moment and try again.'
            : serverMessage || 'Your inquiry could not be sent. Please try again.';
        throw new Error(messageForUser);
      }

      const result = (await response.json()) as StorefrontInquiryResult;
      if (!result.success || typeof result.message !== 'string') {
        throw new Error('Your inquiry could not be confirmed. Please try again.');
      }
      setState('success');
      setFeedback(result.message);
    } catch (error) {
      setState('error');
      setFeedback(
        error instanceof Error
          ? error.message
          : 'Your inquiry could not be sent. Please try again.',
      );
    }
  };

  const id = (name: string) => `${fieldPrefix}-${name}`;

  return (
    <form
      className="space-y-5"
      onChange={handleFormChange}
      onInput={handleFormChange}
      onSubmit={handleSubmit}
      noValidate
    >
      <div>
        <label className="mb-2 block text-sm font-medium" htmlFor={id('name')}>
          Name
        </label>
        <input
          className="w-full rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3 text-white outline-none focus:ring-2"
          id={id('name')}
          name="name"
          maxLength={120}
          required
        />
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium" htmlFor={id('email')}>
          Email
        </label>
        <input
          className="w-full rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3 text-white outline-none focus:ring-2"
          id={id('email')}
          name="email"
          type="email"
          required
        />
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label className="mb-2 block text-sm font-medium" htmlFor={id('phone')}>
            Phone (optional)
          </label>
          <input
            className="w-full rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3 text-white outline-none focus:ring-2"
            id={id('phone')}
            name="phone"
            type="tel"
            maxLength={40}
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium" htmlFor={id('date')}>
            Wedding date (optional)
          </label>
          <input
            className="w-full rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3 text-white outline-none focus:ring-2"
            id={id('date')}
            name="wedding_date"
            type="date"
          />
        </div>
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium" htmlFor={id('message')}>
          How can we help?
        </label>
        <textarea
          className="min-h-32 w-full rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3 text-white outline-none focus:ring-2"
          id={id('message')}
          name="message"
          maxLength={4000}
          required
        />
      </div>

      {feedback ? (
        <p
          aria-live="polite"
          className={state === 'success' ? 'text-emerald-300' : 'text-rose-300'}
          role={state === 'error' ? 'alert' : 'status'}
        >
          {feedback}
        </p>
      ) : null}

      <button
        className="w-full rounded-xl px-5 py-3 font-semibold text-white disabled:cursor-wait disabled:opacity-70"
        disabled={state === 'submitting' || state === 'success'}
        style={{ backgroundColor: themeColor }}
        type="submit"
      >
        {state === 'submitting'
          ? 'Sending…'
          : state === 'error'
            ? 'Try again'
            : state === 'success'
              ? 'Inquiry sent'
              : 'Send inquiry'}
      </button>
    </form>
  );
}
