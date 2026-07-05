import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const PUBLIC_DEMO_COPY_FILES = [
  'app/resources/demos/page.tsx',
  'app/resources/demos/[slug]/page.tsx',
  'app/components/saas/DemoVideoModal.tsx',
  'app/data/marketingDemoVideos.ts',
] as const;

const INTERNAL_COPY_PATTERNS = [
  /Demo script ready/i,
  /Recording script approved/i,
  /Human script/i,
  /Capture routes/i,
  /Recording checklist/i,
  /ready for local browser capture/i,
  /Product Demo Scripts/i,
  /Product Demo Library/i,
  /Review-ready/i,
  /Final marketing MP4s/i,
  /wired for R2/i,
] as const;

function patternsForFile(filePath: string): readonly RegExp[] {
  if (filePath !== 'app/data/marketingDemoVideos.ts') return INTERNAL_COPY_PATTERNS;

  return INTERNAL_COPY_PATTERNS.filter((pattern) => pattern.source !== 'Review-ready');
}

describe('public demo video copy', () => {
  it('keeps internal production language off public demo surfaces', () => {
    for (const filePath of PUBLIC_DEMO_COPY_FILES) {
      const source = readFileSync(filePath, 'utf8');
      for (const pattern of patternsForFile(filePath)) {
        assert.equal(pattern.test(source), false, `${filePath} contains ${pattern}`);
      }
    }
  });
});
