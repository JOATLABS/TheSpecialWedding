import type { UserProfile } from '@/contexts/AdminContext';
import { isBlockedSubscriptionStatus, normalizeSubscriptionStatus } from '@/utils/subscriptionStatus';

export type TrialBannerState =
  | {
      type: 'expired';
      message: string;
      urgent: true;
    }
  | {
      type: 'warning';
      message: string;
      urgent: boolean;
    };

export function getTrialBannerState(userProfile: UserProfile | null): TrialBannerState | null {
  if (!userProfile?.is_wedding_planner) {
    return null;
  }

  const ud = userProfile.user_data || {};
  const status = normalizeSubscriptionStatus(ud.subscription_status || userProfile.subscription_status);
  const trialEnd = ud.trial_end_date || userProfile.trial_end_date;

  if (!status) return null;

  if (isBlockedSubscriptionStatus(status)) {
    return {
      type: 'expired',
      message:
        ud._subscription_block_reason ||
        (status === 'inactive'
          ? 'Choose a plan and complete checkout to access the platform.'
          : 'Your subscription needs attention.'),
      urgent: true,
    };
  }

  if (status === 'trial' && trialEnd) {
    const endDate = new Date(trialEnd);
    const now = new Date();
    const daysLeft = Math.ceil((endDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

    if (daysLeft <= 0) {
      return {
        type: 'expired',
        message: 'Your free trial has ended. Upgrade now to keep your data.',
        urgent: true,
      };
    }

    if (daysLeft <= 3) {
      return {
        type: 'warning',
        message: `Your free trial ends in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}. Upgrade now to avoid losing access.`,
        urgent: daysLeft <= 1,
      };
    }
  }

  return null;
}
