'use client';

import Link from 'next/link';

type Portal = 'planner' | 'couple';

type PortalOption = {
  id: Portal;
  label: string;
  href: string;
};

const portalOptions: PortalOption[] = [
  {
    id: 'planner',
    label: 'Planner Portal',
    href: '/admin/login',
  },
  {
    id: 'couple',
    label: 'Couple Portal',
    href: '/couple/login',
  },
];

export function PortalSwitch({ active }: { active: Portal }) {
  return (
    <nav
      aria-label="Choose login portal"
      className="mb-5 rounded-full border border-white/45 bg-white/35 p-1 shadow-sm shadow-white/20"
    >
      <div className="grid grid-cols-2 gap-1">
        {portalOptions.map((option) => {
          const isActive = option.id === active;
          const classes = isActive
            ? 'bg-wedding-navy text-white shadow-sm shadow-wedding-navy/20'
            : 'text-wedding-navy/70 hover:bg-white/60 hover:text-wedding-navy';

          return (
            <Link
              key={option.id}
              href={option.href}
              aria-current={isActive ? 'page' : undefined}
              className={`rounded-full px-3 py-2 text-center text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose/60 sm:px-4 ${classes}`}
            >
              {option.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
