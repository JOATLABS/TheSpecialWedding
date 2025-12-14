import React from 'react';
import { useDraggable } from '@dnd-kit/core';
import { Guest } from '@/types/table';

interface GuestItemProps {
  guest: Guest;
}

export function GuestItem({ guest }: GuestItemProps) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: `guest-${guest.id}`,
    data: { type: 'guest', guest },
  });

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
      }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className="p-2 mb-2 bg-white rounded shadow text-sm cursor-grab active:cursor-grabbing border border-gray-200 hover:border-blue-300"
    >
      <div className="font-medium text-gray-800">{guest.name}</div>
      {guest.group_id && (
        <div className="text-xs text-gray-500">{guest.group_id}</div>
      )}
    </div>
  );
}
