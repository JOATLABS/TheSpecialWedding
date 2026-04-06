const STATUS_ALIASES: Record<string, string> = {
  trialing: 'trial',
  canceled: 'cancelled',
  incomplete: 'pending_payment',
  incomplete_expired: 'expired',
  unpaid: 'suspended',
};

export const ACTIVE_SUBSCRIPTION_STATUSES = new Set([
  'active',
  'trial',
  'trial_expiring',
]);

export const BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES = new Set([
  'past_due',
  'suspended',
]);

export const BLOCKED_SUBSCRIPTION_STATUSES = new Set([
  'cancelled',
  'expired',
  'inactive',
  'past_due',
  'pending',
  'pending_checkout',
  'pending_payment',
  'suspended',
]);

export const FRESH_CHECKOUT_SUBSCRIPTION_STATUSES = new Set([
  'cancelled',
  'expired',
  'inactive',
  'pending',
  'pending_checkout',
  'pending_payment',
]);

export type PlannerBillingEntryState = 'new_checkout' | 'portal_recovery' | 'dashboard';

export function normalizeSubscriptionStatus(status?: string | null): string {
  const normalized = status?.trim().toLowerCase();
  if (!normalized) return 'unknown';
  return STATUS_ALIASES[normalized] || normalized;
}

export function isBlockedSubscriptionStatus(status?: string | null): boolean {
  return BLOCKED_SUBSCRIPTION_STATUSES.has(normalizeSubscriptionStatus(status));
}

export function getPlannerBillingEntryState(options: {
  status?: string | null;
  hasSubscription: boolean;
  hasPlan: boolean;
}): PlannerBillingEntryState {
  const normalizedStatus = normalizeSubscriptionStatus(options.status);
  const hasActiveBillingRelationship =
    options.hasSubscription && ACTIVE_SUBSCRIPTION_STATUSES.has(normalizedStatus);
  const needsPortalRecovery =
    options.hasSubscription && BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES.has(normalizedStatus);

  if (hasActiveBillingRelationship) {
    return 'dashboard';
  }

  if (needsPortalRecovery) {
    return 'portal_recovery';
  }

  if (
    !options.hasSubscription ||
    !options.hasPlan ||
    FRESH_CHECKOUT_SUBSCRIPTION_STATUSES.has(normalizedStatus) ||
    (BLOCKED_SUBSCRIPTION_STATUSES.has(normalizedStatus) &&
      !BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES.has(normalizedStatus))
  ) {
    return 'new_checkout';
  }

  return 'dashboard';
}
