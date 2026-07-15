import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { after, before, describe, it } from 'node:test';

import { getDemoVideoProductionRequirementById } from '../../app/data/demoVideoProduction';
import {
  validateDemoVideoPlaybackApproval,
  type DemoVideoPlaybackApprovalReceipt,
  type DemoVideoSocialPlaybackApprovalReceipt,
  type DemoVideoWebsitePlaybackApprovalReceipt,
} from '../../scripts/demo-videos/validate-demo-video-playback-approval';

const ROOT = process.cwd();
const DEMO_ID = 'planner-command-center-walkthrough';
const SOCIAL_DEMO_ID = 'connection-over-tools-social';

type ProbedMedia = {
  width: number;
  height: number;
  durationSeconds: number;
  hasAudio: boolean;
};

function run(command: string, args: readonly string[]): string {
  const result = spawnSync(command, args, { encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 });
  assert.equal(
    result.status,
    0,
    `${command} failed: ${result.stderr || result.error?.message || 'unknown error'}`,
  );
  return result.stdout;
}

function createVideo(
  filePath: string,
  width: number,
  height: number,
  withAudio = true,
  durationSeconds = 75,
): void {
  mkdirSync(path.dirname(filePath), { recursive: true });
  const args = [
    '-v',
    'error',
    '-y',
    '-f',
    'lavfi',
    '-i',
    `color=c=0x1b2440:s=${width}x${height}:r=1:d=${durationSeconds}`,
  ];

  if (withAudio) {
    args.push(
      '-f',
      'lavfi',
      '-i',
      `sine=frequency=440:sample_rate=44100:duration=${durationSeconds}`,
      '-shortest',
    );
  }

  args.push('-c:v', 'mpeg4', '-q:v', '20', '-pix_fmt', 'yuv420p');
  if (withAudio) args.push('-c:a', 'aac', '-b:a', '48k');
  args.push('-movflags', '+faststart', filePath);
  run('ffmpeg', args);
}

function createThumbnail(filePath: string, width: number, height: number): void {
  mkdirSync(path.dirname(filePath), { recursive: true });
  run('ffmpeg', [
    '-v',
    'error',
    '-y',
    '-f',
    'lavfi',
    '-i',
    `color=c=0x1b2440:s=${width}x${height}`,
    '-frames:v',
    '1',
    '-update',
    '1',
    filePath,
  ]);
}

function probe(filePath: string): ProbedMedia {
  const output = run('ffprobe', [
    '-v',
    'error',
    '-show_entries',
    'stream=codec_type,width,height:format=duration',
    '-of',
    'json',
    filePath,
  ]);
  const parsed = JSON.parse(output) as {
    streams: Array<{ codec_type?: string; width?: number; height?: number }>;
    format: { duration?: string };
  };
  const video = parsed.streams.find((stream) => stream.codec_type === 'video');
  assert.ok(video);
  return {
    width: Number(video.width),
    height: Number(video.height),
    durationSeconds: Number(parsed.format.duration),
    hasAudio: parsed.streams.some((stream) => stream.codec_type === 'audio'),
  };
}

function artifactEvidence(rootDir: string, artifactPath: string) {
  const absolutePath = path.join(rootDir, artifactPath);
  const bytes = readFileSync(absolutePath);
  return {
    artifactPath,
    artifactSha256: createHash('sha256').update(bytes).digest('hex'),
    byteLength: statSync(absolutePath).size,
  };
}

function cloneReceipt<T extends DemoVideoPlaybackApprovalReceipt>(receipt: T): T {
  return JSON.parse(JSON.stringify(receipt)) as T;
}

describe('demo video playback approval', () => {
  let fixtureRoot = '';
  let canonicalReceiptPath = '';
  let approvedReceipt: DemoVideoWebsitePlaybackApprovalReceipt;

  before(() => {
    fixtureRoot = mkdtempSync(path.join(os.tmpdir(), 'demo-video-playback-approval-'));
    const requirement = getDemoVideoProductionRequirementById(DEMO_ID);
    assert.ok(requirement);

    const targets = requirement.exportTargets.map((target) => {
      const videoPath = `public/${target.assetPath.replace(/^\//, '')}`;
      const thumbnailPath = `public/${target.thumbnailPath.replace(/^\//, '')}`;
      const absoluteVideoPath = path.join(fixtureRoot, videoPath);
      const absoluteThumbnailPath = path.join(fixtureRoot, thumbnailPath);
      createVideo(absoluteVideoPath, target.width, target.height);
      createThumbnail(absoluteThumbnailPath, target.width, target.height);
      const media = probe(absoluteVideoPath);

      return {
        format: target.format,
        video: {
          ...artifactEvidence(fixtureRoot, videoPath),
          width: media.width,
          height: media.height,
          durationSeconds: media.durationSeconds,
          hasAudio: true as const,
        },
        thumbnail: {
          ...artifactEvidence(fixtureRoot, thumbnailPath),
          width: target.width,
          height: target.height,
        },
        review: {
          fullNormalSpeedPlaybackCompleted: true as const,
          captionsApproved: true as const,
          narrationAndAudioApproved: true as const,
          fullUncroppedProductWindowApproved: true as const,
          localAndDevelopmentContentExcluded: true as const,
          privateContentExcluded: true as const,
          publicSafetyApproved: true as const,
        },
      };
    });
    const captionPath = `public/${requirement.captionPath}`;
    const transcriptPath = `public/${requirement.transcriptPath}`;
    mkdirSync(path.dirname(path.join(fixtureRoot, captionPath)), { recursive: true });
    mkdirSync(path.dirname(path.join(fixtureRoot, transcriptPath)), { recursive: true });
    writeFileSync(path.join(fixtureRoot, captionPath), 'WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nPlanner proof.\n');
    writeFileSync(path.join(fixtureRoot, transcriptPath), '# Planner command center walkthrough\n\nApproved narration.\n');

    approvedReceipt = {
      schemaVersion: 1,
      demoId: DEMO_ID,
      reviewedAt: '2026-07-13T12:00:00.000Z',
      reviewer: 'Jordan Lee',
      reviewMethod: 'human-normal-speed-playback',
      sidecars: {
        captions: artifactEvidence(fixtureRoot, captionPath),
        transcript: artifactEvidence(fixtureRoot, transcriptPath),
      },
      targets,
      websitePlayback: {
        desktopApproved: true,
        mobileApproved: true,
      },
    };
    canonicalReceiptPath = path.join(fixtureRoot, requirement.playbackApprovalPath);
    mkdirSync(path.dirname(canonicalReceiptPath), { recursive: true });
    writeFileSync(canonicalReceiptPath, `${JSON.stringify(approvedReceipt, null, 2)}\n`);
  });

  after(() => {
    if (fixtureRoot) rmSync(fixtureRoot, { recursive: true, force: true });
  });

  function writeReceipt(receipt: DemoVideoPlaybackApprovalReceipt): void {
    writeFileSync(canonicalReceiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
  }

  it('provides a dedicated fail-closed playback approval command', () => {
    const validatorPath = path.join(
      ROOT,
      'scripts/demo-videos/validate-demo-video-playback-approval.ts',
    );

    assert.equal(existsSync(validatorPath), true, 'playback approval validator is missing');

    const packageJson = readFileSync(path.join(ROOT, 'package.json'), 'utf8');
    assert.match(
      packageJson,
      /"demo:validate-playback": "tsx scripts\/demo-videos\/validate-demo-video-playback-approval\.ts"/,
    );
  });

  it('validates media metadata without launching or controlling a browser', () => {
    const validator = readFileSync(
      path.join(ROOT, 'scripts/demo-videos/validate-demo-video-playback-approval.ts'),
      'utf8',
    );

    assert.match(validator, /validateDemoVideoPlaybackApproval/);
    assert.match(validator, /ffprobe/);
    assert.doesNotMatch(validator, /playwright|puppeteer|chromium|computer.?use/i);
    assert.doesNotMatch(
      validator,
      /\.goto\s*\(|\.screenshot\s*\(|page\.(?:locator|evaluate)|browser\.(?:newContext|close)/i,
    );
  });

  it('accepts only a complete canonical human playback approval receipt', () => {
    writeReceipt(approvedReceipt);

    const result = validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot });
    const requirement = getDemoVideoProductionRequirementById(DEMO_ID);
    assert.ok(requirement);

    assert.equal(result.demoId, DEMO_ID);
    assert.equal(result.targetCount, requirement.exportTargets.length);
    assert.equal(result.receiptPath, `output/demo-videos/playback-approvals/${DEMO_ID}.json`);
    assert.deepEqual(
      result.formats,
      requirement.exportTargets.map((target) => target.format).sort(),
    );
  });

  it('rejects unknown demos and placeholder reviewer attestations', () => {
    assert.throws(
      () => validateDemoVideoPlaybackApproval('unknown-demo', { rootDir: fixtureRoot }),
      /Unknown demo/,
    );

    const placeholder = cloneReceipt(approvedReceipt);
    placeholder.reviewer = 'TBD placeholder';
    writeReceipt(placeholder);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      /reviewer.*placeholder/i,
    );
  });

  it('rejects missing, extra, or non-canonical production targets and paths', () => {
    const requirement = getDemoVideoProductionRequirementById(DEMO_ID);
    assert.ok(requirement);
    const exactTargetCount = new RegExp(
      `exactly ${requirement.exportTargets.length} production targets`,
    );
    const missingTarget = cloneReceipt(approvedReceipt);
    missingTarget.targets.pop();
    writeReceipt(missingTarget);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      exactTargetCount,
    );

    const extraTarget = cloneReceipt(approvedReceipt);
    extraTarget.targets.push(cloneReceipt(approvedReceipt).targets[0]);
    writeReceipt(extraTarget);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      exactTargetCount,
    );

    const wrongPath = cloneReceipt(approvedReceipt);
    wrongPath.targets[0].video.artifactPath = 'public/demo-videos/exports/placeholder.mp4';
    writeReceipt(wrongPath);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      /must use the canonical production path/,
    );
  });

  it('rejects checksum, byte-length, dimension, duration, and thumbnail evidence drift', () => {
    const wrongHash = cloneReceipt(approvedReceipt);
    wrongHash.targets[0].video.artifactSha256 = '0'.repeat(64);
    writeReceipt(wrongHash);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      /SHA-256 does not match/,
    );

    const zeroSize = cloneReceipt(approvedReceipt);
    zeroSize.targets[0].thumbnail.byteLength = 0;
    writeReceipt(zeroSize);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      /byteLength must be a positive integer/,
    );

    const wrongDimensions = cloneReceipt(approvedReceipt);
    wrongDimensions.targets[0].video.width -= 1;
    writeReceipt(wrongDimensions);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      /dimensions do not match ffprobe/,
    );

    const wrongDuration = cloneReceipt(approvedReceipt);
    wrongDuration.targets[0].video.durationSeconds += 3;
    writeReceipt(wrongDuration);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      /duration does not match ffprobe/,
    );

    const wrongThumbnailDimensions = cloneReceipt(approvedReceipt);
    wrongThumbnailDimensions.targets[0].thumbnail.height -= 1;
    writeReceipt(wrongThumbnailDimensions);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      /thumbnail dimensions do not match ffprobe/,
    );
  });

  it('rejects rendered video without an ffprobe-confirmed audio stream', () => {
    const receipt = cloneReceipt(approvedReceipt);
    const target = receipt.targets[0];
    const absoluteVideoPath = path.join(fixtureRoot, target.video.artifactPath);
    const originalVideo = readFileSync(absoluteVideoPath);

    try {
      createVideo(absoluteVideoPath, target.video.width, target.video.height, false);
      const media = probe(absoluteVideoPath);
      target.video = {
        ...target.video,
        ...artifactEvidence(fixtureRoot, target.video.artifactPath),
        durationSeconds: media.durationSeconds,
        hasAudio: true,
      };
      writeReceipt(receipt);

      assert.throws(
        () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
        /does not contain an audio stream/,
      );
    } finally {
      writeFileSync(absoluteVideoPath, originalVideo);
    }
  });

  it('requires every human review and desktop/mobile website playback assertion explicitly true', () => {
    const targetReviewFields = [
      'fullNormalSpeedPlaybackCompleted',
      'captionsApproved',
      'narrationAndAudioApproved',
      'fullUncroppedProductWindowApproved',
      'localAndDevelopmentContentExcluded',
      'privateContentExcluded',
      'publicSafetyApproved',
    ] as const;

    for (const field of targetReviewFields) {
      const receipt = cloneReceipt(approvedReceipt);
      receipt.targets[0].review[field] = false as never;
      writeReceipt(receipt);
      assert.throws(
        () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
        new RegExp(`${field} must be explicitly true`),
      );
    }

    for (const field of ['desktopApproved', 'mobileApproved'] as const) {
      const receipt = cloneReceipt(approvedReceipt);
      receipt.websitePlayback[field] = false as never;
      writeReceipt(receipt);
      assert.throws(
        () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
        new RegExp(`${field} must be explicitly true`),
      );
    }
  });

  it('rejects social playback attestations on a website video receipt', () => {
    const receipt = {
      ...cloneReceipt(approvedReceipt),
      socialPlayback: {
        portraitMobileApproved: true,
        safeAreaApproved: true,
      },
    } as unknown as DemoVideoPlaybackApprovalReceipt;
    writeReceipt(receipt);

    assert.throws(
      () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
      /socialPlayback.*not allowed/i,
    );
  });

  it('binds reviewed captions and transcript to their exact canonical bytes', () => {
    const captionPath = path.join(fixtureRoot, approvedReceipt.sidecars.captions.artifactPath);
    const originalCaption = readFileSync(captionPath);

    try {
      writeFileSync(captionPath, 'WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nAltered proof.\n');
      writeReceipt(approvedReceipt);
      assert.throws(
        () => validateDemoVideoPlaybackApproval(DEMO_ID, { rootDir: fixtureRoot }),
        /captions SHA-256 does not match the approval receipt/,
      );
    } finally {
      writeFileSync(captionPath, originalCaption);
      writeReceipt(approvedReceipt);
    }
  });
});

describe('Phase 1 social video playback approval', () => {
  let fixtureRoot = '';
  let canonicalReceiptPath = '';
  let approvedReceipt: DemoVideoSocialPlaybackApprovalReceipt;

  before(() => {
    fixtureRoot = mkdtempSync(path.join(os.tmpdir(), 'social-video-playback-approval-'));
    const requirement = getDemoVideoProductionRequirementById(SOCIAL_DEMO_ID);
    assert.ok(requirement, 'social story must have a production requirement');
    assert.equal(requirement.productionChannel, 'social');
    assert.equal(requirement.exportTargets.length, 1);

    const target = requirement.exportTargets[0];
    assert.equal(target.format, 'social-9x16');
    const videoPath = `public/${target.assetPath.replace(/^\//, '')}`;
    const thumbnailPath = `public/${target.thumbnailPath.replace(/^\//, '')}`;
    const absoluteVideoPath = path.join(fixtureRoot, videoPath);
    const absoluteThumbnailPath = path.join(fixtureRoot, thumbnailPath);
    createVideo(absoluteVideoPath, target.width, target.height, true, 30);
    createThumbnail(absoluteThumbnailPath, target.width, target.height);
    const media = probe(absoluteVideoPath);
    const captionPath = `public/${requirement.captionPath}`;
    const transcriptPath = `public/${requirement.transcriptPath}`;
    mkdirSync(path.dirname(path.join(fixtureRoot, captionPath)), { recursive: true });
    mkdirSync(path.dirname(path.join(fixtureRoot, transcriptPath)), { recursive: true });
    writeFileSync(path.join(fixtureRoot, captionPath), 'WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nSocial proof.\n');
    writeFileSync(path.join(fixtureRoot, transcriptPath), '# One plan. Three clear views.\n\nApproved narration.\n');

    approvedReceipt = {
      schemaVersion: 1,
      demoId: SOCIAL_DEMO_ID,
      reviewedAt: '2026-07-14T12:00:00.000Z',
      reviewer: 'Jordan Lee',
      reviewMethod: 'human-normal-speed-playback',
      sidecars: {
        captions: artifactEvidence(fixtureRoot, captionPath),
        transcript: artifactEvidence(fixtureRoot, transcriptPath),
      },
      targets: [
        {
          format: target.format,
          video: {
            ...artifactEvidence(fixtureRoot, videoPath),
            width: media.width,
            height: media.height,
            durationSeconds: media.durationSeconds,
            hasAudio: true,
          },
          thumbnail: {
            ...artifactEvidence(fixtureRoot, thumbnailPath),
            width: target.width,
            height: target.height,
          },
          review: {
            fullNormalSpeedPlaybackCompleted: true,
            captionsApproved: true,
            narrationAndAudioApproved: true,
            fullUncroppedProductWindowApproved: true,
            localAndDevelopmentContentExcluded: true,
            privateContentExcluded: true,
            publicSafetyApproved: true,
          },
        },
      ],
      socialPlayback: {
        portraitMobileApproved: true,
        safeAreaApproved: true,
      },
    };

    canonicalReceiptPath = path.join(fixtureRoot, requirement.playbackApprovalPath);
    mkdirSync(path.dirname(canonicalReceiptPath), { recursive: true });
    writeFileSync(canonicalReceiptPath, `${JSON.stringify(approvedReceipt, null, 2)}\n`);
  });

  after(() => {
    if (fixtureRoot) rmSync(fixtureRoot, { recursive: true, force: true });
  });

  function writeReceipt(receipt: DemoVideoPlaybackApprovalReceipt): void {
    writeFileSync(canonicalReceiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
  }

  it('accepts one canonical 1080x1920 target with portrait-mobile and safe-area approval', () => {
    writeReceipt(approvedReceipt);

    const result = validateDemoVideoPlaybackApproval(SOCIAL_DEMO_ID, {
      rootDir: fixtureRoot,
    });

    assert.equal(result.demoId, SOCIAL_DEMO_ID);
    assert.equal(result.targetCount, 1);
    assert.deepEqual(result.formats, ['social-9x16']);
  });

  it('accepts sub-frame container timing drift on the approved 35-second social cut', () => {
    assert.doesNotThrow(() => validateDemoVideoPlaybackApproval(
      'built-for-planners-social',
      { rootDir: ROOT },
    ));
  });

  it('requires social playback approval and rejects a website playback attestation', () => {
    for (const field of ['portraitMobileApproved', 'safeAreaApproved'] as const) {
      const receipt = cloneReceipt(approvedReceipt);
      receipt.socialPlayback[field] = false as never;
      writeReceipt(receipt);
      assert.throws(
        () => validateDemoVideoPlaybackApproval(SOCIAL_DEMO_ID, { rootDir: fixtureRoot }),
        new RegExp(`${field} must be explicitly true`),
      );
    }

    const { socialPlayback: _socialPlayback, ...receiptWithoutSocialPlayback } = cloneReceipt(
      approvedReceipt,
    );
    const websiteReceipt: DemoVideoWebsitePlaybackApprovalReceipt = {
      ...receiptWithoutSocialPlayback,
      websitePlayback: {
        desktopApproved: true,
        mobileApproved: true,
      },
    };
    writeReceipt(websiteReceipt);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(SOCIAL_DEMO_ID, { rootDir: fixtureRoot }),
      /websitePlayback.*not allowed/i,
    );
  });

  it('rejects website playback attestations on a social video receipt', () => {
    const receipt = {
      ...cloneReceipt(approvedReceipt),
      websitePlayback: {
        desktopApproved: true,
        mobileApproved: true,
      },
    } as unknown as DemoVideoPlaybackApprovalReceipt;
    writeReceipt(receipt);

    assert.throws(
      () => validateDemoVideoPlaybackApproval(SOCIAL_DEMO_ID, { rootDir: fixtureRoot }),
      /websitePlayback.*not allowed/i,
    );
  });

  it('rejects non-canonical paths and drift in portrait dimensions, duration, or audio', () => {
    const wrongPath = cloneReceipt(approvedReceipt);
    wrongPath.targets[0].video.artifactPath =
      'public/demo-videos/exports/connection-over-tools-social-16x9.mp4';
    writeReceipt(wrongPath);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(SOCIAL_DEMO_ID, { rootDir: fixtureRoot }),
      /must use the canonical production path/,
    );

    const wrongDuration = cloneReceipt(approvedReceipt);
    wrongDuration.targets[0].video.durationSeconds += 3;
    writeReceipt(wrongDuration);
    assert.throws(
      () => validateDemoVideoPlaybackApproval(SOCIAL_DEMO_ID, { rootDir: fixtureRoot }),
      /duration does not match ffprobe/,
    );

    const target = approvedReceipt.targets[0];
    const absoluteVideoPath = path.join(fixtureRoot, target.video.artifactPath);
    const originalVideo = readFileSync(absoluteVideoPath);

    try {
      createVideo(absoluteVideoPath, 1080, 1918, true, 30);
      const portraitDrift = cloneReceipt(approvedReceipt);
      const media = probe(absoluteVideoPath);
      portraitDrift.targets[0].video = {
        ...portraitDrift.targets[0].video,
        ...artifactEvidence(fixtureRoot, target.video.artifactPath),
        width: media.width,
        height: media.height,
        durationSeconds: media.durationSeconds,
      };
      writeReceipt(portraitDrift);
      assert.throws(
        () => validateDemoVideoPlaybackApproval(SOCIAL_DEMO_ID, { rootDir: fixtureRoot }),
        /must be 1080x1920/,
      );

      createVideo(absoluteVideoPath, 1080, 1920, false, 30);
      const missingAudio = cloneReceipt(approvedReceipt);
      const silentMedia = probe(absoluteVideoPath);
      missingAudio.targets[0].video = {
        ...missingAudio.targets[0].video,
        ...artifactEvidence(fixtureRoot, target.video.artifactPath),
        width: silentMedia.width,
        height: silentMedia.height,
        durationSeconds: silentMedia.durationSeconds,
        hasAudio: true,
      };
      writeReceipt(missingAudio);
      assert.throws(
        () => validateDemoVideoPlaybackApproval(SOCIAL_DEMO_ID, { rootDir: fixtureRoot }),
        /does not contain an audio stream/,
      );
    } finally {
      writeFileSync(absoluteVideoPath, originalVideo);
      writeReceipt(approvedReceipt);
    }
  });

  it('rejects a portrait export outside the authored social duration bounds', () => {
    const target = approvedReceipt.targets[0];
    const absoluteVideoPath = path.join(fixtureRoot, target.video.artifactPath);
    const originalVideo = readFileSync(absoluteVideoPath);

    try {
      createVideo(absoluteVideoPath, 1080, 1920, true, 10);
      const tooShort = cloneReceipt(approvedReceipt);
      const media = probe(absoluteVideoPath);
      tooShort.targets[0].video = {
        ...tooShort.targets[0].video,
        ...artifactEvidence(fixtureRoot, target.video.artifactPath),
        width: media.width,
        height: media.height,
        durationSeconds: media.durationSeconds,
      };
      writeReceipt(tooShort);

      assert.throws(
        () => validateDemoVideoPlaybackApproval(SOCIAL_DEMO_ID, { rootDir: fixtureRoot }),
        /duration must stay within 25-35 seconds/,
      );
    } finally {
      writeFileSync(absoluteVideoPath, originalVideo);
      writeReceipt(approvedReceipt);
    }
  });
});
