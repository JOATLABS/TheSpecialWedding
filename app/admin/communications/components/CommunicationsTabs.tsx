'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import {
  canAccessAnyCommunicationsInbox,
  canMessageCouples,
  canSendReminders,
  canSendRsvp,
} from '@/admin/utils/teamAccess';

const COMMUNICATION_TABS = [
  { href: '/admin/communications/inbox', label: 'Inbox', permission: 'inbox' },
  { href: '/admin/communications/invites', label: 'Invites', permission: 'invites' },
  { href: '/admin/communications/reminders', label: 'Reminders', permission: 'reminders' },
  { href: '/admin/communications/individual', label: 'Individual', permission: 'individual' },
  { href: '/admin/communications/history', label: 'History', permission: 'history' },
] as const;

export default function CommunicationsTabs() {
  const { userProfile } = useAdmin();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const weddingId = searchParams.get('wedding_id');
  const hasInboxAccess = canAccessAnyCommunicationsInbox(userProfile);
  const canAccessInvites = canSendRsvp(userProfile);
  const canAccessReminders = canSendReminders(userProfile);
  const canAccessHistory = canAccessInvites || canAccessReminders;

  const visibleTabs = COMMUNICATION_TABS.filter((tab) => {
    switch (tab.permission) {
      case 'inbox':
        return hasInboxAccess;
      case 'invites':
        return canAccessInvites;
      case 'reminders':
      case 'individual':
        return canAccessReminders;
      case 'history':
        return canAccessHistory;
      default:
        return false;
    }
  });

  if (!visibleTabs.length) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-3">
      {visibleTabs.map((tab) => {
        const isActive = pathname === tab.href;
        const href = weddingId ? `${tab.href}?wedding_id=${encodeURIComponent(weddingId)}` : tab.href;

        return (
          <Link
            key={tab.href}
            href={href}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-wedding-navy text-white'
                : 'bg-white text-wedding-navy hover:bg-gray-100 dark:bg-transparent dark:text-gray-100'
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
