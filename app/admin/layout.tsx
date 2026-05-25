'use client';

import { AdminProvider, useAdmin } from '@/contexts/AdminContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SSEProvider } from '@/contexts/SSEContext';
import { ConfirmDialogProvider } from '@/components/ui/ConfirmDialog';
import AdminRouteGuard from '@/components/AdminRouteGuard';
import ErrorBoundary from '@/components/ErrorBoundary';
import {
  WorkspaceBackground,
  WorkspaceShellFrame,
  useResponsiveWorkspaceSidebar,
} from '@/components/layout/WorkspaceChrome';
import Sidebar from './components/Sidebar';
import TopHeader from './components/TopHeader';
import TrialBanner from './components/TrialBanner';
import PlannerActionToastListener from './components/PlannerActionToastListener';
import { AIChatWidget } from '@/components/ai/AIChatWidget';
import { Toaster } from 'sonner';
import { usePathname } from 'next/navigation';


function AdminLayoutContent({ children }: { children: React.ReactNode }) {
  const {
    isMobile,
    isSidebarOpen: sidebarOpen,
    setIsSidebarOpen: setSidebarOpen,
  } = useResponsiveWorkspaceSidebar();
  const pathname = usePathname();
  const { userProfile } = useAdmin();

  // Check if current page is a public page - should not show sidebar/header
  const isLoginPage = pathname === '/admin/login';
  const isPublicPage = isLoginPage || pathname.startsWith('/admin/team/accept');

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
        <WorkspaceBackground />
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
    <WorkspaceShellFrame
      sidebar={(
        <Sidebar
          isOpen={sidebarOpen}
          setIsOpen={setSidebarOpen}
          isMobile={isMobile}
        />
      )}
      header={(
        <TopHeader
          onMenuClick={() => setSidebarOpen(!sidebarOpen)}
          title={getPageTitle()}
        />
      )}
      banner={<TrialBanner />}
      afterShell={
        <>
          {(userProfile?.is_wedding_planner || userProfile?.is_team_member) ? (
            <>
              <AIChatWidget />
              <PlannerActionToastListener />
            </>
          ) : null}
          <Toaster position="top-right" richColors theme="system" />
        </>
      }
      isMobile={isMobile}
      isSidebarOpen={sidebarOpen}
    >
      <ErrorBoundary>
        {children}
      </ErrorBoundary>
    </WorkspaceShellFrame>
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
