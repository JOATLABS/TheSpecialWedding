'use client';

import React, { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

export default function AdminRouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated } = useAdmin();

  useEffect(() => {
    // Skip check for login page
    if (pathname === '/admin/login') return;

    // Redirect to login if not authenticated
    if (!isAuthenticated && pathname.startsWith('/admin')) {
      router.push('/admin/login');
    }
  }, [isAuthenticated, pathname, router]);

  // Don't render protected content if not authenticated (except login page)
  if (!isAuthenticated && pathname.startsWith('/admin') && pathname !== '/admin/login') {
    return null;
  }

  return <>{children}</>;
}