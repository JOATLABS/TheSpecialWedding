import {
  isBlockedSubscriptionStatus,
  normalizeSubscriptionStatus,
} from '@/utils/subscriptionStatus';
import {
  DEFAULT_TEAM_MEMBER_BLOCK_REASON,
  getSubscriptionBlockReason,
  isTeamMemberRole,
  type ProfileLike,
} from '@/utils/roles';

/**
 * adminApiAuthGuard
 *
 * Canonical billing-block policy for admin-side route guards, login redirects,
 * periodic profile checks, and reactive 402 handling. Callers ask this module
 * for a target, then apply that target with the navigation primitive that fits
 * the freshness of their local auth state.
 */

export const PLANNER_BILLING_PATH = '/admin/planner/billing';

export type BillingBlockNavigation = 'client' | 'hard' | 'logout';

export type BillingBlockTarget =
  | {
      kind: 'planner_billing';
      href: typeof PLANNER_BILLING_PATH;
      navigation: Extract<BillingBlockNavigation, 'client' | 'hard'>;
    }
  | {
      kind: 'team_member_login';
      href: string;
      navigation: 'logout';
      reason: string;
    };

export type PaymentRequiredResolution =
  | {
      kind: 'not_payment_required';
    }
  | {
      kind: 'non_billing_payment_required';
      code: string;
      message: string;
    }
  | {
      kind: 'billing_block';
      target: BillingBlockTarget;
    };

export interface BillingProfileLike extends ProfileLike {
  is_root_admin?: boolean;
  is_wedding_planner?: boolean;
  subscription_status?: string | null;
  _subscription_blocked?: boolean;
  user_data?:
    | (ProfileLike['user_data'] & {
        subscription_status?: string | null;
        _subscription_blocked?: boolean;
      })
    | null;
}

type RouterLike = {
  replace: (href: string) => void;
};

type LogoutFn = (options?: {
  message?: string;
  redirectTo?: string;
  showToast?: boolean;
}) => void;

/**
 * Pages that expired/blocked planners are still allowed to reach. Consumed
 * by AdminRouteGuard to decide whether to bounce a blocked planner back to
 * /admin/planner/billing.
 */
export const BILLING_ALLOWED_PATHS = [
  '/admin/login',
  PLANNER_BILLING_PATH,
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

export const TEAM_MEMBER_BLOCKED_ALLOWED_PATHS = [
  '/admin/login',
  '/admin/team/accept',
] as const;

export function isTeamMemberBlockedAllowedPath(path: string): boolean {
  return TEAM_MEMBER_BLOCKED_ALLOWED_PATHS.some(
    (p) => path === p || path.startsWith(p + '/'),
  );
}

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

function buildPlannerBillingTarget(
  navigation: Extract<BillingBlockNavigation, 'client' | 'hard'> = 'client',
): BillingBlockTarget {
  return {
    kind: 'planner_billing',
    href: PLANNER_BILLING_PATH,
    navigation,
  };
}

function buildTeamMemberLoginTarget(reason: string): BillingBlockTarget {
  return {
    kind: 'team_member_login',
    href: `/admin/login?error=${encodeURIComponent(reason)}`,
    navigation: 'logout',
    reason,
  };
}

function getProfileSubscriptionStatus(profile: BillingProfileLike): string {
  return normalizeSubscriptionStatus(
    profile.user_data?.subscription_status || profile.subscription_status,
  );
}

/**
 * Derived route-level billing target. This is the value AdminContext exposes as
 * `billingBlockTarget` for the current path.
 */
export function getBillingBlockTargetForProfile(
  profile: BillingProfileLike | null | undefined,
  path: string,
  options: {
    navigation?: Extract<BillingBlockNavigation, 'client' | 'hard'>;
  } = {},
): BillingBlockTarget | null {
  if (!profile || profile.is_root_admin) {
    return null;
  }

  if (
    isTeamMemberRole(profile) &&
    (profile._subscription_blocked === true ||
      profile.user_data?._subscription_blocked === true) &&
    !isTeamMemberBlockedAllowedPath(path)
  ) {
    return buildTeamMemberLoginTarget(getSubscriptionBlockReason(profile));
  }

  if (
    profile.is_wedding_planner === true &&
    isBlockedSubscriptionStatus(getProfileSubscriptionStatus(profile)) &&
    !isAllowedForExpired(path)
  ) {
    return buildPlannerBillingTarget(options.navigation ?? 'client');
  }

  return null;
}

function getPaymentRequiredBodyCode(body: any): string | null {
  const detail = body?.detail;
  if (detail && typeof detail === 'object') {
    return detail.error || detail.code || null;
  }
  return body?.error || body?.code || null;
}

function getPaymentRequiredBodyMessage(body: any, fallback: string): string {
  const detail = body?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === 'object') {
    const message = detail.message || detail.detail;
    if (typeof message === 'string' && message.trim()) {
      return message;
    }
  }
  if (typeof body?.message === 'string' && body.message.trim()) {
    return body.message;
  }
  return fallback;
}

function isTeamMemberBillingBlockBody(body: any): boolean {
  const message = getPaymentRequiredBodyMessage(body, '').toLowerCase();
  return (
    message.includes("team's subscription") ||
    message.includes('contact your planner')
  );
}

async function readJsonBody(response: Response): Promise<any> {
  try {
    return await response.clone().json();
  } catch {
    return null;
  }
}

/**
 * Reactive response-level 402 resolver. AI credit exhaustion is deliberately
 * not a billing block: those callsites should stay inline and show the user the
 * credits message instead of logging out or redirecting to subscriptions.
 */
export async function resolvePaymentRequiredResponse(
  response: Response,
  options: {
    profile?: BillingProfileLike | null;
    navigation?: Extract<BillingBlockNavigation, 'client' | 'hard'>;
  } = {},
): Promise<PaymentRequiredResolution> {
  if (response.status !== 402) {
    return { kind: 'not_payment_required' };
  }

  const body = await readJsonBody(response);
  const code = getPaymentRequiredBodyCode(body);
  if (code === 'insufficient_credits') {
    return {
      kind: 'non_billing_payment_required',
      code,
      message: getPaymentRequiredBodyMessage(body, 'Insufficient AI credits.'),
    };
  }

  if (options.profile?.is_root_admin) {
    return { kind: 'not_payment_required' };
  }

  if (isTeamMemberRole(options.profile) || isTeamMemberBillingBlockBody(body)) {
    return {
      kind: 'billing_block',
      target: buildTeamMemberLoginTarget(
        getPaymentRequiredBodyMessage(body, DEFAULT_TEAM_MEMBER_BLOCK_REASON),
      ),
    };
  }

  return {
    kind: 'billing_block',
    target: buildPlannerBillingTarget(options.navigation ?? 'hard'),
  };
}

export function applyBillingBlockTarget(
  target: BillingBlockTarget | null | undefined,
  options: {
    router?: RouterLike;
    logout?: LogoutFn;
  } = {},
): boolean {
  if (!target) {
    return false;
  }

  if (target.kind === 'team_member_login') {
    if (options.logout) {
      options.logout({
        message: target.reason,
        redirectTo: target.href,
        showToast: false,
      });
    } else if (typeof window !== 'undefined') {
      window.location.replace(target.href);
    }
    return true;
  }

  if (target.navigation === 'client' && options.router) {
    options.router.replace(target.href);
  } else if (typeof window !== 'undefined') {
    window.location.href = target.href;
  }

  return true;
}

/**
 * Reactive 402 handler. On 402, navigates to /admin/planner/billing via a
 * hard redirect (see module header for why this differs from route-guard
 * behavior). Returns true if the response was handled (caller should bail
 * out without rendering an error). Returns false otherwise.
 *
 * Prefer resolvePaymentRequiredResponse() + applyBillingBlockTarget() when
 * caller profile context is available. This wrapper remains for legacy callers
 * that only know "a planner billing 402 happened".
 */
export function redirectOnBillingBlock(response: Response): boolean {
  if (response.status !== 402) {
    return false;
  }

  return applyBillingBlockTarget(buildPlannerBillingTarget('hard'));
}
