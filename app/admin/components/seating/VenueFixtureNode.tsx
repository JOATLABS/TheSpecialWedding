import React from 'react';
import { useDraggable } from '@dnd-kit/core';
import {
  Accessibility,
  ChefHat,
  DoorOpen,
  Footprints,
  GlassWater,
  Mic2,
  Move,
  Square,
} from 'lucide-react';
import { VenueFixture } from '@/types/table';

interface VenueFixtureNodeProps {
  fixture: VenueFixture;
  disabled?: boolean;
  selected?: boolean;
  hasLayoutWarning?: boolean;
  onSelect?: (fixtureId: string) => void;
}

const fixtureStyles: Record<VenueFixture['type'], string> = {
  dance_floor: 'border-blue-300/70 bg-blue-50/75 text-blue-700 dark:border-blue-500/40 dark:bg-blue-950/50 dark:text-blue-200',
  bar: 'border-amber-300/70 bg-amber-50/75 text-amber-700 dark:border-amber-500/40 dark:bg-amber-950/50 dark:text-amber-200',
  stage: 'border-violet-300/70 bg-violet-50/75 text-violet-700 dark:border-violet-500/40 dark:bg-violet-950/50 dark:text-violet-200',
  entrance: 'border-emerald-300/70 bg-emerald-50/75 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-950/50 dark:text-emerald-200',
  restrooms: 'border-cyan-300/70 bg-cyan-50/75 text-cyan-700 dark:border-cyan-500/40 dark:bg-cyan-950/50 dark:text-cyan-200',
  kitchen: 'border-rose-300/70 bg-rose-50/75 text-rose-700 dark:border-rose-500/40 dark:bg-rose-950/50 dark:text-rose-200',
  vendor_path: 'border-slate-300/80 bg-slate-50/70 text-slate-700 dark:border-slate-500/40 dark:bg-slate-900/60 dark:text-slate-200',
};

function FixtureIcon({ type }: { type: VenueFixture['type'] }) {
  const className = "h-4 w-4";
  switch (type) {
    case 'bar':
      return <GlassWater className={className} aria-hidden="true" />;
    case 'stage':
      return <Mic2 className={className} aria-hidden="true" />;
    case 'entrance':
      return <DoorOpen className={className} aria-hidden="true" />;
    case 'restrooms':
      return <Accessibility className={className} aria-hidden="true" />;
    case 'kitchen':
      return <ChefHat className={className} aria-hidden="true" />;
    case 'vendor_path':
      return <Footprints className={className} aria-hidden="true" />;
    case 'dance_floor':
    default:
      return <Square className={className} aria-hidden="true" />;
  }
}

export function VenueFixtureNode({
  fixture,
  disabled = false,
  selected = false,
  hasLayoutWarning = false,
  onSelect,
}: VenueFixtureNodeProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    isDragging,
  } = useDraggable({
    id: `fixture-${fixture.id}`,
    data: { type: 'fixture', fixture },
    disabled,
  });

  const style: React.CSSProperties = {
    position: 'absolute',
    left: 0,
    top: 0,
    width: fixture.width,
    height: fixture.height,
    transform: transform
      ? `translate3d(${fixture.x + transform.x}px, ${fixture.y + transform.y}px, 0) rotate(${fixture.rotation ?? 0}deg)`
      : `translate3d(${fixture.x}px, ${fixture.y}px, 0) rotate(${fixture.rotation ?? 0}deg)`,
    zIndex: isDragging ? 35 : 5,
    opacity: isDragging ? 0.72 : 1,
    transition: isDragging ? 'none' : 'opacity 180ms ease, box-shadow 180ms ease',
    transformOrigin: 'center center',
  };

  return (
    <div
      ref={setNodeRef}
      data-testid={`venue-fixture-${fixture.id}`}
      style={style}
      className={`
        group flex items-center justify-center rounded-lg border-2 border-dashed
        px-3 text-center shadow-sm backdrop-blur-sm
        ${selected ? 'ring-2 ring-slate-900/70 dark:ring-white/70' : ''}
        ${hasLayoutWarning ? 'ring-2 ring-amber-400/80 dark:ring-amber-300/70' : ''}
        ${fixtureStyles[fixture.type]}
      `}
    >
      <button
        type="button"
        {...listeners}
        {...attributes}
        disabled={disabled}
        onClick={() => onSelect?.(fixture.id)}
        aria-label={`Move ${fixture.label}`}
        title={`Move ${fixture.label}`}
        className="flex h-full w-full items-center justify-center gap-2 text-xs font-semibold leading-tight disabled:cursor-default cursor-grab active:cursor-grabbing"
        style={{ touchAction: 'none' }}
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white/65 text-current shadow-sm dark:bg-slate-950/50">
          <FixtureIcon type={fixture.type} />
        </span>
        <span className="min-w-0 truncate">{fixture.label}</span>
        <Move className="h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-60" aria-hidden="true" />
      </button>
    </div>
  );
}
