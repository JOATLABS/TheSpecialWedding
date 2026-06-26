import React from 'react';
import { Table, Guest, VenueFixture, VenueLayout, VenueLayoutPoint } from '@/types/table';
import { TableNode } from './TableNode';
import { FloorPlanLayer, FloorPlanMode } from './FloorPlanLayer';
import { VenueFixtureNode } from './VenueFixtureNode';

interface SeatingCanvasProps {
  tables: Table[];
  guests: Guest[];
  onTableMove: (id: string, x: number, y: number) => void;
  onTableDelete: (id: string) => void;
  onGuestAssign?: (guestId: string, tableId: string) => void;
  zoom?: number;
  venueLayout: VenueLayout;
  floorPlanMode: FloorPlanMode;
  floorPlanOutline: VenueLayoutPoint[];
  venueFixtures: VenueFixture[];
  selectedFixtureId?: string | null;
  tableWarningIds?: ReadonlySet<string>;
  fixtureWarningIds?: ReadonlySet<string>;
  onFloorPlanPointAdd: (point: VenueLayoutPoint) => void;
  onFloorPlanPointMove: (index: number, point: VenueLayoutPoint) => void;
  onFixtureSelect?: (fixtureId: string) => void;
}

export function SeatingCanvas({
  tables,
  guests,
  onTableMove,
  onTableDelete,
  onGuestAssign,
  zoom = 1,
  venueLayout,
  floorPlanMode,
  floorPlanOutline,
  venueFixtures,
  selectedFixtureId = null,
  tableWarningIds,
  fixtureWarningIds,
  onFloorPlanPointAdd,
  onFloorPlanPointMove,
  onFixtureSelect,
}: SeatingCanvasProps) {
  const scaledWidth = venueLayout.canvas_width * zoom;
  const scaledHeight = venueLayout.canvas_height * zoom;

  return (
    <div className="relative w-full h-full overflow-auto">
      {/* Dot grid background — subtle, elegant, works in both themes */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(circle, var(--dot-color, rgba(148,163,184,0.25)) 1px, transparent 1px)`,
          backgroundSize: '24px 24px',
        }}
      />
      {/* CSS variable for dark mode dot color */}
      <style>{`
        .dark [style*="--dot-color"] { --dot-color: rgba(100,116,139,0.2); }
        :root { --dot-color: rgba(148,163,184,0.25); }
      `}</style>

      {/* Subtle gradient overlay for depth */}
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-br from-primary-50/10 via-transparent to-secondary-50/10 dark:from-primary-900/5 dark:via-transparent dark:to-secondary-900/5" />

      {/* Zoomable canvas content */}
      <div
        className="relative"
        style={{
          width: `${scaledWidth}px`,
          height: `${scaledHeight}px`,
          minWidth: '100%',
          minHeight: '100%',
        }}
      >
        <div
          className="relative origin-top-left"
          style={{
            width: `${venueLayout.canvas_width}px`,
            height: `${venueLayout.canvas_height}px`,
            transform: `scale(${zoom})`,
          }}
        >
          <FloorPlanLayer
            layout={venueLayout}
            outline={floorPlanOutline}
            mode={floorPlanMode}
            onPointAdd={onFloorPlanPointAdd}
            onPointMove={onFloorPlanPointMove}
          />

          {venueFixtures.map((fixture) => (
            <VenueFixtureNode
              key={fixture.id}
              fixture={fixture}
              disabled={floorPlanMode === 'draw'}
              selected={selectedFixtureId === fixture.id}
              hasLayoutWarning={fixtureWarningIds?.has(fixture.id) ?? false}
              onSelect={onFixtureSelect}
            />
          ))}

          {tables.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
              <div className="text-center">
                <div className="w-20 h-20 mx-auto mb-3 rounded-full border-2 border-dashed border-slate-300/50 dark:border-slate-600/50 flex items-center justify-center">
                  <span className="text-3xl text-slate-300 dark:text-slate-600">+</span>
                </div>
                <p className="text-sm text-slate-400 dark:text-slate-500 font-medium">
                  Add tables to get started
                </p>
                <p className="text-xs text-slate-400/60 dark:text-slate-500/60 mt-1">
                  Draw the room outline, then drag guests onto tables
                </p>
              </div>
            </div>
          )}

          {tables.map((table) => (
            <TableNode
              key={table.id}
              table={table}
              guests={guests.filter((g) => g.table_id === table.id)}
              onDelete={onTableDelete}
              hasLayoutWarning={tableWarningIds?.has(table.id) ?? false}
            />
          ))}
        </div>

        {floorPlanMode === 'draw' && floorPlanOutline.length === 0 && tables.length > 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
            <div className="text-center">
              <p className="text-sm text-slate-400 dark:text-slate-500 font-medium">
                Click around the room edge to draw the venue outline
              </p>
              <p className="text-xs text-slate-400/60 dark:text-slate-500/60 mt-1">
                Use at least three points, then save the floor plan
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
