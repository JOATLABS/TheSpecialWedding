import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { describe, it } from 'node:test';

import { DEMO_VIDEO_PLAYLIST, HERO_DEMO_VIDEO, toPublicDemoVideo } from '../../app/data/demoVideos';

const RETAKE_REQUIRED_DEMO_IDS = [
  'planner-command-center-walkthrough',
  'morning-view-demo',
  'wedding-timeline-demo',
  'couple-portal-demo',
  'microsite-auto-publishes-demo',
  'wedding-configuration-demo',
  'gallery-management-demo',
  'guest-management-demo',
  'seating-orchestrator-demo',
  'guest-memories-demo',
  'planner-communications-demo',
  'contract-sign-pay-demo',
  'payment-autopilot-demo',
  'budget-quote-demo',
  'vendor-directory-crm-demo',
  'knowledge-base-demo',
  'forms-canvas-demo',
  'team-permissions-audit-demo',
] as const;

const PUBLIC_FIXTURE_LEAK_PATTERNS = [
  /Development/i,
  /Smoke/i,
  /example\./i,
  /example@/i,
  /fixture/i,
  /Website Walkthrough/i,
  /whether the workspace is real/i,
  /1920x1080/i,
] as const;

const PUBLIC_ASSET_FIELDS = [
  'assetUrl',
  'thumbnailUrl',
  'captionUrl',
  'transcriptUrl',
  'socialAssetUrl',
  'socialThumbnailUrl',
  'recordedAt',
] as const;

const PUBLIC_DIRECT_ASSET_PATHS = RETAKE_REQUIRED_DEMO_IDS.flatMap((demoId) => [
  `public/demo-videos/raw/${demoId}.webm`,
  `public/demo-videos/exports/${demoId}-16x9.mp4`,
  `public/demo-videos/exports/${demoId}-9x16.mp4`,
  `public/demo-videos/thumbnails/${demoId}-16x9.png`,
  `public/demo-videos/thumbnails/${demoId}-9x16.png`,
  `public/demo-videos/captions/${demoId}.json`,
  `public/demo-videos/transcripts/${demoId}.md`,
] as const);

describe('public demo video safety', () => {
  it('does not expose unapproved walkthrough recordings through public demo props', () => {
    for (const demoId of RETAKE_REQUIRED_DEMO_IDS) {
      const demo = DEMO_VIDEO_PLAYLIST.find((candidate) => candidate.id === demoId);
      assert.ok(demo, `missing demo ${demoId}`);

      const publicDemo = toPublicDemoVideo(demo);
      assert.equal(publicDemo.status, 'recording', `${demoId} should be marked for public retake`);

      for (const field of PUBLIC_ASSET_FIELDS) {
        assert.equal(publicDemo[field], undefined, `${demoId} leaked ${field}`);
      }
    }
  });

  it('keeps fixture and proof-review language out of public demo copy fields', () => {
    for (const demo of DEMO_VIDEO_PLAYLIST) {
      const publicDemo = toPublicDemoVideo(demo);
      const publicCopy = [publicDemo.title, publicDemo.audience].join(' ');

      for (const pattern of PUBLIC_FIXTURE_LEAK_PATTERNS) {
        assert.equal(pattern.test(publicCopy), false, `${demo.id} public copy contains ${pattern}`);
      }
    }
  });

  it('keeps the homepage hero walkthrough in a retake-safe state until clean footage exists', () => {
    const publicHero = toPublicDemoVideo(HERO_DEMO_VIDEO);

    assert.equal(publicHero.status, 'recording');
    assert.equal(publicHero.assetUrl, undefined);
    assert.equal(publicHero.thumbnailUrl, undefined);
    assert.equal(publicHero.title, 'Planner command center walkthrough');
  });

  it('keeps retake-required demo files out of the deployable public asset tree', () => {
    for (const assetPath of PUBLIC_DIRECT_ASSET_PATHS) {
      assert.equal(existsSync(assetPath), false, `${assetPath} should not be deployable`);
    }
  });
});
