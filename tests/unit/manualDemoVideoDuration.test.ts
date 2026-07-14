import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { getDemoVideoById } from '../../app/data/demoVideoProduction';
import { assertRenderedDurationMatchesManualCapture } from '../../scripts/demo-videos/validate-demo-video-playback-approval';
import {
  assertDedicatedChannelTake,
  getManualRecordingDurationBounds,
} from '../../scripts/demo-videos/validate-manual-demo-video';

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

  it('requires an explicit dedicated take for social footage only', () => {
    assert.throws(
      () => assertDedicatedChannelTake(
        { productionChannel: 'social' },
        {},
      ),
      /dedicatedChannelTake must be explicitly true/,
    );
    assert.throws(
      () => assertDedicatedChannelTake(
        { productionChannel: 'social' },
        { dedicatedChannelTake: false },
      ),
      /dedicatedChannelTake must be explicitly true/,
    );
    assert.doesNotThrow(() => assertDedicatedChannelTake(
      { productionChannel: 'social' },
      { dedicatedChannelTake: true },
    ));
    assert.doesNotThrow(() => assertDedicatedChannelTake(
      { productionChannel: 'website' },
      {},
    ));
  });

  it('requires the approved export to preserve the validated raw take duration', () => {
    assert.doesNotThrow(() => assertRenderedDurationMatchesManualCapture(30, 30.2));
    assert.throws(
      () => assertRenderedDurationMatchesManualCapture(30, 29.5),
      /duration must match the validated manual recording/,
    );
  });
});
