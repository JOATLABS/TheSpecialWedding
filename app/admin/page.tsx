'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { normalizeRole, type NormalizedRole } from '@/admin/utils/role';

export default function AdminDashboardPage() {
  const { token, userProfile, fetchUserProfile, isSessionInitialized, isAuthenticated } = useAdmin();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const hasRequestedProfile = useRef(false);
  const hasRedirected = useRef(false);

  useEffect(() => {
    if (!isSessionInitialized) {
      return;
    }

    if (!token || !isAuthenticated) {
      setLoading(false);
      if (!hasRedirected.current) {
        hasRedirected.current = true;
        router.replace('/admin/login');
      }
      return;
    }

    if (userProfile) {
      setLoading(false);
      if (!hasRedirected.current) {
        hasRedirected.current = true;
        const role = normalizeRole(userProfile);
        redirectToRoleDashboard(role);
      }
      return;
    }

    if (hasRequestedProfile.current) {
      return;
    }

    hasRequestedProfile.current = true;
    let isActive = true;

    fetchUserProfile()
      .then(profile => {
        if (!isActive) return;
        if (!profile) {
          if (!hasRedirected.current) {
            hasRedirected.current = true;
            router.replace('/admin/login');
          }
          return;
        }

        if (!hasRedirected.current) {
          hasRedirected.current = true;
          const role = normalizeRole(profile);
          redirectToRoleDashboard(role);
        }
      })
      .catch((error) => {
        if (!isActive) return;
        console.error('Failed to fetch user profile for admin landing:', error);
        if (!hasRedirected.current) {
          hasRedirected.current = true;
          router.replace('/admin/login');
        }
      })
      .finally(() => {
        if (isActive) {
          setLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [isSessionInitialized, token, isAuthenticated, userProfile, fetchUserProfile, router]);

  useEffect(() => {
    hasRequestedProfile.current = false;
    hasRedirected.current = false;
    setLoading(true);
  }, [token, isAuthenticated]);

  const redirectToRoleDashboard = (role: NormalizedRole) => {
    switch (role) {
      case 'ROOT_ADMIN':
        router.replace('/admin/saas');
        break;
      case 'WEDDING_PLANNER':
        router.replace('/admin/weddings');
        break;
      case 'VENDOR':
        router.replace('/admin/vendor');
        break;
      default:
        console.warn(`Unknown or unsupported admin role encountered: ${role}`);
        router.replace('/admin/login');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-500 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  // This component primarily handles redirects
  // The actual dashboard content is rendered in role-specific pages
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-500 mx-auto"></div>
        <p className="mt-4 text-gray-600 dark:text-gray-400">Redirecting to your dashboard...</p>
      </div>
    </div>
  );
}