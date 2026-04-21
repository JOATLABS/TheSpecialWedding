'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { isBlockedSubscriptionStatus, normalizeSubscriptionStatus } from '@/utils/subscriptionStatus';
import { isAllowedForExpired } from '@/utils/adminApiAuthGuard';
import { getSubscriptionBlockReason, isTeamMemberRole } from '@/utils/roles';

// Pages a blocked team member can still REACH without being force-logged-out.
// /admin/login is where they'll be deposited by the redirect, and
// /admin/team/accept must keep working so an invite acceptance flow isn't
// broken by a stale block tag. Anywhere else, we treat the block as a
// session-level event: hard-logout + redirect to /admin/login?error=<reason>
// so Step 4's banner surfaces the backend detail inline. See CLAUDE.md →
// "PR1 — Team-Member Subscription Gate" Step 6.
const TEAM_MEMBER_BLOCKED_ALLOWED_PATHS = [
  '/admin/login',
  '/admin/team/accept',
];

function isTeamMemberBlockedAllowedPath(path: string): boolean {
  return TEAM_MEMBER_BLOCKED_ALLOWED_PATHS.some(
    (p) => path === p || path.startsWith(p + '/'),
  );
}

function getRootAdminRedirect(path: string): string | null {
  if (path === '/admin/planner' || path.startsWith('/admin/planner/')) {
    return '/admin';
  }

  if (/^\/admin\/weddings\/[^/]+(?:\/.*)?$/.test(path)) {
    return '/admin/weddings';
  }

  return null;
}

// Inverse of getRootAdminRedirect: paths that ONLY root admins should access.
// Non-root users (planners, team members) hitting these get bounced to
// their own dashboard. Keep this list conservative — most /admin/* routes
// are shared between root admin and planners (guests, weddings, budget, etc.).
function getNonRootAdminRedirect(path: string): string | null {
  // `/admin` exactly is the Platform Health Overview — root admin only.
  if (path === '/admin') {
    return '/admin/planner';
  }
  return null;
}

export default function AdminRouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading, userProfile, logout } = useAdmin();

  useEffect(() => {
    // Don't do anything while still loading auth state
    if (isLoading) return;

    // Skip check for public pages (login, accept invite)
    if (pathname === '/admin/login') return;
    if (pathname.startsWith('/admin/team/accept')) return;

    // Redirect to login if not authenticated
    if (!isAuthenticated && pathname.startsWith('/admin')) {
      router.replace('/admin/login');
      return;
    }

    // Subscription gate: redirect unpaid/expired/blocked planners to billing
    if (isAuthenticated && userProfile) {
      if (userProfile.is_root_admin) {
        const redirectPath = getRootAdminRedirect(pathname);
        if (redirectPath && redirectPath !== pathname) {
          router.replace(redirectPath);
          return;
        }
      } else {
        // Planner or team member: keep them out of root-admin-only paths.
        const redirectPath = getNonRootAdminRedirect(pathname);
        if (redirectPath && redirectPath !== pathname) {
          router.replace(redirectPath);
          return;
        }
      }

      const ud = userProfile.user_data || {};
      const status = normalizeSubscriptionStatus(ud.subscription_status || userProfile.subscription_status);
      const isPlanner = userProfile.is_wedding_planner;
      const isBlocked = isBlockedSubscriptionStatus(status);

      if (isPlanner && isBlocked && !isAllowedForExpired(pathname)) {
        router.replace('/admin/planner/billing');
        return;
      }

      // Team-member subscription gate. Backend tags the profile with
      // `_subscription_blocked = true` whenever the owning planner is blocked.
      // Unlike the planner branch above, team members have no self-serve
      // billing surface — only the planner can resolve it. We therefore
      // treat the block as a session-level event: hard-logout + redirect to
      // /admin/login?error=<reason> so Step 4's banner surfaces the reason
      // inline. `logout()` does `window.location.replace(...)`, which is a
      // hard navigation and discards the stale in-memory profile. See
      // CLAUDE.md → "PR1 — Team-Member Subscription Gate" Step 6, and
      // AGENTS.md → "Known Open Issues" item 8 (future unification of
      // billing-block navigation target).
      const teamBlocked =
        userProfile._subscription_blocked === true && isTeamMemberRole(userProfile);
      if (teamBlocked && !isTeamMemberBlockedAllowedPath(pathname)) {
        const reason = getSubscriptionBlockReason(userProfile);
        logout({
          message: reason,
          redirectTo: `/admin/login?error=${encodeURIComponent(reason)}`,
          showToast: false,
        });
        return;
      }
    }
  }, [isAuthenticated, isLoading, logout, pathname, router, userProfile]);

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-light-bg dark:bg-dark-bg">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto"></div>
          <p className="mt-4 text-slate-600 dark:text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render protected content if not authenticated (except public pages)
  if (!isAuthenticated && pathname.startsWith('/admin') && pathname !== '/admin/login' && !pathname.startsWith('/admin/team/accept')) {
    return null;
  }

  // Don't render feature pages for blocked planners or team members — the
  // useEffect above has already scheduled the redirect or logout. Rendering
  // nothing here prevents the normal dashboard from firing its gated feature
  // endpoints and producing raw 402 console noise during the brief window
  // before the hard navigation fires.
  if (isAuthenticated && userProfile) {
    if (userProfile.is_root_admin) {
      const redirectPath = getRootAdminRedirect(pathname);
      if (redirectPath && redirectPath !== pathname) {
        return null;
      }
    } else {
      const redirectPath = getNonRootAdminRedirect(pathname);
      if (redirectPath && redirectPath !== pathname) {
        return null;
      }
    }

    const ud = userProfile.user_data || {};
    const status = normalizeSubscriptionStatus(ud.subscription_status || userProfile.subscription_status);
    const isPlanner = userProfile.is_wedding_planner;
    const isBlocked = isBlockedSubscriptionStatus(status);

    if (isPlanner && isBlocked && !isAllowedForExpired(pathname)) {
      return null; // Don't render — useEffect above will redirect
    }

    const teamBlocked =
      userProfile._subscription_blocked === true && isTeamMemberRole(userProfile);
    if (teamBlocked && !isTeamMemberBlockedAllowedPath(pathname)) {
      return null; // Don't render — useEffect above will logout + redirect
    }
  }

  return <>{children}</>;
}
