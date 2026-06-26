import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { seatingCollisionDetection } from '../../app/admin/utils/seatingCollisionDetection';

function rect(left: number, top: number, width: number, height: number) {
  return {
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
  };
}

function collisionArgs(
  pointerCoordinates: { x: number; y: number } | null,
  activeRect = rect(96, 96, 40, 40)
) {
  const tableRect = rect(100, 100, 240, 220);
  const tableContainer = {
    id: 'table-drop-1',
    key: 'table-drop-1',
    disabled: false,
    data: { current: { type: 'table-drop', tableId: 'table-1' } },
    node: { current: null },
    rect: { current: tableRect },
  };

  return {
    active: {
      id: 'guest-1',
      data: { current: { type: 'guest' } },
      rect: { current: { initial: activeRect, translated: activeRect } },
    },
    collisionRect: activeRect,
    droppableRects: new Map([['table-drop-1', tableRect]]),
    droppableContainers: [tableContainer],
    pointerCoordinates,
  } as Parameters<typeof seatingCollisionDetection>[0];
}

describe('seating collision detection', () => {
  it('uses pointer collisions when the pointer is inside a table drop zone', () => {
    const collisions = seatingCollisionDetection(collisionArgs({ x: 120, y: 120 }));

    assert.equal(collisions[0]?.id, 'table-drop-1');
  });

  it('falls back to rectangle intersection when pointer coordinates miss the drop zone', () => {
    const collisions = seatingCollisionDetection(collisionArgs({ x: 80, y: 80 }));

    assert.equal(collisions[0]?.id, 'table-drop-1');
  });

  it('uses a bounded closest-center fallback for guest drops near a table', () => {
    const nearButNotIntersecting = rect(340, 170, 40, 40);

    const collisions = seatingCollisionDetection(collisionArgs(null, nearButNotIntersecting));

    assert.equal(collisions[0]?.id, 'table-drop-1');
  });

  it('does not seat a guest when the drop ends far from every table', () => {
    const sidebarDrop = rect(-300, -300, 40, 40);

    const collisions = seatingCollisionDetection(collisionArgs(null, sidebarDrop));

    assert.equal(collisions.length, 0);
  });
});
