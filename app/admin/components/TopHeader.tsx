'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
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

// Polling configuration
const BASE_POLL_INTERVAL = 60000; // 60 seconds
const MAX_POLL_INTERVAL = 300000; // 5 minutes max backoff
const FOCUS_DEBOUNCE_MS = 2000; // 2 second debounce for focus events

export default function TopHeader({ onMenuClick, title }: TopHeaderProps) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { userProfile, token, logout } = useAdmin();
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [showDropdown, setShowDropdown] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Polling state refs (refs to avoid re-renders and stale closures)
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const currentIntervalMs = useRef(BASE_POLL_INTERVAL);
  const consecutiveErrors = useRef(0);
  const lastFocusFetch = useRef(0);
  const isPollingEnabled = useRef(true);

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

  // Stop polling (e.g., on auth failure)
  const stopPolling = useCallback(() => {
    isPollingEnabled.current = false;
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  // Reset backoff on success
  const resetBackoff = useCallback(() => {
    consecutiveErrors.current = 0;
    currentIntervalMs.current = BASE_POLL_INTERVAL;
  }, []);

  // Increase backoff on error (exponential with cap)
  const increaseBackoff = useCallback(() => {
    consecutiveErrors.current += 1;
    // Exponential backoff: 60s -> 120s -> 240s -> 300s (capped)
    currentIntervalMs.current = Math.min(
      BASE_POLL_INTERVAL * Math.pow(2, consecutiveErrors.current),
      MAX_POLL_INTERVAL
    );
  }, []);

  // Fetch combined notification count (platform announcements + activity notifications)
  const fetchNotificationCount = useCallback(async (isManualFetch = false) => {
    if (!token) return;

    // Skip if polling disabled (auth failure) unless it's a manual fetch after re-auth
    if (!isPollingEnabled.current && !isManualFetch) return;

    // Skip if tab is hidden (save resources)
    if (document.hidden && !isManualFetch) return;

    try {
      // Fetch both counts in parallel
      const [platformRes, activityRes] = await Promise.allSettled([
        // Platform announcements (from root admin)
        fetch(`${getApiBaseUrl()}/admin/user/notifications/count`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }),
        // Activity notifications (RSVPs, forms, payments - for planners)
        fetch(`${getApiBaseUrl()}/admin/planner/activity-notifications/count`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }),
      ]);

      let totalUnread = 0;
      let hasAuthError = false;

      // Check platform response
      if (platformRes.status === 'fulfilled') {
        if (platformRes.value.status === 401) {
          hasAuthError = true;
        } else if (platformRes.value.ok) {
          const platformData = await platformRes.value.json();
          totalUnread += platformData.unread || 0;
        }
      }

      // Check activity response (may fail for root admin - that's expected)
      if (activityRes.status === 'fulfilled') {
        if (activityRes.value.status === 401) {
          hasAuthError = true;
        } else if (activityRes.value.ok) {
          const activityData = await activityRes.value.json();
          totalUnread += activityData.unread || 0;
        }
      }

      // Handle authentication failure - stop polling, user needs to re-login
      if (hasAuthError) {
        console.warn('Notification polling: Authentication failed (401). Stopping polling.');
        stopPolling();
        // Optionally trigger logout for expired sessions
        // logout();
        return;
      }

      // Success - reset backoff and update count
      resetBackoff();
      setUnreadCount(totalUnread);
    } catch (error) {
      console.error('Failed to fetch notification count:', error);
      increaseBackoff();
    }
  }, [token, stopPolling, resetBackoff, increaseBackoff]);

  // Start polling with current interval
  const startPolling = useCallback(() => {
    // Clear any existing interval
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    // Only start if enabled
    if (!isPollingEnabled.current) return;

    pollIntervalRef.current = setInterval(() => {
      fetchNotificationCount();
    }, currentIntervalMs.current);
  }, [fetchNotificationCount]);

  // Fetch on mount, with smart polling that respects visibility and auth state
  useEffect(() => {
    // Reset polling state on mount/token change
    isPollingEnabled.current = true;
    resetBackoff();

    // Initial fetch
    fetchNotificationCount(true);

    // Start interval polling
    startPolling();

    // Handle visibility change - pause polling when tab hidden, resume when visible
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab hidden - stop polling to save resources
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      } else {
        // Tab visible again - fetch immediately and restart polling
        fetchNotificationCount();
        startPolling();
      }
    };

    // Debounced focus handler - avoid multiple rapid calls when focusing
    const handleFocus = () => {
      const now = Date.now();
      if (now - lastFocusFetch.current > FOCUS_DEBOUNCE_MS) {
        lastFocusFetch.current = now;
        fetchNotificationCount();
      }
    };

    // Listen for custom event when notifications are marked as read
    const handleNotificationsRead = () => {
      fetchNotificationCount();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);
    window.addEventListener('notifications-updated', handleNotificationsRead);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('notifications-updated', handleNotificationsRead);
    };
  }, [fetchNotificationCount, startPolling, resetBackoff]);

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

          {/* Notifications - links to history tab for root admin to see sent/received notifications */}
          <Link
            href="/admin/notifications?tab=history"
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors relative"
            aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
          >
            <Bell size={20} className="text-slate-600 dark:text-slate-400" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center px-1 text-[10px] font-bold text-white bg-red-500 rounded-full shadow-sm">
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
              <ChevronDown size={16} className="hidden sm:block text-slate-400" />
            </button>

            {/* Dropdown Menu */}
            {showDropdown && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-50">
                <button
                  onClick={() => {
                    setShowDropdown(false);
                    setShowSettingsModal(true);
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                >
                  <Settings size={16} />
                  Account Settings
                </button>
                <hr className="my-1 border-slate-200 dark:border-slate-700" />
                <button
                  onClick={() => {
                    setShowDropdown(false);
                    logout();
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                >
                  <LogOut size={16} />
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
