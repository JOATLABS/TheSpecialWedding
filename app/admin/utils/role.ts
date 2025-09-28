import { AllowedRole } from '@/admin/config/routePolicy';

export type NormalizedRole = AllowedRole | 'UNKNOWN';

type Profile = Record<string, any> | null | undefined;

function collectRoleCandidates(profile: Profile): string[] {
  if (!profile) return [];

  const directCandidates: Array<string | undefined | null> = [
    profile.role,
    profile.user_role,
    profile.userRole,
    profile.user?.role,
    profile.user_data?.role,
  ];

  return directCandidates
    .map((candidate) => (candidate == null ? undefined : String(candidate)))
    .filter((candidate): candidate is string => Boolean(candidate))
    .map((candidate) => candidate.trim().toLowerCase());
}

export function normalizeRole(profile: Profile): NormalizedRole {
  if (!profile) {
    return 'UNKNOWN';
  }

  if (profile.is_root_admin) {
    return 'ROOT_ADMIN';
  }

  if (profile.is_wedding_planner) {
    return 'WEDDING_PLANNER';
  }

  if (profile.is_vendor) {
    return 'VENDOR';
  }

  const roleCandidates = collectRoleCandidates(profile);

  if (roleCandidates.some((role) => role === 'root_admin' || role === 'rootadmin')) {
    return 'ROOT_ADMIN';
  }

  if (roleCandidates.includes('admin')) {
    // Legacy single-admin accounts report "admin"; treat them as ROOT_ADMIN to
    // preserve historical privileges documented in the authentication service.
    return 'ROOT_ADMIN';
  }

  if (roleCandidates.includes('wedding_planner')) {
    return 'WEDDING_PLANNER';
  }

  if (roleCandidates.includes('vendor')) {
    return 'VENDOR';
  }

  return 'UNKNOWN';
}

export function hasAnyRole(profile: any, roles: AllowedRole[]): boolean {
  const r = normalizeRole(profile);
  return roles.includes(r as AllowedRole);
}