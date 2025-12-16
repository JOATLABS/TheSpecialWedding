import React from 'react';
import { DndContext, DragEndEvent, useSensor, useSensors, PointerSensor, DragOverlay, defaultDropAnimationSideEffects } from '@dnd-kit/core';
import { Table, Guest } from '@/types/table';
import { TableNode } from './TableNode';
import { motion } from 'framer-motion';

interface SeatingCanvasProps {
  tables: Table[];
  guests: Guest[];
  onTableMove: (id: string, x: number, y: number) => void;
  onGuestAssign: (guestId: string, tableId: string) => void;
  onTableDelete: (id: string) => void;
}

export function SeatingCanvas({
  tables,
  guests,
  onTableMove,
  onGuestAssign,
  onTableDelete
}: SeatingCanvasProps) {

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over, delta } = event;

    if (!active || !active.data.current) return;

    const type = active.data.current.type;

    if (type === 'table') {
      const table = active.data.current.table as Table;
      onTableMove(table.id, table.x + delta.x, table.y + delta.y);
    } else if (type === 'guest' && over) {
      const guest = active.data.current.guest as Guest;

      // Check if dropped on a table drop zone
      if (over.data.current && over.data.current.type === 'table-drop') {
        const tableId = over.data.current.tableId;
        if (tableId !== guest.table_id) {
          onGuestAssign(guest.id, tableId);
        }
      }
    }
  };

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="relative w-full h-full overflow-hidden bg-[#f8fafc]">

        {/* Animated Background - Liquid/Mesh Gradient */}
        <div className="absolute inset-0 opacity-40 pointer-events-none">
          <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-purple-200 rounded-full blur-[100px] animate-blob mix-blend-multiply" />
          <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] bg-blue-200 rounded-full blur-[100px] animate-blob animation-delay-2000 mix-blend-multiply" />
          <div className="absolute bottom-[-20%] left-[20%] w-[50%] h-[50%] bg-pink-200 rounded-full blur-[100px] animate-blob animation-delay-4000 mix-blend-multiply" />
        </div>

        {/* Grid Pattern Overlay */}
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage: 'linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)',
            backgroundSize: '40px 40px'
          }}
        />

        {/* Content Layer */}
        <div className="relative w-full h-full z-10">
          {tables.map(table => (
            <TableNode
              key={table.id}
              table={table}
              guests={guests.filter(g => g.table_id === table.id)}
              onDelete={onTableDelete}
            />
          ))}
        </div>
      </div>
    </DndContext>
  );
}
