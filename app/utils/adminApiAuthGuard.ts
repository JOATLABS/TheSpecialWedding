/**
 * adminApiAuthGuard
 *
 * Centralized billing-block policy for admin-side navigation and API
 * response handling. Two responsibilities:
 *
 *   1. BILLING_ALLOWED_PATHS + isAllowedForExpired — the canonical list of
 *      routes a blocked planner may still reach (login, billing pages,
 *      team-invite accept). Consumed by AdminRouteGuard for preemptive
 *      route-level gating.
 *
 *   2. redirectOnBillingBlock(response) — reactive 402 handler used by
 *      AdminContext.apiRequest AND by service modules that perform their
 *      own fetches (e.g. behavioralAnalyticsApi, campaignAdvertisingApi).
 *      See AGENTS.md → "Known Open Issues" item 5.
 *
 * Why the two live in the same module:
 *   Both encode the same domain policy ("which routes are exempt from the
 *   billing block, and where do we send the user if we hit one that isn't?").
 *   Previously the path list lived only in AdminRouteGuard and the redirect
 *   target was duplicated inline in apiRequest. Co-locating them makes it
 *   obvious when the policy needs to change.
 *
 * IMPORTANT — two different navigation strategies co-exist:
 *   - AdminRouteGuard + AdminContext.login use `router.replace` because the
 *     in-memory profile is fresh and we want to preserve React state.
 *   - redirectOnBillingBlock uses `window.location.href` because a mid-
 *     session 402 means the cached profile is stale and we need a clean
 *     re-hydrate.
 *   AGENTS.md → "Known Open Issues" item 8 tracks the plan to unify this
 *   behind a single derived `billingBlockTarget` state.
 *
 * NOTE: Team-member-specific 402 handling (logout + /admin/login?error=…)
 * lives inside AdminContext.apiRequest because it requires userProfile
 * context. This helper therefore only handles the planner-blocked case.
 */

/**
 * Pages that expired/blocked planners are still allowed to reach. Consumed
 * by AdminRouteGuard to decide whether to bounce a blocked planner back to
 * /admin/planner/billing.
 */
export const BILLING_ALLOWED_PATHS = [
  '/admin/login',
  '/admin/planner/billing',
  '/admin/billing',
] as const;

/**
 * Extra paths a blocked planner may reach (not covered by BILLING_ALLOWED_PATHS).
 * Kept separate from the planner billing list so each exemption has a clear
 * domain reason.
 */
const BILLING_EXTRA_ALLOWED_PREFIXES = [
  '/admin/team/accept', // Team-invite acceptance must work even if planner is blocked.
] as const;

/**
 * Returns true if `path` is one of the routes a blocked planner may still
 * visit without being bounced to /admin/planner/billing.
 */
export function isAllowedForExpired(path: string): boolean {
  if (
    BILLING_ALLOWED_PATHS.some(
      (p) => path === p || path.startsWith(p + '/'),
    )
  ) {
    return true;
  }
  if (BILLING_EXTRA_ALLOWED_PREFIXES.some((p) => path.startsWith(p))) {
    return true;
  }
  return false;
}

/**
 * Reactive 402 handler. On 402, navigates to /admin/planner/billing via a
 * hard redirect (see module header for why this differs from route-guard
 * behavior). Returns true if the response was handled (caller should bail
 * out without rendering an error). Returns false otherwise.
 */
export function redirectOnBillingBlock(response: Response): boolean {
  if (response.status !== 402) {
    return false;
  }

  if (typeof window !== 'undefined') {
    // Hard navigation — also clears any in-memory cached state so the
    // billing page renders against a fresh profile fetch.
    window.location.href = '/admin/planner/billing';
  }

  return true;
}
