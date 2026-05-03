'use client';

import { useCallback, useEffect, useState } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';

/**
 * Shape returned by `GET /stripe/connect/status` on the backend.
 *
 * `charges_enabled` is the load-bearing flag for "can this planner accept
 * money right now". `payouts_enabled` controls whether collected funds
 * actually settle to their bank — connected planners can still take card
 * payments without payouts being live, but it's worth surfacing.
 */
export interface StripeConnectStatus {
  status: string;
  charges_enabled: boolean;
  payouts_enabled: boolean;
  details_submitted: boolean;
}

export interface UseStripeConnectResult {
  status: StripeConnectStatus | null;
  /**
   * True when the planner can actually receive a payment (charges enabled
   * AND onboarding submitted). Use this to gate any "request payment"
   * surface — sending a couple to Checkout while charges are disabled
   * just produces a backend rejection.
   */
  isReady: boolean;
  loading: boolean;
  error: Error | null;
  /**
   * Re-fetch the status. Call this after the planner returns from Stripe
   * onboarding (or any flow that may have flipped charges_enabled),
   * since there's no push channel for connect-state updates.
   */
  refetch: () => Promise<void>;
}

/**
 * Single source of truth for Stripe Connect status across the planner
 * billing surface. Previously the Connect card and the Payment Requests
 * card each had to fetch this independently, which made it impossible
 * to gate the "Request payment" CTA on whether onboarding was complete.
 *
 * Lift state here, consume in both components, refetch on demand.
 */
export function useStripeConnect(): UseStripeConnectResult {
  const { token } = useAdmin();
  const [status, setStatus] = useState<StripeConnectStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${getApiBaseUrl()}/stripe/connect/status`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (response.ok) {
        const data = (await response.json()) as StripeConnectStatus;
        setStatus(data);
      } else {
        // 404 / no Connect account is a legitimate "not yet" state, not
        // an error — keep status null and let isReady evaluate to false.
        setStatus(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void fetchStatus();
  }, [fetchStatus]);

  const isReady = Boolean(
    status && status.details_submitted && status.charges_enabled,
  );

  return { status, isReady, loading, error, refetch: fetchStatus };
}
