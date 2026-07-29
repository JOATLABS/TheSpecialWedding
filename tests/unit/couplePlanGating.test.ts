import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

// Contract for couple-plan feature gating (operator ruling 2026-07-28): the
// self-serve couple-plan purchaser uses the PLANNER dashboard for their own
// single wedding, and exactly FOUR surfaces are gated — couple portal,
// service packages, team seats, and a second wedding. Backend enforces with
// 403s; the frontend must hide those surfaces (no dead menu items) and never
// use user-facing "lifetime" language.

const source = (path: string) => readFileSync(path, 'utf8');

const planAccess = source('app/admin/utils/planAccess.ts');
const teamAccess = source('app/admin/utils/teamAccess.ts');
const sidebar = source('app/admin/components/Sidebar.tsx');
const weddingsPage = source('app/admin/weddings/page.tsx');
const packagesPage = source('app/admin/packages/page.tsx');
const teamPage = source('app/admin/planner/team/page.tsx');
const billingConstants = source('app/constants/billing.py');
const featureGates = source('app/dependencies/feature_gates.py');

describe('couple plan gating contract', () => {
  it('keeps the frontend plan id in sync with the backend catalog', () => {
    assert.match(planAccess, /COUPLE_PLAN_ID = 'plan_couple'/);
    assert.match(billingConstants, /COUPLE_PLAN_ID = "plan_couple"/);
  });

  it('keeps the internal couple plan out of the public catalog', () => {
    // /public/subscription-plans returns every ACTIVE plan; the couple plan
    // must be seeded inactive so it can never leak onto planner pricing.
    const seedStart = billingConstants.indexOf('COUPLE_PLAN_SEED');
    assert.notEqual(seedStart, -1);
    const seed = billingConstants.slice(seedStart);
    assert.match(seed, /"is_active": False/);
    assert.match(seed, /"max_weddings": 1/);
    assert.match(seed, /"staff_seats": 0/);
    assert.match(seed, /"packages": False/);
    assert.match(seed, /"couple_portal": False/);
    // Storefront half of the packaging\/storefront gate (operator
    // clarification 2026-07-28): these keys are fail-closed — literal True
    // required by storefront_entitlement_service — so explicit False keeps
    // every storefront endpoint 403 for the couple plan.
    assert.match(seed, /"planner_storefront": False/);
    assert.match(seed, /"custom_domain": False/);
  });

  it('hides Packages and Team from the couple-plan sidebar', () => {
    assert.match(planAccess, /COUPLE_PLAN_HIDDEN_NAV_NAMES = new Set\(\['Packages', 'Team'\]\)/);
    assert.match(sidebar, /isCouplePlan\(userProfile\)/);
    assert.match(sidebar, /COUPLE_PLAN_HIDDEN_NAV_NAMES\.has\(item\.name\)/);
  });

  it('removes all couple-portal surfaces for couple-plan workspaces', () => {
    // canManageCouplePortal gates every couple-portal affordance (weddings
    // list toggle, wedding-detail Couple tab, planner dashboard) — a single
    // couple-plan short-circuit there hides them all.
    const fnStart = teamAccess.indexOf('export function canManageCouplePortal');
    assert.notEqual(fnStart, -1);
    const fnBody = teamAccess.slice(fnStart, teamAccess.indexOf('}', fnStart + 400));
    assert.match(fnBody, /if \(isCouplePlan\(userProfile\)\) return false;/);
  });

  it('replaces the Add Wedding CTA with the locked one-wedding copy', () => {
    assert.match(weddingsPage, /isCouplePlan\(userProfile\) \? \(/);
    assert.match(weddingsPage, /COUPLE_PLAN_ONE_WEDDING_COPY/);
    assert.match(
      planAccess,
      /The couple plan covers one wedding — your workspace already includes it\./,
    );
  });

  it('shows included-with-planner-plans copy on direct visits to gated pages', () => {
    assert.match(planAccess, /INCLUDED_WITH_PLANNER_PLANS_COPY = 'Included with planner plans\.'/);
    assert.match(packagesPage, /isCouplePlan\(userProfile\)/);
    assert.match(packagesPage, /INCLUDED_WITH_PLANNER_PLANS_COPY/);
    assert.match(teamPage, /isCouplePlan\(userProfile\)/);
    assert.match(teamPage, /INCLUDED_WITH_PLANNER_PLANS_COPY/);
  });

  it('enforces the gates server-side, not just in the UI', () => {
    // Include-by-default polarity: planner plans that never declare the keys
    // keep access; only an explicit False (the couple plan) is blocked.
    assert.match(featureGates, /def require_plan_included_feature/);
    assert.match(featureGates, /features\.get\(feature_name\) is False/);
    assert.match(featureGates, /require_packages_feature = require_plan_included_feature/);
    assert.match(featureGates, /require_couple_portal_feature = require_plan_included_feature/);
  });

  it('never uses user-facing "lifetime" language in the gating copy', () => {
    for (const file of [planAccess, sidebar]) {
      const withoutComments = file
        .split('\n')
        .filter((line) => !line.trim().startsWith('//') && !line.trim().startsWith('*'))
        .join('\n');
      assert.doesNotMatch(withoutComments, /lifetime/i);
    }
  });
});
