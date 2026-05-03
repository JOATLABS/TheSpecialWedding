'use client';

/**
 * Payouts (Stripe Connect) card on /admin/planner/billing.
 *
 * Surfaces the planner's Stripe Connect status so they can onboard before
 * sending packages to couples. Without a charges-enabled Connect account,
 * `package_service.send_to_couple` would (post-gate) refuse to send, and
 * even if a deposit somehow charged, it would land in the platform Stripe
 * account instead of the planner's. This card is the planner's only
 * in-product affordance for setting up payouts.
 *
 * States:
 *   - loading                   → spinner row
 *   - not_connected | pending   → amber-bordered card with CTA that posts
 *                                 to /stripe/connect/onboard and redirects
 *                                 to the returned hosted-onboarding URL
 *   - returning from Stripe     → "Verifying" state, polls refetch() every
 *                                 2s for up to 30s until charges_enabled
 *                                 flips
 *   - ready                     → standard card with "Ready" badge
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  Banknote,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ExternalLink,
} from 'lucide-react';
import { toast } from 'sonner';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { useStripeConnect } from '@/hooks/useStripeConnect';

const SUPPORTED_COUNTRIES = [
  { code: 'US', name: 'United States' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'IT', name: 'Italy' },
  { code: 'ES', name: 'Spain' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'IE', name: 'Ireland' },
  { code: 'AT', name: 'Austria' },
  { code: 'BE', name: 'Belgium' },
  { code: 'DK', name: 'Denmark' },
  { code: 'FI', name: 'Finland' },
  { code: 'NO', name: 'Norway' },
  { code: 'SE', name: 'Sweden' },
  { code: 'CH', name: 'Switzerland' },
  { code: 'PT', name: 'Portugal' },
  { code: 'LU', name: 'Luxembourg' },
  { code: 'NZ', name: 'New Zealand' },
  { code: 'SG', name: 'Singapore' },
  { code: 'HK', name: 'Hong Kong' },
  { code: 'JP', name: 'Japan' },
] as const;

const POLL_INTERVAL_MS = 2_000;
const POLL_TIMEOUT_MS = 30_000;
const STRIPE_RETURN_PARAM = 'stripe_return';
const STRIPE_RETURN_VALUES = ['connect', 'connect_retry'];

export default function PayoutsCard() {
  const { token } = useAdmin();
  const { status, isReady, loading, refetch } = useStripeConnect();
  const searchParams = useSearchParams();
  const [isStartingOnboarding, setIsStartingOnboarding] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [selectedCountry, setSelectedCountry] = useState('US');
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollDeadlineRef = useRef<number>(0);

  // Did the user just return from Stripe hosted onboarding?
  const stripeReturnValue = searchParams?.get(STRIPE_RETURN_PARAM) ?? '';
  const cameBackFromStripe = STRIPE_RETURN_VALUES.includes(stripeReturnValue);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const tick = useCallback(async () => {
    await refetch();
    if (Date.now() >= pollDeadlineRef.current) {
      stopPolling();
      return;
    }
    pollTimerRef.current = setTimeout(tick, POLL_INTERVAL_MS);
  }, [refetch, stopPolling]);

  // Kick off polling once when we land back from Stripe and aren't ready yet.
  useEffect(() => {
    if (!cameBackFromStripe || isReady || isPolling) return;
    pollDeadlineRef.current = Date.now() + POLL_TIMEOUT_MS;
    setIsPolling(true);
    pollTimerRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
    // tick is stable enough; we intentionally don't restart polling on every
    // tick recreation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameBackFromStripe, isReady]);

  // Stop polling once the status flips to ready.
  useEffect(() => {
    if (isReady && isPolling) stopPolling();
  }, [isReady, isPolling, stopPolling]);

  const handleStartOnboarding = useCallback(async () => {
    if (!token) {
      toast.error('You need to be signed in to set up payouts.');
      return;
    }
    try {
      setIsStartingOnboarding(true);
      const baseUrl = getApiBaseUrl();
      const returnUrl = `${window.location.origin}/admin/planner/billing?${STRIPE_RETURN_PARAM}=connect`;
      const refreshUrl = `${window.location.origin}/admin/planner/billing?${STRIPE_RETURN_PARAM}=connect_retry`;
      const response = await fetch(`${baseUrl}/stripe/connect/onboard`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
        body: JSON.stringify({
          country: selectedCountry,
          return_url: returnUrl,
          refresh_url: refreshUrl,
        }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(
          (err && (err.detail || err.message)) ||
            'Failed to start payout setup',
        );
      }
      const data = (await response.json()) as { url?: string };
      if (!data.url) {
        throw new Error('Stripe did not return an onboarding URL.');
      }
      window.location.href = data.url;
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to start payout setup',
      );
      setIsStartingOnboarding(false);
    }
  }, [token]);

  // ===== Render =====

  // Loading skeleton (first fetch in flight, no cached status yet).
  if (loading && !status) {
    return (
      <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-6">
        <CardContent className="flex items-center gap-3 p-0">
          <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Loading payout status…
          </span>
        </CardContent>
      </Card>
    );
  }

  // Verifying state (returned from Stripe, polling for charges_enabled).
  if (isPolling && !isReady) {
    return (
      <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-6">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-gray-900 dark:text-gray-100">
              Payouts
            </CardTitle>
            <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              Verifying
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Confirming your payout setup with Stripe — this usually takes a few
            seconds.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Ready state.
  if (isReady) {
    return (
      <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-6">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-gray-900 dark:text-gray-100">
              Payouts
            </CardTitle>
            <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              Ready
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0 space-y-2">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            You&apos;re set up to collect payments from couples. Funds settle
            directly to your connected account.
          </p>
          {!status?.payouts_enabled && (
            <p className="text-xs text-yellow-700 dark:text-yellow-300">
              Note: bank payouts are still being verified by Stripe. You can
              accept payments now; transfers resume once verification
              completes.
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  // Pending or not_connected state.
  const hasStartedSetup = !!status && status.details_submitted;
  return (
    <Card className="bg-white dark:bg-gray-800 border-amber-300 dark:border-amber-600/60 p-6">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-gray-900 dark:text-gray-100">
            Payouts
          </CardTitle>
          <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            {hasStartedSetup ? 'Setup incomplete' : 'Not set up'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0 space-y-4">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Set up payouts to collect deposits and milestone payments from
          couples. Until this is complete, you can&apos;t send packages — and
          any payments would route to the platform instead of you.
        </p>
        {!hasStartedSetup ? (
          <div className="space-y-2">
            <label
              htmlFor="stripe-connect-country"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Business country
            </label>
            <select
              id="stripe-connect-country"
              value={selectedCountry}
              onChange={(event) => setSelectedCountry(event.target.value)}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-wedding-rose dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
            >
              {SUPPORTED_COUNTRIES.map((country) => (
                <option key={country.code} value={country.code}>
                  {country.name}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Choose where your business is registered. Stripe locks this on
              first account creation.
            </p>
          </div>
        ) : (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Your Stripe account already exists, so its business country stays
            fixed while you finish setup.
          </p>
        )}
        <Button
          onClick={handleStartOnboarding}
          disabled={isStartingOnboarding}
          isLoading={isStartingOnboarding}
        >
          {!isStartingOnboarding && <Banknote className="w-4 h-4 mr-2" />}
          {hasStartedSetup ? 'Resume payout setup' : 'Set up payouts'}
          {!isStartingOnboarding && (
            <ExternalLink className="w-3 h-3 ml-2" />
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
