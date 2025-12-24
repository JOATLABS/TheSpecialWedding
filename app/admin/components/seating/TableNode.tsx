import React from 'react';
import { useDroppable, useDraggable } from '@dnd-kit/core';
import { Table, Guest } from '@/types/table';
import { GuestItem } from './GuestItem';
import { motion, AnimatePresence } from 'framer-motion';

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
    transform,
    isDragging
  } = useDraggable({
    id: `table-${table.id}`,
    data: { type: 'table', table },
  });

  // Droppable for accepting guests
  const { setNodeRef: setDroppableRef, isOver } = useDroppable({
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
    zIndex: isDragging ? 50 : 10,
  };

  const isOverCapacity = guests.length > table.capacity;

  // Visual variants for table shape
  const borderRadius = table.shape === 'round' ? 'rounded-[32px]' : 'rounded-2xl';

  return (
    <div
      ref={setDraggableRef}
      style={style}
      className={`group transition-shadow duration-300 ${isDragging ? 'z-50' : ''}`}
    >
      <motion.div
        layoutId={`table-${table.id}`}
        initial={{ scale: 0.9, opacity: 0, rotateX: 0, rotateY: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        whileHover={{ scale: 1.02, rotateX: 5, rotateY: 5 }}
        whileTap={{ scale: 0.98 }}
        className={`
          w-72 ${borderRadius}
          bg-white/40 backdrop-blur-xl
          border border-white/50
          shadow-[0_8px_32px_0_rgba(31,38,135,0.07)]
          overflow-hidden
          transition-all duration-300
          ${isOver ? 'ring-2 ring-blue-400/50 bg-blue-50/40' : ''}
          ${isOverCapacity ? 'ring-2 ring-red-400/50' : ''}
        `}
        style={{ transformStyle: "preserve-3d", perspective: 1000 }}
      >
        {/* Header / Handle */}
        <div
          {...listeners}
          {...attributes}
          className={`
            p-3 border-b border-white/20
            flex justify-between items-center
            cursor-grab active:cursor-grabbing
            bg-gradient-to-r from-white/40 to-transparent
          `}
        >
          <div className="flex items-center gap-2">
            <div className={`
              w-8 h-8 flex items-center justify-center
              ${table.shape === 'round' ? 'rounded-full' : 'rounded-md'}
              bg-white/50 border border-white/40 text-gray-600 shadow-sm
            `}>
              <span className="text-xs font-bold">{guests.length}</span>
            </div>
            <span className="font-playfair font-semibold text-gray-800">{table.name}</span>
          </div>

          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-1 rounded-full bg-white/30 border border-white/20 ${isOverCapacity ? 'text-red-600 font-bold' : 'text-gray-500'}`}>
              Max {table.capacity}
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(table.id); }}
              className="w-6 h-6 flex items-center justify-center rounded-full hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
            >
              ×
            </button>
          </div>
        </div>

        {/* Guest List Drop Zone */}
        <div
          ref={setDroppableRef}
          className="p-3 min-h-[120px] max-h-[240px] overflow-y-auto custom-scrollbar"
        >
          <AnimatePresence>
            {guests.map((guest) => (
              <GuestItem key={guest.id} guest={guest} />
            ))}
          </AnimatePresence>

          {guests.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-gray-400 py-6 gap-2">
              <div className="w-12 h-12 rounded-full border-2 border-dashed border-gray-300 flex items-center justify-center">
                <span className="text-xl">+</span>
              </div>
              <span className="text-xs font-medium">Drop Guests Here</span>
            </div>
          )}
        </div>

        {/* Footer decoration */}
        <div className="h-1 bg-gradient-to-r from-blue-400/30 via-purple-400/30 to-pink-400/30" />
      </motion.div>
    </div>
  );
}
