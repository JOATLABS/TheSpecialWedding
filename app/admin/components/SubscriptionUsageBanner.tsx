'use client';

/**
 * SubscriptionUsageBanner — thin planner-facing banner that surfaces per-resource
 * cap state by polling the canonical `/users/{id}/usage/check` endpoint.
 *
 * The backend returns a soft-cap shape for `ai_credits` (always allowed, with
 * `overage`, `overage_credits`, `overage_cost_cents`) and a hard-cap shape for
 * `storage`, `weddings`, `staff_seats` (`allowed: false` when the limit is hit).
 * We intentionally depend on the live-query path in SubscriptionService so the
 * banner never drifts when counter writes race.
 *
 * Root admins bypass — they have no personal plan cap.
 */

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Database, HardDrive, Sparkles, Users } from 'lucide-react';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { getPlannerScopedUserId } from '@/admin/utils/teamAccess';

type ResourceType = 'storage' | 'ai_credits' | 'weddings' | 'staff_seats';

interface UsageCheckResponse {
  allowed?: boolean;
  limit?: number;
  // The backend's canonical "used" key is ``current_usage`` across all
  // resource branches in SubscriptionService.check_usage_limits. ``used``
  // is kept as a back-compat alias only — never assume it's populated.
  current_usage?: number;
  used?: number;
  remaining?: number;
  message?: string;
  // storage hard-cap fields
  current_usage_bytes?: number;
  current_usage_gb?: number;
  limit_gb?: number;
  // ai_credits soft-cap fields
  overage?: boolean;
  overage_credits?: number;
  overage_credits_projected?: number;
  overage_price_per_credit_usd?: number;
  overage_cost_cents?: number;
}

interface SubscriptionUsageBannerProps {
  resourceType: ResourceType;
  /**
   * Pre-flight amount for a specific action (e.g. bytes about to be uploaded
   * for storage, credits about to be consumed for ai_credits). Leave 0/omitted
   * for a generic status banner. Polled on mount.
   */
  requestedAmount?: number;
  /**
   * Hide the banner entirely when usage is below warnThresholdPct (default 80).
   * Useful for surfaces where we only want to interrupt on real state changes.
   */
  quietUntilWarn?: boolean;
  warnThresholdPct?: number;
  className?: string;
}

const RESOURCE_COPY: Record<
  ResourceType,
  {
    label: string;
    softCap: boolean;
    icon: typeof HardDrive;
    unit: string;
  }
> = {
  storage: { label: 'Photo storage', softCap: false, icon: HardDrive, unit: 'GB' },
  ai_credits: { label: 'AI credits', softCap: true, icon: Sparkles, unit: 'credits' },
  weddings: { label: 'Weddings', softCap: false, icon: Database, unit: 'weddings' },
  staff_seats: { label: 'Team seats', softCap: false, icon: Users, unit: 'seats' },
};

function formatCost(cents: number): string {
  if (!cents) return '$0.00';
  return `$${(cents / 100).toFixed(2)}`;
}

export default function SubscriptionUsageBanner({
  resourceType,
  requestedAmount = 0,
  quietUntilWarn = false,
  warnThresholdPct = 80,
  className = '',
}: SubscriptionUsageBannerProps) {
  const { userProfile, token } = useAdmin();
  const [state, setState] = useState<UsageCheckResponse | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    const scopedId = getPlannerScopedUserId(userProfile);
    if (!userProfile || userProfile.is_root_admin || !scopedId || !token) {
      setState(null);
      setLoaded(true);
      return;
    }

    try {
      const baseUrl = getApiBaseUrl();
      const amountParam = requestedAmount > 0 ? `&amount=${requestedAmount}` : '&amount=0';
      const response = await fetch(
        `${baseUrl}/users/${encodeURIComponent(scopedId)}/usage/check?resource_type=${resourceType}${amountParam}`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        },
      );
      if (response.ok) {
        setState((await response.json()) as UsageCheckResponse);
      } else {
        setState(null);
      }
    } catch {
      setState(null);
    } finally {
      setLoaded(true);
    }
  }, [resourceType, requestedAmount, token, userProfile]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!loaded || !state) return null;

  const copy = RESOURCE_COPY[resourceType];
  const Icon = copy.icon;

  // Hard-cap surfaces: only render when at cap, OR when quietUntilWarn is off
  // AND we're above the warn threshold.
  if (!copy.softCap) {
    const limit = state.limit_gb ?? state.limit ?? 0;
    // For storage, the backend reports ``current_usage_gb`` (the GB-rounded
    // form the bar should plot). For weddings/staff_seats, the backend
    // returns ``current_usage``. ``used`` is the legacy alias retained for
    // forward-compat only. See SubscriptionService.check_usage_limits.
    const used =
      state.current_usage_gb ?? state.current_usage ?? state.used ?? 0;
    const isUnlimited = limit === -1;
    const pct = !isUnlimited && limit > 0 ? (used / limit) * 100 : 0;
    const hitCap = state.allowed === false;
    const aboveWarn = !isUnlimited && pct >= warnThresholdPct;

    if (!hitCap && (!aboveWarn || isUnlimited)) return null;

    const unit = resourceType === 'storage' ? 'GB' : copy.unit;
    const usedLabel = resourceType === 'storage' ? used.toFixed(1) : String(used);
    const limitLabel = isUnlimited ? 'unlimited' : `${limit} ${unit}`;

    const bannerColor = hitCap
      ? 'border-red-300 bg-red-50 text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-200'
      : 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200';

    return (
      <div
        className={`rounded-xl border px-4 py-3 text-sm ${bannerColor} ${className}`}
        role={hitCap ? 'alert' : 'status'}
      >
        <div className="flex items-start gap-3">
          <Icon className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold">
              {hitCap
                ? `${copy.label} limit reached`
                : `${copy.label} nearing plan limit`}
            </p>
            <p className="mt-1 text-xs">
              {state.message ||
                `Using ${usedLabel} of ${limitLabel}${
                  !isUnlimited && limit > 0
                    ? ` (${Math.min(100, Math.round(pct))}%)`
                    : ''
                }.`}
              {hitCap && ' Upgrade your plan to continue.'}
            </p>
          </div>
          {hitCap && (
            <a
              href="/admin/planner/billing"
              className="shrink-0 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-red-700 shadow-sm hover:bg-red-100 dark:bg-red-900 dark:text-red-100 dark:hover:bg-red-800"
            >
              Upgrade
            </a>
          )}
        </div>
      </div>
    );
  }

  // Soft-cap surface (ai_credits): show warn at threshold, overage callout at limit.
  const limit = state.limit ?? 0;
  // ai_credits returns ``current_usage`` from check_usage_limits. ``used`` is
  // the legacy alias and is never populated by the current backend.
  const used = state.current_usage ?? state.used ?? 0;
  const isUnlimited = limit === -1;
  const pct = !isUnlimited && limit > 0 ? (used / limit) * 100 : 0;
  const inOverage = Boolean(state.overage);
  const aboveWarn = !isUnlimited && pct >= warnThresholdPct;

  if (quietUntilWarn && !aboveWarn && !inOverage) return null;
  if (isUnlimited) return null;

  const bannerColor = inOverage
    ? 'border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-900/40 dark:bg-orange-950/30 dark:text-orange-200'
    : aboveWarn
      ? 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200'
      : 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-200';

  const priceEach = state.overage_price_per_credit_usd ?? 0;
  const priceLabel =
    priceEach > 0 ? `$${priceEach.toFixed(3)} per extra credit` : 'metered overage';

  return (
    <div
      className={`rounded-xl border px-4 py-3 text-sm ${bannerColor} ${className}`}
      role={inOverage ? 'alert' : 'status'}
    >
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="flex-1">
          <p className="font-semibold">
            {inOverage
              ? 'AI credits over plan — overage billing active'
              : aboveWarn
                ? 'AI credits running low'
                : 'AI credits'}
          </p>
          <p className="mt-1 text-xs">
            {inOverage ? (
              <>
                Using {used} of {limit} included credits. Extra usage:{' '}
                <span className="font-semibold">
                  {state.overage_credits ?? 0} credits ·{' '}
                  {formatCost(state.overage_cost_cents ?? 0)}
                </span>{' '}
                this cycle. Next charge includes overage at {priceLabel}.
              </>
            ) : (
              <>
                Using {used} of {limit} credits ({Math.min(100, Math.round(pct))}%).
                Going over rolls onto metered overage billing.
              </>
            )}
          </p>
        </div>
        {(inOverage || aboveWarn) && (
          <a
            href="/admin/planner/billing"
            className="shrink-0 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
          >
            Upgrade plan
          </a>
        )}
      </div>
    </div>
  );
}

export { type ResourceType, type UsageCheckResponse };
