import React from 'react';
import { useDraggable } from '@dnd-kit/core';
import { Guest } from '@/types/table';
import { motion } from 'framer-motion';

interface GuestItemProps {
  guest: Guest;
}

export function GuestItem({ guest }: GuestItemProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `guest-${guest.id}`,
    data: { type: 'guest', guest },
  });

  const style = transform
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
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9 }}
      whileHover={{ scale: 1.02, boxShadow: "0 4px 15px rgba(0,0,0,0.1)" }}
      whileTap={{ scale: 0.98 }}
      className={`
        relative p-3 mb-2 rounded-xl text-sm cursor-grab active:cursor-grabbing
        border border-white/20 backdrop-blur-md shadow-sm
        transition-colors duration-200
        ${isDragging
          ? 'bg-blue-50/80 border-blue-300 ring-2 ring-blue-200/50 shadow-lg z-50'
          : 'bg-white/60 hover:bg-white/80'}
      `}
    >
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${guest.table_id ? 'bg-green-400' : 'bg-amber-400'}`} />
        <div className="font-medium text-gray-800">{guest.name}</div>
      </div>
      {guest.group_id && (
        <div className="text-xs text-gray-500 mt-1 ml-4 font-light tracking-wide">{guest.group_id}</div>
      )}
    </motion.div>
  );
}
