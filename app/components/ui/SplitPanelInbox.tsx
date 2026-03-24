'use client';

import React, { useCallback, useRef } from 'react';
import { GripVertical, RefreshCw, Inbox } from 'lucide-react';

export interface SplitPanelInboxProps {
  /** Left panel content (conversation list) */
  listContent: React.ReactNode;
  /** Right panel content (detail/chat view) */
  detailContent: React.ReactNode;
  /** Whether a conversation is selected (controls detail panel visibility) */
  hasSelection: boolean;
  /** Loading state for the list */
  loading?: boolean;
  /** Empty state message for the list */
  emptyMessage?: string;
  emptySubMessage?: string;
  /** Whether to show mobile detail panel */
  mobileShowDetail?: boolean;
  /** Whether the drag handle for resizing is enabled */
  resizable?: boolean;
  /** Default list panel width percent (default 40) */
  defaultListWidth?: number;
  /** Minimum height (default calc(100vh-300px)) */
  minHeight?: string;
}

export default function SplitPanelInbox({
  listContent,
  detailContent,
  hasSelection,
  loading = false,
  emptyMessage,
  emptySubMessage,
  mobileShowDetail = false,
  resizable = false,
  defaultListWidth = 40,
  minHeight = 'calc(100vh-300px)',
}: SplitPanelInboxProps) {
  const [listWidthPercent, setListWidthPercent] = React.useState(defaultListWidth);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!resizable) return;
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handleMouseMove = (ev: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const percent = (x / rect.width) * 100;
      setListWidthPercent(Math.min(70, Math.max(20, percent)));
    };

    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [resizable]);

  return (
    <div ref={containerRef} className="flex min-h-[600px] gap-0">
      {/* Left Panel — List */}
      <div
        className={`bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 overflow-hidden flex-shrink-0 ${
          mobileShowDetail ? 'hidden lg:block' : ''
        }`}
        style={{ width: `${listWidthPercent}%` }}
      >
        <div
          className="divide-y divide-gray-100 dark:divide-slate-800 overflow-y-auto"
          style={{ maxHeight: minHeight }}
        >
          {loading ? (
            <div className="p-8 text-center text-gray-400">
              <RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin" />
              <p>Loading messages...</p>
            </div>
          ) : emptyMessage ? (
            <div className="p-12 text-center text-gray-400">
              <Inbox className="w-12 h-12 mx-auto mb-3 opacity-40" />
              <p className="font-medium mb-1">{emptyMessage}</p>
              {emptySubMessage && <p className="text-sm">{emptySubMessage}</p>}
            </div>
          ) : (
            listContent
          )}
        </div>
      </div>

      {/* Drag Handle / Spacer */}
      {resizable ? (
        <div
          onMouseDown={handleMouseDown}
          className="hidden lg:flex items-center justify-center w-3 cursor-col-resize group flex-shrink-0 hover:bg-slate-200/50 dark:hover:bg-slate-700/50 rounded transition-colors mx-0.5"
          title="Drag to resize panels"
        >
          <GripVertical className="w-3.5 h-3.5 text-slate-300 dark:text-slate-600 group-hover:text-slate-500 dark:group-hover:text-slate-400 transition-colors" />
        </div>
      ) : (
        <div className="hidden lg:flex items-center justify-center w-3 flex-shrink-0 mx-0.5" />
      )}

      {/* Right Panel — Detail */}
      <div className={`flex-1 min-w-0 ${!mobileShowDetail ? 'hidden lg:block' : ''}`}>
        {hasSelection ? (
          detailContent
        ) : (
          <div
            className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 flex items-center justify-center"
            style={{ height: minHeight }}
          >
            <div className="text-center text-gray-400">
              <Inbox className="w-14 h-14 mx-auto mb-4 opacity-30" />
              <p className="font-medium text-gray-500 dark:text-gray-400">
                Select a conversation
              </p>
              <p className="text-sm mt-1">Choose a message from the list</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
