import type { UserProfile } from '@/contexts/AdminContext';

// Internal entitlement plan backing the self-serve couple offer — must match
// app/constants/billing.py::COUPLE_PLAN_ID. The couple-plan purchaser uses
// the planner dashboard for their own single wedding; exactly four surfaces
// are gated (operator ruling 2026-07-28, backend-enforced — the UI hiding
// here is a courtesy, not the barrier):
//   1. couple-portal invitations (they ARE the couple),
//   2. service packages (planner-to-client feature),
//   3. team member seats,
//   4. creating a second wedding.
export const COUPLE_PLAN_ID = 'plan_couple';

// Locked copy. Never say "lifetime" — the workspace closes 90 days after the
// wedding date.
export const COUPLE_PLAN_ONE_WEDDING_COPY =
  'The couple plan covers one wedding — your workspace already includes it.';
export const INCLUDED_WITH_PLANNER_PLANS_COPY = 'Included with planner plans.';

// Sidebar items that never render for a couple-plan workspace.
export const COUPLE_PLAN_HIDDEN_NAV_NAMES = new Set(['Packages', 'Team']);

export function isCouplePlan(userProfile?: UserProfile | null): boolean {
  if (!userProfile) return false;
  return (
    userProfile.plan_id === COUPLE_PLAN_ID ||
    userProfile.user_data?.plan_id === COUPLE_PLAN_ID
  );
}
