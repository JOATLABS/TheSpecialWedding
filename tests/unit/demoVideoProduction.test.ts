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

  it('defines the two export formats every published demo must produce', () => {
    for (const requirement of DEMO_VIDEO_PRODUCTION_REQUIREMENTS) {
      const webTarget = getDemoVideoExportTarget(requirement, 'web-16x9');
      const socialTarget = getDemoVideoExportTarget(requirement, 'social-9x16');

      assert.equal(webTarget?.compositionId, 'DemoVideo16x9');
      assert.equal(webTarget?.width, 1920);
      assert.equal(webTarget?.height, 1080);
      assert.equal(webTarget?.assetPath, `/demo-videos/exports/${requirement.demoId}-16x9.mp4`);

      assert.equal(socialTarget?.compositionId, 'DemoVideo9x16');
      assert.equal(socialTarget?.width, 1080);
      assert.equal(socialTarget?.height, 1920);
      assert.equal(socialTarget?.assetPath, `/demo-videos/exports/${requirement.demoId}-9x16.mp4`);

      assert.match(requirement.rawRecordingPath, /^output\/demo-videos\/raw\//);
      assert.doesNotMatch(requirement.rawRecordingPath, /(?:^|\/)public\//);
      assert.match(requirement.captureReceiptPath, /^output\/demo-videos\/receipts\//);
      assert.match(requirement.renderInputPath, /^demo-videos\/\.render-input\//);
    }
  });

  it('captures protected-surface and side-effect requirements before recording', () => {
    const hero = getDemoVideoProductionRequirementById('planner-command-center-walkthrough');
    const memories = getDemoVideoProductionRequirementById('guest-memories-demo');
    const contract = getDemoVideoProductionRequirementById('contract-sign-pay-demo');

    assert.ok(hero);
    assert.deepEqual(hero.routeParameters, ['id', 'slug']);
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

    assert.ok(memories);
    assert.ok(memories.captureSurfaces.includes('guest-token'));
    assert.ok(
      memories.sideEffectGuards.some((guard) => guard.includes('prepared non-private demo media')),
    );

    assert.ok(contract);
    assert.ok(contract.captureSurfaces.includes('vendor-token'));
    assert.ok(contract.sideEffectGuards.some((guard) => guard.includes('Stripe test-mode')));
  });

  it('builds a transcript from the approved script', () => {
    const transcript = buildDemoVideoTranscript(DEMO_VIDEO_PLAYLIST[0]);

    assert.match(transcript, /^# Planner command center walkthrough/);
    assert.match(transcript, /## Script/);
    assert.match(transcript, /Open Morning View/);
  });
});
