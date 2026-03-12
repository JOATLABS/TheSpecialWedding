'use client';

import { AdminProvider } from '@/contexts/AdminContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { ConfirmDialogProvider } from '@/components/ui/ConfirmDialog';
import AdminRouteGuard from '@/components/AdminRouteGuard';
import ErrorBoundary from '@/components/ErrorBoundary';
import Sidebar from './components/Sidebar';
import TopHeader from './components/TopHeader';
import { AIChatWidget } from '@/components/ai/AIChatWidget';
import { Toaster } from 'sonner';
import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';


function AdminLayoutContent({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const pathname = usePathname();

  // Check if current page is a public page - should not show sidebar/header
  const isLoginPage = pathname === '/admin/login';
  const isPublicPage = isLoginPage || pathname.startsWith('/admin/team/accept');

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 1024;
      setIsMobile(mobile);
      if (mobile) setSidebarOpen(false);
      else setSidebarOpen(true);
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Determine Page Title based on Path (Simplistic mapping)
  const getPageTitle = () => {
    if (pathname.includes('/admin/planner')) return 'Dashboard';
    // if (pathname.includes('/admin/weddings')) return 'Weddings';
    // if (pathname.includes('/admin/guests')) return 'Guest Management';
    // if (pathname.includes('/admin/budget')) return 'Budget Tracker';
    // if (pathname.includes('/admin/profile')) return 'Settings';
    return undefined; // Let Header decide default
  };

  // For public pages (login, accept invite), render without sidebar/header
  if (isPublicPage) {
    return (
      <div className="min-h-screen bg-light-bg dark:bg-dark-bg text-light-text dark:text-dark-text font-sans transition-colors duration-300">
        {/* Background Mesh Gradient (Fixed) */}
        <div className="fixed inset-0 z-0 pointer-events-none opacity-40 dark:opacity-20">
           <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-primary-400/30 blur-[100px] animate-float" />
           <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-secondary-400/30 blur-[100px] animate-float" style={{ animationDelay: '-3s' }} />
        </div>
        <main className="relative z-10 min-h-screen">
          {children}
        </main>
        <Toaster position="top-right" richColors theme="system" />
      </div>
    );
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-light-bg dark:bg-dark-bg text-light-text dark:text-dark-text font-sans transition-colors duration-300">
      {/* Background Mesh Gradient (Fixed) */}
      <div className="fixed inset-0 z-0 pointer-events-none opacity-40 dark:opacity-20 overflow-hidden" aria-hidden="true">
         <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-primary-400/30 blur-[100px] animate-float" />
         <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-secondary-400/30 blur-[100px] animate-float" style={{ animationDelay: '-3s' }} />
      </div>

      <Sidebar
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
        isMobile={isMobile}
      />

      <div
        className="relative z-10 flex flex-col min-h-screen transition-[margin] duration-300 ease-out"
        style={{
          marginLeft: !isMobile ? (sidebarOpen ? '18rem' : '5rem') : '0'
        }}
      >
        <TopHeader
          onMenuClick={() => setSidebarOpen(!sidebarOpen)}
          title={getPageTitle()}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 overflow-x-hidden" id="main-content">
           <ErrorBoundary>
             {children}
           </ErrorBoundary>
        </main>
      </div>

      {/* AI Chat Widget - Available on all admin pages */}
      <AIChatWidget />

      <Toaster position="top-right" richColors theme="system" />
    </div>
  );
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ThemeProvider>
      <AdminProvider>
        <ConfirmDialogProvider>
          <AdminRouteGuard>
            <AdminLayoutContent>{children}</AdminLayoutContent>
          </AdminRouteGuard>
        </ConfirmDialogProvider>
      </AdminProvider>
    </ThemeProvider>
  );
}
