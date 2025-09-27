import { AllowedRole } from '@/admin/config/routePolicy';

export type NormalizedRole = AllowedRole | 'UNKNOWN';

export function normalizeRole(profile: any): NormalizedRole {
  if (!profile) return 'UNKNOWN';

  const roleValue = String(
    profile.role ??
      profile.user_role ??
      profile.user?.role ??
      ''
  ).trim().toLowerCase();

  if (
    profile.is_root_admin ||
    roleValue === 'root_admin' ||
    roleValue === 'root-admin' ||
    roleValue === 'rootadmin' ||
    roleValue === 'root' ||
    roleValue === 'admin' ||
    roleValue === 'root_admin_role'
  ) {
    return 'ROOT_ADMIN';
  }

  if (
    profile.is_wedding_planner ||
    roleValue === 'wedding_planner' ||
    roleValue === 'wedding-planner' ||
    roleValue === 'weddingplanner' ||
    roleValue === 'planner'
  ) {
    return 'WEDDING_PLANNER';
  }

  if (
    profile.is_vendor ||
    roleValue === 'vendor' ||
    roleValue === 'vendor_user' ||
    roleValue === 'vendor-user'
  ) {
    return 'VENDOR';
  }

  return 'UNKNOWN';
}

export function hasAnyRole(profile: any, roles: AllowedRole[]): boolean {
  const r = normalizeRole(profile);
  return roles.includes(r as AllowedRole);
}