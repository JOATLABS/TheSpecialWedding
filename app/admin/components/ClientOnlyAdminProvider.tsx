'use client';

import dynamic from 'next/dynamic';
import { ReactNode } from 'react';
import { createAutomationAttrs } from '@/utils/automation-attrs';

// Create a client-only version of AdminProvider
const AdminProvider = dynamic(
  () => import('@/contexts/AdminContext').then(mod => ({ default: mod.AdminProvider })),
  {
    ssr: false,
    loading: () => (
      <div
        {...createAutomationAttrs({
          entity: 'auth',
          action: 'loading',
          context: 'provider',
          state: 'hydrating'
        })}
        className="min-h-screen flex items-center justify-center bg-wedding-ivory dark:bg-gray-900"
      >
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-wedding-rose"></div>
      </div>
    )
  }
);

interface ClientOnlyAdminProviderProps {
  children: ReactNode;
}

export default function ClientOnlyAdminProvider({ children }: ClientOnlyAdminProviderProps) {
  return <AdminProvider>{children}</AdminProvider>;
}