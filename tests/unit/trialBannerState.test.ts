import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { getTrialBannerState } from '../../app/admin/components/trialBannerState';

describe('trial banner billing scope', () => {
  it('does not render a planner billing banner for root admin profiles', () => {
    const result = getTrialBannerState({
      email: 'root@example.com',
      role: 'ROOT_ADMIN',
      is_root_admin: true,
      is_wedding_planner: false,
      is_vendor: false,
      subscription_status: 'inactive',
      user_data: {
        subscription_status: 'inactive',
      },
    });

    assert.equal(result, null);
  });

  it('renders the upgrade banner for blocked planner profiles', () => {
    const result = getTrialBannerState({
      email: 'planner@example.com',
      role: 'wedding_planner',
      is_root_admin: false,
      is_wedding_planner: true,
      is_vendor: false,
      subscription_status: 'inactive',
      user_data: {
        subscription_status: 'inactive',
      },
    });

    assert.deepEqual(result, {
      type: 'expired',
      message: 'Choose a plan and complete checkout to access the platform.',
      urgent: true,
    });
  });
});
