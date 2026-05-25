'use client';

import React from 'react';
import { Send, Loader2, Archive } from 'lucide-react';

export interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  sending?: boolean;
  disabled?: boolean;
  archived?: boolean;
  placeholder?: string;
  /** Accent color for focus ring and send button */
  accentColor?: 'rose' | 'indigo';
  rows?: number;
}

const accentClasses = {
  rose: {
    focus: 'focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent',
    button: 'bg-rose-500 hover:bg-rose-600',
  },
  indigo: {
    focus: 'focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500',
    button: 'bg-indigo-600 hover:bg-indigo-700',
  },
};

export default function ChatInput({
  value,
  onChange,
  onSend,
  sending = false,
  disabled = false,
  archived = false,
  placeholder = 'Type a message...',
  accentColor = 'indigo',
  rows = 2,
}: ChatInputProps) {
  const colors = accentClasses[accentColor];

  if (archived) {
    return (
      <div className="border-t border-gray-200 dark:border-slate-700 p-3 bg-gray-50 dark:bg-slate-700/50">
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center flex items-center justify-center gap-2">
          <Archive className="w-4 h-4" />
          Messaging is disabled for archived weddings.
        </p>
      </div>
    );
  }

  return (
    <div className="p-4 border-t border-gray-100 dark:border-slate-800 bg-gray-50 dark:bg-slate-800/50">
      <div className="flex items-end gap-2">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`flex-1 p-3 border border-gray-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900 text-gray-900 dark:text-white ${colors.focus} resize-none placeholder-gray-400 dark:placeholder-slate-500`}
          rows={rows}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          disabled={disabled || sending}
        />
        <button
          type="button"
          onClick={onSend}
          disabled={disabled || !value.trim() || sending}
          aria-label={sending ? 'Sending message' : 'Send message'}
          className={`relative z-10 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg ${colors.button} text-white transition disabled:cursor-not-allowed disabled:opacity-50`}
        >
          {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </div>
    </div>
  );
}
