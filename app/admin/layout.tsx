'use client';

import { AdminProvider } from '@/contexts/AdminContext';
import AdminRouteGuard from '@/components/AdminRouteGuard';
import AdminHeader from './components/AdminHeader';
import { Toaster } from 'sonner';

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AdminProvider>
      <AdminRouteGuard>
        <div className="min-h-screen flex flex-col bg-wedding-ivory font-body text-wedding-navy">
          {/* Toast Notifications */}
          <Toaster position="top-right" richColors />

          {/* HEADER */}
          <AdminHeader />

        {/* MAIN CONTENT */}
        <main className="flex-1 p-8 space-y-8 animate-fade-in">
          {children}
        </main>
      </div>
      </AdminRouteGuard>
    </AdminProvider>
  );
}
