'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

export default function AdminRouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAdmin();

  useEffect(() => {
    // Don't do anything while still loading auth state
    if (isLoading) return;

    // Skip check for public pages (login, accept invite)
    if (pathname === '/admin/login') return;
    if (pathname.startsWith('/admin/team/accept')) return;

    // Redirect to login if not authenticated
    if (!isAuthenticated && pathname.startsWith('/admin')) {
      router.push('/admin/login');
    }
  }, [isAuthenticated, isLoading, pathname, router]);

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

  return <>{children}</>;
}
