import { AllowedRole } from '@/admin/config/routePolicy';

export type NormalizedRole = AllowedRole | 'UNKNOWN';

export function normalizeRole(profile: any): NormalizedRole {
  if (!profile) return 'UNKNOWN';
  if (profile.is_root_admin) return 'ROOT_ADMIN';
  if (profile.is_wedding_planner) return 'WEDDING_PLANNER';
  if (profile.is_vendor) return 'VENDOR';
  return 'UNKNOWN';
}

export function hasAnyRole(profile: any, roles: AllowedRole[]): boolean {
  const r = normalizeRole(profile);
  return roles.includes(r as AllowedRole);
}