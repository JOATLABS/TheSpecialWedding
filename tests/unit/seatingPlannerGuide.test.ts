import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  buildSeatingPlannerGuideSteps,
  getActiveSeatingGuideStep,
  type SeatingPlannerGuideState,
} from '@/admin/utils/seatingPlannerGuide';

const baseState: SeatingPlannerGuideState = {
  hasRoomOutline: false,
  hasVenueReference: false,
  fixtureCount: 0,
  tableCount: 0,
  seatedGuestCount: 0,
  unseatedGuestCount: 24,
  layoutIssueCount: 0,
  floorPlanDirty: false,
};

describe('seatingPlannerGuide', () => {
  it('starts planners with the room outline step', () => {
    const steps = buildSeatingPlannerGuideSteps(baseState);
    const activeStep = getActiveSeatingGuideStep(steps);

    assert.deepEqual(
      {
        id: activeStep.id,
        action: activeStep.action,
        actionLabel: activeStep.actionLabel,
      },
      {
        id: 'room',
        action: 'add-room',
        actionLabel: 'Add room',
      }
    );
  });

  it('advances through venue reference, fixtures, tables, and guest seating', () => {
    const steps = buildSeatingPlannerGuideSteps({
      ...baseState,
      hasRoomOutline: true,
      hasVenueReference: true,
      fixtureCount: 2,
      tableCount: 8,
      seatedGuestCount: 0,
    });

    assert.deepEqual(steps.filter((step) => step.done).map((step) => step.id), [
      'room',
      'reference',
      'fixtures',
      'tables',
    ]);
    assert.equal(getActiveSeatingGuideStep(steps).id, 'guests');
  });

  it('describes the same fixture options exposed in the seating toolbar', () => {
    const fixtureStep = buildSeatingPlannerGuideSteps(baseState).find((step) => step.id === 'fixtures');

    assert.ok(fixtureStep);
    assert.match(fixtureStep.description, /dance floors/i);
    assert.match(fixtureStep.description, /vendor paths/i);
    assert.doesNotMatch(fixtureStep.description, /buffet|column|service area/i);
  });

  it('keeps review active when layout checks need attention', () => {
    const steps = buildSeatingPlannerGuideSteps({
      ...baseState,
      hasRoomOutline: true,
      hasVenueReference: true,
      fixtureCount: 1,
      tableCount: 6,
      seatedGuestCount: 10,
      layoutIssueCount: 2,
    });
    const activeStep = getActiveSeatingGuideStep(steps);

    assert.deepEqual(
      {
        id: activeStep.id,
        title: activeStep.title,
        done: activeStep.done,
      },
      {
        id: 'review',
        title: 'Review layout checks',
        done: false,
      }
    );
  });

  it('offers saving when the floor plan has unsaved edits', () => {
    const steps = buildSeatingPlannerGuideSteps({
      ...baseState,
      hasRoomOutline: true,
      hasVenueReference: true,
      fixtureCount: 1,
      tableCount: 6,
      seatedGuestCount: 10,
      floorPlanDirty: true,
    });
    const activeStep = getActiveSeatingGuideStep(steps);

    assert.deepEqual(
      {
        id: activeStep.id,
        action: activeStep.action,
        actionLabel: activeStep.actionLabel,
      },
      {
        id: 'review',
        action: 'save-layout',
        actionLabel: 'Save layout',
      }
    );
  });
});
