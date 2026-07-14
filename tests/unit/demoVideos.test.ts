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
    const phaseOneDemos = FEATURE_DEMO_VIDEOS
      .filter((demo) => demo.priority === 'phase-one');
    const phaseOneFeatureIds = phaseOneDemos.map((demo) => demo.featureId);

    assert.deepEqual(phaseOneFeatureIds, [
      'dashboard',
      'couple-portal',
      'wedding-website',
      'guest-management',
      'seating-orchestrator',
      'book-the-client',
      'vendor-network',
    ]);

    const expectedCheckpointRoutes: Record<string, readonly string[]> = {
      'morning-view-demo': [
        '/admin/planner',
        '/admin/planner',
        '/admin/weddings/wedding_marketing_capture_avery_morgan',
      ],
      'couple-portal-demo': [
        '/couple/dashboard',
        '/couple/dashboard',
        '/couple/dashboard',
        '/couple/dashboard',
      ],
      'microsite-auto-publishes-demo': [
        '/admin/weddings/wedding_marketing_capture_sofia_daniel',
        '/sofia-and-daniel',
        '/sofia-and-daniel/gallery',
      ],
      'guest-management-demo': [
        '/admin/guests',
        '/admin/guests',
        '/admin/guests',
      ],
      'seating-orchestrator-demo': [
        '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
        '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
        '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel',
      ],
      'contract-sign-pay-demo': [
        '/admin/vendors/contracts/67c100000000000000000001',
        '/admin/vendors/contracts/67c100000000000000000001',
        '/admin/vendors/contracts/67c100000000000000000001',
        '/portal/marketing-capture-contract-payment-portal-token',
        '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
      ],
      'vendor-directory-crm-demo': [
        '/vendors',
        '/vendors/67c400000000000000000001',
        '/admin/vendors',
        '/admin/vendors',
        '/admin/vendors',
      ],
    };
    const mutationAction = /\b(?:add|approve|create|delete|drag|edit|pay|remove|save|send|sign|submit|update|upload)\b/i;

    for (const demo of phaseOneDemos) {
      const checkpoints = demo.captureCheckpoints ?? [];
      assert.ok(checkpoints.length >= 3, `${demo.id} needs at least three exact checkpoints`);
      assert.deepEqual(
        checkpoints.map((checkpoint) => checkpoint.route),
        expectedCheckpointRoutes[demo.id],
        `${demo.id} checkpoint journey drifted`,
      );

      for (const checkpoint of checkpoints) {
        assert.ok(checkpoint.label.trim(), `capture label missing for ${demo.id}`);
        assert.ok(checkpoint.action.trim(), `capture action missing for ${demo.id}`);
        assert.ok(checkpoint.visibleResult.trim(), `visible result missing for ${demo.id}`);
        assert.doesNotMatch(checkpoint.route, /\[[^\]]+\]/, `${demo.id} has an unresolved checkpoint route`);
        assert.doesNotMatch(checkpoint.action, mutationAction, `${demo.id} checkpoint must stay read-only`);
      }

      for (const step of demo.script) {
        assert.doesNotMatch(step.action, mutationAction, `${demo.id} script must stay read-only`);
      }
    }

    const vendorDemo = phaseOneDemos.find((demo) => demo.id === 'vendor-directory-crm-demo');
    assert.ok(vendorDemo);
    assert.equal(vendorDemo.routePlan.some((route) => route.startsWith('/portal/')), false);
    assert.doesNotMatch(
      `${vendorDemo.script.map((step) => step.action).join(' ')} ${vendorDemo.script.map((step) => step.voiceover).join(' ')}`,
      /vendor portal|vendors? can collaborate through scoped portals/i,
    );
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
        assert.equal(
          Boolean(demo.socialAssetUrl),
          Boolean(demo.socialThumbnailUrl),
          `published social assets must be paired when present: ${demo.id}`,
        );
        assert.ok(demo.recordedAt, `published demo must have recordedAt: ${demo.id}`);
        assert.ok(demo.appBuildLabel, `published demo must have appBuildLabel: ${demo.id}`);
      }
    }
  });

  it('keeps the connected hero walkthrough inside the Phase 1 60-90 second target', () => {
    assert.equal(HERO_DEMO_VIDEO.id, 'planner-command-center-walkthrough');
    assert.equal(HERO_DEMO_VIDEO.durationSeconds, 85);
    assert.equal(HERO_DEMO_VIDEO.priority, 'hero');
    assert.deepEqual(
      HERO_DEMO_VIDEO.captureCheckpoints?.map((checkpoint) => checkpoint.label),
      [
        'Planner command center',
        'Wedding event source',
        'Public event plan',
        'Couple timeline',
        'Guest response slice',
        'Seating plan',
        'Vendor contract context',
        'Return to command center',
      ],
    );
    assert.deepEqual(
      HERO_DEMO_VIDEO.captureCheckpoints?.map((checkpoint) => checkpoint.route),
      [
        '/admin/planner',
        '/admin/weddings/wedding_marketing_capture_sofia_daniel',
        '/sofia-and-daniel',
        '/couple/dashboard',
        '/admin/guests',
        '/admin/seating',
        '/admin/vendors',
        '/admin/planner',
      ],
    );
    const mutationAction = /\b(?:add|approve|create|delete|drag|edit|pay|remove|save|send|sign|submit|update|upload)\b/i;
    for (const checkpoint of HERO_DEMO_VIDEO.captureCheckpoints ?? []) {
      assert.ok(checkpoint.action.trim(), `capture action missing for ${checkpoint.label}`);
      assert.ok(checkpoint.visibleResult.trim(), `visible result missing for ${checkpoint.label}`);
      assert.doesNotMatch(checkpoint.action, mutationAction, `${checkpoint.label} must stay read-only`);
    }
    for (const step of HERO_DEMO_VIDEO.script) {
      assert.doesNotMatch(step.action, mutationAction, `hero step ${step.timestamp} must stay read-only`);
    }
    assert.deepEqual(HERO_DEMO_VIDEO.script.at(-1), {
      timestamp: '1:20-1:25',
      action: 'Hold on the command center as the outro appears.',
      voiceover: 'One planner-owned workspace. Start with one wedding.',
    });
    assert.equal(HERO_DEMO_VIDEO.routePlan.some((route) => route.startsWith('/admin/budget')), false);
    assert.equal(HERO_DEMO_VIDEO.routePlan.some((route) => route.includes('/portal/')), false);
  });
});
