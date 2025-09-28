'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { SECURE_ROUTES } from '@/admin/config/routePolicy';
import { normalizeRole, type NormalizedRole } from '@/admin/utils/role';
import { useAdmin } from '@/contexts/AdminContext';

const ROLE_HOME_ROUTE: Partial<Record<NormalizedRole, string>> = {
  ROOT_ADMIN: '/admin/saas',
  WEDDING_PLANNER: '/admin/planner',
  VENDOR: '/admin/vendor',
};

function sanitizeNextPath(rawValue: string | null): string | null {
  if (!rawValue) {
    return null;
  }

  if (!rawValue.startsWith('/admin')) {
    return null;
  }

  if (rawValue.includes('..')) {
    return null;
  }

  return rawValue;
}

function resolveRoleDestination(role: NormalizedRole, fallback: string | null): string | null {
  if (fallback) {
    return fallback;
  }

  if (role in ROLE_HOME_ROUTE) {
    return ROLE_HOME_ROUTE[role as keyof typeof ROLE_HOME_ROUTE] ?? null;
  }

  const defaultSecureRoute = SECURE_ROUTES.find((route) => route.path !== '/admin');
  return defaultSecureRoute?.path ?? null;
}

export default function AdminLandingPage() {
  const { isSessionInitialized, isAuthenticated, token, userProfile, fetchUserProfile } = useAdmin();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [pendingDestination, setPendingDestination] = useState<string | null>(null);
  const [redirectError, setRedirectError] = useState<string | null>(null);
  const [isFetchingProfile, setIsFetchingProfile] = useState(false);

  const hasRequestedProfile = useRef(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const requestedNext = useMemo(() => sanitizeNextPath(searchParams?.get('next') ?? null), [searchParams]);

  useEffect(() => {
    if (!isSessionInitialized) {
      return;
    }

    if (!isAuthenticated || !token) {
      if (mountedRef.current) {
        setRedirectError('UNAUTHENTICATED');
      }
      return;
    }

    const applyDestination = (profile: unknown) => {
      const normalizedRole = normalizeRole(profile as Record<string, unknown> | null | undefined);
      const target = resolveRoleDestination(normalizedRole, requestedNext);

      if (!target) {
        console.error('Admin landing: unable to resolve dashboard destination for role', {
          normalizedRole,
          requestedNext,
        });
        if (mountedRef.current) {
          setRedirectError('UNKNOWN_ROLE');
        }
        return;
      }

      if (mountedRef.current) {
        setPendingDestination(target);
      }
    };

    if (userProfile) {
      applyDestination(userProfile);
      return;
    }

    if (hasRequestedProfile.current) {
      return;
    }

    hasRequestedProfile.current = true;
    if (mountedRef.current) {
      setIsFetchingProfile(true);
    }

    fetchUserProfile()
      .then((profile) => {
        if (!mountedRef.current) {
          return;
        }

        if (!profile) {
          setRedirectError('PROFILE_UNAVAILABLE');
          return;
        }

        applyDestination(profile);
      })
      .catch((error) => {
        console.error('Admin landing profile fetch failed', error);
        if (mountedRef.current) {
          setRedirectError('PROFILE_ERROR');
        }
      })
      .finally(() => {
        if (mountedRef.current) {
          setIsFetchingProfile(false);
        }
      });
  }, [
    fetchUserProfile,
    isAuthenticated,
    isSessionInitialized,
    requestedNext,
    token,
    userProfile,
  ]);

  useEffect(() => {
    if (!pendingDestination) {
      return;
    }

    router.replace(pendingDestination);
  }, [pendingDestination, router]);

  useEffect(() => {
    if (!redirectError) {
      return;
    }

    router.replace('/admin/login');
  }, [redirectError, router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white px-4 text-gray-600">
      <div className="flex flex-col items-center space-y-3 text-center">
        <div className="h-12 w-12 animate-spin rounded-full border-2 border-rose-400 border-t-transparent" />
        <p className="text-sm font-medium tracking-wide">
          {isFetchingProfile ? 'Loading your dashboard…' : 'Preparing your admin workspace…'}
        </p>
        <p className="text-xs text-gray-400">Please keep this tab open while we verify your session.</p>
      </div>
    </div>
  );
}
