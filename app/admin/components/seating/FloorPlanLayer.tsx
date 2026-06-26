import React, { useRef, useState } from 'react';
import { VenueLayout, VenueLayoutPoint } from '@/types/table';

export type FloorPlanMode = 'select' | 'draw';

export const DEFAULT_FLOOR_PLAN_RECTANGLE: VenueLayoutPoint[] = [
  { x: 120, y: 100 },
  { x: 1480, y: 100 },
  { x: 1480, y: 900 },
  { x: 120, y: 900 },
];

export function pointsToSvgPoints(points: VenueLayoutPoint[]): string {
  return points.map((point) => `${Math.round(point.x)},${Math.round(point.y)}`).join(' ');
}

export function clampVenuePoint(
  point: VenueLayoutPoint,
  layout: Pick<VenueLayout, 'canvas_width' | 'canvas_height'>
): VenueLayoutPoint {
  return {
    x: Math.min(Math.max(point.x, 0), layout.canvas_width),
    y: Math.min(Math.max(point.y, 0), layout.canvas_height),
  };
}

export function getCanvasPointFromPointer(
  event: Pick<React.PointerEvent<SVGSVGElement>, 'clientX' | 'clientY'>,
  svg: SVGSVGElement,
  layout: Pick<VenueLayout, 'canvas_width' | 'canvas_height'>
): VenueLayoutPoint {
  const ctm = svg.getScreenCTM?.();

  if (ctm && typeof svg.createSVGPoint === 'function') {
    const svgPoint = svg.createSVGPoint();
    svgPoint.x = event.clientX;
    svgPoint.y = event.clientY;
    const transformedPoint = svgPoint.matrixTransform(ctm.inverse());
    return clampVenuePoint({ x: transformedPoint.x, y: transformedPoint.y }, layout);
  }

  const rect = svg.getBoundingClientRect();
  const width = rect.width || layout.canvas_width;
  const height = rect.height || layout.canvas_height;
  return clampVenuePoint(
    {
      x: ((event.clientX - rect.left) / width) * layout.canvas_width,
      y: ((event.clientY - rect.top) / height) * layout.canvas_height,
    },
    layout
  );
}

interface FloorPlanLayerProps {
  layout: VenueLayout;
  outline: VenueLayoutPoint[];
  mode: FloorPlanMode;
  onPointAdd: (point: VenueLayoutPoint) => void;
  onPointMove: (index: number, point: VenueLayoutPoint) => void;
}

export function FloorPlanLayer({
  layout,
  outline,
  mode,
  onPointAdd,
  onPointMove,
}: FloorPlanLayerProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [activePointIndex, setActivePointIndex] = useState<number | null>(null);
  const pointsValue = pointsToSvgPoints(outline);
  const canCloseOutline = outline.length >= 3;
  const isDrawing = mode === 'draw';
  const showScaleRuler = Boolean(layout.scale_pixels && layout.scale_distance);
  const scaleRulerLength = Math.min(
    layout.scale_pixels ?? 0,
    Math.max(80, layout.canvas_width - 160)
  );
  const scaleRulerX = 80;
  const scaleRulerY = Math.max(80, layout.canvas_height - 72);
  const scaleRulerLabel = layout.scale_pixels && layout.scale_distance
    ? `${layout.scale_distance}${layout.scale_unit ?? 'ft'}`
    : '';

  const getPoint = (event: React.PointerEvent<SVGSVGElement | SVGCircleElement>) => {
    if (!svgRef.current) return null;
    return getCanvasPointFromPointer(event, svgRef.current, layout);
  };

  const handleCanvasPointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    if (!isDrawing || activePointIndex !== null) return;
    event.preventDefault();
    event.stopPropagation();
    const point = getPoint(event);
    if (point) onPointAdd(point);
  };

  const handlePointPointerDown = (
    event: React.PointerEvent<SVGCircleElement>,
    index: number
  ) => {
    if (!isDrawing) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setActivePointIndex(index);
  };

  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    if (!isDrawing || activePointIndex === null) return;
    event.preventDefault();
    const point = getPoint(event);
    if (point) onPointMove(activePointIndex, point);
  };

  const finishPointMove = (event: React.PointerEvent<SVGSVGElement>) => {
    if (activePointIndex === null) return;
    event.preventDefault();
    setActivePointIndex(null);
  };

  return (
    <svg
      ref={svgRef}
      data-testid="floor-plan-svg"
      aria-label="Venue floor plan drawing area"
      className={`absolute inset-0 ${isDrawing ? 'z-20' : 'z-0'}`}
      viewBox={`0 0 ${layout.canvas_width} ${layout.canvas_height}`}
      preserveAspectRatio="none"
      style={{ pointerEvents: isDrawing ? 'auto' : 'none', touchAction: 'none' }}
      onPointerDown={handleCanvasPointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={finishPointMove}
      onPointerCancel={finishPointMove}
    >
      {isDrawing && (
        <rect
          data-testid="floor-plan-hit-area"
          x={0}
          y={0}
          width={layout.canvas_width}
          height={layout.canvas_height}
          fill="transparent"
          pointerEvents="all"
        />
      )}

      {layout.background_image_data_url && (
        <image
          data-testid="floor-plan-background-image"
          href={layout.background_image_data_url}
          x={0}
          y={0}
          width={layout.canvas_width}
          height={layout.canvas_height}
          preserveAspectRatio="xMidYMid meet"
          opacity={layout.background_locked === false ? 0.32 : 0.42}
          pointerEvents="none"
        />
      )}

      {canCloseOutline && (
        <polygon
          data-testid="floor-plan-polygon"
          points={pointsValue}
          className="fill-blue-500/5 stroke-blue-500/70 dark:fill-blue-400/10 dark:stroke-blue-300/70"
          strokeWidth={4}
          strokeDasharray="18 12"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
          pointerEvents="none"
        />
      )}

      {showScaleRuler && (
        <g
          data-testid="floor-plan-scale-ruler"
          className="text-slate-700 dark:text-slate-200"
          pointerEvents="none"
        >
          <line
            x1={scaleRulerX}
            y1={scaleRulerY}
            x2={scaleRulerX + scaleRulerLength}
            y2={scaleRulerY}
            className="stroke-slate-700 dark:stroke-slate-200"
            strokeWidth={3}
            vectorEffect="non-scaling-stroke"
          />
          <line
            x1={scaleRulerX}
            y1={scaleRulerY - 10}
            x2={scaleRulerX}
            y2={scaleRulerY + 10}
            className="stroke-slate-700 dark:stroke-slate-200"
            strokeWidth={3}
            vectorEffect="non-scaling-stroke"
          />
          <line
            x1={scaleRulerX + scaleRulerLength}
            y1={scaleRulerY - 10}
            x2={scaleRulerX + scaleRulerLength}
            y2={scaleRulerY + 10}
            className="stroke-slate-700 dark:stroke-slate-200"
            strokeWidth={3}
            vectorEffect="non-scaling-stroke"
          />
          <rect
            x={scaleRulerX - 8}
            y={scaleRulerY - 34}
            width={Math.max(82, scaleRulerLabel.length * 9 + 18)}
            height={24}
            rx={6}
            className="fill-white/85 stroke-slate-200 dark:fill-slate-950/80 dark:stroke-slate-700"
            vectorEffect="non-scaling-stroke"
          />
          <text
            x={scaleRulerX + 8}
            y={scaleRulerY - 17}
            className="fill-slate-700 text-xs font-semibold dark:fill-slate-200"
          >
            {scaleRulerLabel}
          </text>
        </g>
      )}

      {outline.length > 1 && !canCloseOutline && (
        <polyline
          data-testid="floor-plan-polyline"
          points={pointsValue}
          className="fill-none stroke-blue-500/70 dark:stroke-blue-300/70"
          strokeWidth={4}
          strokeDasharray="18 12"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
          pointerEvents="none"
        />
      )}

      {isDrawing &&
        outline.map((point, index) => (
          <circle
            key={`${point.x}-${point.y}-${index}`}
            data-testid={`floor-plan-point-${index}`}
            cx={point.x}
            cy={point.y}
            r={8}
            className="fill-white stroke-blue-500 dark:fill-slate-950 dark:stroke-blue-300 cursor-move"
            strokeWidth={3}
            vectorEffect="non-scaling-stroke"
            pointerEvents="auto"
            onPointerDown={(event) => handlePointPointerDown(event, index)}
          />
        ))}
    </svg>
  );
}
