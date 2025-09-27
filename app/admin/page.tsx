'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { normalizeRole, type NormalizedRole } from '@/admin/utils/role';

export default function AdminDashboardPage() {
  const { token, userProfile, fetchUserProfile, isSessionInitialized } = useAdmin();
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isSessionInitialized) {
      return;
    }

    if (!token) {
      setLoading(false);
      router.replace('/admin/login');
      return;
    }

    if (userProfile) {
      setLoading(false);
      return;
    }

    let isMounted = true;

    const initializeDashboard = async () => {
      try {
        await fetchUserProfile();
      } catch (error) {
        console.error('Failed to fetch user profile:', error);
        router.replace('/admin/login');
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    initializeDashboard();

    return () => {
      isMounted = false;
    };
  }, [isSessionInitialized, token, userProfile, fetchUserProfile, router]);

  useEffect(() => {
    // Redirect based on role when profile is available
    if (loading || !userProfile) {
      return;
    }
    const role = normalizeRole(userProfile);
    redirectToRoleDashboard(role);
  }, [userProfile, loading, router]);

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
        // SECURITY: Unknown role - redirect to login
        console.warn(`Unknown role: ${role}`);
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