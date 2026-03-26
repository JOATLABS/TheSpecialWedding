'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

// Pages that expired/blocked planners are allowed to access
const BILLING_PATHS = [
  '/admin/login',
  '/admin/planner/billing',
  '/admin/billing',
];

function getRootAdminRedirect(path: string): string | null {
  if (path === '/admin/planner' || path.startsWith('/admin/planner/')) {
    return '/admin';
  }

  if (/^\/admin\/weddings\/[^/]+(?:\/.*)?$/.test(path)) {
    return '/admin/weddings';
  }

  return null;
}

function isAllowedForExpired(path: string): boolean {
  if (BILLING_PATHS.some((p) => path === p || path.startsWith(p + '/'))) return true;
  if (path.startsWith('/admin/team/accept')) return true;
  return false;
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
      router.push('/admin/login');
      return;
    }

    // Subscription gate: redirect expired/blocked planners to billing
    if (isAuthenticated && userProfile) {
      if (userProfile.is_root_admin) {
        const redirectPath = getRootAdminRedirect(pathname);
        if (redirectPath && redirectPath !== pathname) {
          router.replace(redirectPath);
          return;
        }
      }

      const ud = userProfile.user_data || {};
      const status = ud.subscription_status || userProfile.subscription_status;
      const isPlanner = userProfile.is_wedding_planner;
      const isBlocked = status && ['expired', 'cancelled', 'suspended', 'pending_payment'].includes(status);

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
    }

    const ud = userProfile.user_data || {};
    const status = ud.subscription_status || userProfile.subscription_status;
    const isPlanner = userProfile.is_wedding_planner;
    const isBlocked = status && ['expired', 'cancelled', 'suspended', 'pending_payment'].includes(status);

    if (isPlanner && isBlocked && !isAllowedForExpired(pathname)) {
      return null; // Don't render — useEffect above will redirect
    }
  }

  return <>{children}</>;
}
