import React from 'react';
import { DndContext, DragEndEvent, useSensor, useSensors, PointerSensor } from '@dnd-kit/core';
import { Table, Guest } from '@/types/table';
import { TableNode } from './TableNode';
import { LiquidBackground } from './LiquidBackground';

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
      <div className="relative w-full h-full overflow-hidden bg-light-bg dark:bg-dark-bg">

        {/* 3D Liquid Background */}
        <LiquidBackground />

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
