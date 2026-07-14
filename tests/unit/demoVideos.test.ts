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

    const vendorContractFeature = MARKETING_FEATURES.find((feature) => feature.id === 'book-the-client');
    const vendorContractDemo = phaseOneDemos.find((demo) => demo.id === 'contract-sign-pay-demo');
    assert.ok(vendorContractFeature);
    assert.ok(vendorContractDemo);
    assert.equal(vendorContractFeature.title, 'Vendor Contracts → Payment Milestones');
    assert.equal(vendorContractDemo.title, 'Vendor Contracts -> Payment Milestones');
    assert.doesNotMatch(vendorContractFeature.description, /couple signs|funds land|pay the vendor/i);
    assert.equal(vendorContractDemo.routePlan.some((route) => route.startsWith('/portal/')), false);

    const vendorNetworkFeature = MARKETING_FEATURES.find((feature) => feature.id === 'vendor-network');
    assert.ok(vendorNetworkFeature);
    const vendorWorkflowCopy = [
      vendorContractFeature.title,
      vendorContractFeature.tagline,
      vendorContractFeature.description,
      vendorContractDemo.title,
      vendorContractDemo.audience,
      vendorContractDemo.captureNotes,
      ...vendorContractDemo.seedRequirements,
      ...vendorContractDemo.script.flatMap((step) => [step.action, step.voiceover]),
      vendorNetworkFeature.title,
      vendorNetworkFeature.tagline,
      vendorNetworkFeature.description,
    ].join(' ');
    assert.doesNotMatch(
      vendorWorkflowCopy,
      /couple-facing signature|couple signs|client payment portal|connected account|funds land|payouts?|stripe/i,
    );

    const morningView = phaseOneDemos.find((demo) => demo.id === 'morning-view-demo');
    const couplePortal = phaseOneDemos.find((demo) => demo.id === 'couple-portal-demo');
    const microsite = phaseOneDemos.find((demo) => demo.id === 'microsite-auto-publishes-demo');
    const guestManagement = phaseOneDemos.find((demo) => demo.id === 'guest-management-demo');
    const seating = phaseOneDemos.find((demo) => demo.id === 'seating-orchestrator-demo');
    assert.ok(morningView);
    assert.ok(couplePortal);
    assert.ok(microsite);
    assert.ok(guestManagement);
    assert.ok(seating);

    const joinedCopy = (demo: (typeof phaseOneDemos)[number]) => [
      demo.title,
      demo.audience,
      demo.captureNotes,
      ...demo.seedRequirements,
      ...demo.recordingChecklist,
      ...demo.captureCheckpoints?.flatMap((checkpoint) => [
        checkpoint.action,
        checkpoint.visibleResult,
      ]) ?? [],
      ...demo.script.flatMap((step) => [step.action, step.voiceover]),
    ].join(' ');

    assert.doesNotMatch(joinedCopy(morningView), /final 16:9 crop|payment|message|milestone/i);
    assert.match(joinedCopy(morningView), /RSVP/i);
    assert.doesNotMatch(joinedCopy(couplePortal), /review, respond, and self-serve/i);
    assert.equal(microsite.title, 'Planner Record → Public Microsite');
    assert.doesNotMatch(joinedCopy(microsite), /auto-publish|latest plan|reads from|built from/i);
    assert.doesNotMatch(joinedCopy(guestManagement), /when one guest changes|updates the rest/i);
    assert.doesNotMatch(joinedCopy(guestManagement), /expand|household|accessibility|guest token/i);
    assert.match(joinedCopy(guestManagement), /collapsed/i);
    assert.match(joinedCopy(guestManagement), /Card View/i);
    assert.match(joinedCopy(guestManagement), /clear the RSVP filter/i);
    assert.match(joinedCopy(guestManagement), /Priya Shah/i);
    assert.match(joinedCopy(guestManagement), /Vegetarian/i);
    assert.match(joinedCopy(seating), /70%/i);
    assert.match(joinedCopy(vendorDemo), /prepared planner tab/i);
    assert.match(joinedCopy(vendorDemo), /manually switch/i);
    assert.match(joinedCopy(vendorDemo), /address bar.*hidden|hidden.*address bar/i);
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
        assert.ok(demo.recordedAt, `published demo must have recordedAt: ${demo.id}`);
        assert.ok(demo.appBuildLabel, `published demo must have appBuildLabel: ${demo.id}`);
      }
    }
  });

  it('keeps the connected hero walkthrough outcome-led and recordable', () => {
    assert.equal(HERO_DEMO_VIDEO.id, 'planner-command-center-walkthrough');
    assert.equal(HERO_DEMO_VIDEO.durationSeconds, 75);
    assert.equal(HERO_DEMO_VIDEO.priority, 'hero');
    assert.deepEqual(
      HERO_DEMO_VIDEO.captureCheckpoints?.map((checkpoint) => checkpoint.label),
      [
        'Planner command center',
        'Wedding event source',
        'Public event plan',
        'Couple timeline',
        'Guest response context',
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
      timestamp: '1:05-1:15',
      action: 'Return to the command center, then hold for the five-second outro.',
      voiceover: 'One planner-owned workspace. Start with one wedding.',
    });
    assert.equal(HERO_DEMO_VIDEO.captureCheckpoints?.length, 6);
    assert.equal(HERO_DEMO_VIDEO.routePlan.length, 5);
    assert.equal(HERO_DEMO_VIDEO.routePlan.some((route) => route.startsWith('/admin/budget')), false);
    assert.equal(HERO_DEMO_VIDEO.routePlan.some((route) => route.startsWith('/admin/seating')), false);
    assert.equal(HERO_DEMO_VIDEO.routePlan.some((route) => route.startsWith('/admin/vendors')), false);
    assert.equal(HERO_DEMO_VIDEO.routePlan.some((route) => route.includes('/portal/')), false);
  });
});
