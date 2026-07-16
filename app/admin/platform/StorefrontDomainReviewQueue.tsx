'use client';

import {
  AlertTriangle,
  CheckCircle2,
  CloudCog,
  Loader2,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { getApiBaseUrl } from '@/utils/env';

type ReviewAction =
  | 'approve_o2o_cutover'
  | 'adopt_ambiguous_create'
  | 'deny_hostname_conflict'
  | 'cancel_hostname_conflict';

interface ReviewSummary {
  review_id: string;
  review_type:
    | 'o2o_cutover'
    | 'ambiguous_create'
    | 'hostname_conflict'
    | 'investigation';
  hostname: string;
  application_status: string;
  action: string;
  revision: number;
  updated_at: string | null;
  support_id: string | null;
  allowed_actions: ReviewAction[];
}

interface ReviewDetail extends ReviewSummary {
  planner_id: string;
  attempt_id: string;
  intent: string | null;
  ownership_status: string | null;
  routing_dns_status: string | null;
  provider_hostname_status: string | null;
  ssl_status: string | null;
  https_status: string | null;
  authoritative_dns_provider: string | null;
  authoritative_nameservers: string[];
  provider_candidate_ids: string[];
  provider_lookup_status: 'not_required' | 'available' | 'unavailable' | 'invalid';
  provider_lookup_message: string | null;
  provider_lookup_support_id: string | null;
  error_code: string | null;
  error_message: string | null;
  customer_action: string | null;
}

interface ReviewListResponse {
  items: ReviewSummary[];
  has_more: boolean;
}

interface StorefrontDomainReviewQueueProps {
  token: string;
  fetchImpl?: typeof fetch;
}

const actionButtonClass =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-primary-800 px-4 text-sm font-semibold text-white transition hover:bg-primary-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600 dark:disabled:bg-slate-700 dark:disabled:text-slate-300';
const secondaryButtonClass =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:cursor-not-allowed disabled:bg-slate-200 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800 dark:disabled:bg-slate-800';

function humanize(value: string): string {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function safeErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') return fallback;
  const candidate = (body as { error?: unknown }).error;
  if (!candidate || typeof candidate !== 'object') return fallback;
  const message = (candidate as { message?: unknown }).message;
  return typeof message === 'string' && message.trim() && message.length <= 500
    ? message.trim()
    : fallback;
}

export default function StorefrontDomainReviewQueue({
  token,
  fetchImpl = fetch,
}: StorefrontDomainReviewQueueProps) {
  const [queue, setQueue] = useState<ReviewSummary[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [selected, setSelected] = useState<ReviewDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [candidateId, setCandidateId] = useState('');
  const [announcement, setAnnouncement] = useState('');
  const detailRequestSequence = useRef(0);

  const request = useCallback(
    async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const response = await fetchImpl(`${getApiBaseUrl()}${path}`, {
        ...init,
        credentials: 'include',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          ...init?.headers,
        },
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(
          safeErrorMessage(body, 'The storefront-domain review request failed.'),
        );
      }
      return body as T;
    },
    [fetchImpl, token],
  );

  const loadQueue = useCallback(async () => {
    detailRequestSequence.current += 1;
    setLoading(true);
    setError(null);
    try {
      const response = await request<ReviewListResponse>(
        '/admin/storefront/custom-domain/operator/reviews?limit=100',
      );
      setQueue(response.items);
      setHasMore(response.has_more);
      setSelected((current) =>
        current && response.items.some((item) => item.review_id === current.review_id)
          ? current
          : null,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The review queue could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    if (token) void loadQueue();
  }, [loadQueue, token]);

  const loadDetail = async (reviewId: string) => {
    const requestSequence = detailRequestSequence.current + 1;
    detailRequestSequence.current = requestSequence;
    setLoadingDetail(true);
    setError(null);
    setReason('');
    setConfirmed(false);
    setCandidateId('');
    try {
      const detail = await request<ReviewDetail>(
        `/admin/storefront/custom-domain/operator/reviews/${encodeURIComponent(reviewId)}`,
      );
      if (detailRequestSequence.current !== requestSequence) return;
      setSelected(detail);
      if (detail.provider_candidate_ids.length === 1) {
        setCandidateId(detail.provider_candidate_ids[0] ?? '');
      }
    } catch (caught) {
      if (detailRequestSequence.current !== requestSequence) return;
      setSelected(null);
      setError(caught instanceof Error ? caught.message : 'The review could not be loaded.');
    } finally {
      if (detailRequestSequence.current === requestSequence) {
        setLoadingDetail(false);
      }
    }
  };

  const submitDecision = async (action: ReviewAction) => {
    if (!selected || reason.trim().length < 10 || !confirmed) return;
    let path: string;
    let body: Record<string, unknown> = {
      planner_id: selected.planner_id,
      hostname: selected.hostname,
      attempt_id: selected.attempt_id,
      revision: selected.revision,
      reason: reason.trim(),
    };
    if (action === 'approve_o2o_cutover') {
      path = '/admin/storefront/custom-domain/operator/o2o/approve';
    } else if (action === 'adopt_ambiguous_create') {
      if (!candidateId || selected.provider_candidate_ids.length !== 1) return;
      path = '/admin/storefront/custom-domain/operator/ambiguous-create/adopt';
      body = { ...body, provider_hostname_id: candidateId };
    } else {
      path = '/admin/storefront/custom-domain/operator/conflict/resolve';
      body = {
        ...body,
        decision: action === 'deny_hostname_conflict' ? 'denied' : 'cancelled',
      };
    }

    setSubmitting(true);
    setError(null);
    try {
      const receipt = await request<{ operation_id: string; decision: string }>(path, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setAnnouncement(
        `Review ${receipt.decision}. Receipt ${receipt.operation_id} was recorded.`,
      );
      setSelected(null);
      await loadQueue();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The review decision failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const canDecide = reason.trim().length >= 10 && confirmed && !submitting;

  return (
    <section className="space-y-5" aria-labelledby="storefront-domain-review-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="storefront-domain-review-title"
            className="text-xl font-semibold text-slate-950 dark:text-slate-100"
          >
            Storefront domain reviews
          </h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-300">
            Resolve only ownership-proven O2O migrations, hostname conflicts, and
            ambiguous Cloudflare creates. Every decision is fenced to the exact owner,
            hostname, attempt, and revision shown here.
          </p>
        </div>
        <button type="button" onClick={() => void loadQueue()} className={secondaryButtonClass}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> Refresh reviews
        </button>
      </div>

      <p className="sr-only" role="status" aria-live="polite">
        {announcement}
      </p>
      {error ? (
        <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-950 dark:border-red-800 dark:bg-red-950/40 dark:text-red-100">
          {error}
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.4fr)]">
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold text-slate-950 dark:text-slate-100">
              Pending reviews
            </h3>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
              {queue.length}
            </span>
          </div>
          {loading ? (
            <p className="mt-4 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading reviews…
            </p>
          ) : queue.length === 0 ? (
            <div className="mt-4 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100">
              <CheckCircle2 className="mb-2 h-5 w-5" aria-hidden="true" />
              No storefront domains currently require operator review.
            </div>
          ) : (
            <div className="mt-4 space-y-2">
              {queue.map((review) => (
                <button
                  key={review.review_id}
                  type="button"
                  onClick={() => void loadDetail(review.review_id)}
                  className={`w-full rounded-lg border p-3 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
                    selected?.review_id === review.review_id
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/30'
                      : 'border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800'
                  }`}
                >
                  <span className="block text-sm font-semibold text-slate-950 dark:text-slate-100">
                    {review.hostname}
                  </span>
                  <span className="mt-1 block text-xs text-slate-600 dark:text-slate-300">
                    {humanize(review.review_type)} · revision {review.revision}
                  </span>
                </button>
              ))}
              {hasMore ? (
                <p className="pt-2 text-xs text-amber-700 dark:text-amber-300">
                  More than 100 reviews are pending. Clear this queue before continuing rollout.
                </p>
              ) : null}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
          {loadingDetail ? (
            <p className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading exact review…
            </p>
          ) : !selected ? (
            <div className="text-center text-sm text-slate-600 dark:text-slate-300">
              <ShieldAlert className="mx-auto mb-3 h-8 w-8" aria-hidden="true" />
              Select a review to inspect its exact target and permitted decisions.
            </div>
          ) : (
            <div className="space-y-5">
              <div className="flex items-start gap-3">
                {selected.review_type === 'investigation' ? (
                  <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-600" aria-hidden="true" />
                ) : (
                  <CloudCog className="mt-0.5 h-5 w-5 text-primary-700 dark:text-primary-300" aria-hidden="true" />
                )}
                <div>
                  <h3 className="font-semibold text-slate-950 dark:text-slate-100">
                    {humanize(selected.review_type)}
                  </h3>
                  <p className="mt-1 break-all text-sm text-slate-600 dark:text-slate-300">
                    {selected.hostname}
                  </p>
                </div>
              </div>

              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                {[
                  ['Planner', selected.planner_id],
                  ['Attempt', selected.attempt_id],
                  ['Revision', String(selected.revision)],
                  ['Ownership', selected.ownership_status ?? 'Not recorded'],
                  ['DNS provider', selected.authoritative_dns_provider ?? 'Not detected'],
                  ['Provider hostname', selected.provider_hostname_status ?? 'Not started'],
                  ['SSL', selected.ssl_status ?? 'Not started'],
                  ['HTTPS', selected.https_status ?? 'Not started'],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950">
                    <dt className="font-medium text-slate-600 dark:text-slate-400">{label}</dt>
                    <dd className="mt-1 break-all font-semibold text-slate-950 dark:text-slate-100">{value}</dd>
                  </div>
                ))}
              </dl>

              {selected.error_message || selected.customer_action ? (
                <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
                  <p className="font-semibold">{selected.error_message ?? humanize(selected.error_code ?? 'Review required')}</p>
                  {selected.customer_action ? <p className="mt-1 leading-6">{selected.customer_action}</p> : null}
                  {selected.support_id ? <p className="mt-2 font-medium">Support ID: {selected.support_id}</p> : null}
                </div>
              ) : null}

              {selected.review_type === 'ambiguous_create' ? (
                <div>
                  {selected.provider_lookup_status === 'unavailable' ||
                  selected.provider_lookup_status === 'invalid' ? (
                    <div
                      role="status"
                      className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
                    >
                      <p className="font-semibold">
                        {selected.provider_lookup_message ??
                          'Independent Cloudflare evidence is unavailable.'}
                      </p>
                      {selected.provider_lookup_support_id ? (
                        <p className="mt-1 font-medium">
                          Support ID: {selected.provider_lookup_support_id}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                  <label htmlFor="storefront-provider-candidate" className="text-sm font-semibold text-slate-950 dark:text-slate-100">
                    Independently observed new Cloudflare ID
                  </label>
                  <select
                    id="storefront-provider-candidate"
                    value={candidateId}
                    onChange={(event) => setCandidateId(event.target.value)}
                    className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100"
                  >
                    <option value="">Select a candidate</option>
                    {selected.provider_candidate_ids.map((id) => <option key={id} value={id}>{id}</option>)}
                  </select>
                  {selected.provider_candidate_ids.length !== 1 ? (
                    <p className="mt-2 text-sm font-medium text-amber-700 dark:text-amber-300">
                      Adoption is disabled unless exactly one new exact hostname was created during this attempt.
                    </p>
                  ) : null}
                </div>
              ) : null}

              {selected.allowed_actions.length ? (
                <div className="space-y-4 border-t border-slate-200 pt-5 dark:border-slate-700">
                  <div>
                    <label htmlFor="storefront-review-reason" className="text-sm font-semibold text-slate-950 dark:text-slate-100">
                      Decision reason
                    </label>
                    <textarea
                      id="storefront-review-reason"
                      rows={3}
                      maxLength={1000}
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                      placeholder="Record the evidence reviewed and why this exact decision is safe."
                      className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-3 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100"
                    />
                  </div>
                  <label className="flex items-start gap-3 text-sm text-slate-800 dark:text-slate-200">
                    <input
                      type="checkbox"
                      checked={confirmed}
                      onChange={(event) => setConfirmed(event.target.checked)}
                      className="mt-1 h-4 w-4"
                    />
                    I reviewed this exact owner, hostname, attempt, revision, and provider evidence.
                  </label>
                  <div className="flex flex-wrap gap-3">
                    {selected.allowed_actions.map((action) => (
                      <button
                        key={action}
                        type="button"
                        onClick={() => void submitDecision(action)}
                        disabled={
                          !canDecide ||
                          (action === 'adopt_ambiguous_create' &&
                            (!candidateId || selected.provider_candidate_ids.length !== 1))
                        }
                        className={
                          action === 'cancel_hostname_conflict'
                            ? secondaryButtonClass
                            : actionButtonClass
                        }
                      >
                        {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
                        {humanize(action)}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
                  No automated decision is safe for this state. Use the support ID and provider receipts for engineering investigation.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
