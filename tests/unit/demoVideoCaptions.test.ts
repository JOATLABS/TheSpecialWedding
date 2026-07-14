import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { HERO_DEMO_VIDEO } from '../../app/data/demoVideos';
import { buildWebVttForDemo } from '../../scripts/demo-videos/captions';

describe('demo video WebVTT captions', () => {
  it('provides a canonical WebVTT sidecar generator', () => {
    const webVtt = buildWebVttForDemo(HERO_DEMO_VIDEO);

    assert.match(webVtt, /^WEBVTT\n\n/);
    assert.match(webVtt, /00:00:00\.000 --> 00:00:10\.000/);
    assert.match(webVtt, /Start with one wedding in the planner command center/);
    assert.match(webVtt, /00:01:05\.000 --> 00:01:15\.000/);
  });
});
