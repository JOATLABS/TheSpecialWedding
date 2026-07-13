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

  it('preserves the full product window and reserves a separate web caption band', () => {
    assert.match(source, /<Video[\s\S]*?src=\{staticFile\(props\.rawVideoPath\)\}[\s\S]*?objectFit:\s*['"]contain['"]/);
    assert.doesNotMatch(source, /objectFit:\s*isVertical\s*\?\s*['"]contain['"]\s*:\s*['"]cover['"]/);
    assert.match(source, /const WEB_CAPTION_BAND_HEIGHT = \d+/);
    assert.match(source, /data-caption-band/);
    assert.match(source, /data-product-window/);
    assert.match(source, /bottom:\s*isVertical\s*\?\s*250\s*:\s*WEB_CAPTION_BAND_HEIGHT/);
    assert.match(source, /height:\s*isVertical\s*\?\s*undefined\s*:\s*WEB_CAPTION_BAND_HEIGHT/);
    assert.match(source, /captionSafeArea/);
    assert.match(source, /fontSize:\s*isVertical\s*\?\s*\d+\s*:\s*\d+/);
    assert.doesNotMatch(source, /audience/);
    assert.doesNotMatch(source, /formatLabel/);
  });
});
