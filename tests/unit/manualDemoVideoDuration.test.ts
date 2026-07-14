import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { getDemoVideoById } from '../../app/data/demoVideoProduction';
import { getManualRecordingDurationBounds } from '../../scripts/demo-videos/validate-manual-demo-video';

describe('manual demo video duration bounds', () => {
  it('keeps human-driven takes close to their authored duration', () => {
    const hero = getDemoVideoById('planner-command-center-walkthrough');
    const morningView = getDemoVideoById('morning-view-demo');

    assert.ok(hero);
    assert.ok(morningView);
    assert.deepEqual(getManualRecordingDurationBounds(hero), {
      minimumDuration: 70,
      maximumDuration: 80,
    });
    assert.deepEqual(getManualRecordingDurationBounds(morningView), {
      minimumDuration: 55,
      maximumDuration: 65,
    });
  });

  it('does not accept the old 75-percent shortcut for feature takes', () => {
    const morningView = getDemoVideoById('morning-view-demo');

    assert.ok(morningView);
    const bounds = getManualRecordingDurationBounds(morningView);
    assert.ok(45 < bounds.minimumDuration);
  });
});
