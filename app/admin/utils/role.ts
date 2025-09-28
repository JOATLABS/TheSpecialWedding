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
    profile.user_data?.role_name,
    profile.role_name,
  ];

  return directCandidates
    .flatMap((candidate) => {
      if (candidate == null) {
        return [];
      }

      const value = String(candidate).trim();
      if (!value) {
        return [];
      }

      return value.split(/[,\s]+/); // allow multi-role strings like "planner admin"
    })
    .map((candidate) => candidate.toLowerCase())
    .filter((candidate, index, all) => candidate.length > 0 && all.indexOf(candidate) === index);
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

  if (roleCandidates.some((role) => role === 'root_admin' || role === 'rootadmin' || role === 'root')) {
    return 'ROOT_ADMIN';
  }

  if (roleCandidates.includes('admin')) {
    // Legacy single-admin accounts report "admin"; treat them as ROOT_ADMIN to
    // preserve historical privileges documented in the authentication service.
    return 'ROOT_ADMIN';
  }

  if (roleCandidates.some((role) => role === 'wedding_planner' || role === 'weddingplanner' || role === 'wedding-planner' || role === 'planner')) {
    return 'WEDDING_PLANNER';
  }

  if (roleCandidates.includes('vendor') || roleCandidates.includes('vendors')) {
    return 'VENDOR';
  }

  return 'UNKNOWN';
}

export function hasAnyRole(profile: any, roles: AllowedRole[]): boolean {
  const r = normalizeRole(profile);
  return roles.includes(r as AllowedRole);
}
