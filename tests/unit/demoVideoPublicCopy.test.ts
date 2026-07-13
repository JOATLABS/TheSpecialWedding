import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

import { HERO_DEMO_VIDEO, toPublicDemoVideo } from '../../app/data/demoVideos';

const REMOVED_DEMO_ROUTE_FILES = [
  'app/resources/demos/page.tsx',
  'app/resources/demos/[slug]/page.tsx',
] as const;

const PUBLIC_DEMO_COPY_FILES = [
  'app/components/saas/DemoVideoModal.tsx',
] as const;

const PUBLIC_CLIENT_DEMO_FILES = [
  'app/components/saas/DemoVideoLauncher.tsx',
  'app/components/saas/DemoVideoModal.tsx',
  'app/components/landing-page/FeatureShowcase.client.tsx',
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

const DEMO_MODAL_JUNK_PATTERNS = [
  /Why planners watch/i,
  /Built for/i,
  /More ways to watch/i,
  /Open vertical social cut/i,
  /Read transcript/i,
  /Planner proof/i,
  /Length/i,
  /Format/i,
  /Focus/i,
] as const;

describe('public demo video copy', () => {
  it('keeps the standalone demo route removed', () => {
    for (const filePath of REMOVED_DEMO_ROUTE_FILES) {
      assert.equal(existsSync(filePath), false, `${filePath} should not exist`);
    }
  });

  it('keeps internal production language off public demo surfaces', () => {
    for (const filePath of PUBLIC_DEMO_COPY_FILES) {
      const source = readFileSync(filePath, 'utf8');
      for (const pattern of INTERNAL_COPY_PATTERNS) {
        assert.equal(pattern.test(source), false, `${filePath} contains ${pattern}`);
      }
    }
  });

  it('keeps the removed competing marketing video manifest from drifting back in', () => {
    assert.equal(existsSync('app/data/marketingDemoVideos.ts'), false);
  });

  it('keeps the demo modal focused on video playback', () => {
    const source = readFileSync('app/components/saas/DemoVideoModal.tsx', 'utf8');
    for (const pattern of DEMO_MODAL_JUNK_PATTERNS) {
      assert.equal(pattern.test(source), false, `Demo modal contains ${pattern}`);
    }
  });

  it('does not import internal recording data into public client demo components', () => {
    for (const filePath of PUBLIC_CLIENT_DEMO_FILES) {
      const source = readFileSync(filePath, 'utf8');
      assert.equal(source.includes('data/demoVideos'), false, `${filePath} imports internal demo data`);
    }
  });

  it('strips recording fields before demo data crosses into public components', () => {
    const publicDemo = toPublicDemoVideo(HERO_DEMO_VIDEO) as Record<string, unknown>;
    for (const internalKey of [
      'routePlan',
      'seedRequirements',
      'script',
      'recordingChecklist',
      'captureNotes',
      'appBuildLabel',
    ]) {
      assert.equal(internalKey in publicDemo, false, `public demo leaked ${internalKey}`);
    }
  });
});
