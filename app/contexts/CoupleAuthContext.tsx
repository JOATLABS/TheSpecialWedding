'use client';

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';

import { coupleFetch, extractApiErrorMessage, logoutCoupleSession } from '@/couple/lib/auth';

interface CoupleProfile {
  id: string;
  email: string;
  partner1_name?: string;
  partner2_name?: string;
  wedding_id?: string;
  access_state?: string;
  portal_access_state?: string;
  portal_access_detail?: string | null;
  onboarding_completed?: boolean;
  onboarding_completed_at?: string | null;
  onboarding_steps_completed?: string[];
}

type CoupleAuthStatus = 'loading' | 'authenticated' | 'unauthenticated';
type CoupleAuthErrorKind = 'blocked' | 'unauthenticated';

interface CoupleSessionResult {
  status: 'success' | 'blocked' | 'unauthenticated' | 'error';
  message?: string | null;
}

interface CoupleAuthContextType {
  authStatus: CoupleAuthStatus;
  isAuthenticated: boolean;
  isLoading: boolean;
  coupleProfile: CoupleProfile | null;
  authErrorMessage: string | null;
  authErrorKind: CoupleAuthErrorKind | null;
  logout: (options?: { redirectTo?: string }) => Promise<void>;
  expireSession: (message?: string) => Promise<void>;
  revalidateSession: () => Promise<CoupleSessionResult>;
}

const CoupleAuthContext = createContext<CoupleAuthContextType | null>(null);

function isPublicCouplePath(pathname: string): boolean {
  return (
    pathname === '/couple/login' ||
    pathname.startsWith('/couple/setup') ||
    pathname.startsWith('/couple/forgot-password') ||
    pathname.startsWith('/couple/reset-password')
  );
}

export function CoupleAuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [authStatus, setAuthStatus] = useState<CoupleAuthStatus>('loading');
  const [isLoading, setIsLoading] = useState(true);
  const [coupleProfile, setCoupleProfile] = useState<CoupleProfile | null>(null);
  const [authErrorMessage, setAuthErrorMessage] = useState<string | null>(null);
  const [authErrorKind, setAuthErrorKind] = useState<CoupleAuthErrorKind | null>(null);
  const sessionCheckRef = useRef<Promise<CoupleSessionResult> | null>(null);
  const lastSessionCheckAtRef = useRef(0);

  const fetchCoupleProfile = useCallback(async () => {
    try {
      const response = await coupleFetch('/couple/profile', {
        cache: 'no-store',
      });

      if (response.ok) {
        const profile = await response.json();
        setCoupleProfile(profile);
        setAuthStatus('authenticated');
        setAuthErrorMessage(null);
        setAuthErrorKind(null);
        return { status: 'success', message: null } as const;
      }

      if (response.status === 401 || response.status === 403 || response.status === 404) {
        const detail = await extractApiErrorMessage(
          response,
          response.status === 403
            ? 'This wedding portal is currently unavailable.'
            : 'Session expired. Please sign in again.',
        );

        setCoupleProfile(null);
        setAuthStatus('unauthenticated');
        setAuthErrorMessage(detail);
        setAuthErrorKind(response.status === 403 ? 'blocked' : 'unauthenticated');
        return {
          status: response.status === 403 ? 'blocked' : 'unauthenticated',
          message: detail,
        } as const;
      }

      return { status: 'error', message: null } as const;
    } catch {
      return { status: 'error', message: null } as const;
    }
  }, []);

  const logout = useCallback(async (options?: { redirectTo?: string }) => {
    const redirectTo = options?.redirectTo ?? '/couple/login';

    try {
      await logoutCoupleSession();
    } finally {
      setCoupleProfile(null);
      setAuthStatus('unauthenticated');
      setAuthErrorMessage(null);
      setAuthErrorKind(null);
      window.location.replace(redirectTo);
    }
  }, []);

  const expireSession = useCallback(async (message = 'Session expired. Please sign in again.') => {
    await logout({
      redirectTo: `/couple/login?message=${encodeURIComponent(message)}`,
    });
  }, [logout]);

  const revalidateSession = useCallback(async (): Promise<CoupleSessionResult> => {
    if (sessionCheckRef.current) {
      return sessionCheckRef.current;
    }

    sessionCheckRef.current = (async () => {
      try {
        return await fetchCoupleProfile();
      } finally {
        sessionCheckRef.current = null;
      }
    })();

    return sessionCheckRef.current;
  }, [fetchCoupleProfile]);

  useEffect(() => {
    let cancelled = false;
    const publicPath = isPublicCouplePath(pathname);

    if (publicPath) {
      setAuthStatus('unauthenticated');
      setCoupleProfile(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    void (async () => {
      const result = await fetchCoupleProfile();
      if (cancelled) {
        return;
      }

      if (result.status === 'error') {
        setAuthStatus((current) => (current === 'authenticated' ? current : 'unauthenticated'));
      }

      setIsLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [fetchCoupleProfile, pathname]);

  useEffect(() => {
    if (typeof window === 'undefined' || isPublicCouplePath(pathname)) {
      return;
    }

    const maybeRevalidate = () => {
      if (document.hidden) {
        return;
      }

      const now = Date.now();
      if (now - lastSessionCheckAtRef.current < 15_000) {
        return;
      }
      lastSessionCheckAtRef.current = now;

      void (async () => {
        const shouldCheck = authStatus === 'authenticated' || !!coupleProfile;
        if (!shouldCheck) {
          return;
        }

        const result = await revalidateSession();
        if (result.status === 'unauthenticated' || result.status === 'blocked') {
          await expireSession(result.message ?? undefined);
        }
      })();
    };

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        maybeRevalidate();
      }
    };

    window.addEventListener('focus', maybeRevalidate);
    window.addEventListener('pageshow', maybeRevalidate);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('focus', maybeRevalidate);
      window.removeEventListener('pageshow', maybeRevalidate);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [authStatus, coupleProfile, expireSession, pathname, revalidateSession]);

  return (
    <CoupleAuthContext.Provider
      value={{
        authStatus,
        isAuthenticated: authStatus === 'authenticated',
        isLoading,
        coupleProfile,
        authErrorMessage,
        authErrorKind,
        logout,
        expireSession,
        revalidateSession,
      }}
    >
      {children}
    </CoupleAuthContext.Provider>
  );
}

export function useCoupleAuth() {
  const context = useContext(CoupleAuthContext);
  if (!context) {
    throw new Error('useCoupleAuth must be used within CoupleAuthProvider');
  }
  return context;
}
