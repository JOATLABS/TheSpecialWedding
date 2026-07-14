import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';

import * as demoVideoProduction from '../../app/data/demoVideoProduction';
import {
  DEMO_VIDEO_PLAYLIST,
  type DemoCaptureCheckpoint,
  type DemoVideo,
} from '../../app/data/demoVideos';
import * as demoVideos from '../../app/data/demoVideos';
import {
  getManualRecordingDurationBounds,
  validateManualCaptureCheckpoints,
} from '../../scripts/demo-videos/validate-manual-demo-video';

const SOCIAL_STORIES = [
  {
    id: 'connection-over-tools-social',
    pillar: 'Connection Over Tools',
  },
  {
    id: 'disorganization-tax-social',
    pillar: 'Disorganization Tax',
  },
  {
    id: 'couple-experience-boundaries-social',
    pillar: 'Couple Experience + Boundaries',
  },
  {
    id: 'built-for-planners-social',
    pillar: 'Built for Planners',
  },
] as const;

type SocialStory = DemoVideo & {
  productionChannel: 'social';
  phaseOnePillar: string;
  socialOutcome: string;
};

type SocialPublicationApproval = {
  approval: 'approved';
  captureReceiptPath: string;
  playbackApprovalPath: string;
  appBuildCommit: string;
  appBuildLabel: string;
  recordedAt: string;
  assetUrl: string;
  thumbnailUrl: string;
  captionUrl: string;
  transcriptUrl: string;
};

function getSocialStories(): readonly SocialStory[] {
  const stories = (demoVideos as unknown as {
    PHASE_ONE_SOCIAL_VIDEO_STORIES?: readonly SocialStory[];
  }).PHASE_ONE_SOCIAL_VIDEO_STORIES;
  assert.ok(stories, 'PHASE_ONE_SOCIAL_VIDEO_STORIES must be a first-class catalog');
  return stories;
}

function withFrameProof(checkpoints: readonly DemoCaptureCheckpoint[]) {
  return checkpoints.map((checkpoint, index) => ({
    ...checkpoint,
    atSeconds: 2 + index * 6,
    frameSha256: 'a'.repeat(64),
  }));
}

describe('Phase 1 social video pipeline', () => {
  it('defines exactly four pillar-native 20-35 second social stories', () => {
    const stories = getSocialStories();

    assert.deepEqual(
      stories.map(({ id, phaseOnePillar }) => ({ id, pillar: phaseOnePillar })),
      SOCIAL_STORIES,
    );

    for (const story of stories) {
      assert.equal(story.productionChannel, 'social');
      assert.ok(story.durationSeconds >= 20 && story.durationSeconds <= 35);
      assert.ok(story.socialOutcome.length >= 40);
      assert.equal(story.priority, 'phase-one');
      assert.equal(story.status, 'recording');
      assert.equal(story.assetUrl, undefined);
      assert.equal(story.thumbnailUrl, undefined);
      assert.equal(story.captionUrl, undefined);
      assert.equal(story.transcriptUrl, undefined);
    }
  });

  it('keeps every social take separate from website IDs, checkpoints, routes, and receipts', () => {
    const stories = getSocialStories();
    const websiteIds = new Set(DEMO_VIDEO_PLAYLIST.map((demo) => demo.id));
    const routePlans = new Set<string>();
    const checkpointLabels = new Set<string>();
    const rawPaths = new Set<string>();
    const receiptPaths = new Set<string>();

    for (const story of stories) {
      assert.equal(websiteIds.has(story.id), false, `${story.id} reuses a website demo id`);
      assert.ok(story.captureCheckpoints);
      assert.ok(story.captureCheckpoints.length >= 3);
      assert.equal(routePlans.has(JSON.stringify(story.routePlan)), false);
      routePlans.add(JSON.stringify(story.routePlan));

      for (const checkpoint of story.captureCheckpoints) {
        assert.equal(
          checkpointLabels.has(checkpoint.label),
          false,
          `${checkpoint.label} is reused by another social story`,
        );
        checkpointLabels.add(checkpoint.label);
      }

      assert.doesNotThrow(() => {
        validateManualCaptureCheckpoints(withFrameProof(story.captureCheckpoints ?? []), story);
      });

      const bounds = getManualRecordingDurationBounds(story);
      assert.equal(bounds.minimumDuration, Math.max(20, story.durationSeconds - 5));
      assert.equal(bounds.maximumDuration, Math.min(35, story.durationSeconds + 5));

      const requirement = demoVideoProduction.getDemoVideoProductionRequirementById(story.id);
      assert.ok(requirement);
      assert.equal(requirement.productionChannel, 'social');
      assert.match(requirement.rawRecordingPath, /^output\/demo-videos\/raw\//);
      assert.match(requirement.captureReceiptPath, /^output\/demo-videos\/receipts\//);
      assert.equal(rawPaths.has(requirement.rawRecordingPath), false);
      assert.equal(receiptPaths.has(requirement.captureReceiptPath), false);
      rawPaths.add(requirement.rawRecordingPath);
      receiptPaths.add(requirement.captureReceiptPath);
      assert.equal(
        DEMO_VIDEO_PLAYLIST.some(
          (demo) => requirement.captureReceiptPath.endsWith(`/${demo.id}.json`),
        ),
        false,
      );
    }
  });

  it('defines only a canonical vertical export and selects it by default for social stories', () => {
    const stories = getSocialStories();
    const resolver = (demoVideoProduction as unknown as {
      resolveDemoVideoRenderTarget?: (
        requirement: ReturnType<typeof demoVideoProduction.getDemoVideoProductionRequirement>,
        requestedFormat?: string,
      ) => { format: string; compositionId: string; width: number; height: number };
    }).resolveDemoVideoRenderTarget;
    assert.equal(typeof resolver, 'function', 'renderer target resolution must be channel-aware');

    for (const story of stories) {
      const requirement = demoVideoProduction.getDemoVideoProductionRequirementById(story.id);
      assert.ok(requirement);
      assert.equal(requirement.exportTargets.length, 1);
      const target = requirement.exportTargets[0];
      assert.equal(target.format, 'social-9x16');
      assert.equal(target.compositionId, 'DemoVideo9x16');
      assert.equal(target.width, 1080);
      assert.equal(target.height, 1920);
      assert.equal(target.assetPath, `/demo-videos/exports/${story.id}-9x16.mp4`);
      assert.equal(
        target.thumbnailPath,
        `/demo-videos/thumbnails/${story.id}-9x16.png`,
      );
      assert.equal(resolver?.(requirement).format, 'social-9x16');
      assert.throws(() => resolver?.(requirement, 'web-16x9'), /does not define a web-16x9/);
    }

    const websiteRequirement = demoVideoProduction.getDemoVideoProductionRequirementById(
      'planner-command-center-walkthrough',
    );
    assert.ok(websiteRequirement);
    assert.equal(resolver?.(websiteRequirement).format, 'web-16x9');
    assert.throws(
      () => resolver?.(websiteRequirement, 'social-9x16'),
      /does not define a social-9x16/,
    );
  });

  it('routes inventory and rendering through the social contract without website fallbacks', () => {
    const tsx = path.resolve('node_modules/.bin/tsx');
    const demoId = SOCIAL_STORIES[0].id;
    const env = {
      ...process.env,
      PATH: `/opt/homebrew/opt/node@22/bin:${process.env.PATH ?? ''}`,
    };
    const inventory = spawnSync(
      tsx,
      ['scripts/demo-videos/validate-demo-video-production.ts', '--demo', demoId],
      { cwd: process.cwd(), encoding: 'utf8', env },
    );
    assert.equal(
      inventory.status,
      0,
      `social inventory failed:\n${inventory.stdout}\n${inventory.stderr}`,
    );
    assert.match(inventory.stdout, /targets=social-9x16:/);

    const render = spawnSync(
      tsx,
      ['scripts/demo-videos/render-demo-video.ts', '--demo', demoId],
      { cwd: process.cwd(), encoding: 'utf8', env },
    );
    assert.equal(render.status, 1, 'an unrecorded social story must fail closed');
    assert.match(
      render.stderr,
      /Manual capture receipt does not exist: .*output\/demo-videos\/receipts\//,
    );
    assert.doesNotMatch(render.stderr, /does not define a web-16x9 export target/);
  });

  it('includes social stories in route preflight without adding them to the website playlist', () => {
    const routeVerifier = readFileSync(
      path.resolve('scripts/demo-videos/verify-demo-routes.ts'),
      'utf8',
    );

    assert.match(routeVerifier, /DEMO_VIDEO_PRODUCTION_CATALOG/);
    assert.doesNotMatch(routeVerifier, /DEMO_VIDEO_PLAYLIST/);
  });

  it('keeps social publication on its own empty, canonical allowlist', () => {
    const stories = getSocialStories();
    const publicationApi = demoVideos as unknown as {
      APPROVED_PHASE_ONE_SOCIAL_VIDEO_PUBLICATIONS?: Readonly<Record<string, unknown>>;
      isCompletePhaseOneSocialVideoPublicationApproval?: (
        approval: SocialPublicationApproval | undefined,
        story: SocialStory,
      ) => boolean;
      applyPhaseOneSocialVideoPublicationApproval?: (story: SocialStory) => SocialStory;
    };

    assert.deepEqual(
      Object.keys(publicationApi.APPROVED_PHASE_ONE_SOCIAL_VIDEO_PUBLICATIONS ?? {}),
      [],
    );
    assert.equal(
      typeof publicationApi.isCompletePhaseOneSocialVideoPublicationApproval,
      'function',
    );
    assert.equal(typeof publicationApi.applyPhaseOneSocialVideoPublicationApproval, 'function');

    const story = stories[0];
    const approval: SocialPublicationApproval = {
      approval: 'approved',
      captureReceiptPath: `output/demo-videos/receipts/${story.id}.json`,
      playbackApprovalPath: `output/demo-videos/playback-approvals/${story.id}.json`,
      appBuildCommit: 'a'.repeat(40),
      appBuildLabel: 'Phase 1 social proof',
      recordedAt: '2026-07-14T12:00:00.000Z',
      assetUrl: `/demo-videos/exports/${story.id}-9x16.mp4`,
      thumbnailUrl: `/demo-videos/thumbnails/${story.id}-9x16.png`,
      captionUrl: `/demo-videos/captions/${story.id}.vtt`,
      transcriptUrl: `/demo-videos/transcripts/${story.id}.md`,
    };
    assert.equal(
      publicationApi.isCompletePhaseOneSocialVideoPublicationApproval?.(approval, story),
      true,
    );
    assert.equal(
      publicationApi.isCompletePhaseOneSocialVideoPublicationApproval?.(
        {
          ...approval,
          assetUrl: `/demo-videos/exports/${story.id}-16x9.mp4`,
        },
        story,
      ),
      false,
    );

    const unpublished = publicationApi.applyPhaseOneSocialVideoPublicationApproval?.({
      ...story,
      status: 'published',
      assetUrl: approval.assetUrl,
      thumbnailUrl: approval.thumbnailUrl,
      captionUrl: approval.captionUrl,
      transcriptUrl: approval.transcriptUrl,
      recordedAt: approval.recordedAt,
    });
    assert.ok(unpublished);
    assert.equal(unpublished.status, 'recording');
    assert.equal(unpublished.assetUrl, undefined);
    assert.equal(unpublished.thumbnailUrl, undefined);
    assert.equal(unpublished.captionUrl, undefined);
    assert.equal(unpublished.transcriptUrl, undefined);
    assert.equal(unpublished.recordedAt, undefined);
  });
});
