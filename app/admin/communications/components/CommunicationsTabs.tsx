'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { getVisibleCommunicationsTabs } from '@/admin/utils/communicationsAccess';

const COMMUNICATION_TABS = [
  { href: '/admin/communications/inbox', label: 'Inbox', id: 'inbox' },
  { href: '/admin/communications/invites', label: 'Invites', id: 'invites' },
  { href: '/admin/communications/reminders', label: 'Reminders', id: 'reminders' },
  { href: '/admin/communications/individual', label: 'Individual', id: 'individual' },
  { href: '/admin/communications/history', label: 'History', id: 'history' },
] as const;

export default function CommunicationsTabs() {
  const { userProfile } = useAdmin();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const weddingId = searchParams.get('wedding_id');
  const visibleTabIds = getVisibleCommunicationsTabs(userProfile);
  const visibleTabs = COMMUNICATION_TABS.filter((tab) => visibleTabIds.includes(tab.id));

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
