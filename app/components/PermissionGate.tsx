'use client';

import React from 'react';
import { useAdmin } from '@/contexts/AdminContext';

interface PermissionGateProps {
  children: React.ReactNode;
  roles?: string[];
  requireRootAdmin?: boolean;
  requireWeddingPlanner?: boolean;
  requireVendor?: boolean;
  fallback?: React.ReactNode;
  hideWhenDenied?: boolean;
}

export const PermissionGate: React.FC<PermissionGateProps> = ({
  children,
  roles = [],
  requireRootAdmin = false,
  requireWeddingPlanner = false,
  requireVendor = false,
  fallback = null,
  hideWhenDenied = true
}) => {
  const { userProfile } = useAdmin();

  if (!userProfile) {
    return hideWhenDenied ? null : (fallback || <div>Authentication required</div>);
  }

  // Check specific role requirements
  if (requireRootAdmin && !userProfile.is_root_admin) {
    return hideWhenDenied ? null : (fallback || <div>Admin access required</div>);
  }

  if (requireWeddingPlanner && !userProfile.is_wedding_planner) {
    return hideWhenDenied ? null : (fallback || <div>Wedding planner access required</div>);
  }

  if (requireVendor && !userProfile.is_vendor) {
    return hideWhenDenied ? null : (fallback || <div>Vendor access required</div>);
  }

  // Check if user's role is in the allowed roles array
  if (roles.length > 0) {
    const hasAllowedRole = roles.some(role => {
      switch (role) {
        case 'ROOT_ADMIN':
          return userProfile.is_root_admin;
        case 'wedding_planner':
          return userProfile.is_wedding_planner;
        case 'vendor':
          return userProfile.is_vendor;
        default:
          return userProfile.role === role;
      }
    });

    if (!hasAllowedRole) {
      return hideWhenDenied ? null : (fallback || <div>Insufficient permissions</div>);
    }
  }

  return <>{children}</>;
};

// Convenience components for common use cases
export const RootAdminOnly: React.FC<Omit<PermissionGateProps, 'requireRootAdmin'>> = (props) => (
  <PermissionGate {...props} requireRootAdmin />
);

export const WeddingPlannerOnly: React.FC<Omit<PermissionGateProps, 'requireWeddingPlanner'>> = (props) => (
  <PermissionGate {...props} requireWeddingPlanner />
);

export const VendorOnly: React.FC<Omit<PermissionGateProps, 'requireVendor'>> = (props) => (
  <PermissionGate {...props} requireVendor />
);

export const PlannerOrAdmin: React.FC<Omit<PermissionGateProps, 'roles'>> = (props) => (
  <PermissionGate {...props} roles={['ROOT_ADMIN', 'wedding_planner']} />
);

export default PermissionGate;
