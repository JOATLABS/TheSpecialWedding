'use client';

import { useAdmin } from '@/contexts/AdminContext';
import { usePathname } from 'next/navigation';

export default function AdminHeader() {
  const { logout } = useAdmin();
  const pathname = usePathname();
  const isLoginPage = pathname === '/admin/login';

  if (isLoginPage) return null;

  return (
    <header className="glass px-8 py-4 flex items-center justify-between">
      <h1 className="font-heading text-2xl text-wedding-rose">
        Admin Panel
      </h1>
      <nav className="space-x-6 font-medium">
        <a
          href="/admin/weddings"
          className="hover:text-wedding-gold transition"
        >
          Weddings
        </a>
        <a
          href="/admin/gallery/upload"
          className="hover:text-wedding-gold transition"
        >
          Gallery
        </a>
        <a
          href="/admin/import"
          className="hover:text-wedding-gold transition"
        >
          Import Guests
        </a>
        <a
          href="/admin/guests"
          className="hover:text-wedding-gold transition"
        >
          Manage Guests
        </a>
        <a
          href="/admin/reminders"
          className="hover:text-wedding-gold transition"
        >
          SMS Reminders
        </a>
        <button
          onClick={logout}
          className="text-red-500 hover:underline"
        >
          Logout
        </button>
      </nav>
    </header>
  );
}