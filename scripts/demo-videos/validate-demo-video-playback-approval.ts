import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  getDemoVideoById,
  getDemoVideoProductionRequirementById,
  type DemoVideoExportFormat,
  type DemoVideoExportTarget,
} from '../../app/data/demoVideoProduction';
import { getRequiredValue, parseCliArgs, resolveFromRepo } from './cli';

type PlaybackArtifactEvidence = {
  artifactPath: string;
  artifactSha256: string;
  byteLength: number;
};

type PlaybackVideoEvidence = PlaybackArtifactEvidence & {
  width: number;
  height: number;
  durationSeconds: number;
  hasAudio: true;
};

type PlaybackThumbnailEvidence = PlaybackArtifactEvidence & {
  width: number;
  height: number;
};

type HumanPlaybackReview = {
  fullNormalSpeedPlaybackCompleted: true;
  captionsApproved: true;
  narrationAndAudioApproved: true;
  fullUncroppedProductWindowApproved: true;
  localAndDevelopmentContentExcluded: true;
  privateContentExcluded: true;
  publicSafetyApproved: true;
};

export type DemoVideoPlaybackApprovalTarget = {
  format: DemoVideoExportFormat;
  video: PlaybackVideoEvidence;
  thumbnail: PlaybackThumbnailEvidence;
  review: HumanPlaybackReview;
};

export type DemoVideoPlaybackApprovalReceipt = {
  schemaVersion: 1;
  demoId: string;
  reviewedAt: string;
  reviewer: string;
  reviewMethod: 'human-normal-speed-playback';
  targets: DemoVideoPlaybackApprovalTarget[];
  websitePlayback: {
    desktopApproved: true;
    mobileApproved: true;
  };
};

export type DemoVideoPlaybackApprovalValidation = {
  demoId: string;
  receiptPath: string;
  reviewer: string;
  reviewedAt: string;
  targetCount: number;
  formats: DemoVideoExportFormat[];
};

type MediaProbe = {
  width: number;
  height: number;
  durationSeconds?: number;
  hasAudio: boolean;
};

type ValidationOptions = {
  rootDir?: string;
};

const REVIEW_ASSERTIONS = [
  'fullNormalSpeedPlaybackCompleted',
  'captionsApproved',
  'narrationAndAudioApproved',
  'fullUncroppedProductWindowApproved',
  'localAndDevelopmentContentExcluded',
  'privateContentExcluded',
  'publicSafetyApproved',
] as const;

const PLACEHOLDER_REVIEWER = /(?:^|[\s_-])(?:unknown|placeholder|tbd|todo|pending|n\/a)(?:$|[\s_-])/i;
const SHA256 = /^[0-9a-f]{64}$/;

function assertRecord(value: unknown, label: string): asserts value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} must be a JSON object.`);
  }
}

function assertExplicitTrue(value: unknown, label: string): asserts value is true {
  if (value !== true) {
    throw new Error(`${label} must be explicitly true.`);
  }
}

function assertPositiveInteger(value: unknown, label: string): asserts value is number {
  if (!Number.isInteger(value) || Number(value) <= 0) {
    throw new Error(`${label} must be a positive integer.`);
  }
}

function assertPositiveNumber(value: unknown, label: string): asserts value is number {
  if (!Number.isFinite(value) || Number(value) <= 0) {
    throw new Error(`${label} must be a positive number.`);
  }
}

function sha256(bytes: Buffer): string {
  return createHash('sha256').update(bytes).digest('hex');
}

function probeMedia(artifactPath: string, label: string): MediaProbe {
  const result = spawnSync(
    'ffprobe',
    [
      '-v',
      'error',
      '-show_entries',
      'stream=codec_type,width,height:format=duration',
      '-of',
      'json',
      artifactPath,
    ],
    { encoding: 'utf8', maxBuffer: 1024 * 1024 },
  );

  if (result.error) {
    throw new Error(`ffprobe could not inspect ${label}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`ffprobe rejected ${label} (exit ${result.status ?? 'unknown'}).`);
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(result.stdout);
  } catch {
    throw new Error(`ffprobe returned invalid JSON for ${label}.`);
  }
  assertRecord(parsed, `ffprobe result for ${label}`);
  if (!Array.isArray(parsed.streams)) {
    throw new Error(`${label} does not contain inspectable media streams.`);
  }

  const streams = parsed.streams.filter(
    (stream): stream is Record<string, unknown> => Boolean(stream) && typeof stream === 'object' && !Array.isArray(stream),
  );
  const video = streams.find((stream) => stream.codec_type === 'video');
  if (!video) {
    throw new Error(`${label} does not contain a video/image stream.`);
  }

  const width = Number(video.width);
  const height = Number(video.height);
  if (![width, height].every((value) => Number.isInteger(value) && value > 0)) {
    throw new Error(`${label} has invalid ffprobe dimensions.`);
  }

  const format = parsed.format;
  const rawDuration = format && typeof format === 'object' && !Array.isArray(format)
    ? Number((format as Record<string, unknown>).duration)
    : Number.NaN;

  return {
    width,
    height,
    durationSeconds: Number.isFinite(rawDuration) && rawDuration > 0 ? rawDuration : undefined,
    hasAudio: streams.some((stream) => stream.codec_type === 'audio'),
  };
}

function readReceipt(receiptPath: string): unknown {
  if (!fs.existsSync(receiptPath) || !fs.statSync(receiptPath).isFile()) {
    throw new Error(`Playback approval receipt does not exist: ${receiptPath}`);
  }
  if (fs.lstatSync(receiptPath).isSymbolicLink()) {
    throw new Error('Playback approval receipt must be a direct file, not a symbolic link.');
  }

  try {
    return JSON.parse(fs.readFileSync(receiptPath, 'utf8')) as unknown;
  } catch {
    throw new Error(`Playback approval receipt is not valid JSON: ${receiptPath}`);
  }
}

function assertReceiptIdentity(
  parsed: unknown,
  demoId: string,
): asserts parsed is DemoVideoPlaybackApprovalReceipt {
  assertRecord(parsed, 'Playback approval receipt');
  if (parsed.schemaVersion !== 1) {
    throw new Error('Playback approval receipt schemaVersion must be 1.');
  }
  if (parsed.demoId !== demoId) {
    throw new Error(`Playback approval receipt demoId must be ${demoId}.`);
  }
  if (parsed.reviewMethod !== 'human-normal-speed-playback') {
    throw new Error('Playback approval reviewMethod must be human-normal-speed-playback.');
  }

  const reviewedAt = typeof parsed.reviewedAt === 'string' ? parsed.reviewedAt : '';
  const parsedDate = new Date(reviewedAt);
  if (!reviewedAt || Number.isNaN(parsedDate.getTime()) || parsedDate.toISOString() !== reviewedAt) {
    throw new Error('Playback approval reviewedAt must be an exact ISO timestamp.');
  }

  const reviewer = typeof parsed.reviewer === 'string' ? parsed.reviewer.trim() : '';
  if (reviewer.length < 3 || PLACEHOLDER_REVIEWER.test(reviewer)) {
    throw new Error('Playback approval reviewer must identify a human and cannot use placeholder values.');
  }
  if (reviewer !== parsed.reviewer) {
    throw new Error('Playback approval reviewer must not contain leading or trailing whitespace.');
  }

  if (!Array.isArray(parsed.targets)) {
    throw new Error('Playback approval targets must be an array.');
  }
  assertRecord(parsed.websitePlayback, 'websitePlayback');
  assertExplicitTrue(parsed.websitePlayback.desktopApproved, 'desktopApproved');
  assertExplicitTrue(parsed.websitePlayback.mobileApproved, 'mobileApproved');
}

function assertArtifact(
  evidence: Record<string, unknown>,
  expectedPath: string,
  rootDir: string,
  label: string,
): { absolutePath: string; probe: MediaProbe } {
  if (evidence.artifactPath !== expectedPath) {
    throw new Error(`${label} must use the canonical production path ${expectedPath}.`);
  }
  if (typeof evidence.artifactSha256 !== 'string' || !SHA256.test(evidence.artifactSha256)) {
    throw new Error(`${label} artifactSha256 must be a full lowercase SHA-256 checksum.`);
  }
  assertPositiveInteger(evidence.byteLength, `${label} byteLength`);

  const absolutePath = path.resolve(rootDir, expectedPath);
  const normalizedRoot = path.resolve(rootDir);
  if (!absolutePath.startsWith(`${normalizedRoot}${path.sep}`)) {
    throw new Error(`${label} artifact path escapes the repository root.`);
  }
  if (!fs.existsSync(absolutePath) || !fs.statSync(absolutePath).isFile()) {
    throw new Error(`${label} does not exist at ${expectedPath}.`);
  }
  if (fs.lstatSync(absolutePath).isSymbolicLink()) {
    throw new Error(`${label} must be a direct file, not a symbolic link.`);
  }

  const bytes = fs.readFileSync(absolutePath);
  if (bytes.byteLength === 0) {
    throw new Error(`${label} must be nonempty.`);
  }
  if (bytes.byteLength !== evidence.byteLength) {
    throw new Error(`${label} byte length does not match the approval receipt.`);
  }
  if (sha256(bytes) !== evidence.artifactSha256) {
    throw new Error(`${label} SHA-256 does not match the approval receipt.`);
  }

  return { absolutePath, probe: probeMedia(absolutePath, label) };
}

function validateTarget(
  value: unknown,
  expected: DemoVideoExportTarget,
  rootDir: string,
): { format: DemoVideoExportFormat; durationSeconds: number } {
  assertRecord(value, `${expected.format} approval target`);
  if (value.format !== expected.format) {
    throw new Error(`Playback approval target format must be ${expected.format}.`);
  }
  assertRecord(value.video, `${expected.format} video evidence`);
  assertRecord(value.thumbnail, `${expected.format} thumbnail evidence`);
  assertRecord(value.review, `${expected.format} human review`);

  for (const assertion of REVIEW_ASSERTIONS) {
    assertExplicitTrue(value.review[assertion], assertion);
  }
  assertExplicitTrue(value.video.hasAudio, `${expected.format} video hasAudio`);

  const expectedVideoPath = `public/${expected.assetPath.replace(/^\//, '')}`;
  const videoArtifact = assertArtifact(
    value.video,
    expectedVideoPath,
    rootDir,
    `${expected.format} rendered video`,
  );
  assertPositiveInteger(value.video.width, `${expected.format} video width`);
  assertPositiveInteger(value.video.height, `${expected.format} video height`);
  assertPositiveNumber(value.video.durationSeconds, `${expected.format} video durationSeconds`);
  if (
    value.video.width !== videoArtifact.probe.width
    || value.video.height !== videoArtifact.probe.height
  ) {
    throw new Error(`${expected.format} rendered video dimensions do not match ffprobe.`);
  }
  if (videoArtifact.probe.width !== expected.width || videoArtifact.probe.height !== expected.height) {
    throw new Error(
      `${expected.format} rendered video must be ${expected.width}x${expected.height}; ffprobe found ${videoArtifact.probe.width}x${videoArtifact.probe.height}.`,
    );
  }
  if (!videoArtifact.probe.durationSeconds) {
    throw new Error(`${expected.format} rendered video does not have a positive ffprobe duration.`);
  }
  if (Math.abs(value.video.durationSeconds - videoArtifact.probe.durationSeconds) > 0.25) {
    throw new Error(`${expected.format} rendered video duration does not match ffprobe.`);
  }
  if (!videoArtifact.probe.hasAudio) {
    throw new Error(`${expected.format} rendered video does not contain an audio stream.`);
  }

  const expectedThumbnailPath = `public/${expected.thumbnailPath.replace(/^\//, '')}`;
  const thumbnailArtifact = assertArtifact(
    value.thumbnail,
    expectedThumbnailPath,
    rootDir,
    `${expected.format} thumbnail`,
  );
  assertPositiveInteger(value.thumbnail.width, `${expected.format} thumbnail width`);
  assertPositiveInteger(value.thumbnail.height, `${expected.format} thumbnail height`);
  if (
    value.thumbnail.width !== thumbnailArtifact.probe.width
    || value.thumbnail.height !== thumbnailArtifact.probe.height
  ) {
    throw new Error(`${expected.format} thumbnail dimensions do not match ffprobe.`);
  }
  if (
    thumbnailArtifact.probe.width !== expected.width
    || thumbnailArtifact.probe.height !== expected.height
  ) {
    throw new Error(
      `${expected.format} thumbnail must be ${expected.width}x${expected.height}; ffprobe found ${thumbnailArtifact.probe.width}x${thumbnailArtifact.probe.height}.`,
    );
  }

  return { format: expected.format, durationSeconds: videoArtifact.probe.durationSeconds };
}

export function validateDemoVideoPlaybackApproval(
  demoId: string,
  options: ValidationOptions = {},
): DemoVideoPlaybackApprovalValidation {
  const demo = getDemoVideoById(demoId);
  const requirement = getDemoVideoProductionRequirementById(demoId);
  if (!demo || !requirement) {
    throw new Error(`Unknown demo "${demoId}".`);
  }

  const rootDir = path.resolve(options.rootDir ?? resolveFromRepo());
  const receiptPath = path.resolve(rootDir, requirement.playbackApprovalPath);
  const parsed = readReceipt(receiptPath);
  assertReceiptIdentity(parsed, demoId);

  if (parsed.targets.length !== requirement.exportTargets.length) {
    throw new Error(
      `Playback approval must contain exactly ${requirement.exportTargets.length} production targets.`,
    );
  }

  const targetsByFormat = new Map<string, unknown>();
  for (const target of parsed.targets) {
    assertRecord(target, 'Playback approval target');
    if (typeof target.format !== 'string' || targetsByFormat.has(target.format)) {
      throw new Error('Playback approval target formats must be known and unique.');
    }
    targetsByFormat.set(target.format, target);
  }

  const validatedTargets = requirement.exportTargets.map((expected) => {
    const target = targetsByFormat.get(expected.format);
    if (!target) {
      throw new Error(`Playback approval is missing the ${expected.format} production target.`);
    }
    return validateTarget(target, expected, rootDir);
  });

  const durations = validatedTargets.map((target) => target.durationSeconds);
  if (Math.max(...durations) - Math.min(...durations) > 0.5) {
    throw new Error('Rendered production targets must have matching ffprobe durations.');
  }

  return {
    demoId,
    receiptPath: requirement.playbackApprovalPath,
    reviewer: parsed.reviewer,
    reviewedAt: parsed.reviewedAt,
    targetCount: validatedTargets.length,
    formats: validatedTargets.map((target) => target.format).sort(),
  };
}

function main(): void {
  const args = parseCliArgs(process.argv.slice(2));
  const demoId = getRequiredValue(args, 'demo');
  const validation = validateDemoVideoPlaybackApproval(demoId);
  console.log(
    `Validated human playback approval for ${validation.demoId}: ${validation.formats.join(', ')}, reviewed by ${validation.reviewer} at ${validation.reviewedAt}.`,
  );
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
