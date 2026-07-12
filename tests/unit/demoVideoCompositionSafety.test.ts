import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';

const source = readFileSync(
  path.join(process.cwd(), 'remotion/DemoVideoComposition.tsx'),
  'utf8',
);

describe('demo video marketing composition safety', () => {
  it('keeps production scaffolding and review labels out of rendered media', () => {
    for (const forbidden of [
      'Website walkthrough',
      'Social cutdown',
      'Browser recording required',
      '1920x1080',
      '1080x1920',
      'DEMO PREVIEW',
      'proof',
    ]) {
      assert.equal(source.includes(forbidden), false, `composition still exposes ${forbidden}`);
    }
  });

  it('uses the product recording as the dominant frame with restrained safe-area captions', () => {
    assert.match(source, /objectFit:\s*['"]cover['"]/);
    assert.match(source, /captionSafeArea/);
    assert.match(source, /fontSize:\s*isVertical\s*\?\s*\d+\s*:\s*\d+/);
    assert.doesNotMatch(source, /audience/);
    assert.doesNotMatch(source, /formatLabel/);
  });
});
