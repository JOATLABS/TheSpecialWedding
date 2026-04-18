'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useSSEEvent } from '@/contexts/SSEContext';
import { Settings, LogOut } from 'lucide-react';
import { getApiBaseUrl } from '@/utils/env';
import AccountSettingsModal from './AccountSettingsModal';
import { WorkspaceTopHeader } from '@/components/layout/WorkspaceChrome';

interface TopHeaderProps {
  onMenuClick: () => void;
  title?: string;
}

export default function TopHeader({ onMenuClick, title }: TopHeaderProps) {
  const { userProfile, token, logout } = useAdmin();
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  // --- SSE: subscribe to notification events via the shared SSEProvider ---
  useSSEEvent('notification-count', useCallback((data: unknown) => {
    const d = data as { unread?: number };
    setUnreadCount(d.unread || 0);
  }, []));

  useSSEEvent('notification-new', useCallback((data: unknown) => {
    window.dispatchEvent(new CustomEvent('notification-received', { detail: data }));
  }, []));

  // Listen for local "notifications-updated" events (e.g. user marks as read)
  // to trigger an immediate re-fetch via a one-shot REST call
  useEffect(() => {
    if (!token) return;
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
    window.addEventListener('notifications-updated', handleNotificationsRead);
    return () => window.removeEventListener('notifications-updated', handleNotificationsRead);
  }, [token]);

  return (
    <>
      <WorkspaceTopHeader
        onMenuClick={onMenuClick}
        title={title}
        notificationHref={userProfile?.is_root_admin ? '/admin/notifications?tab=inbox' : '/admin/notifications?tab=history'}
        notificationCount={unreadCount}
        user={{
          name: userProfile?.first_name || userProfile?.email?.split('@')[0] || 'User',
          email: userProfile?.email,
          profileImageUrl: userProfile?.profile_image_url,
          initials: `${userProfile?.first_name?.charAt(0) || ''}${userProfile?.last_name?.charAt(0) || ''}`.toUpperCase() || undefined,
        }}
        menuItems={[
          {
            key: 'settings',
            label: 'Account Settings',
            icon: Settings,
            onSelect: () => setShowSettingsModal(true),
          },
          {
            key: 'logout',
            label: 'Logout',
            icon: LogOut,
            tone: 'danger',
            onSelect: () => logout(),
          },
        ]}
      />
      <AccountSettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
      />
    </>
  );
}
