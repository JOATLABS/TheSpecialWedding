import React from 'react';
import { Table, Guest } from '@/types/table';
import { TableNode } from './TableNode';
import { LiquidBackground } from './LiquidBackground';

interface SeatingCanvasProps {
  tables: Table[];
  guests: Guest[];
  onTableMove: (id: string, x: number, y: number) => void;
  onTableDelete: (id: string) => void;
}

export function SeatingCanvas({
  tables,
  guests,
  onTableMove,
  onTableDelete
}: SeatingCanvasProps) {
  // DndContext is now provided by parent (page.tsx) to include both Sidebar and Canvas
  return (
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
  );
}
