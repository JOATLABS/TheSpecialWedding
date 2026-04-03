'use client';

import React from 'react';
import { Heart, Mail, Paperclip, Reply } from 'lucide-react';

export interface InboxListItemProps {
  id: string;
  type: 'email' | 'couple' | 'planner';
  name: string;
  preview: string;
  isRead: boolean;
  timestamp?: string;
  isSelected?: boolean;
  onClick?: () => void;
  /** Unread message count badge */
  unreadCount?: number;
  /** Wedding label tag */
  weddingLabel?: string;
  /** Whether the email has attachments */
  hasAttachments?: boolean;
  /** Whether the planner has replied to the email */
  hasReplied?: boolean;
  /** Accent color for selected/unread states */
  accentColor?: 'rose' | 'indigo';
}

const accentClasses = {
  rose: {
    selected: 'bg-rose-50 dark:bg-rose-900/10 border-l-rose-500',
    unreadBorder: 'border-l-rose-400 bg-rose-50/50 dark:bg-rose-900/5 hover:bg-rose-50 dark:hover:bg-rose-900/10',
    unreadIcon: 'bg-rose-100 dark:bg-rose-900/30',
    unreadIconColor: 'text-rose-500',
    badge: 'bg-rose-100 text-rose-600 dark:bg-rose-900/30 dark:text-rose-400',
    typeBadgeCouple: 'bg-rose-50 text-rose-500 dark:bg-rose-900/20 dark:text-rose-400',
    typeBadgeEmail: 'bg-blue-50 text-blue-500 dark:bg-blue-900/20 dark:text-blue-400',
  },
  indigo: {
    selected: 'bg-indigo-50 dark:bg-indigo-900/10 border-l-indigo-500',
    unreadBorder: 'border-l-indigo-400 bg-indigo-50/50 dark:bg-indigo-900/5 hover:bg-indigo-50 dark:hover:bg-indigo-900/10',
    unreadIcon: 'bg-indigo-100 dark:bg-indigo-900/30',
    unreadIconColor: 'text-indigo-500',
    badge: 'bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400',
    typeBadgeCouple: 'bg-indigo-50 text-indigo-500 dark:bg-indigo-900/20 dark:text-indigo-400',
    typeBadgeEmail: 'bg-blue-50 text-blue-500 dark:bg-blue-900/20 dark:text-blue-400',
  },
};

const typeLabels: Record<string, string> = {
  email: 'Email',
  couple: 'Couple',
  planner: 'Planner',
};

export default function InboxListItem({
  type,
  name,
  preview,
  isRead,
  timestamp,
  isSelected = false,
  onClick,
  unreadCount,
  weddingLabel,
  hasAttachments,
  hasReplied,
  accentColor = 'indigo',
}: InboxListItemProps) {
  const colors = accentClasses[accentColor];

  const IconComponent = type === 'email' ? Mail : Heart;
  const typeBadgeClass = type === 'email' ? colors.typeBadgeEmail : colors.typeBadgeCouple;

  return (
    <div
      onClick={onClick}
      className={`px-4 py-3 cursor-pointer transition-colors border-l-3 ${
        isSelected
          ? colors.selected
          : isRead
            ? 'border-l-transparent hover:bg-gray-50 dark:hover:bg-slate-800/50'
            : `${colors.unreadBorder}`
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="mt-1 flex-shrink-0">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center ${
              !isRead ? colors.unreadIcon : 'bg-gray-100 dark:bg-slate-700'
            }`}
          >
            <IconComponent
              size={13}
              className={!isRead ? colors.unreadIconColor : 'text-gray-400 dark:text-gray-500'}
            />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <p
              className={`text-sm truncate ${
                !isRead
                  ? 'font-semibold text-gray-900 dark:text-white'
                  : 'font-medium text-gray-700 dark:text-gray-300'
              }`}
            >
              {name}
            </p>
            {timestamp && (
              <span className="text-xs text-gray-400 flex-shrink-0">{timestamp}</span>
            )}
          </div>

          <p
            className={`text-sm truncate mb-0.5 ${
              !isRead
                ? 'text-gray-800 dark:text-gray-200'
                : 'text-gray-600 dark:text-gray-400'
            }`}
          >
            {preview}
          </p>

          <div className="flex items-center gap-2 mt-1">
            {hasAttachments && (
              <span className="inline-flex items-center gap-0.5 text-xs text-gray-400">
                <Paperclip size={10} />
              </span>
            )}
            {hasReplied && (
              <span className="inline-flex items-center gap-0.5 text-xs text-emerald-500">
                <Reply size={10} />
                Replied
              </span>
            )}
            {(unreadCount || 0) > 0 && (
              <span
                className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium ${colors.badge}`}
              >
                {unreadCount}
              </span>
            )}
            {weddingLabel && (
              <span className="text-xs text-gray-400 bg-gray-100 dark:bg-slate-700 px-1.5 py-0.5 rounded truncate max-w-[120px]">
                {weddingLabel}
              </span>
            )}
            <span className={`text-xs px-1.5 py-0.5 rounded ${typeBadgeClass}`}>
              {typeLabels[type] || type}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
