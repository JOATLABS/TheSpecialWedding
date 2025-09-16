'use client';

import { usePathname } from 'next/navigation';

interface AdminHeaderProps {
  onToggleSidebar: () => void;
}

export default function AdminHeader({ onToggleSidebar }: AdminHeaderProps) {
  const pathname = usePathname();
  const isLoginPage = pathname === '/admin/login';

  if (isLoginPage) return null;

  return (
    <header className="lg:hidden glass px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between relative">
      <h1 className="font-heading text-xl text-wedding-rose">Admin Panel</h1>

      {/* Mobile Menu Button */}
      <button
        onClick={onToggleSidebar}
        className="p-2 rounded-lg hover:bg-white/10 transition"
        aria-label="Toggle sidebar"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 6h16M4 12h16M4 18h16"
          />
        </svg>
      </button>
    </header>
  );
}