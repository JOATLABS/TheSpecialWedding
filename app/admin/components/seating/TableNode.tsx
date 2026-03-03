import React from 'react';
import { useDroppable, useDraggable } from '@dnd-kit/core';
import { Table, Guest } from '@/types/table';
import { GuestItem } from './GuestItem';
import { Trash2, GripVertical } from 'lucide-react';

interface TableNodeProps {
  table: Table;
  guests: Guest[];
  onDelete: (id: string) => void;
}

export function TableNode({ table, guests, onDelete }: TableNodeProps) {
  // Draggable for moving the table itself (outer positioned wrapper)
  const {
    attributes,
    listeners,
    setNodeRef: setDraggableRef,
    transform,
    isDragging,
  } = useDraggable({
    id: `table-${table.id}`,
    data: { type: 'table', table },
  });

  // Droppable for accepting guests — covers the entire visible card
  const { setNodeRef: setDroppableRef, isOver } = useDroppable({
    id: `table-drop-${table.id}`,
    data: { type: 'table-drop', tableId: table.id },
  });

  const style: React.CSSProperties = {
    transform: transform
      ? `translate3d(${transform.x + table.x}px, ${transform.y + table.y}px, 0)`
      : `translate3d(${table.x}px, ${table.y}px, 0)`,
    position: 'absolute',
    left: 0,
    top: 0,
    zIndex: isDragging ? 50 : 10,
    opacity: isDragging ? 0.5 : 1,
    transition: isDragging ? 'none' : 'opacity 200ms ease',
  };

  const isOverCapacity = guests.length > table.capacity;
  const isAtCapacity = guests.length >= table.capacity;
  const wouldExceedCapacity = isOver && isAtCapacity;
  const utilizationPct = table.capacity > 0 ? (guests.length / table.capacity) * 100 : 0;

  // Shape styling
  const isRound = table.shape === 'round';
  const borderRadius = isRound ? 'rounded-[28px]' : 'rounded-2xl';

  // Ring color based on state
  const ringClass = wouldExceedCapacity
    ? 'ring-2 ring-amber-400/60 dark:ring-amber-500/40'
    : isOver
    ? 'ring-2 ring-blue-400/60 dark:ring-blue-400/40'
    : isOverCapacity
    ? 'ring-2 ring-red-400/60 dark:ring-red-500/40'
    : '';

  // Background tint based on state
  const bgTint = wouldExceedCapacity
    ? 'bg-amber-50/30 dark:bg-amber-900/10'
    : isOver
    ? 'bg-blue-50/30 dark:bg-blue-900/10'
    : '';

  return (
    // Outer wrapper: draggable ref for table positioning
    <div ref={setDraggableRef} style={style} className="group">
      {/* Inner card: droppable ref for guest drops — NOT overflow-hidden
          so dragged guests inside aren't clipped */}
      <div
        ref={setDroppableRef}
        className={`
          relative w-72 ${borderRadius}
          bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl
          border border-white/50 dark:border-slate-700/50
          shadow-sm hover:shadow-lg
          transition-shadow duration-300
          ${ringClass} ${bgTint}
        `}
      >
        {/* Header / Drag Handle */}
        <div
          {...listeners}
          {...attributes}
          className="px-3 py-2.5 border-b border-white/30 dark:border-slate-700/30 flex justify-between items-center cursor-grab active:cursor-grabbing bg-gradient-to-r from-white/40 dark:from-slate-800/40 to-transparent select-none"
        >
          <div className="flex items-center gap-2">
            <GripVertical className="w-4 h-4 text-slate-400 dark:text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" />
            <div
              className={`
              w-7 h-7 flex items-center justify-center text-xs font-bold
              ${isRound ? 'rounded-full' : 'rounded-md'}
              ${
                isOverCapacity
                  ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800/40'
                  : 'bg-white/50 dark:bg-slate-700/50 text-slate-600 dark:text-slate-300 border border-white/40 dark:border-slate-600/40'
              }
            `}
            >
              {guests.length}
            </div>
            <span className="font-semibold text-slate-800 dark:text-gray-100 text-sm">
              {table.name}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full border ${
                isOverCapacity
                  ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-200/50 dark:border-red-800/30 font-bold'
                  : 'bg-white/30 dark:bg-slate-700/30 text-slate-500 dark:text-slate-400 border-white/20 dark:border-slate-600/20'
              }`}
            >
              {guests.length}/{table.capacity}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(table.id);
              }}
              className="w-6 h-6 flex items-center justify-center rounded-full opacity-0 group-hover:opacity-100 hover:bg-red-50 dark:hover:bg-red-900/30 text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 transition-all"
              title="Delete table"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Capacity bar */}
        <div className="h-0.5 bg-slate-100 dark:bg-slate-800">
          <div
            className={`h-full transition-all duration-500 ${
              isOverCapacity
                ? 'bg-red-400 dark:bg-red-500'
                : utilizationPct > 80
                ? 'bg-amber-400 dark:bg-amber-500'
                : 'bg-emerald-400 dark:bg-emerald-500'
            }`}
            style={{ width: `${Math.min(100, utilizationPct)}%` }}
          />
        </div>

        {/* Guest List Area */}
        <div
          className={`p-2.5 min-h-[100px] max-h-[220px] overflow-y-auto ${borderRadius === 'rounded-[28px]' ? 'rounded-b-[28px]' : 'rounded-b-2xl'}`}
          style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(148,163,184,0.3) transparent' }}
        >
          {guests.map((guest) => (
            <GuestItem key={guest.id} guest={guest} compact />
          ))}

          {guests.length === 0 && !wouldExceedCapacity && (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 py-6 gap-1.5">
              <div className="w-10 h-10 rounded-full border-2 border-dashed border-slate-300/50 dark:border-slate-600/50 flex items-center justify-center">
                <span className="text-lg text-slate-300 dark:text-slate-600">+</span>
              </div>
              <span className="text-[11px] font-medium">Drop guests here</span>
            </div>
          )}

          {/* Capacity warning overlay on drag-over */}
          {wouldExceedCapacity && (
            <div className="absolute inset-x-0 bottom-0 top-[42px] flex flex-col items-center justify-center bg-amber-50/80 dark:bg-amber-900/30 backdrop-blur-sm rounded-b-2xl z-10">
              <div className="text-amber-600 dark:text-amber-400 text-center px-4">
                <p className="text-xs font-semibold">Table at capacity</p>
                <p className="text-[10px] opacity-75 mt-0.5">
                  ({guests.length}/{table.capacity} seats filled)
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
