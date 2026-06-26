import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { validateSeatingLayout } from '../../app/admin/utils/seatingLayoutValidation';
import { Table, VenueFixture, VenueLayoutPoint } from '../../app/types/table';

const outline: VenueLayoutPoint[] = [
  { x: 100, y: 100 },
  { x: 900, y: 100 },
  { x: 900, y: 700 },
  { x: 100, y: 700 },
];

const table: Table = {
  id: 'table-1',
  wedding_id: 'wedding-1',
  name: 'Head Table',
  shape: 'round',
  capacity: 8,
  x: 300,
  y: 240,
};

const fixture: VenueFixture = {
  id: 'fixture-1',
  type: 'bar',
  label: 'Bar',
  x: 360,
  y: 260,
  width: 180,
  height: 90,
};

describe('seating layout validation', () => {
  it('flags overlapping venue objects', () => {
    const issues = validateSeatingLayout({
      tables: [table],
      fixtures: [fixture],
      outline,
      canvasWidth: 1000,
      canvasHeight: 800,
    });

    assert.equal(issues.some((issue) => issue.message === 'Head Table overlaps Bar.'), true);
  });

  it('flags objects that leave the room outline', () => {
    const issues = validateSeatingLayout({
      tables: [{ ...table, x: 840, y: 620 }],
      fixtures: [],
      outline,
      canvasWidth: 1000,
      canvasHeight: 800,
    });

    assert.equal(
      issues.some((issue) => issue.message === 'Head Table is partly outside the room outline.'),
      true
    );
  });

  it('uses rotated fixture bounds for room checks', () => {
    const issues = validateSeatingLayout({
      tables: [],
      fixtures: [{ ...fixture, x: 720, y: 260, rotation: 45 }],
      outline,
      canvasWidth: 1000,
      canvasHeight: 800,
    });

    assert.equal(
      issues.some((issue) => issue.message === 'Bar is partly outside the room outline.'),
      true
    );
  });
});
