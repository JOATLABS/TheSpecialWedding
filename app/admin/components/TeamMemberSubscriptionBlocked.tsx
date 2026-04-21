/**
 * TeamMemberSubscriptionBlocked — DEPRECATED, null export.
 *
 * This component previously rendered an in-app "Team access paused" shell
 * (Lock icon, mailto link to the owning planner, signout button) whenever
 * `AdminRouteGuard` detected `_subscription_blocked = true` on a team
 * member's profile.
 *
 * That shell has been superseded by PR1 Step 6 of the Team-Member
 * Subscription Gate: `AdminRouteGuard` now hard-logs-out the blocked team
 * member and redirects to `/admin/login?error=<reason>`, where Step 4's
 * inline banner surfaces the backend detail.
 *
 * Why we kept the file instead of deleting it:
 * - The component was imported in a few older places (tests, AGENTS.md
 *   references, doc examples). A null default export keeps those imports
 *   compiling while the call graph settles.
 * - The file path is referenced in `CLAUDE.md → "PR1 — Team-Member
 *   Subscription Gate"` Step 7. Leaving a neutralized stub makes the
 *   deprecation discoverable from that pointer.
 *
 * Do NOT add logic back to this file. If a new team-member block surface
 * is needed, build it at the login banner layer (Step 4) or a shared
 * billing-block state path (AGENTS.md → Known Open Issues, item 8).
 */
export default function TeamMemberSubscriptionBlocked(): null {
  return null;
}
