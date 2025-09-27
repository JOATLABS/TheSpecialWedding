'use client';

import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

import { SECURE_ROUTES } from '@/admin/config/routePolicy';
import { normalizeRole, type NormalizedRole } from '@/admin/utils/role';
import { useAdmin } from '@/contexts/AdminContext';

const ROLE_HOME_ROUTE: Partial<Record<NormalizedRole, string>> = {
  ROOT_ADMIN: '/admin/saas',
  WEDDING_PLANNER: '/admin/planner',
  VENDOR: '/admin/vendor',
};

function resolveRoleDestination(role: NormalizedRole): string {
  if (role in ROLE_HOME_ROUTE) {
    return ROLE_HOME_ROUTE[role as keyof typeof ROLE_HOME_ROUTE] ?? '/admin/login';
  }

  const defaultSecureRoute = SECURE_ROUTES.find((route) => route.path !== '/admin');
  return defaultSecureRoute?.path ?? '/admin/login';
}

export default function AdminLandingPage() {
  const router = useRouter();
  const {
    isAuthenticated,
    isSessionInitialized,
    token,
    userProfile,
    fetchUserProfile,
  } = useAdmin();
  const hasRequestedProfile = useRef(false);

  useEffect(() => {
    if (!isSessionInitialized) {
      return;
    }

    if (!isAuthenticated || !token) {
      hasRequestedProfile.current = false;
      router.replace('/admin/login');
      return;
    }

    if (!userProfile) {
      if (hasRequestedProfile.current) {
        return;
      }

      hasRequestedProfile.current = true;
      fetchUserProfile().catch((error) => {
        console.error('Admin landing failed to hydrate profile', error);
        hasRequestedProfile.current = false;
        router.replace('/admin/login');
      });
      return;
    }

    const role = normalizeRole(userProfile);
    const destination = resolveRoleDestination(role);

    router.replace(destination);
  }, [
    fetchUserProfile,
    isAuthenticated,
    isSessionInitialized,
    router,
    token,
    userProfile,
  ]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-wedding-ivory text-sm text-gray-500">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-500" />
      <p className="mt-4">Preparing your dashboard…</p>
    </div>
  );
}
