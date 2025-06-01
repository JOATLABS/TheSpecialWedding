// This file is part of the admin panel layout for a Next.js application.

import { AdminProvider } from '@/contexts/AdminContext';
import { Toaster } from 'sonner';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminProvider>
      <div className="min-h-screen bg-gray-50 text-gray-900">
        <Toaster position="top-right" richColors />
        <header className="bg-white shadow px-6 py-4 flex justify-between items-center">
          <h1 className="text-lg font-semibold">Admin Panel</h1>
          <nav className="space-x-4 text-sm">
            <a href="/admin/gallery/upload" className="hover:underline">Gallery Upload</a>
            <a href="/admin/login" onClick={() => localStorage.removeItem('admin_token')} className="text-red-500 hover:underline">
              Logout
            </a>
          </nav>
        </header>
        <main className="p-6">{children}</main>
      </div>
    </AdminProvider>
  );
}
