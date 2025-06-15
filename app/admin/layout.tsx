'use client';

import { AdminProvider } from '@/contexts/AdminContext';
import { Toaster } from 'sonner';

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AdminProvider>
      <div className="min-h-screen flex flex-col bg-wedding-ivory font-body text-wedding-navy">
        {/* Toast Notifications */}
        <Toaster position="top-right" richColors />

        {/* HEADER */}
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
              href="/admin/login"
              onClick={() => localStorage.removeItem('admin_token')}
              className="text-red-500 hover:underline"
            >
              Logout
            </a>
          </nav>
        </header>

        {/* MAIN CONTENT */}
        <main className="flex-1 p-8 space-y-8 animate-fade-in">
          {children}
        </main>
      </div>
    </AdminProvider>
  );
}
