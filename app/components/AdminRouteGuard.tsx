'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { getRootCommunicationsRedirect } from '@/admin/utils/communicationsAccess';
import { applyBillingBlockTarget } from '@/utils/adminApiAuthGuard';

function getRootAdminRedirect(path: string): string | null {
  const communicationsRedirect = getRootCommunicationsRedirect(path);
  if (communicationsRedirect) return communicationsRedirect;

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
  const { isAuthenticated, isLoading, userProfile, logout, billingBlockTarget } = useAdmin();
  const isPublicPage = pathname === '/admin/login' || pathname.startsWith('/admin/team/accept');

  useEffect(() => {
    // Don't do anything while still loading auth state
    if (isLoading) return;

    // Skip check for public pages (login, accept invite)
    if (isPublicPage) return;

    // Redirect to login if not authenticated
    if (!isAuthenticated && pathname.startsWith('/admin')) {
      router.replace('/admin/login');
      return;
    }

    // Subscription gate: redirect unpaid/expired/blocked planners to billing
    if (isAuthenticated && userProfile) {
      if (billingBlockTarget) {
        applyBillingBlockTarget(billingBlockTarget, { router, logout });
        return;
      }

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

    }
  }, [billingBlockTarget, isAuthenticated, isLoading, isPublicPage, logout, pathname, router, userProfile]);

  if (isPublicPage) {
    return <>{children}</>;
  }

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
  if (!isAuthenticated && pathname.startsWith('/admin')) {
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

    if (billingBlockTarget) {
      return null; // Don't render — useEffect above will redirect
    }
  }

  return <>{children}</>;
}
