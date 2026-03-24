'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useVendorAuth } from '../layout';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import {
  Bell,
  RefreshCw,
  CheckCheck,
  Trash2,
  Megaphone,
  CreditCard,
  AlertTriangle,
  Info,
} from 'lucide-react';

const API_BASE = getApiBaseUrl();

interface Notification {
  _id: string;
  title: string;
  message: string;
  type?: string;
  priority?: string;
  is_read: boolean;
  is_dismissed: boolean;
  created_at: string;
  action_url?: string;
}

export default function VendorNotificationsPage() {
  const { token } = useVendorAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const loadNotifications = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const params = new URLSearchParams({ limit: '50' });
      if (unreadOnly) params.set('unread_only', 'true');

      const res = await fetch(
        `${API_BASE}/admin/user/notifications?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (!res.ok) throw new Error('Failed to load notifications');
      const data = await res.json();
      setNotifications(data.notifications || data || []);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, unreadOnly]);

  useEffect(() => { loadNotifications(); }, [loadNotifications]);

  const markRead = async (id: string) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/admin/user/notifications/${id}/read`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to mark as read');
      setNotifications((prev) =>
        prev.map((n) => (n._id === id ? { ...n, is_read: true } : n))
      );
      window.dispatchEvent(new Event('notifications-updated'));
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  const markAllRead = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/admin/user/notifications/read-all`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to mark all as read');
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      window.dispatchEvent(new Event('notifications-updated'));
      toast.success('All notifications marked as read');
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  const dismissNotification = async (id: string) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/admin/user/notifications/${id}/dismiss`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to dismiss notification');
      setNotifications((prev) => prev.filter((n) => n._id !== id));
      window.dispatchEvent(new Event('notifications-updated'));
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  const getTypeIcon = (type?: string) => {
    switch (type) {
      case 'campaign_approved':
      case 'campaign_paused':
      case 'campaign_update':
        return <Megaphone size={16} className="text-primary-500" />;
      case 'billing':
      case 'payment':
        return <CreditCard size={16} className="text-emerald-500" />;
      case 'warning':
      case 'suspension':
        return <AlertTriangle size={16} className="text-amber-500" />;
      default:
        return <Info size={16} className="text-blue-500" />;
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <RefreshCw size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Notifications</h1>
          <p className="text-sm text-slate-500 mt-1">
            {unreadCount > 0
              ? `${unreadCount} unread notification${unreadCount !== 1 ? 's' : ''}`
              : 'All caught up'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-primary-600 hover:bg-primary-50 dark:hover:bg-primary-900/20 rounded-lg transition-colors"
            >
              <CheckCheck size={16} />
              Mark all read
            </button>
          )}
          <button
            onClick={loadNotifications}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg"
            aria-label="Refresh notifications"
          >
            <RefreshCw size={16} className="text-slate-400" />
          </button>
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setUnreadOnly(false)}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
            !unreadOnly
              ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400 font-medium'
              : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700'
          }`}
        >
          All
        </button>
        <button
          onClick={() => setUnreadOnly(true)}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
            unreadOnly
              ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400 font-medium'
              : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700'
          }`}
        >
          Unread
        </button>
      </div>

      {/* Notifications List */}
      {notifications.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700">
          <Bell size={40} className="mx-auto text-slate-300 mb-3" />
          <h3 className="text-sm font-medium text-slate-900 dark:text-white">
            {unreadOnly ? 'No unread notifications' : 'No notifications yet'}
          </h3>
          <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">
            {unreadOnly
              ? 'You\'re all caught up! Switch to "All" to see past notifications.'
              : 'Notifications about your campaigns, billing, and account will appear here.'}
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 divide-y divide-slate-100 dark:divide-slate-700">
          {notifications.map((n) => (
            <div
              key={n._id}
              className={`flex items-start gap-3 px-5 py-4 transition-colors ${
                !n.is_read ? 'bg-primary-50/30 dark:bg-primary-900/5' : ''
              }`}
            >
              {/* Unread dot */}
              <div className="pt-1 w-5 shrink-0 flex justify-center">
                {!n.is_read && (
                  <span className="w-2 h-2 rounded-full bg-primary-500" />
                )}
              </div>

              {/* Icon */}
              <div className="pt-0.5 shrink-0">{getTypeIcon(n.type)}</div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 dark:text-white">
                  {n.title}
                </p>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                  {n.message}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {new Date(n.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1 shrink-0">
                {!n.is_read && (
                  <button
                    onClick={() => markRead(n._id)}
                    className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                    title="Mark as read"
                  >
                    <CheckCheck size={14} className="text-slate-400" />
                  </button>
                )}
                <button
                  onClick={() => dismissNotification(n._id)}
                  className="p-1.5 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                  title="Dismiss"
                >
                  <Trash2 size={14} className="text-slate-400 hover:text-red-500" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
