import { after, afterEach, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, render } from '@testing-library/react';

import { installDom } from './testDom';
import { Guest, Table, VenueLayout } from '../../app/types/table';

let PrintableSeatingChart: typeof import('../../app/admin/components/seating/PrintableSeatingChart')['PrintableSeatingChart'];
let domHandle: ReturnType<typeof installDom> | null = null;

const tables: Table[] = [
  {
    id: 'table-1',
    wedding_id: 'wedding-1',
    name: 'Table 1',
    shape: 'round',
    capacity: 8,
    x: 240,
    y: 220,
  },
];

const guests: Guest[] = [
  {
    id: 'guest-1',
    wedding_id: 'wedding-1',
    name: 'Avery Planner',
    table_id: 'table-1',
  },
];

const venueLayout: VenueLayout = {
  id: 'layout-1',
  wedding_id: 'wedding-1',
  canvas_width: 1600,
  canvas_height: 1000,
  outline: [
    { x: 100, y: 120 },
    { x: 900, y: 120 },
    { x: 900, y: 680 },
    { x: 100, y: 680 },
  ],
  background_image_data_url: 'data:image/png;base64,abc123',
  background_image_name: 'venue.png',
  background_locked: true,
  scale_pixels: 240,
  scale_distance: 30,
  scale_unit: 'ft',
  fixtures: [
    {
      id: 'fixture-1',
      type: 'bar',
      label: 'Cocktail Bar',
      x: 260,
      y: 280,
      width: 220,
      height: 100,
      rotation: 15,
    },
  ],
};

describe('PrintableSeatingChart floor plan context', () => {
  before(async () => {
    domHandle = installDom();
    ({ PrintableSeatingChart } = await import('../../app/admin/components/seating/PrintableSeatingChart'));
  });

  afterEach(() => {
    cleanup();
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it('renders venue floor plan context behind printable seating tables', () => {
    const view = render(
      <PrintableSeatingChart
        tables={tables}
        guests={guests}
        coupleName="Avery & Jordan"
        weddingDate="2026-09-12"
        venueLayout={venueLayout}
        onClose={() => {}}
      />
    );

    const floorPlanLayer = view.getByTestId('printable-floor-plan-layer');
    assert.equal(floorPlanLayer.getAttribute('viewBox'), '0 0 1600 1000');
    assert.equal(floorPlanLayer.textContent?.includes('Cocktail Bar'), true);
    assert.equal(floorPlanLayer.textContent?.includes('30ft'), true);
    assert.equal(floorPlanLayer.querySelector('polygon')?.getAttribute('points'), '100,120 900,120 900,680 100,680');
    assert.equal(view.getByText('Table 1').textContent, 'Table 1');
  });
});
