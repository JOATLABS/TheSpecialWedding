/**
 * Role-centralization helpers for admin-side code paths.
 *
 * Mirrors the Python `app/utils/planner_billing_scope.is_planner_billing_role`
 * pattern — an isolated predicate module so callsites import from one place
 * instead of repeating `profile.role === 'team_member' || profile.is_team_member === true`
 * across the frontend. See CLAUDE.md → "Roles must move toward a centralized enum".
 *
 * Structural `ProfileLike` accepts both the full AdminContext `UserProfile` and
 * the thin subset `AdminRouteGuard` works with — avoids an import cycle with
 * AdminContext.
 *
 * Scope: only two helpers live here today (isTeamMemberRole,
 * getSubscriptionBlockReason). New role callsites should import from here;
 * existing scattered checks should be folded in opportunistically when the
 * surrounding code is already being touched, not via a mass rewrite.
 */

export interface ProfileLike {
  role?: string;
  is_team_member?: boolean;
  _subscription_block_reason?: string;
  user_data?:
    | {
        _subscription_block_reason?: string;
      }
    | null;
}

/**
 * True when the profile represents a team member. Matches both legacy
 * `role === 'team_member'` and the explicit boolean tag added during PR1
 * profile hydration.
 */
export function isTeamMemberRole(
  profile: ProfileLike | null | undefined,
): boolean {
  if (!profile) return false;
  return profile.is_team_member === true || profile.role === 'team_member';
}

/**
 * Fallback copy for team-member subscription-block redirects when the backend
 * has not (yet) provided a detail string. Keep in sync with
 * `app/utils/team_subscription_gate.py::build_team_member_block_reason` — that
 * backend helper produces a richer string including the owner's email and the
 * subscription status when those are available; this constant is the best
 * neutral phrasing when neither is.
 */
export const DEFAULT_TEAM_MEMBER_BLOCK_REASON =
  "Your team's subscription requires attention. Please contact your planner to restore access.";

/**
 * Best-effort extraction of the subscription-block reason from a tagged
 * profile. Falls back to `DEFAULT_TEAM_MEMBER_BLOCK_REASON` when neither the
 * top-level nor the `user_data` nested field is set.
 *
 * Preserves the dual-shape read that used to live inline in
 * TeamMemberSubscriptionBlocked — some profile hydration paths put the reason
 * at the top level; others nest it under `user_data`.
 */
export function getSubscriptionBlockReason(
  profile: ProfileLike | null | undefined,
): string {
  if (!profile) return DEFAULT_TEAM_MEMBER_BLOCK_REASON;
  const fromTop = profile._subscription_block_reason;
  const fromUserData = profile.user_data?._subscription_block_reason;
  const candidate =
    (fromTop && fromTop.trim()) || (fromUserData && fromUserData.trim());
  return candidate ? candidate : DEFAULT_TEAM_MEMBER_BLOCK_REASON;
}
