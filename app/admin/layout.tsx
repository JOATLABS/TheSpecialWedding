'use client';

import { AdminProvider } from '@/contexts/AdminContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import AdminRouteGuard from '@/components/AdminRouteGuard';
import Sidebar from './components/Sidebar';
import TopHeader from './components/TopHeader';
import { Toaster } from 'sonner';
import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';

function AdminLayoutContent({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const pathname = usePathname();

  // Check if current page is the login page - should not show sidebar/header
  const isLoginPage = pathname === '/admin/login';

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
    if (pathname.includes('/admin/weddings')) return 'Weddings';
    if (pathname.includes('/admin/guests')) return 'Guest Management';
    if (pathname.includes('/admin/budget')) return 'Budget Tracker';
    if (pathname.includes('/admin/profile')) return 'Settings';
    return undefined; // Let Header decide default
  };

  // For login page, render without sidebar/header
  if (isLoginPage) {
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
    <div className="min-h-screen bg-light-bg dark:bg-dark-bg text-light-text dark:text-dark-text font-sans transition-colors duration-300">
      {/* Background Mesh Gradient (Fixed) */}
      <div className="fixed inset-0 z-0 pointer-events-none opacity-40 dark:opacity-20">
         <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-primary-400/30 blur-[100px] animate-float" />
         <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-secondary-400/30 blur-[100px] animate-float" style={{ animationDelay: '-3s' }} />
      </div>

      <Sidebar
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
        isMobile={isMobile}
      />

      <motion.div
        layout
        className="relative z-10 flex flex-col min-h-screen transition-all duration-300 ease-[cubic-bezier(0.25,0.1,0.25,1)]"
        style={{
          marginLeft: !isMobile ? (sidebarOpen ? '18rem' : '5rem') : '0'
        }}
      >
        <TopHeader
          onMenuClick={() => setSidebarOpen(!sidebarOpen)}
          title={getPageTitle()}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 overflow-x-hidden">
           {children}
        </main>
      </motion.div>

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
        <AdminRouteGuard>
          <AdminLayoutContent>{children}</AdminLayoutContent>
        </AdminRouteGuard>
      </AdminProvider>
    </ThemeProvider>
  );
}
