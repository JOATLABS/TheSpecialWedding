import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  PLANNER_BILLING_PATH,
  getBillingBlockTargetForProfile,
  resolvePaymentRequiredResponse,
} from '../../app/utils/adminApiAuthGuard';

describe('admin billing-block target policy', () => {
  it('derives a client-side billing target for blocked planners outside allowed paths', () => {
    const target = getBillingBlockTargetForProfile(
      {
        role: 'wedding_planner',
        is_root_admin: false,
        is_wedding_planner: true,
        subscription_status: 'expired',
      },
      '/admin/guests',
    );

    assert.deepEqual(target, {
      kind: 'planner_billing',
      href: PLANNER_BILLING_PATH,
      navigation: 'client',
    });
  });

  it('does not loop blocked planners on billing or invite-acceptance routes', () => {
    const blockedPlanner = {
      role: 'wedding_planner',
      is_root_admin: false,
      is_wedding_planner: true,
      subscription_status: 'inactive',
    };

    assert.equal(
      getBillingBlockTargetForProfile(blockedPlanner, '/admin/planner/billing'),
      null,
    );
    assert.equal(
      getBillingBlockTargetForProfile(blockedPlanner, '/admin/team/accept/token-123'),
      null,
    );
  });

  it('derives a logout target for blocked team members instead of planner billing', () => {
    const target = getBillingBlockTargetForProfile(
      {
        role: 'team_member',
        is_team_member: true,
        _subscription_blocked: true,
        _subscription_block_reason: 'Planner subscription inactive',
      },
      '/admin/guests',
    );

    assert.deepEqual(target, {
      kind: 'team_member_login',
      href: '/admin/login?error=Planner%20subscription%20inactive',
      navigation: 'logout',
      reason: 'Planner subscription inactive',
    });
  });

  it('resolves reactive 402s to the same targets without treating AI credits as billing blocks', async () => {
    const aiCreditResponse = new Response(
      JSON.stringify({
        detail: {
          error: 'insufficient_credits',
          message: 'You need 3 credits but have 0.',
        },
      }),
      { status: 402, headers: { 'Content-Type': 'application/json' } },
    );

    const creditResult = await resolvePaymentRequiredResponse(aiCreditResponse, {
      profile: { role: 'wedding_planner', is_wedding_planner: true },
      navigation: 'hard',
    });

    assert.deepEqual(creditResult, {
      kind: 'non_billing_payment_required',
      code: 'insufficient_credits',
      message: 'You need 3 credits but have 0.',
    });

    const plannerResult = await resolvePaymentRequiredResponse(
      new Response(JSON.stringify({ detail: 'Subscription expired' }), {
        status: 402,
        headers: { 'Content-Type': 'application/json' },
      }),
      {
        profile: { role: 'wedding_planner', is_wedding_planner: true },
        navigation: 'hard',
      },
    );

    assert.deepEqual(plannerResult, {
      kind: 'billing_block',
      target: {
        kind: 'planner_billing',
        href: PLANNER_BILLING_PATH,
        navigation: 'hard',
      },
    });

    const teamResult = await resolvePaymentRequiredResponse(
      new Response(JSON.stringify({ detail: 'Owner billing is blocked' }), {
        status: 402,
        headers: { 'Content-Type': 'application/json' },
      }),
      {
        profile: { role: 'team_member', is_team_member: true },
        navigation: 'hard',
      },
    );

    assert.deepEqual(teamResult, {
      kind: 'billing_block',
      target: {
        kind: 'team_member_login',
        href: '/admin/login?error=Owner%20billing%20is%20blocked',
        navigation: 'logout',
        reason: 'Owner billing is blocked',
      },
    });
  });

  it('uses the team-member 402 body when profile hydration has not completed', async () => {
    const reason =
      "Your team's subscription requires attention (status: past_due). Please contact your planner at owner@example.com to restore access.";
    const result = await resolvePaymentRequiredResponse(
      new Response(JSON.stringify({ detail: reason }), {
        status: 402,
        headers: { 'Content-Type': 'application/json' },
      }),
      { profile: null, navigation: 'hard' },
    );

    assert.deepEqual(result, {
      kind: 'billing_block',
      target: {
        kind: 'team_member_login',
        href: `/admin/login?error=${encodeURIComponent(reason)}`,
        navigation: 'logout',
        reason,
      },
    });
  });

  it('keeps stale direct billing navigation copies out of route-specific admin code', () => {
    const guardedFiles = [
      'app/admin/guests/page.tsx',
      'app/admin/hooks/useGuests.ts',
      'app/admin/hooks/useTables.ts',
      'app/admin/page.tsx',
      'app/components/AdminRouteGuard.tsx',
      'app/contexts/AdminContext.tsx',
    ];

    for (const file of guardedFiles) {
      const source = readFileSync(join(process.cwd(), file), 'utf8');
      assert.doesNotMatch(
        source,
        /window\.location\.href\s*=\s*['"]\/admin\/planner\/billing['"]/,
        `${file} must not hard-code planner billing hard navigation`,
      );
      assert.doesNotMatch(
        source,
        /router\.replace\(\s*['"]\/admin\/planner\/billing['"]\s*\)/,
        `${file} must use the shared billing-block target before client navigation`,
      );
      if (file !== 'app/contexts/AdminContext.tsx') {
        assert.doesNotMatch(
          source,
          /redirectOnBillingBlock/,
          `${file} must not bypass the shared billing-block target resolver`,
        );
      }
    }
  });
});
