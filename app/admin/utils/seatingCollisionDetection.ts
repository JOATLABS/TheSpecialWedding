import {
  closestCenter,
  pointerWithin,
  rectIntersection,
  type CollisionDetection,
} from '@dnd-kit/core';

const TABLE_DROP_FALLBACK_DISTANCE_PX = 220;

function rectCenter(rect: { left: number; top: number; width: number; height: number }) {
  return {
    x: rect.left + rect.width / 2,
    y: rect.top + rect.height / 2,
  };
}

function distanceFromPointToRect(
  point: { x: number; y: number },
  rect: { left: number; top: number; right: number; bottom: number }
) {
  const dx = Math.max(rect.left - point.x, 0, point.x - rect.right);
  const dy = Math.max(rect.top - point.y, 0, point.y - rect.bottom);
  return Math.hypot(dx, dy);
}

export const seatingCollisionDetection: CollisionDetection = (args) => {
  const pointerCollisions = pointerWithin(args);

  if (pointerCollisions.length > 0) {
    return pointerCollisions;
  }

  const rectangleCollisions = rectIntersection(args);

  if (rectangleCollisions.length > 0) {
    return rectangleCollisions;
  }

  if (args.active.data.current?.type !== 'guest') {
    return [];
  }

  const dragCenter = rectCenter(args.collisionRect);
  const nearbyTableDrops = args.droppableContainers.filter((container) => {
    if (container.data.current?.type !== 'table-drop') {
      return false;
    }

    const rect = args.droppableRects.get(container.id);
    if (!rect) {
      return false;
    }

    return distanceFromPointToRect(dragCenter, rect) <= TABLE_DROP_FALLBACK_DISTANCE_PX;
  });

  if (nearbyTableDrops.length === 0) {
    return [];
  }

  return closestCenter({
    ...args,
    droppableContainers: nearbyTableDrops,
  });
};
