'use client';

import React, { useEffect, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { normalizeRole } from '@/admin/utils/role';
import { AllowedRole } from '@/admin/config/routePolicy';
import { useAdmin } from '@/contexts/AdminContext';

interface AdminGuardProps {
  requiredRoles?: AllowedRole[];
  children: React.ReactNode;
}

export function AdminGuard({ requiredRoles, children }: AdminGuardProps) {
  const { isAuthenticated, userProfile, fetchUserProfile, token, logout } = useAdmin();
  const router = useRouter();
  const pathname = usePathname();
  const attemptedRef = useRef(false);

  useEffect(() => {
    if (!isAuthenticated || !token) {
      if (!pathname.startsWith('/admin/login')) {
        router.replace('/admin/login');
      }
      return;
    }
    if (!userProfile && !attemptedRef.current) {
      attemptedRef.current = true;
      fetchUserProfile().catch(() => {
        logout();
        router.replace('/admin/login');
      });
    }
  }, [isAuthenticated, token, userProfile, fetchUserProfile, router, pathname, logout]);

  if (!isAuthenticated || !token || !userProfile) {
    return (
      <div className="p-8 text-sm text-gray-500 animate-pulse">
        Securing admin area…
      </div>
    );
  }

  if (requiredRoles && requiredRoles.length > 0) {
    const role = normalizeRole(userProfile);
    if (!requiredRoles.includes(role as any)) {
      return (
        <div className="p-8 text-red-500 font-medium">
          Access denied for this role.
        </div>
      );
    }
  }

  return <>{children}</>;
}