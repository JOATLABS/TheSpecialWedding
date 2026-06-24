import { after, afterEach, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, fireEvent, render } from '@testing-library/react';

import { installDom } from './testDom';
import { VenueLayout } from '../../app/types/table';

let FloorPlanLayer: typeof import('../../app/admin/components/seating/FloorPlanLayer')['FloorPlanLayer'];
let clampVenuePoint: typeof import('../../app/admin/components/seating/FloorPlanLayer')['clampVenuePoint'];
let getCanvasPointFromPointer: typeof import('../../app/admin/components/seating/FloorPlanLayer')['getCanvasPointFromPointer'];
let pointsToSvgPoints: typeof import('../../app/admin/components/seating/FloorPlanLayer')['pointsToSvgPoints'];
let domHandle: ReturnType<typeof installDom> | null = null;

const layout: VenueLayout = {
  id: 'layout-1',
  wedding_id: 'wedding-1',
  canvas_width: 1600,
  canvas_height: 1000,
  outline: [],
  fixtures: [],
};

describe('floor plan drawing layer', () => {
  before(async () => {
    domHandle = installDom();
    ({
      FloorPlanLayer,
      clampVenuePoint,
      getCanvasPointFromPointer,
      pointsToSvgPoints,
    } = await import('../../app/admin/components/seating/FloorPlanLayer'));
  });

  afterEach(() => {
    cleanup();
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('serializes and clamps venue outline points in canvas coordinates', () => {
    assert.equal(
      pointsToSvgPoints([
        { x: 120.4, y: 100.2 },
        { x: 1480.6, y: 900.9 },
      ]),
      '120,100 1481,901'
    );
    assert.deepEqual(
      clampVenuePoint({ x: -30, y: 1800 }, layout),
      { x: 0, y: 1000 }
    );
  });

  it('translates pointer coordinates into the SVG view box', () => {
    const view = render(
      <svg data-testid="svg" viewBox="0 0 1600 1000" />
    );
    const svg = view.getByTestId('svg') as unknown as SVGSVGElement;
    svg.getScreenCTM = () => null;
    svg.getBoundingClientRect = () => ({
      left: 20,
      top: 10,
      width: 800,
      height: 500,
      right: 820,
      bottom: 510,
      x: 20,
      y: 10,
      toJSON: () => ({}),
    });

    const point = getCanvasPointFromPointer(
      { clientX: 420, clientY: 260 },
      svg,
      layout
    );

    assert.deepEqual(point, { x: 800, y: 500 });
  });

  it('renders a closed room outline and adds points in draw mode', () => {
    const addedPoints: Array<{ x: number; y: number }> = [];
    const view = render(
      <FloorPlanLayer
        layout={layout}
        outline={[
          { x: 120, y: 100 },
          { x: 1480, y: 100 },
          { x: 1480, y: 900 },
        ]}
        mode="draw"
        onPointAdd={(point) => addedPoints.push(point)}
        onPointMove={() => {}}
      />
    );
    const svg = view.getByTestId('floor-plan-svg') as unknown as SVGSVGElement;
    svg.getScreenCTM = () => null;
    svg.getBoundingClientRect = () => ({
      left: 0,
      top: 0,
      width: 1600,
      height: 1000,
      right: 1600,
      bottom: 1000,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    assert.equal(view.getByTestId('floor-plan-polygon').getAttribute('points'), '120,100 1480,100 1480,900');

    fireEvent.pointerDown(svg, { clientX: 120, clientY: 900 });

    assert.deepEqual(addedPoints, [{ x: 120, y: 900 }]);
  });

  it('renders an uploaded floor plan backdrop under the room outline', () => {
    const view = render(
      <FloorPlanLayer
        layout={{
          ...layout,
          background_image_data_url: 'data:image/png;base64,abc123',
          background_locked: true,
        }}
        outline={[
          { x: 120, y: 100 },
          { x: 1480, y: 100 },
          { x: 1480, y: 900 },
        ]}
        mode="select"
        onPointAdd={() => {}}
        onPointMove={() => {}}
      />
    );

    const image = view.getByTestId('floor-plan-background-image');
    assert.equal(image.getAttribute('href'), 'data:image/png;base64,abc123');
    assert.equal(image.getAttribute('preserveAspectRatio'), 'xMidYMid meet');
    assert.equal(view.getByTestId('floor-plan-polygon').getAttribute('points'), '120,100 1480,100 1480,900');
  });
});
