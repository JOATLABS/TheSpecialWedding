'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import { useCoupleAuth } from '@/contexts/CoupleAuthContext';

function isPublicCouplePath(pathname: string): boolean {
  return (
    pathname === '/couple/login' ||
    pathname.startsWith('/couple/setup') ||
    pathname.startsWith('/couple/forgot-password') ||
    pathname.startsWith('/couple/reset-password')
  );
}

export default function CoupleRouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { authErrorKind, authErrorMessage, isAuthenticated, isLoading } = useCoupleAuth();

  const isPublicPage = isPublicCouplePath(pathname);

  useEffect(() => {
    if (isLoading || isPublicPage) {
      return;
    }

    if (!isAuthenticated) {
      const params = new URLSearchParams();
      if (authErrorMessage) {
        params.set('message', authErrorMessage);
      }
      if (authErrorKind === 'blocked') {
        params.set('access', 'blocked');
      }

      const redirectTarget = params.toString()
        ? `/couple/login?${params.toString()}`
        : '/couple/login';
      router.replace(redirectTarget);
    }
  }, [authErrorKind, authErrorMessage, isAuthenticated, isLoading, isPublicPage, router]);

  if (isPublicPage) {
    return <>{children}</>;
  }

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

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
