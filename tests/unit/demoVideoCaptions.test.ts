import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  HERO_DEMO_VIDEO,
  PHASE_ONE_SOCIAL_VIDEO_STORIES,
} from '../../app/data/demoVideos';
import {
  buildCaptionsForDemo,
  buildWebVttForDemo,
} from '../../scripts/demo-videos/captions';
import { getManualRecordingDurationBounds } from '../../scripts/demo-videos/validate-manual-demo-video';

describe('demo video WebVTT captions', () => {
  it('provides a canonical WebVTT sidecar generator', () => {
    const webVtt = buildWebVttForDemo(HERO_DEMO_VIDEO);

    assert.match(webVtt, /^WEBVTT\n\n/);
    assert.match(webVtt, /00:00:00\.000 --> 00:00:10\.000/);
    assert.match(webVtt, /Start with one wedding in the planner command center/);
    assert.match(webVtt, /00:01:05\.000 --> 00:01:15\.000/);
  });

  it('keeps every social cue out of the fixed five-second activation outro', () => {
    for (const story of PHASE_ONE_SOCIAL_VIDEO_STORIES) {
      const { minimumDuration } = getManualRecordingDurationBounds(story);
      const captions = buildCaptionsForDemo(story, minimumDuration);
      const outroStartsAtMs = (minimumDuration - 5) * 1000;

      assert.ok(captions.length > 0, `${story.id} must have caption cues`);
      assert.ok(
        Math.max(...captions.map((caption) => caption.endMs)) <= outroStartsAtMs,
        `${story.id} captions must end before its five-second outro`,
      );
    }
  });
});
