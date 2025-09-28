'use client';

import React, { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { normalizeRole } from '@/admin/utils/role';
import { AllowedRole } from '@/admin/config/routePolicy';
import { useAdmin } from '@/contexts/AdminContext';

interface AdminGuardProps {
  requiredRoles?: AllowedRole[];
  children: React.ReactNode;
}

export function AdminGuard({ requiredRoles, children }: AdminGuardProps) {
  const { userProfile, fetchUserProfile, isAuthenticated, token, isSessionInitialized } = useAdmin();
  const attemptedRef = useRef(false);
  const router = useRouter();

  useEffect(() => {
    if (!isSessionInitialized) {
      return;
    }

    if (!isAuthenticated || !token) {
      router.replace('/admin/login');
      return;
    }

    if (!userProfile && !attemptedRef.current) {
      attemptedRef.current = true;
      fetchUserProfile().catch(() => {
        console.error('Failed to fetch user profile');
        // Don't logout - middleware handles auth
      });
    }
  }, [userProfile, fetchUserProfile, isAuthenticated, token, isSessionInitialized, router]);

  // Show loading state while session is hydrating or profile is still loading
  if (!isSessionInitialized || !isAuthenticated || !token || !userProfile) {
    return (
      <div className="p-8 text-sm text-gray-500 animate-pulse">
        Loading user profile…
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