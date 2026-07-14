'use client';

import { FormEvent, useId, useRef, useState } from 'react';

import { getApiBaseUrl } from '@/utils/env';
import type {
  StorefrontInquiryPayload,
  StorefrontInquiryResult,
} from './storefrontTypes';

type SubmissionState =
  | 'idle'
  | 'submitting'
  | 'success'
  | 'success_with_edits'
  | 'error';
type InquiryPayloadWithoutKey = Omit<StorefrontInquiryPayload, 'idempotency_key'>;

const UNSENT_EDITS_FEEDBACK =
  'Your previous inquiry was sent. Your latest edits were not sent.';

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

function readFormPayload(form: HTMLFormElement): InquiryPayloadWithoutKey {
  const valueOf = (fieldName: string) => {
    const control = form.elements.namedItem(fieldName) as
      | HTMLInputElement
      | HTMLTextAreaElement
      | null;
    return control?.value.trim() ?? '';
  };
  const phone = valueOf('phone');
  const weddingDate = valueOf('wedding_date');
  return {
    name: valueOf('name'),
    email: valueOf('email'),
    phone: phone || undefined,
    wedding_date: weddingDate || undefined,
    message: valueOf('message'),
  };
}

async function readJsonBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function readErrorMessage(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null;
  const errorBody = body as { detail?: unknown; message?: unknown };
  if (typeof errorBody.detail === 'string' && errorBody.detail.trim()) {
    return errorBody.detail;
  }
  if (typeof errorBody.message === 'string' && errorBody.message.trim()) {
    return errorBody.message;
  }
  return null;
}

function rejectsOnlyUnknownIdempotencyKey(body: unknown): boolean {
  if (!body || typeof body !== 'object') return false;
  const detail = (body as { detail?: unknown }).detail;
  if (!Array.isArray(detail) || detail.length !== 1) return false;
  const issue = detail[0] as { type?: unknown; loc?: unknown };
  return (
    issue?.type === 'extra_forbidden' &&
    Array.isArray(issue.loc) &&
    issue.loc[0] === 'body' &&
    issue.loc[issue.loc.length - 1] === 'idempotency_key'
  );
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
  const lastSuccessFeedbackRef = useRef<string | null>(null);

  const handleFormChange = (event: FormEvent<HTMLFormElement>) => {
    if (state === 'success' || state === 'success_with_edits') {
      const sentFingerprint = inquiryAttemptRef.current?.requestFingerprint;
      const currentFingerprint = JSON.stringify(readFormPayload(event.currentTarget));
      const hasUnsentEdits = currentFingerprint !== sentFingerprint;
      setState(hasUnsentEdits ? 'success_with_edits' : 'success');
      setFeedback(
        hasUnsentEdits
          ? UNSENT_EDITS_FEEDBACK
          : lastSuccessFeedbackRef.current,
      );
      return;
    }
    if (state === 'error') {
      setState('idle');
      setFeedback(null);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (state === 'submitting') {
      return;
    }

    const form = event.currentTarget;
    const payloadWithoutKey = readFormPayload(form);
    const { name, email, message } = payloadWithoutKey;

    if (!name || !email || !message) {
      setState('error');
      setFeedback('Enter your name, email, and a message.');
      return;
    }

    setState('submitting');
    setFeedback(null);
    try {
      const requestFingerprint = JSON.stringify(payloadWithoutKey);
      const previousAttempt = inquiryAttemptRef.current;
      const idempotencyKey =
        previousAttempt?.requestFingerprint === requestFingerprint
          ? previousAttempt.idempotencyKey
          : createIdempotencyKey();
      inquiryAttemptRef.current = { idempotencyKey, requestFingerprint };
      const url = `${getApiBaseUrl()}/api/storefront/${encodeURIComponent(identifier)}/inquiries`;
      const requestInit = (body: StorefrontInquiryPayload | InquiryPayloadWithoutKey) => ({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      let response = await fetchImpl(
        url,
        requestInit({
          ...payloadWithoutKey,
          idempotency_key: idempotencyKey,
        } satisfies StorefrontInquiryPayload),
      );
      let responseBody: unknown = null;
      if (!response.ok && response.status === 422) {
        responseBody = await readJsonBody(response);
        if (rejectsOnlyUnknownIdempotencyKey(responseBody)) {
          // Old backends reject the newly added field before endpoint code runs,
          // so this exact validation response is safe to retry once without it.
          response = await fetchImpl(url, requestInit(payloadWithoutKey));
          responseBody = null;
        }
      }

      if (!response.ok) {
        responseBody = responseBody ?? (await readJsonBody(response));
        const serverMessage = readErrorMessage(responseBody);
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
      lastSuccessFeedbackRef.current = result.message;
      const valuesChangedDuringSubmit =
        JSON.stringify(readFormPayload(form)) !== requestFingerprint;
      setState(valuesChangedDuringSubmit ? 'success_with_edits' : 'success');
      setFeedback(
        valuesChangedDuringSubmit
          ? UNSENT_EDITS_FEEDBACK
          : result.message,
      );
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
          className={
            state === 'success' || state === 'success_with_edits'
              ? 'text-emerald-300'
              : 'text-rose-300'
          }
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
            : state === 'success_with_edits'
              ? 'Send updated inquiry'
            : state === 'success'
              ? 'Inquiry sent'
              : 'Send inquiry'}
      </button>
    </form>
  );
}
