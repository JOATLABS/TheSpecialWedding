'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { BarChart3, Settings, MessageSquare, CreditCard } from 'lucide-react';

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  {
    href: '/admin/vendor/ads',
    label: 'Overview',
    icon: <BarChart3 className="w-4 h-4" />,
  },
  {
    href: '/admin/vendor/ads',
    label: 'Campaigns',
    icon: <Settings className="w-4 h-4" />,
  },
  {
    href: '/admin/vendor/ads',
    label: 'Leads',
    icon: <MessageSquare className="w-4 h-4" />,
  },
  {
    href: '/admin/vendor/ads',
    label: 'Billing',
    icon: <CreditCard className="w-4 h-4" />,
  },
];

export default function AdsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      {/* Sub-navigation */}
      <div className="border-b border-white/10 dark:border-white/10">
        <nav className="flex gap-1 overflow-x-auto" aria-label="Ads navigation">
          {navItems.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors ${
                  isActive
                    ? 'border-b-2 border-wedding-rose text-wedding-rose'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Page content */}
      {children}
    </div>
  );
}
