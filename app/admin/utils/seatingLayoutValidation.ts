import { Table, VenueFixture, VenueLayoutPoint } from '@/types/table';

export type SeatingLayoutIssueTarget = 'table' | 'fixture' | 'layout';
export type SeatingLayoutIssueSeverity = 'warning' | 'error';

export interface SeatingLayoutIssue {
  id: string;
  severity: SeatingLayoutIssueSeverity;
  targetType: SeatingLayoutIssueTarget;
  targetId?: string;
  message: string;
}

interface Rect {
  id: string;
  label: string;
  type: 'table' | 'fixture';
  x: number;
  y: number;
  width: number;
  height: number;
}

interface ValidateSeatingLayoutArgs {
  tables: Table[];
  fixtures: VenueFixture[];
  outline: VenueLayoutPoint[];
  canvasWidth: number;
  canvasHeight: number;
}

const TABLE_WIDTH = 288;
const TABLE_HEIGHT = 180;

function rectFromTable(table: Table): Rect {
  return {
    id: table.id,
    label: table.name,
    type: 'table',
    x: table.x,
    y: table.y,
    width: TABLE_WIDTH,
    height: TABLE_HEIGHT,
  };
}

function rectFromFixture(fixture: VenueFixture): Rect {
  return rotatedBoundingRect({
    id: fixture.id,
    label: fixture.label,
    type: 'fixture',
    x: fixture.x,
    y: fixture.y,
    width: fixture.width,
    height: fixture.height,
  }, fixture.rotation ?? 0);
}

function rectCorners(rect: Rect): VenueLayoutPoint[] {
  return [
    { x: rect.x, y: rect.y },
    { x: rect.x + rect.width, y: rect.y },
    { x: rect.x + rect.width, y: rect.y + rect.height },
    { x: rect.x, y: rect.y + rect.height },
  ];
}

function rotatedBoundingRect(rect: Rect, rotation: number): Rect {
  const normalizedRotation = rotation % 360;
  if (normalizedRotation === 0) return rect;

  const radians = normalizedRotation * (Math.PI / 180);
  const centerX = rect.x + rect.width / 2;
  const centerY = rect.y + rect.height / 2;
  const corners = rectCorners(rect).map((point) => {
    const offsetX = point.x - centerX;
    const offsetY = point.y - centerY;
    return {
      x: centerX + offsetX * Math.cos(radians) - offsetY * Math.sin(radians),
      y: centerY + offsetX * Math.sin(radians) + offsetY * Math.cos(radians),
    };
  });
  const xs = corners.map((point) => point.x);
  const ys = corners.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  return {
    ...rect,
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
  };
}

function isInsideCanvas(rect: Rect, canvasWidth: number, canvasHeight: number): boolean {
  return rect.x >= 0
    && rect.y >= 0
    && rect.x + rect.width <= canvasWidth
    && rect.y + rect.height <= canvasHeight;
}

export function pointInPolygon(point: VenueLayoutPoint, polygon: VenueLayoutPoint[]): boolean {
  if (polygon.length < 3) return true;

  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const current = polygon[i];
    const previous = polygon[j];
    const intersects = ((current.y > point.y) !== (previous.y > point.y))
      && point.x < ((previous.x - current.x) * (point.y - current.y)) / (previous.y - current.y) + current.x;
    if (intersects) inside = !inside;
  }
  return inside;
}

function rectInsideOutline(rect: Rect, outline: VenueLayoutPoint[]): boolean {
  if (outline.length < 3) return true;
  return rectCorners(rect).every((corner) => pointInPolygon(corner, outline));
}

export function rectsOverlap(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.width
    && a.x + a.width > b.x
    && a.y < b.y + b.height
    && a.y + a.height > b.y;
}

function issueTargetFor(rect: Rect): Pick<SeatingLayoutIssue, 'targetType' | 'targetId'> {
  return {
    targetType: rect.type,
    targetId: rect.id,
  };
}

export function validateSeatingLayout({
  tables,
  fixtures,
  outline,
  canvasWidth,
  canvasHeight,
}: ValidateSeatingLayoutArgs): SeatingLayoutIssue[] {
  const issues: SeatingLayoutIssue[] = [];
  const rects = [
    ...tables.map(rectFromTable),
    ...fixtures.map(rectFromFixture),
  ];

  if (outline.length > 0 && outline.length < 3) {
    issues.push({
      id: 'outline-incomplete',
      severity: 'error',
      targetType: 'layout',
      message: 'Room outline needs at least three points before it can guide the layout.',
    });
  }

  for (const rect of rects) {
    if (!isInsideCanvas(rect, canvasWidth, canvasHeight)) {
      issues.push({
        id: `${rect.type}-${rect.id}-canvas`,
        severity: 'warning',
        ...issueTargetFor(rect),
        message: `${rect.label} is partly outside the canvas.`,
      });
    }

    if (!rectInsideOutline(rect, outline)) {
      issues.push({
        id: `${rect.type}-${rect.id}-outline`,
        severity: 'warning',
        ...issueTargetFor(rect),
        message: `${rect.label} is partly outside the room outline.`,
      });
    }
  }

  for (let i = 0; i < rects.length; i += 1) {
    for (let j = i + 1; j < rects.length; j += 1) {
      const current = rects[i];
      const next = rects[j];
      if (!rectsOverlap(current, next)) continue;
      issues.push({
        id: `${current.type}-${current.id}-${next.type}-${next.id}-overlap`,
        severity: 'warning',
        targetType: current.type,
        targetId: current.id,
        message: `${current.label} overlaps ${next.label}.`,
      });
    }
  }

  return issues;
}
