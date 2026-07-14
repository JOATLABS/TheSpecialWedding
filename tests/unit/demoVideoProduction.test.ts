import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { DEMO_VIDEO_PLAYLIST } from '../../app/data/demoVideos';
import {
  DEMO_VIDEO_PRODUCTION_REQUIREMENTS,
  buildDemoVideoTranscript,
  getDemoVideoExportTarget,
  getDemoVideoProductionRequirementById,
} from '../../app/data/demoVideoProduction';

describe('demo video production requirements', () => {
  it('tracks production requirements for every scripted demo', () => {
    const requirementIds = DEMO_VIDEO_PRODUCTION_REQUIREMENTS.map((requirement) => requirement.demoId);

    assert.deepEqual(requirementIds, DEMO_VIDEO_PLAYLIST.map((demo) => demo.id));
  });

  it('defines a website export without squeezing the same desktop take into a social cut', () => {
    for (const requirement of DEMO_VIDEO_PRODUCTION_REQUIREMENTS) {
      const webTarget = getDemoVideoExportTarget(requirement, 'web-16x9');
      const socialTarget = getDemoVideoExportTarget(requirement, 'social-9x16');

      assert.equal(webTarget?.compositionId, 'DemoVideo16x9');
      assert.equal(webTarget?.width, 1920);
      assert.equal(webTarget?.height, 1080);
      assert.equal(webTarget?.assetPath, `/demo-videos/exports/${requirement.demoId}-16x9.mp4`);

      assert.equal(socialTarget, undefined);
      assert.equal(requirement.exportTargets.length, 1);

      assert.match(requirement.rawRecordingPath, /^output\/demo-videos\/raw\//);
      assert.doesNotMatch(requirement.rawRecordingPath, /(?:^|\/)public\//);
      assert.match(requirement.narrationPath, /^output\/demo-videos\/narration\//);
      assert.doesNotMatch(requirement.narrationPath, /(?:^|\/)public\//);
      assert.match(requirement.captureReceiptPath, /^output\/demo-videos\/receipts\//);
      assert.match(requirement.renderInputPath, /^demo-videos\/\.render-input\//);
      assert.match(requirement.renderNarrationInputPath, /^demo-videos\/\.render-input\//);
      assert.equal(
        requirement.captionPath,
        `demo-videos/captions/${requirement.demoId}.vtt`,
      );
      assert.match(requirement.playbackApprovalPath, /^output\/demo-videos\/playback-approvals\//);
    }
  });

  it('captures protected-surface and side-effect requirements before recording', () => {
    const hero = getDemoVideoProductionRequirementById('planner-command-center-walkthrough');
    const memories = getDemoVideoProductionRequirementById('guest-memories-demo');
    const contract = getDemoVideoProductionRequirementById('contract-sign-pay-demo');

    assert.ok(hero);
    assert.deepEqual(hero.routeParameters, []);
    assert.ok(hero.captureSurfaces.includes('planner-admin'));
    assert.ok(hero.captureSurfaces.includes('couple-portal'));
    assert.equal(
      hero.rawRecordingPath,
      'output/demo-videos/raw/planner-command-center-walkthrough.mp4',
    );
    assert.equal(
      hero.captureReceiptPath,
      'output/demo-videos/receipts/planner-command-center-walkthrough.json',
    );
    assert.equal(
      hero.renderInputPath,
      'demo-videos/.render-input/planner-command-center-walkthrough.mp4',
    );
    assert.equal(
      hero.narrationPath,
      'output/demo-videos/narration/planner-command-center-walkthrough.m4a',
    );
    assert.equal(
      hero.renderNarrationInputPath,
      'demo-videos/.render-input/planner-command-center-walkthrough.m4a',
    );

    assert.ok(memories);
    assert.ok(memories.captureSurfaces.includes('guest-token'));
    assert.ok(
      memories.sideEffectGuards.some((guard) => guard.includes('prepared non-private demo media')),
    );

    assert.ok(contract);
    assert.deepEqual(contract.captureSurfaces, ['planner-admin']);
    assert.equal(contract.captureSurfaces.includes('client-payment-token'), false);
    assert.equal(contract.captureSurfaces.includes('vendor-token'), false);
    assert.equal(
      contract.sideEffectGuards.some((guard) => guard.includes('read-only client payment')),
      false,
    );
    assert.equal(contract.sideEffectGuards.some((guard) => guard.includes('Stripe test-mode')), false);
    assert.ok(contract.sideEffectGuards.some((guard) => guard.includes('seeded read-only finance')));
  });

  it('builds a transcript from the approved script', () => {
    const transcript = buildDemoVideoTranscript(DEMO_VIDEO_PLAYLIST[0]);

    assert.match(transcript, /^# Planner command center walkthrough/);
    assert.match(transcript, /## Script/);
    assert.match(transcript, /Scan the planner portfolio and choose Manage for Sofia & Daniel/);
    assert.match(transcript, /One planner-owned workspace\. Start with one wedding\./);
  });
});
