'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

interface UserProfile {
  email: string;
  role: string;
  company_name?: string;
  subscription_plan_id?: string;
  subscription_status?: string;
  is_active: boolean;
}

export default function AdminDashboardPage() {
  const { token } = useAdmin();
  const router = useRouter();
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
      return;
    }

    fetchUserProfile();
  }, [token, router]);

  const fetchUserProfile = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/profile?t=${Date.now()}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache'
        },
        cache: 'no-store',
      });

      if (response.ok) {
        const profile = await response.json();
        setUserProfile(profile);
        
        // Redirect based on role
        redirectToRoleDashboard(profile.role);
      } else {
        // If profile fetch fails, try to determine role from JWT payload
        if (token) {
          const payload = parseJwtPayload(token);
          if (payload?.role) {
            redirectToRoleDashboard(payload.role);
          } else {
            // Fallback to SAAS dashboard for unknown roles
            router.push('/admin/saas');
          }
        } else {
          router.push('/admin/login');
        }
      }
    } catch (error) {
      console.error('Failed to fetch user profile:', error);
      // Fallback to SAAS dashboard on error
      router.push('/admin/saas');
    } finally {
      setLoading(false);
    }
  };

  const parseJwtPayload = (token: string) => {
    try {
      const payload = token.split('.')[1];
      const decoded = atob(payload);
      return JSON.parse(decoded);
    } catch (error) {
      console.error('Failed to parse JWT:', error);
      return null;
    }
  };

  const redirectToRoleDashboard = (role: string) => {
    switch (role) {
      case 'ROOT_ADMIN':
      case 'admin':
        router.push('/admin/saas');
        break;
      case 'wedding_planner':
        router.push('/admin/planner');
        break;
      case 'vendor':
        router.push('/admin/vendor');
        break;
      default:
        // Unknown role - default to SAAS dashboard
        router.push('/admin/saas');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  // This should not render as we redirect immediately
  return null;
}