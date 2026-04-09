import type { UserProfile } from '@/contexts/AdminContext';

type TeamPermissionKey =
  | 'manage_guests'
  | 'manage_budget'
  | 'manage_gallery'
  | 'manage_seating'
  | 'manage_vendors'
  | 'send_rsvp'
  | 'send_reminders'
  | 'manage_forms'
  | 'view_analytics'
  | 'manage_wedding_settings'
  | 'manage_contracts'
  | 'manage_packages'
  | 'manage_couple_portal'
  | 'message_couples';

const TEAM_BASE_NAV_NAMES = ['Dashboard', 'Calendar', 'Notifications', 'Support'] as const;

const TEAM_PERMISSION_NAV_MAP: Record<TeamPermissionKey, string[]> = {
  manage_guests: ['Guests'],
  manage_budget: ['Budget'],
  manage_gallery: ['Gallery'],
  manage_seating: ['Seating'],
  manage_vendors: ['Vendors'],
  send_rsvp: ['Guests', 'Communications'],
  send_reminders: ['Communications'],
  manage_forms: ['Forms'],
  view_analytics: [],
  manage_wedding_settings: ['Weddings'],
  manage_contracts: ['Vendors'],
  manage_packages: ['Packages'],
  manage_couple_portal: ['Weddings'],
  message_couples: ['Communications'],
};

export function canManageCouplePortal(userProfile?: UserProfile | null): boolean {
  if (!userProfile) return false;
  return Boolean(
    userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.manage_couple_portal
  );
}

export function canAccessWeddings(userProfile?: UserProfile | null): boolean {
  if (!userProfile) return false;
  return Boolean(
    userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.manage_wedding_settings ||
      userProfile.team_permissions?.manage_couple_portal
  );
}

export function canMessageCouples(userProfile?: UserProfile | null): boolean {
  if (!userProfile) return false;
  return Boolean(
    userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.message_couples
  );
}

export function canSendRsvp(userProfile?: UserProfile | null): boolean {
  if (!userProfile) return false;
  return Boolean(
    userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.send_rsvp
  );
}

export function canSendReminders(userProfile?: UserProfile | null): boolean {
  if (!userProfile) return false;
  return Boolean(
    userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      userProfile.team_permissions?.send_reminders
  );
}

export function canAccessGuestCommunications(userProfile?: UserProfile | null): boolean {
  return canSendRsvp(userProfile) || canSendReminders(userProfile);
}

export function canAccessSupportInbox(userProfile?: UserProfile | null): boolean {
  if (!userProfile) return false;
  return Boolean(
    userProfile.is_root_admin ||
      userProfile.is_wedding_planner ||
      (userProfile.is_team_member && userProfile.team_permissions)
  );
}

export function canAccessAnyCommunicationsInbox(userProfile?: UserProfile | null): boolean {
  return Boolean(
    canAccessGuestCommunications(userProfile) ||
      canMessageCouples(userProfile) ||
      canAccessSupportInbox(userProfile)
  );
}

export function getAllowedTeamNavNames(userProfile?: UserProfile | null): Set<string> {
  const allowedNavNames = new Set<string>(TEAM_BASE_NAV_NAMES);
  if (!userProfile?.is_team_member || !userProfile.team_permissions) {
    return allowedNavNames;
  }

  for (const [permissionName, navNames] of Object.entries(TEAM_PERMISSION_NAV_MAP)) {
    if (userProfile.team_permissions[permissionName]) {
      navNames.forEach((name) => allowedNavNames.add(name));
    }
  }

  return allowedNavNames;
}
