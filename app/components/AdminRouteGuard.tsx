'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { isBlockedSubscriptionStatus, normalizeSubscriptionStatus } from '@/utils/subscriptionStatus';
import { isAllowedForExpired } from '@/utils/adminApiAuthGuard';
import TeamMemberSubscriptionBlocked from '@/admin/components/TeamMemberSubscriptionBlocked';

// Pages a blocked team member can still see. We keep this conservative —
// the whole point of the gate is to stop the dashboard + its 402-noisy
// feature fetches from rendering. Kept separate from planner-billing paths
// in adminApiAuthGuard because team-member block UX is distinct (no self-
// serve billing page; they contact the planner).
const TEAM_MEMBER_BLOCKED_ALLOWED_PATHS = [
  '/admin/login',
  '/admin/team/accept',
];

function isTeamMemberBlockedAllowedPath(path: string): boolean {
  return TEAM_MEMBER_BLOCKED_ALLOWED_PATHS.some(
    (p) => path === p || path.startsWith(p + '/'),
  );
}

function isTeamMemberRole(profile: { role?: string; is_team_member?: boolean } | null | undefined): boolean {
  if (!profile) return false;
  return profile.is_team_member === true || profile.role === 'team_member';
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
  const { isAuthenticated, isLoading, userProfile } = useAdmin();

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
      }
    }
  }, [isAuthenticated, isLoading, pathname, router, userProfile]);

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

  // Don't render feature pages for blocked planners — they'll be redirected
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

    // Team-member subscription gate: when the parent planner's subscription
    // is blocked, the backend tags the team member's profile with
    // _subscription_blocked=true. Render a dedicated blocked shell so the
    // team member never sees the normal dashboard (which would fire every
    // gated feature endpoint and surface raw 402 console errors).
    //
    // We DO NOT redirect — there's no team-member-owned billing page, only
    // the planner can resolve this. The shell tells them to contact the
    // planner and lets them sign out.
    const teamBlocked =
      userProfile._subscription_blocked === true && isTeamMemberRole(userProfile);
    if (teamBlocked && !isTeamMemberBlockedAllowedPath(pathname)) {
      return <TeamMemberSubscriptionBlocked />;
    }
  }

  return <>{children}</>;
}
