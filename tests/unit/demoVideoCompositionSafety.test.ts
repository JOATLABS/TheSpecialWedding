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

  it('preserves the full product window and uses the full web canvas height', () => {
    assert.match(source, /<Video[\s\S]*?src=\{staticFile\(props\.rawVideoPath\)\}[\s\S]*?objectFit:\s*['"]contain['"]/);
    assert.doesNotMatch(source, /objectFit:\s*isVertical\s*\?\s*['"]contain['"]\s*:\s*['"]cover['"]/);
    assert.match(source, /data-product-window/);
    assert.match(source, /inset:\s*isVertical\s*\?/);
    assert.doesNotMatch(source, /WEB_CAPTION_BAND_HEIGHT/);
    assert.doesNotMatch(source, /data-caption-band/);
    assert.doesNotMatch(source, /activeCaption|captionSafeArea|props\.captions/);
    assert.doesNotMatch(source, /audience/);
    assert.doesNotMatch(source, /formatLabel/);
  });

  it('renders an explicit narration track instead of silently discarding the approved script', () => {
    assert.match(source, /import\s*\{[^}]*Audio[^}]*Video[^}]*\}\s*from\s*['"]@remotion\/media['"]/);
    assert.match(source, /<Audio\s+src=\{staticFile\(props\.narrationPath\)\}/);
    assert.match(source, /<Video[\s\S]*?muted/);
  });

  it('ends with a real activation CTA rather than promising one only in capture notes', () => {
    assert.match(source, /const OUTRO_DURATION_SECONDS = 5/);
    assert.match(source, /data-demo-outro/);
    assert.match(source, /One planner-owned workspace\./);
    assert.match(source, /Start with one wedding\./);
  });
});
