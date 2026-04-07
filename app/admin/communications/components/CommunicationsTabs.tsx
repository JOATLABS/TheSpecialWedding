'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';

const COMMUNICATION_TABS = [
  { href: '/admin/communications/inbox', label: 'Inbox' },
  { href: '/admin/communications/invites', label: 'Invites' },
  { href: '/admin/communications/reminders', label: 'Reminders' },
  { href: '/admin/communications/individual', label: 'Individual' },
  { href: '/admin/communications/history', label: 'History' },
];

export default function CommunicationsTabs() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const weddingId = searchParams.get('wedding_id');

  return (
    <div className="flex flex-wrap gap-3">
      {COMMUNICATION_TABS.map((tab) => {
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
