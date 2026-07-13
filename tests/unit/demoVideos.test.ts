import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  DEMO_VIDEO_PLAYLIST,
  FEATURE_DEMO_VIDEOS,
  HERO_DEMO_VIDEO,
  getDemoVideoByFeatureId,
} from '../../app/data/demoVideos';
import { MARKETING_FEATURES } from '../../app/data/marketingFeatures';

describe('demo video manifest', () => {
  it('includes one demo script for every public marketing feature', () => {
    const missingDemoIds = MARKETING_FEATURES
      .filter((feature) => !getDemoVideoByFeatureId(feature.id))
      .map((feature) => feature.id);
    const unknownDemoIds = FEATURE_DEMO_VIDEOS
      .filter((demo) => !MARKETING_FEATURES.some((feature) => feature.id === demo.featureId))
      .map((demo) => demo.featureId);

    assert.deepEqual(missingDemoIds, []);
    assert.deepEqual(unknownDemoIds, []);
    assert.equal(FEATURE_DEMO_VIDEOS.length, MARKETING_FEATURES.length);
  });

  it('keeps the seven conversion-critical clips in phase one', () => {
    const phaseOneFeatureIds = FEATURE_DEMO_VIDEOS
      .filter((demo) => demo.priority === 'phase-one')
      .map((demo) => demo.featureId);

    assert.deepEqual(phaseOneFeatureIds, [
      'dashboard',
      'couple-portal',
      'wedding-website',
      'guest-management',
      'seating-orchestrator',
      'book-the-client',
      'vendor-network',
    ]);
  });

  it('keeps scripted clips useful before final recordings are attached', () => {
    for (const demo of DEMO_VIDEO_PLAYLIST) {
      assert.ok(demo.title.trim(), `demo title missing for ${demo.id}`);
      assert.ok(demo.audience.trim(), `demo audience missing for ${demo.id}`);
      assert.ok(demo.durationSeconds > 0, `duration missing for ${demo.id}`);
      assert.ok(demo.routePlan.length > 0, `route plan missing for ${demo.id}`);
      assert.ok(demo.seedRequirements.length > 0, `seed requirements missing for ${demo.id}`);
      assert.ok(demo.script.length > 0, `script missing for ${demo.id}`);
      assert.ok(demo.recordingChecklist.length > 0, `recording checklist missing for ${demo.id}`);

      if (demo.status === 'published') {
        assert.ok(demo.assetUrl, `published demo must have assetUrl: ${demo.id}`);
        assert.ok(demo.thumbnailUrl, `published demo must have thumbnailUrl: ${demo.id}`);
        assert.ok(demo.captionUrl, `published demo must have captionUrl: ${demo.id}`);
        assert.ok(demo.transcriptUrl, `published demo must have transcriptUrl: ${demo.id}`);
        assert.ok(demo.socialAssetUrl, `published demo must have socialAssetUrl: ${demo.id}`);
        assert.ok(demo.socialThumbnailUrl, `published demo must have socialThumbnailUrl: ${demo.id}`);
        assert.ok(demo.recordedAt, `published demo must have recordedAt: ${demo.id}`);
        assert.ok(demo.appBuildLabel, `published demo must have appBuildLabel: ${demo.id}`);
      }
    }
  });

  it('keeps the connected hero walkthrough inside the Phase 1 60-90 second target', () => {
    assert.equal(HERO_DEMO_VIDEO.id, 'planner-command-center-walkthrough');
    assert.equal(HERO_DEMO_VIDEO.durationSeconds, 90);
    assert.equal(HERO_DEMO_VIDEO.priority, 'hero');
    assert.deepEqual(
      HERO_DEMO_VIDEO.captureCheckpoints?.map((checkpoint) => checkpoint.route),
      [
        '/admin/planner',
        '/admin/weddings/wedding_marketing_capture_sofia_daniel',
        '/sofia-and-daniel',
        '/couple/dashboard',
        '/admin/guests',
        '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
        '/admin/vendors',
        '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
        '/admin/planner',
      ],
    );
    for (const checkpoint of HERO_DEMO_VIDEO.captureCheckpoints ?? []) {
      assert.ok(checkpoint.action.trim(), `capture action missing for ${checkpoint.label}`);
      assert.ok(checkpoint.visibleResult.trim(), `visible result missing for ${checkpoint.label}`);
    }
  });
});
