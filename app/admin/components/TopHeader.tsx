'use client';

import React from 'react';
import { useTheme } from '@/contexts/ThemeContext';
import { useAdmin } from '@/contexts/AdminContext';
import { Menu, Sun, Moon, Bell, User } from 'lucide-react';
import Link from 'next/link';

interface TopHeaderProps {
  onMenuClick: () => void;
  title?: string;
}

export default function TopHeader({ onMenuClick, title }: TopHeaderProps) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { userProfile } = useAdmin();

  const toggleTheme = () => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  };

  return (
    <header className="sticky top-0 z-30 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-slate-200/50 dark:border-slate-700/50">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
        {/* Left: Menu Button & Title */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors lg:hidden"
            aria-label="Toggle menu"
          >
            <Menu size={20} className="text-slate-600 dark:text-slate-400" />
          </button>

          {title && (
            <h1 className="text-xl font-heading font-semibold text-slate-800 dark:text-white">
              {title}
            </h1>
          )}
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Toggle theme"
          >
            {resolvedTheme === 'dark' ? (
              <Sun size={20} className="text-amber-500" />
            ) : (
              <Moon size={20} className="text-slate-600" />
            )}
          </button>

          {/* Notifications */}
          <Link
            href="/admin/notifications"
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors relative"
          >
            <Bell size={20} className="text-slate-600 dark:text-slate-400" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-primary-500 rounded-full" />
          </Link>

          {/* User Profile */}
          <Link
            href="/admin/profile"
            className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-secondary-400 flex items-center justify-center overflow-hidden">
              {userProfile?.profile_image_url ? (
                <img
                  src={userProfile.profile_image_url}
                  alt="Profile"
                  className="w-full h-full object-cover"
                />
              ) : userProfile?.first_name || userProfile?.last_name ? (
                <span className="text-sm font-semibold text-white">
                  {(userProfile.first_name?.charAt(0) || '') + (userProfile.last_name?.charAt(0) || '')}
                </span>
              ) : (
                <User size={16} className="text-white" />
              )}
            </div>
            <span className="hidden sm:block text-sm font-medium text-slate-700 dark:text-slate-300">
              {userProfile?.first_name || userProfile?.email?.split('@')[0] || 'User'}
            </span>
          </Link>
        </div>
      </div>
    </header>
  );
}
