import React from 'react';
import { getSession } from '@/lib/auth';
import { AdminProvider } from '@/contexts/AdminContext';

export async function AdminAuthWrapper({ children }: { children: React.ReactNode }) {
  // Check authentication on the server
  const session = await getSession();

  return (
    <AdminProvider initialAuth={session?.isAuthenticated || false}>
      {children}
    </AdminProvider>
  );
}