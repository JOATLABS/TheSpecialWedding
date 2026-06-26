export type SeatingGuideAction = 'add-room' | 'add-reference' | 'add-fixture' | 'add-table' | 'save-layout';

export type SeatingGuideStepId =
  | 'room'
  | 'reference'
  | 'fixtures'
  | 'tables'
  | 'guests'
  | 'review';

export interface SeatingPlannerGuideState {
  hasRoomOutline: boolean;
  hasVenueReference: boolean;
  fixtureCount: number;
  tableCount: number;
  seatedGuestCount: number;
  unseatedGuestCount: number;
  layoutIssueCount: number;
  floorPlanDirty: boolean;
}

export interface SeatingPlannerGuideStep {
  id: SeatingGuideStepId;
  title: string;
  description: string;
  done: boolean;
  action?: SeatingGuideAction;
  actionLabel?: string;
}

export function buildSeatingPlannerGuideSteps(state: SeatingPlannerGuideState): SeatingPlannerGuideStep[] {
  const hasAnyLayout = state.hasRoomOutline || state.hasVenueReference || state.fixtureCount > 0;
  const hasAnyGuests = state.seatedGuestCount > 0 || state.unseatedGuestCount > 0;
  const guestsHandled = state.seatedGuestCount > 0 || (!hasAnyGuests && state.tableCount > 0);

  return [
    {
      id: 'room',
      title: 'Map the room',
      description: 'Create the venue boundary first so tables stay inside the real event space.',
      done: state.hasRoomOutline,
      action: 'add-room',
      actionLabel: state.hasRoomOutline ? 'Adjust room' : 'Add room',
    },
    {
      id: 'reference',
      title: 'Add a venue reference',
      description: 'Use an uploaded plan or scale marker to keep the seating chart tied to the venue.',
      done: state.hasVenueReference,
      action: 'add-reference',
      actionLabel: state.hasVenueReference ? 'Review reference' : 'Open tools',
    },
    {
      id: 'fixtures',
      title: 'Place fixtures',
      description:
        'Add dance floors, bars, stages, entrances, restrooms, kitchens, or vendor paths planners need to account for.',
      done: state.fixtureCount > 0,
      action: 'add-fixture',
      actionLabel: 'Add fixture',
    },
    {
      id: 'tables',
      title: 'Place tables',
      description: 'Add or move tables after the room and key fixtures are visible.',
      done: state.tableCount > 0,
      action: 'add-table',
      actionLabel: 'Add table',
    },
    {
      id: 'guests',
      title: 'Seat guests',
      description: hasAnyGuests
        ? 'Drag one guest at a time from the side panel onto the target table.'
        : 'Import or add guests, then drag one guest at a time from the side panel onto a table.',
      done: guestsHandled,
    },
    {
      id: 'review',
      title: state.layoutIssueCount > 0 ? 'Review layout checks' : 'Save and export',
      description:
        state.layoutIssueCount > 0
          ? `${state.layoutIssueCount} layout ${state.layoutIssueCount === 1 ? 'issue needs' : 'issues need'} review before sharing.`
          : 'Save the floor plan so exports and future edits match the room layout.',
      done: hasAnyLayout && guestsHandled && !state.floorPlanDirty && state.layoutIssueCount === 0,
      action: state.floorPlanDirty ? 'save-layout' : undefined,
      actionLabel: state.floorPlanDirty ? 'Save layout' : undefined,
    },
  ];
}

export function getActiveSeatingGuideStep(steps: SeatingPlannerGuideStep[]): SeatingPlannerGuideStep {
  return steps.find((step) => !step.done) ?? steps[steps.length - 1];
}
