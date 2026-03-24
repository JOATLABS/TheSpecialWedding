'use client';

import React from 'react';
import { Eye } from 'lucide-react';

export interface MessageBubbleProps {
  content: string;
  senderName?: string;
  isSelf: boolean;
  timestamp?: string;
  isRead?: boolean;
  showReadIndicator?: boolean;
  /** Primary color for "self" messages. Defaults to 'indigo' */
  accentColor?: 'rose' | 'indigo';
}

const accentClasses = {
  rose: {
    self: 'bg-rose-500 text-white rounded-br-md',
    selfTime: 'text-white/60',
    readIcon: 'text-white/60',
  },
  indigo: {
    self: 'bg-indigo-600 text-white rounded-br-md',
    selfTime: 'text-white/50',
    readIcon: 'text-white/50',
  },
};

export default function MessageBubble({
  content,
  senderName,
  isSelf,
  timestamp,
  isRead,
  showReadIndicator = false,
  accentColor = 'indigo',
}: MessageBubbleProps) {
  const colors = accentClasses[accentColor];

  return (
    <div className={`flex ${isSelf ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] px-3.5 py-2.5 rounded-2xl text-sm ${
          isSelf
            ? colors.self
            : 'bg-gray-100 dark:bg-slate-700 text-gray-900 dark:text-white rounded-bl-md'
        }`}
      >
        {!isSelf && senderName && (
          <p className="text-xs font-medium mb-1 opacity-70">{senderName}</p>
        )}
        <p className="whitespace-pre-wrap">{content}</p>
        {timestamp && (
          <div className={`flex items-center gap-1.5 mt-1 ${isSelf ? 'justify-end' : ''}`}>
            <span className={`text-[10px] ${
              isSelf ? colors.selfTime : 'text-gray-400'
            }`}>
              {timestamp}
            </span>
            {isSelf && showReadIndicator && isRead && (
              <Eye className={`w-3 h-3 ${colors.readIcon}`} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
