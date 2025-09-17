'use client';

import { DarkModeProvider } from '@/contexts/DarkModeContext';
import AdminHeader from './components/AdminHeader';
import AdminSidebar from './components/AdminSidebar';
import { Toaster } from 'sonner';
import { useState } from 'react';
import dynamic from 'next/dynamic';

// Dynamic import for AdminProvider to prevent hydration mismatch
// Following Next.js best practices for authentication-dependent components
const AdminProvider = dynamic(
  () => import('@/contexts/AdminContext').then(mod => ({ default: mod.AdminProvider })),
  {
    ssr: false,
    loading: () => (
      <div className="min-h-screen flex items-center justify-center bg-wedding-ivory dark:bg-gray-900">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-wedding-rose"></div>
      </div>
    )
  }
);

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Sidebar should be closed by default on mobile, open on desktop
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleToggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  const handleCloseSidebar = () => {
    setSidebarOpen(false);
  };

  return (
    <DarkModeProvider>
      <AdminProvider>
        <div className="min-h-screen flex bg-wedding-ivory dark:bg-gray-900 font-body text-wedding-navy dark:text-gray-100 transition-colors duration-200">
          {/* Toast Notifications */}
          <Toaster position="top-right" richColors />

          {/* SIDEBAR */}
          <AdminSidebar isOpen={sidebarOpen} onClose={handleCloseSidebar} />

          {/* MAIN CONTENT AREA */}
          <div className="flex-1 flex flex-col min-h-screen">
            {/* MOBILE HEADER */}
            <AdminHeader onToggleSidebar={handleToggleSidebar} />

            {/* MAIN CONTENT */}
            <main className="flex-1 p-4 lg:p-8 space-y-8 animate-fade-in">
              {children}
            </main>
          </div>
        </div>
      </AdminProvider>
    </DarkModeProvider>
  );
}
