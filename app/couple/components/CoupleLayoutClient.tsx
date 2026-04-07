'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { CoupleSSEProvider } from '@/contexts/CoupleSSEContext';
import ErrorBoundary from '@/components/ErrorBoundary';
import { Toaster } from 'sonner';

interface CoupleLayoutClientProps {
  children: React.ReactNode;
}

export default function CoupleLayoutClient({ children }: CoupleLayoutClientProps) {
  const pathname = usePathname();

  // Public pages (login, setup, forgot-password, reset-password) don't get sidebar/header
  const isPublicPage =
    pathname === '/couple/login' ||
    pathname.startsWith('/couple/setup') ||
    pathname.startsWith('/couple/forgot-password') ||
    pathname.startsWith('/couple/reset-password') ||
    pathname.startsWith('/couple/forms/');

  if (isPublicPage) {
    return (
      <ThemeProvider>
        <div className="min-h-screen bg-light-bg dark:bg-dark-bg text-light-text dark:text-dark-text font-sans transition-colors duration-300">
          {/* Mesh gradient background */}
          <div className="fixed inset-0 z-0 pointer-events-none opacity-40 dark:opacity-20" aria-hidden="true">
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
      </ThemeProvider>
    );
  }

  // Dashboard pages get the full layout with mesh gradient
  // The sidebar + header are rendered by the dashboard page itself
  // since it needs to manage section state
  return (
    <ThemeProvider>
      <CoupleSSEProvider>
        <div className="min-h-screen bg-light-bg dark:bg-dark-bg text-light-text dark:text-dark-text font-sans transition-colors duration-300">
          {/* Mesh gradient background */}
          <div className="fixed inset-0 z-0 pointer-events-none opacity-40 dark:opacity-20 overflow-hidden" aria-hidden="true">
            <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-primary-400/30 blur-[100px] animate-float" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-secondary-400/30 blur-[100px] animate-float" style={{ animationDelay: '-3s' }} />
          </div>
          <div className="relative z-10 min-h-screen">
            <ErrorBoundary>
              {children}
            </ErrorBoundary>
          </div>

          <Toaster position="top-right" richColors theme="system" />
        </div>
      </CoupleSSEProvider>
    </ThemeProvider>
  );
}
