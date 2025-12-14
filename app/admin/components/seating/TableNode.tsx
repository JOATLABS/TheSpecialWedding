import React from 'react';
import { useDroppable, useDraggable } from '@dnd-kit/core';
import { Table, Guest } from '@/types/table';
import { GuestItem } from './GuestItem';

interface TableNodeProps {
  table: Table;
  guests: Guest[];
  onDelete: (id: string) => void;
}

export function TableNode({ table, guests, onDelete }: TableNodeProps) {
  // Draggable for moving the table itself
  const {
    attributes,
    listeners,
    setNodeRef: setDraggableRef,
    transform
  } = useDraggable({
    id: `table-${table.id}`,
    data: { type: 'table', table },
  });

  // Droppable for accepting guests
  const { setNodeRef: setDroppableRef } = useDroppable({
    id: `table-drop-${table.id}`,
    data: { type: 'table-drop', tableId: table.id },
  });

  const style = {
    transform: transform
      ? `translate3d(${transform.x + table.x}px, ${transform.y + table.y}px, 0)`
      : `translate3d(${table.x}px, ${table.y}px, 0)`,
    position: 'absolute' as const,
    left: 0,
    top: 0,
  };

  const isOverCapacity = guests.length > table.capacity;

  return (
    <div
      ref={setDraggableRef}
      style={style}
      className={`
        w-64 bg-white/90 backdrop-blur rounded-lg shadow-lg border-2
        ${isOverCapacity ? 'border-red-400' : 'border-blue-200'}
        flex flex-col
      `}
    >
      {/* Header / Handle */}
      <div
        {...listeners}
        {...attributes}
        className="p-2 border-b border-gray-100 flex justify-between items-center cursor-move bg-gray-50 rounded-t-lg"
      >
        <span className="font-semibold text-gray-700">{table.name}</span>
        <div className="flex items-center gap-2">
          <span className={`text-xs ${isOverCapacity ? 'text-red-500 font-bold' : 'text-gray-500'}`}>
            {guests.length}/{table.capacity}
          </span>
          <button
            onClick={() => onDelete(table.id)}
            className="text-gray-400 hover:text-red-500"
          >
            ×
          </button>
        </div>
      </div>

      {/* Guest List Drop Zone */}
      <div
        ref={setDroppableRef}
        className="p-2 min-h-[100px] max-h-[200px] overflow-y-auto"
      >
        {guests.map((guest) => (
          <GuestItem key={guest.id} guest={guest} />
        ))}
        {guests.length === 0 && (
          <div className="text-center text-gray-400 text-xs py-4">
            Drag guests here
          </div>
        )}
      </div>
    </div>
  );
}
