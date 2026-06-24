import React from 'react';
import { useDraggable } from '@dnd-kit/core';
import { GripVertical } from 'lucide-react';
import { Guest } from '@/types/table';

interface GuestItemProps {
  guest: Guest;
  compact?: boolean;
}

export function getGuestItemStyle(isDragging: boolean): React.CSSProperties {
  return {
    opacity: isDragging ? 0.35 : 1,
    transition: isDragging ? 'none' : 'opacity 200ms ease, box-shadow 200ms ease',
  };
}

export function GuestItem({ guest, compact = false }: GuestItemProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `guest-${guest.id}`,
    data: { type: 'guest', guest },
  });

  const style = getGuestItemStyle(isDragging);

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-testid={`guest-item-${guest.id}`}
      className={`
        relative mb-1.5 rounded-xl text-sm
        border backdrop-blur-md shadow-sm
        ${compact ? 'px-2.5 py-2' : 'px-3 py-3'}
        ${isDragging
          ? 'border-blue-300/50 dark:border-blue-700/50 bg-blue-50/40 dark:bg-blue-900/20'
          : 'border-white/30 dark:border-slate-600/30 bg-white/60 dark:bg-slate-800/60 hover:bg-white/80 dark:hover:bg-slate-700/60'}
      `}
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          {...listeners}
          {...attributes}
          aria-label={`Drag ${guest.name} to a table`}
          title="Drag guest"
          className={`
            -ml-1 flex flex-shrink-0 items-center justify-center rounded-md
            text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300
            cursor-grab active:cursor-grabbing focus:outline-none focus:ring-2 focus:ring-primary-400/40
            ${compact ? 'h-5 w-5' : 'h-6 w-6'}
          `}
          style={{ touchAction: 'none' }}
        >
          <GripVertical className={compact ? 'h-3.5 w-3.5' : 'h-4 w-4'} aria-hidden="true" />
        </button>
        <div
          className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
            guest.table_id
              ? 'bg-emerald-400 dark:bg-emerald-500'
              : 'bg-amber-400 dark:bg-amber-500'
          }`}
        />
        <span className={`font-medium text-slate-800 dark:text-gray-100 ${compact ? 'text-xs' : 'text-sm'}`}>
          {guest.name}
        </span>
      </div>
      {guest.group_id && (
        <div className={`text-slate-500 dark:text-slate-400 ml-3.5 font-light tracking-wide ${compact ? 'text-[10px] mt-0.5' : 'text-xs mt-1'}`}>
          {guest.group_id}
        </div>
      )}
    </div>
  );
}
