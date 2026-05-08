'use client';
import { AdminProvider, useAdmin } from '@/contexts/AdminContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SSEProvider } from '@/contexts/SSEContext';
import { ConfirmDialogProvider } from '@/components/ui/ConfirmDialog';
import AdminRouteGuard from '@/components/AdminRouteGuard';
import ErrorBoundary from '@/components/ErrorBoundary';
import Sidebar from './components/Sidebar';
import TopHeader from './components/TopHeader';
import TrialBanner from './components/TrialBanner';
import SubscriptionUsageBanner from './components/SubscriptionUsageBanner';
import { AIChatWidget } from '@/components/ai/AIChatWidget';
import PlannerActionToastListener from './components/PlannerActionToastListener';
import { Toaster } from 'sonner';
import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';


function AdminLayoutContent({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const pathname = usePathname();
  const { userProfile } = useAdmin();

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
    // Only show "Dashboard" for the exact planner dashboard page, not sub-pages
    if (pathname === '/admin/planner') return 'Dashboard';
    return undefined; // Let individual pages use their own PageHeader
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
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
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
        <TrialBanner />

        {/*
         * Global soft-cap banner for AI credits. Renders only when the planner
         * is above the warn threshold or actively in overage — the component
         * returns null otherwise, so this is free on normal pages. Shown to
         * planners and their team members; root admins are bypassed inside
         * the component.
         */}
        {(userProfile?.is_wedding_planner || userProfile?.is_team_member) && (
          <div className="px-4 pt-4 sm:px-6 lg:px-8">
            <SubscriptionUsageBanner resourceType="ai_credits" quietUntilWarn />
          </div>
        )}

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

      {/* AI Chat Widget - Only for planners and their team members (paid feature) */}
      {(userProfile?.is_wedding_planner || userProfile?.is_team_member) && <AIChatWidget />}

      {/*
       * Two-stage wedding-checklist nudge (chunk 5). Listens to the
       * notification-received CustomEvent that TopHeader dispatches
       * from the SSE notification-new channel. Renders an action-button
       * toast for wedding_created (Stage 1) and couple_portal_accepted
       * (Stage 2). Component returns null itself — purely an event
       * listener bridge between SSE → sonner.toast.custom.
       */}
      {(userProfile?.is_wedding_planner || userProfile?.is_team_member) && (
        <PlannerActionToastListener />
      )}

      <Toaster position="top-right" richColors theme="system" />
    </div>
  );
}

export default function AdminLayoutClient({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ThemeProvider>
      <AdminProvider>
        <SSEProvider>
          <ConfirmDialogProvider>
            <AdminRouteGuard>
              <AdminLayoutContent>{children}</AdminLayoutContent>
            </AdminRouteGuard>
          </ConfirmDialogProvider>
        </SSEProvider>
      </AdminProvider>
    </ThemeProvider>
  );
}
