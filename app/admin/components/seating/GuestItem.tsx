import React from 'react';
import { useDraggable } from '@dnd-kit/core';
import { Guest } from '@/types/table';
import { motion } from 'framer-motion';

interface GuestItemProps {
  guest: Guest;
  compact?: boolean;
}

export function GuestItem({ guest, compact = false }: GuestItemProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `guest-${guest.id}`,
    data: { type: 'guest', guest },
  });

  const style: React.CSSProperties | undefined = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        zIndex: 999,
      }
    : undefined;

  return (
    <motion.div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: isDragging ? 0.3 : 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={`
        relative mb-1.5 rounded-xl text-sm cursor-grab active:cursor-grabbing
        border backdrop-blur-md shadow-sm
        transition-colors duration-200
        ${compact ? 'px-2.5 py-2' : 'px-3 py-3'}
        ${isDragging
          ? 'border-blue-300/50 dark:border-blue-700/50 bg-blue-50/40 dark:bg-blue-900/20'
          : 'border-white/30 dark:border-slate-600/30 bg-white/60 dark:bg-slate-800/60 hover:bg-white/80 dark:hover:bg-slate-700/60'}
      `}
    >
      <div className="flex items-center gap-2">
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
    </motion.div>
  );
}
