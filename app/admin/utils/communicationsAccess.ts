import type { UserProfile } from '@/contexts/AdminContext';
import {
  canAccessAnyCommunicationsInbox,
  canAccessGuestCommunications,
  canAccessSupportInbox,
  canMessageCouples,
  canSendReminders,
  canSendRsvp,
} from '@/admin/utils/teamAccess';

export type CommunicationsTab =
  | 'inbox'
  | 'invites'
  | 'reminders'
  | 'individual'
  | 'history';

export type InboxSource =
  | 'inbound_email'
  | 'couple_messages'
  | 'guest_sms'
  | 'platform_support';

export function getVisibleCommunicationsTabs(
  userProfile?: UserProfile | null,
): CommunicationsTab[] {
  if (!userProfile) return [];
  if (userProfile.is_root_admin) return ['inbox'];

  const tabs: CommunicationsTab[] = [];
  const canInvite = canSendRsvp(userProfile);
  const canRemind = canSendReminders(userProfile);

  if (canAccessAnyCommunicationsInbox(userProfile)) tabs.push('inbox');
  if (canInvite) tabs.push('invites');
  if (canRemind) tabs.push('reminders', 'individual');
  if (canInvite || canRemind) tabs.push('history');
  return tabs;
}

export function getInboxSources(
  userProfile?: UserProfile | null,
): InboxSource[] {
  if (!userProfile) return [];
  if (userProfile.is_root_admin) return ['platform_support'];

  const sources: InboxSource[] = [];
  if (canAccessGuestCommunications(userProfile)) sources.push('inbound_email');
  if (canMessageCouples(userProfile)) sources.push('couple_messages');
  if (canAccessSupportInbox(userProfile)) {
    sources.push('guest_sms', 'platform_support');
  }
  return sources;
}

export function getRootCommunicationsRedirect(path: string): string | null {
  if (path === '/admin/reminders' || path.startsWith('/admin/reminders/')) {
    return '/admin/communications/inbox';
  }

  if (
    path.startsWith('/admin/communications/')
    && path !== '/admin/communications/inbox'
  ) {
    return '/admin/communications/inbox';
  }

  return null;
}
