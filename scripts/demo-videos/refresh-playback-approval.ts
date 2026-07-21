import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { DEMO_VIDEO_PRODUCTION_CATALOG } from '../../app/data/demoVideos';
import {
  getDemoVideoById,
  getDemoVideoProductionRequirementById,
  resolveDemoVideoRenderTarget,
} from '../../app/data/demoVideoProduction';
import { parseCliArgs, resolveFromRepo, type CliArgs } from './cli';
import { validateDemoVideoPlaybackApproval } from './validate-demo-video-playback-approval';

/**
 * Refreshes the mechanical evidence (hashes, byte lengths, dimensions,
 * durations) inside an existing human playback-approval receipt after a
 * re-render, so a narration or render refresh does not require hand-computing
 * every checksum in the runbook template.
 *
 * It deliberately refuses to invent approval: the receipt must already exist,
 * the reviewer must be named, and every review assertion must be explicitly
 * attested on the command line after actually watching the new export. The
 * canonical validator runs on the result, so a refresh that does not hold up
 * fails closed.
 */

const COMMON_ATTESTATIONS = [
  ['attest-full-playback', 'fullNormalSpeedPlaybackCompleted', 'watched the complete export at normal speed'],
  ['attest-captions', 'captionsApproved', 'captions are accurate and readable'],
  ['attest-narration', 'narrationAndAudioApproved', 'narration and audio are approved'],
  ['attest-product-window', 'fullUncroppedProductWindowApproved', 'the full product window is uncropped'],
  ['attest-local-excluded', 'localAndDevelopmentContentExcluded', 'no local/development content is visible'],
  ['attest-private-excluded', 'privateContentExcluded', 'no private content is visible'],
  ['attest-public-safety', 'publicSafetyApproved', 'the export passes public-safety review'],
] as const;

const WEBSITE_ATTESTATIONS = [
  ['attest-desktop-playback', 'desktopApproved', 'website modal playback verified on desktop'],
  ['attest-mobile-playback', 'mobileApproved', 'website modal playback verified on mobile'],
] as const;

const SOCIAL_ATTESTATIONS = [
  ['attest-portrait-mobile', 'portraitMobileApproved', 'portrait-mobile playback verified'],
  ['attest-safe-area', 'safeAreaApproved', 'pillar/title/outcome/CTA verified inside social safe areas'],
] as const;

type MediaProbe = {
  width: number;
  height: number;
  durationSeconds?: number;
  hasAudio: boolean;
};

function sha256File(filePath: string): { artifactSha256: string; byteLength: number } {
  const bytes = fs.readFileSync(filePath);
  return {
    artifactSha256: createHash('sha256').update(bytes).digest('hex'),
    byteLength: bytes.byteLength,
  };
}

function probeMedia(filePath: string, label: string): MediaProbe {
  const result = spawnSync(
    'ffprobe',
    ['-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', filePath],
    { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 },
  );

  if (result.error || result.status !== 0) {
    throw new Error(`ffprobe could not inspect ${label}: ${result.error?.message ?? result.stderr}`);
  }

  const parsed = JSON.parse(result.stdout) as {
    streams?: Array<{ codec_type?: string; width?: number; height?: number }>;
    format?: { duration?: string };
  };
  const video = parsed.streams?.find((stream) => stream.codec_type === 'video');
  if (!video || typeof video.width !== 'number' || typeof video.height !== 'number') {
    throw new Error(`${label} has no probeable video/image stream.`);
  }

  const duration = Number.parseFloat(parsed.format?.duration ?? '');
  return {
    width: video.width,
    height: video.height,
    durationSeconds: Number.isFinite(duration) && duration > 0 ? duration : undefined,
    hasAudio: parsed.streams?.some((stream) => stream.codec_type === 'audio') ?? false,
  };
}

function collectAttestations(
  args: CliArgs,
  entries: readonly (readonly [string, string, string])[],
): Record<string, true> {
  const attestAll = args.flags.has('attest-all');
  const missing = entries.filter(([flag]) => !attestAll && !args.flags.has(flag));
  if (missing.length > 0) {
    throw new Error(
      'Refusing to write an approval that was not explicitly attested. Missing: '
        + missing.map(([flag, , meaning]) => `--${flag} (${meaning})`).join(', ')
        + '. Watch the new export first, then re-run with the missing flags or --attest-all.',
    );
  }

  return Object.fromEntries(entries.map(([, field]) => [field, true as const]));
}

function refreshApproval(demoId: string, args: CliArgs, reviewer: string, reviewedAt: string): void {
  const demo = getDemoVideoById(demoId);
  const requirement = getDemoVideoProductionRequirementById(demoId);
  if (!demo || !requirement) {
    throw new Error(`Unknown demo "${demoId}".`);
  }

  const receiptPath = resolveFromRepo(requirement.playbackApprovalPath);
  if (!fs.existsSync(receiptPath)) {
    throw new Error(
      `No existing playback approval at ${requirement.playbackApprovalPath}. First-time approvals `
        + 'follow the runbook template so the reviewer authors the receipt deliberately.',
    );
  }

  const receipt = JSON.parse(fs.readFileSync(receiptPath, 'utf8')) as Record<string, unknown>;
  const target = resolveDemoVideoRenderTarget(requirement);
  const isSocial = requirement.productionChannel === 'social';

  const review = collectAttestations(args, COMMON_ATTESTATIONS);
  const channelReview = collectAttestations(
    args,
    isSocial ? SOCIAL_ATTESTATIONS : WEBSITE_ATTESTATIONS,
  );

  const videoPath = resolveFromRepo('public', target.assetPath.replace(/^\//, ''));
  const thumbnailPath = resolveFromRepo('public', target.thumbnailPath.replace(/^\//, ''));
  const captionsPath = resolveFromRepo('public', requirement.captionPath);
  const transcriptPath = resolveFromRepo('public', requirement.transcriptPath);
  for (const [label, filePath] of [
    ['Rendered video', videoPath],
    ['Rendered thumbnail', thumbnailPath],
    ['Captions', captionsPath],
    ['Transcript', transcriptPath],
  ] as const) {
    if (!fs.existsSync(filePath)) {
      throw new Error(`${label} is missing at ${filePath}; render the demo before refreshing approval.`);
    }
  }

  const videoProbe = probeMedia(videoPath, 'rendered video');
  const thumbnailProbe = probeMedia(thumbnailPath, 'rendered thumbnail');
  if (!videoProbe.durationSeconds) {
    throw new Error('Rendered video has no probeable duration.');
  }
  if (!videoProbe.hasAudio) {
    throw new Error('Rendered video has no audio stream; re-render with narration before approving.');
  }

  const updated = {
    ...receipt,
    schemaVersion: 1,
    demoId,
    reviewedAt,
    reviewer,
    reviewMethod: 'human-normal-speed-playback',
    sidecars: {
      captions: {
        artifactPath: `public/${requirement.captionPath}`,
        ...sha256File(captionsPath),
      },
      transcript: {
        artifactPath: `public/${requirement.transcriptPath}`,
        ...sha256File(transcriptPath),
      },
    },
    targets: [
      {
        format: target.format,
        video: {
          artifactPath: `public${target.assetPath}`,
          ...sha256File(videoPath),
          width: videoProbe.width,
          height: videoProbe.height,
          durationSeconds: Number(videoProbe.durationSeconds.toFixed(3)),
          hasAudio: true,
        },
        thumbnail: {
          artifactPath: `public${target.thumbnailPath}`,
          ...sha256File(thumbnailPath),
          width: thumbnailProbe.width,
          height: thumbnailProbe.height,
        },
        review,
      },
    ],
    ...(isSocial
      ? { socialPlayback: channelReview, websitePlayback: undefined }
      : { websitePlayback: channelReview, socialPlayback: undefined }),
  };
  delete (updated as Record<string, unknown>)[isSocial ? 'websitePlayback' : 'socialPlayback'];

  fs.writeFileSync(receiptPath, `${JSON.stringify(updated, null, 2)}\n`);

  const validation = validateDemoVideoPlaybackApproval(demoId);
  console.log(
    `${demoId}: refreshed playback approval (${validation.formats.join(', ')}, `
      + `${validation.durationSeconds.toFixed(2)}s) reviewed by ${validation.reviewer}.`,
  );
}

function main(): void {
  const args = parseCliArgs(process.argv.slice(2));
  const reviewer = args.values.get('reviewer')?.trim();
  if (!reviewer) {
    throw new Error('Pass --reviewer "Full Name" — approvals must name the human who watched the export.');
  }

  const reviewedAt = args.values.get('reviewed-at') ?? new Date().toISOString();
  const requested = args.repeatedValues.get('demo') ?? [];
  const demoIds = args.flags.has('all-published')
    ? DEMO_VIDEO_PRODUCTION_CATALOG.filter((demo) => demo.status === 'published').map((demo) => demo.id)
    : requested;

  if (demoIds.length === 0) {
    throw new Error('Pass --demo <id> (repeatable) or --all-published.');
  }

  for (const demoId of demoIds) {
    refreshApproval(demoId, args, reviewer, reviewedAt);
  }
}

const isMainModule = process.argv[1]
  ? path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))
  : false;

if (isMainModule) {
  try {
    main();
  } catch (error: unknown) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}
