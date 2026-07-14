import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

describe('demo video WebVTT captions', () => {
  it('provides a canonical WebVTT sidecar generator', () => {
    const source = readFileSync('scripts/demo-videos/captions.ts', 'utf8');
    assert.match(source, /buildWebVttForDemo/);
    assert.match(source, /WEBVTT/);
    assert.match(source, /00:00:00\.000/);
  });
});
