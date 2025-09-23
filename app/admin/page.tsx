'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { AdminGuard } from '@/admin/components/AdminGuard';

export default function AdminDashboardPage() {
  const { token, userProfile, fetchUserProfile } = useAdmin();
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initializeDashboard = async () => {
      if (!token) {
        router.push('/admin/login');
        return;
      }

      try {
        // Fetch user profile if not already loaded
        if (!userProfile) {
          await fetchUserProfile();
        }
      } catch (error) {
        console.error('Failed to fetch user profile:', error);
        router.push('/admin/login');
      } finally {
        setLoading(false);
      }
    };

    initializeDashboard();
  }, [token, fetchUserProfile, router]);

  useEffect(() => {
    // Redirect based on role when profile is available
    if (userProfile && !loading) {
      redirectToRoleDashboard(userProfile.role);
    }
  }, [userProfile, loading, router]);

  const redirectToRoleDashboard = (role: string) => {
    switch (role) {
      case 'ROOT_ADMIN':
        router.push('/admin/weddings');
        break;
      case 'admin':
        router.push('/admin/forms');
        break;
      case 'planner':
        router.push('/admin/weddings');
        break;
      default:
        // SECURITY: Unknown role - redirect to login
        console.warn(`Unknown role: ${role}`);
        router.push('/admin/login');
    }
  };

  if (loading) {
    return (
      <AdminGuard>
        <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-wedding-rose mx-auto"></div>
            <p className="mt-4 text-gray-600 dark:text-gray-400">Loading dashboard...</p>
          </div>
        </div>
      </AdminGuard>
    );
  }

  // This component primarily handles redirects
  // The actual dashboard content is rendered in role-specific pages
  return (
    <AdminGuard>
      <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-wedding-rose mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Redirecting to your dashboard...</p>
        </div>
      </div>
    </AdminGuard>
  );
}