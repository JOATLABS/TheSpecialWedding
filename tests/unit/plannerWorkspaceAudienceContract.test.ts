import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const readSource = (path: string) => readFileSync(path, 'utf8');

describe('planner workspace audience contract', () => {
  it('identifies both public signup flows as planner workspaces before registration', () => {
    const primarySignup = readSource('app/components/saas/SignupModal.tsx');
    const alternateSignup = readSource('app/components/saas/PlannerAuthSection.tsx');

    assert.match(primarySignup, /Create your planner workspace/);
    assert.match(primarySignup, /person or team responsible for managing weddings/);
    assert.match(primarySignup, /Planning business or team name/);
    assert.match(primarySignup, /role: 'wedding_planner'/);
    assert.match(primarySignup, /href="\/terms"/);
    assert.match(primarySignup, /href="\/privacy"/);

    assert.match(alternateSignup, /Launch your planner workspace/);
    assert.match(alternateSignup, /workspace used by the person or team managing weddings/);
    assert.match(alternateSignup, /Planning business or team name/);
    assert.match(alternateSignup, /role: 'wedding_planner'/);
  });

  it('keeps the public vendor directory focused on planner discovery while vendor signup is not ready', () => {
    const navigation = readSource('app/components/saas/SaasNav.tsx');
    const directory = readSource('app/vendors/VendorsDirectoryClient.tsx');

    // The nav CTA is the unified "Start free" signup label; the planner audience is
    // still signalled by the directory link, and vendor signup stays absent.
    assert.match(navigation, /Planner vendor directory/);
    assert.match(navigation, /Start free/);
    assert.doesNotMatch(navigation, /portal\/ads\/signup/);
    assert.doesNotMatch(navigation, /List your business|Vendor sign ?up/i);
    assert.match(directory, /Use this directory to discover vendors for the weddings you manage/);
    assert.doesNotMatch(directory, /portal\/ads\/signup/);
    assert.doesNotMatch(directory, /List Your Business/);
  });

  it('orients new planners and preserves the assigned-team-member empty state', () => {
    const onboarding = readSource('app/admin/components/OnboardingModal.tsx');
    const dashboard = readSource('app/admin/planner/page.tsx');

    assert.match(onboarding, /This Is Your Planner Workspace/);
    assert.match(onboarding, /Create one workspace for each wedding you manage/);
    assert.match(dashboard, /userProfile\?\.is_team_member \? \(/);
    assert.match(dashboard, /No weddings assigned/);
    assert.match(dashboard, /Add your first wedding/);
    assert.match(dashboard, /\/admin\/support\?tab=knowledge_base/);
  });
});
