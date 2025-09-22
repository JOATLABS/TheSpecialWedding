'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { SECURE_ROUTES } from '@/admin/config/routePolicy';
import { normalizeRole } from '@/admin/utils/role';

interface AdminSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AdminSidebar({ isOpen, onClose }: AdminSidebarProps) {
  const { logout, userProfile, fetchUserProfile, isAuthenticated, token } = useAdmin();
  const pathname = usePathname();
  const [isDarkMode, setIsDarkMode] = React.useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('theme');
      if (stored === 'dark') return true;
      if (stored === 'light') return false;
      return document.documentElement.classList.contains('dark') ||
        window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });

  const toggleDarkMode = () => {
    setIsDarkMode(prev => {
      const next = !prev;
      if (typeof window !== 'undefined') {
        document.documentElement.classList.toggle('dark', next);
        try { localStorage.setItem('theme', next ? 'dark' : 'light'); } catch {}
      }
      return next;
    });
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const stored = localStorage.getItem('theme');
    if (stored === 'dark') {
      document.documentElement.classList.add('dark');
      setIsDarkMode(true);
    } else if (stored === 'light') {
      document.documentElement.classList.remove('dark');
      setIsDarkMode(false);
    }
  }, []);

  const isLoginPage = pathname === '/admin/login';
  useEffect(() => {
    if (!userProfile && isAuthenticated && token) {
      fetchUserProfile().catch(() => {
        // Silent failure: consider forcing logout if critical
        logout();
      });
    }
  }, [userProfile, fetchUserProfile, isAuthenticated, token, logout]);

  if (isLoginPage || !isAuthenticated) return null;

  const role = normalizeRole(userProfile);
  const navLinks = SECURE_ROUTES.filter(r => r.roles.includes(role as any));

  const handleLogout = () => {
    logout();
    onClose();
  };

  const roleLabel = (() => {
    switch (role) {
      case 'ROOT_ADMIN': return 'Root Admin';
      case 'WEDDING_PLANNER': return 'Planner';
      case 'VENDOR': return 'Vendor';
      default: return 'User';
    }
  })();

  return (
    <aside
      className={`fixed top-0 left-0 h-full w-64 z-40 transform transition-transform
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        bg-neutral-900/90 backdrop-blur-md border-r border-neutral-700 text-neutral-100`}
    >
      <div className="flex items-center justify-between px-4 py-4 border-b border-neutral-700">
        <div>
          <h1 className="text-lg font-semibold">Admin Console</h1>
          <p className="text-xs text-neutral-400">{roleLabel}</p>
        </div>
        <button
          onClick={onClose}
          className="text-neutral-400 hover:text-neutral-200"
          aria-label="Close sidebar"
        >
          ✕
        </button>
      </div>

      <nav className="mt-4 px-2 space-y-1">
        {navLinks.map(link => {
          const active = pathname === link.path || pathname.startsWith(link.path + '/');
          return (
            <Link
              key={link.path}
              href={link.path}
              onClick={onClose}
              className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm
              ${active
                ? 'bg-neutral-700 text-white'
                : 'text-neutral-300 hover:bg-neutral-800 hover:text-white'}`}
            >
              <span>{link.icon}</span>
              <span>{link.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto absolute bottom-0 w-full border-t border-neutral-700 p-4 space-y-3">
        <button
          onClick={toggleDarkMode}
          className="w-full text-left text-sm px-3 py-2 rounded bg-neutral-800 hover:bg-neutral-700"
        >
          {isDarkMode ? 'Light Mode' : 'Dark Mode'}
        </button>
        <button
          onClick={handleLogout}
            className="w-full text-left text-sm px-3 py-2 rounded bg-red-600/80 hover:bg-red-600 text-white"
        >
          Logout
        </button>
      </div>
    </aside>
  );
}