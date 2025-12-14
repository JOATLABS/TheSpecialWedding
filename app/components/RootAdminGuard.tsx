'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

interface RootAdminGuardProps {
  children: React.ReactNode;
  fallbackPath?: string;
}

/**
 * RootAdminGuard - Protects routes that should only be accessible to ROOT_ADMIN users
 *
 * This component provides role-based access control for sensitive admin pages like:
 * - SaaS configuration and management
 * - Platform-wide analytics
 * - Wedding planner account management
 * - Subscription plan management
 *
 * Regular wedding planners will be redirected to their dashboard.
 *
 * @param children - The protected content to render if user is ROOT_ADMIN
 * @param fallbackPath - Where to redirect non-root admins (default: /admin)
 */
export default function RootAdminGuard({ children, fallbackPath = '/admin' }: RootAdminGuardProps) {
  const router = useRouter();
  const { isAuthenticated, userProfile, fetchUserProfile } = useAdmin();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const checkRootAdminAccess = async () => {
      // If not authenticated, the AdminRouteGuard will handle redirect to login
      if (!isAuthenticated) {
        setIsChecking(false);
        return;
      }

      // If we don't have user profile yet, try to fetch it
      if (!userProfile) {
        await fetchUserProfile();
        // Give it a moment to load
        setTimeout(() => setIsChecking(false), 500);
        return;
      }

      // Check if user is ROOT_ADMIN
      if (!userProfile.is_root_admin) {
        console.warn('Access denied: ROOT_ADMIN role required');
        router.push(fallbackPath);
        return;
      }

      // User is ROOT_ADMIN, allow access
      setIsChecking(false);
    };

    checkRootAdminAccess();
  }, [isAuthenticated, userProfile, router, fallbackPath, fetchUserProfile]);

  // Show loading state while checking permissions
  if (isChecking || !userProfile) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Verifying permissions...</p>
        </div>
      </div>
    );
  }

  // Only render children if user is ROOT_ADMIN
  if (!userProfile.is_root_admin) {
    return null;
  }

  return <>{children}</>;
}
