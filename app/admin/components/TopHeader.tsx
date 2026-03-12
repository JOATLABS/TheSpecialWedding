'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useTheme } from '@/contexts/ThemeContext';
import { useAdmin } from '@/contexts/AdminContext';
import { Menu, Sun, Moon, Bell, User, Settings, LogOut, ChevronDown } from 'lucide-react';
import Link from 'next/link';
import { getApiBaseUrl } from '@/utils/env';
import AccountSettingsModal from './AccountSettingsModal';

interface TopHeaderProps {
  onMenuClick: () => void;
  title?: string;
}

// SSE reconnection configuration
const INITIAL_RECONNECT_DELAY = 1000; // 1 second
const MAX_RECONNECT_DELAY = 30000;    // 30 seconds cap
const MAX_RECONNECT_ATTEMPTS = 20;    // Stop after 20 consecutive failures

export default function TopHeader({ onMenuClick, title }: TopHeaderProps) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { userProfile, token, logout } = useAdmin();
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [showDropdown, setShowDropdown] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // SSE connection refs
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const isConnecting = useRef(false);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // SSE connection management
  useEffect(() => {
    if (!token) return;

    const closeConnection = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      isConnecting.current = false;
    };

    const connect = () => {
      // Close any existing connection before opening a new one (prevents race on token change)
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (isConnecting.current) return;
      isConnecting.current = true;

      // EventSource doesn't support custom headers, so we pass the token as a query param.
      // The backend SSE endpoint accepts ?token= for this reason.
      const url = `${getApiBaseUrl()}/admin/notifications/stream?token=${encodeURIComponent(token)}`;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.addEventListener('notification-count', (event) => {
        try {
          const data = JSON.parse(event.data);
          setUnreadCount(data.unread || 0);
          // Reset reconnect counter on successful data
          reconnectAttempts.current = 0;
        } catch {
          // Ignore malformed events
        }
      });

      es.addEventListener('notification-new', (event) => {
        try {
          const data = JSON.parse(event.data);
          // Dispatch custom event so other components (e.g. notification panel) can react
          window.dispatchEvent(new CustomEvent('notification-received', { detail: data }));
        } catch {
          // Ignore malformed events
        }
      });

      es.onopen = () => {
        isConnecting.current = false;
        reconnectAttempts.current = 0;
      };

      es.onerror = () => {
        isConnecting.current = false;
        es.close();
        eventSourceRef.current = null;

        // Reconnect with exponential backoff
        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current),
            MAX_RECONNECT_DELAY
          );
          reconnectAttempts.current += 1;
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        }
      };
    };

    // Connect on mount
    connect();

    // Pause SSE when tab is hidden, resume when visible
    const handleVisibilityChange = () => {
      if (document.hidden) {
        closeConnection();
      } else {
        reconnectAttempts.current = 0;
        connect();
      }
    };

    // Listen for local "notifications-updated" events (e.g. user marks as read)
    // to trigger an immediate re-fetch via a one-shot REST call
    const handleNotificationsRead = async () => {
      try {
        const [platformRes, activityRes] = await Promise.allSettled([
          fetch(`${getApiBaseUrl()}/admin/user/notifications/count`, {
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          }),
          fetch(`${getApiBaseUrl()}/admin/planner/activity-notifications/count`, {
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          }),
        ]);
        let total = 0;
        if (platformRes.status === 'fulfilled' && platformRes.value.ok) {
          total += ((await platformRes.value.json()).unread || 0);
        }
        if (activityRes.status === 'fulfilled' && activityRes.value.ok) {
          total += ((await activityRes.value.json()).unread || 0);
        }
        setUnreadCount(total);
      } catch {
        // SSE will catch up on next push
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('notifications-updated', handleNotificationsRead);

    return () => {
      closeConnection();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('notifications-updated', handleNotificationsRead);
    };
  }, [token]);

  const toggleTheme = () => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  };

  return (
    <header className="sticky top-0 z-30 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-slate-200/50 dark:border-slate-700/50" role="banner">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
        {/* Left: Menu Button & Title */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors lg:hidden"
            aria-label="Toggle navigation menu"
            aria-controls="sidebar"
          >
            <Menu size={20} className="text-slate-600 dark:text-slate-400" aria-hidden="true" />
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
            aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} theme`}
            title={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {resolvedTheme === 'dark' ? (
              <Sun size={20} className="text-amber-500" aria-hidden="true" />
            ) : (
              <Moon size={20} className="text-slate-600" aria-hidden="true" />
            )}
          </button>

          {/* Notifications - links to history tab for root admin to see sent/received notifications */}
          <Link
            href="/admin/notifications?tab=history"
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors relative"
            aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
            title={`View notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
          >
            <Bell size={20} className="text-slate-600 dark:text-slate-400" aria-hidden="true" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center px-1 text-[10px] font-bold text-white bg-red-500 rounded-full shadow-sm" aria-label={`${unreadCount} unread notifications`}>
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </Link>

          {/* User Profile Dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              aria-label="User menu"
              aria-haspopup="true"
              aria-expanded={showDropdown}
              aria-controls="user-dropdown-menu"
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-secondary-400 flex items-center justify-center overflow-hidden">
                {userProfile?.profile_image_url ? (
                  <img
                    src={userProfile.profile_image_url}
                    alt={`${userProfile?.first_name || 'User'} profile`}
                    className="w-full h-full object-cover"
                  />
                ) : userProfile?.first_name || userProfile?.last_name ? (
                  <span className="text-sm font-semibold text-white">
                    {(userProfile.first_name?.charAt(0) || '') + (userProfile.last_name?.charAt(0) || '')}
                  </span>
                ) : (
                  <User size={16} className="text-white" aria-hidden="true" />
                )}
              </div>
              <span className="hidden sm:block text-sm font-medium text-slate-700 dark:text-slate-300">
                {userProfile?.first_name || userProfile?.email?.split('@')[0] || 'User'}
              </span>
              <ChevronDown size={16} className={`hidden sm:block text-slate-400 transition-transform ${showDropdown ? 'rotate-180' : ''}`} aria-hidden="true" />
            </button>

            {/* Dropdown Menu */}
            {showDropdown && (
              <div
                className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-50"
                id="user-dropdown-menu"
                role="menu"
              >
                <button
                  onClick={() => {
                    setShowDropdown(false);
                    setShowSettingsModal(true);
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                  role="menuitem"
                >
                  <Settings size={16} aria-hidden="true" />
                  Account Settings
                </button>
                <hr className="my-1 border-slate-200 dark:border-slate-700" />
                <button
                  onClick={() => {
                    setShowDropdown(false);
                    logout();
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                  role="menuitem"
                >
                  <LogOut size={16} aria-hidden="true" />
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Account Settings Modal */}
      <AccountSettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
      />
    </header>
  );
}
