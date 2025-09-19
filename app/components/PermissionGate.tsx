'use client';

import React from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { createAutomationAttrs } from '../utils/automation-attrs';

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
    return hideWhenDenied ? null : (
      fallback || (
        <div
          {...createAutomationAttrs({
            entity: 'permission',
            action: 'denied',
            context: 'auth',
            state: 'unauthenticated'
          })}
        >
          Authentication required
        </div>
      )
    );
  }

  // Check specific role requirements
  if (requireRootAdmin && !userProfile.is_root_admin) {
    return hideWhenDenied ? null : (
      fallback || (
        <div
          {...createAutomationAttrs({
            entity: 'permission',
            action: 'denied',
            context: 'role',
            state: 'insufficient',
            custom: {
              'required-role': 'ROOT_ADMIN',
              'user-role': userProfile.role
            }
          })}
        >
          Admin access required
        </div>
      )
    );
  }

  if (requireWeddingPlanner && !userProfile.is_wedding_planner) {
    return hideWhenDenied ? null : (
      fallback || (
        <div
          {...createAutomationAttrs({
            entity: 'permission',
            action: 'denied',
            context: 'role',
            state: 'insufficient',
            custom: {
              'required-role': 'wedding_planner',
              'user-role': userProfile.role
            }
          })}
        >
          Wedding planner access required
        </div>
      )
    );
  }

  if (requireVendor && !userProfile.is_vendor) {
    return hideWhenDenied ? null : (
      fallback || (
        <div
          {...createAutomationAttrs({
            entity: 'permission',
            action: 'denied',
            context: 'role',
            state: 'insufficient',
            custom: {
              'required-role': 'vendor',
              'user-role': userProfile.role
            }
          })}
        >
          Vendor access required
        </div>
      )
    );
  }

  // Check if user's role is in the allowed roles array
  if (roles.length > 0) {
    const hasAllowedRole = roles.some(role => {
      switch (role) {
        case 'ROOT_ADMIN':
        case 'admin':
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
      return hideWhenDenied ? null : (
        fallback || (
          <div
            {...createAutomationAttrs({
              entity: 'permission',
              action: 'denied',
              context: 'role',
              state: 'insufficient',
              custom: {
                'required-roles': roles.join(','),
                'user-role': userProfile.role
              }
            })}
          >
            Insufficient permissions
          </div>
        )
      );
    }
  }

  return (
    <div
      {...createAutomationAttrs({
        entity: 'permission',
        action: 'granted',
        context: 'role',
        state: 'authorized',
        custom: {
          'user-role': userProfile.role,
          'is-root-admin': userProfile.is_root_admin.toString(),
          'is-wedding-planner': userProfile.is_wedding_planner.toString(),
          'is-vendor': userProfile.is_vendor.toString()
        }
      })}
    >
      {children}
    </div>
  );
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
  <PermissionGate {...props} roles={['ROOT_ADMIN', 'admin', 'wedding_planner']} />
);

export default PermissionGate;