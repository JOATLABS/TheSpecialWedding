import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import type { DemoCaptureCheckpoint, DemoVideo } from '../../app/data/demoVideos';
import {
  getDemoVideoById,
  getDemoVideoProductionRequirementById,
} from '../../app/data/demoVideoProduction';
import { parseCliArgs, resolveFromRepo } from './cli';

type ManualCaptureBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type ManualCaptureCheckpoint = DemoCaptureCheckpoint & {
  atSeconds: number;
  frameSha256: string;
};

type ManualRuntimeBuildIdentity = {
  origin: string;
  identitySelector: 'meta[name="tsw-app-build-commit"]';
  observedCommit: string;
  verifiedAt: string;
};

export type ManualDemoVideoCaptureReceipt = {
  schemaVersion: 2;
  demoId: string;
  captureMethod: 'manual-visible-browser';
  recordedAt: string;
  appBuildCommit: string;
  runtimeBuildIdentity: ManualRuntimeBuildIdentity;
  source: {
    artifactPath: string;
    artifactSha256: string;
    byteLength: number;
    width: number;
    height: number;
    durationSeconds: number;
    captureBounds: ManualCaptureBounds;
  };
  operatorAttestation: {
    browserWasVisible: true;
    interactionsWereManual: true;
    scriptedBrowserCaptureWasUsed: false;
    dedicatedChannelTake?: true;
    fullWindowWasVisible: true;
    browserAddressBarWasHidden: true;
    realCustomerDataWasExcluded: true;
    sideEffectsWereTriggered: false;
  };
  checkpoints: ManualCaptureCheckpoint[];
  review: {
    reviewedFrameCount: number;
    rawFrameReview: 'approved';
    publicSafetyReview: 'approved';
  };
};

export type ManualDemoVideoValidation = {
  demoId: string;
  artifactPath: string;
  artifactSha256: string;
  byteLength: number;
  width: number;
  height: number;
  durationSeconds: number;
  checkpointCount: number;
  appBuildCommit: string;
};

export type ManualDemoVideoValidationOptions = {
  allowStagedPublicationChanges?: boolean;
  verifyGitAncestry?: boolean;
};

type VideoProbe = {
  width: number;
  height: number;
  durationSeconds: number;
};

export type ManualRecordingDurationBounds = {
  minimumDuration: number;
  maximumDuration: number;
};

const MANUAL_RECORDING_DURATION_TOLERANCE_SECONDS = 5;

export function assertDedicatedChannelTake(
  demo: Pick<DemoVideo, 'productionChannel'>,
  operatorAttestation: { dedicatedChannelTake?: unknown },
): void {
  if (
    demo.productionChannel === 'social'
    && operatorAttestation.dedicatedChannelTake !== true
  ) {
    throw new Error('operatorAttestation.dedicatedChannelTake must be explicitly true for social footage.');
  }
}

export function getManualRecordingDurationBounds(
  demo: Pick<DemoVideo, 'durationSeconds' | 'productionChannel'>,
): ManualRecordingDurationBounds {
  if (demo.productionChannel === 'social') {
    return {
      minimumDuration: Math.max(
        20,
        demo.durationSeconds - MANUAL_RECORDING_DURATION_TOLERANCE_SECONDS,
      ),
      maximumDuration: Math.min(
        35,
        demo.durationSeconds + MANUAL_RECORDING_DURATION_TOLERANCE_SECONDS,
      ),
    };
  }

  return {
    minimumDuration: Math.max(1, demo.durationSeconds - MANUAL_RECORDING_DURATION_TOLERANCE_SECONDS),
    maximumDuration: demo.durationSeconds + MANUAL_RECORDING_DURATION_TOLERANCE_SECONDS,
  };
}

function assertRecord(value: unknown, label: string): asserts value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} must be a JSON object.`);
  }
}

function readReceipt(receiptPath: string): ManualDemoVideoCaptureReceipt {
  if (!fs.existsSync(receiptPath) || !fs.statSync(receiptPath).isFile()) {
    throw new Error(`Manual capture receipt does not exist: ${receiptPath}`);
  }

  const parsed: unknown = JSON.parse(fs.readFileSync(receiptPath, 'utf8'));
  assertRecord(parsed, 'Manual capture receipt');
  return parsed as ManualDemoVideoCaptureReceipt;
}

function sha256(bytes: Buffer): string {
  return createHash('sha256').update(bytes).digest('hex');
}

export function extractVideoFrameSha256(artifactPath: string, atSeconds: number): string {
  const result = spawnSync(
    'ffmpeg',
    [
      '-v',
      'error',
      '-i',
      artifactPath,
      '-ss',
      atSeconds.toFixed(3),
      '-map',
      '0:v:0',
      '-frames:v',
      '1',
      '-f',
      'image2pipe',
      '-vcodec',
      'png',
      'pipe:1',
    ],
    { maxBuffer: 32 * 1024 * 1024 },
  );

  if (result.error) {
    throw new Error(`ffmpeg could not extract the reviewed frame: ${result.error.message}`);
  }
  if (result.status !== 0 || !Buffer.isBuffer(result.stdout) || result.stdout.length === 0) {
    throw new Error(
      `ffmpeg could not extract the reviewed frame at ${atSeconds.toFixed(3)} seconds.`,
    );
  }

  return sha256(result.stdout);
}

function probeVideo(artifactPath: string): VideoProbe {
  const result = spawnSync(
    'ffprobe',
    [
      '-v',
      'error',
      '-select_streams',
      'v:0',
      '-show_entries',
      'stream=width,height:format=duration',
      '-of',
      'json',
      artifactPath,
    ],
    { encoding: 'utf8', maxBuffer: 1024 * 1024 },
  );

  if (result.error) {
    throw new Error(`ffprobe could not inspect the manual recording: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`ffprobe rejected the manual recording (exit ${result.status ?? 'unknown'}).`);
  }

  const parsed: unknown = JSON.parse(result.stdout);
  assertRecord(parsed, 'ffprobe result');
  const streams = parsed.streams;
  const format = parsed.format;
  if (!Array.isArray(streams) || streams.length === 0) {
    throw new Error('Manual recording does not contain a video stream.');
  }
  assertRecord(streams[0], 'ffprobe video stream');
  assertRecord(format, 'ffprobe format');

  const width = Number(streams[0].width);
  const height = Number(streams[0].height);
  const durationSeconds = Number(format.duration);
  if (![width, height, durationSeconds].every((value) => Number.isFinite(value) && value > 0)) {
    throw new Error('Manual recording has invalid width, height, or duration metadata.');
  }

  return { width, height, durationSeconds };
}

function assertTrue(value: unknown, label: string): void {
  if (value !== true) throw new Error(`${label} must be explicitly true.`);
}

function assertFalse(value: unknown, label: string): void {
  if (value !== false) throw new Error(`${label} must be explicitly false.`);
}

function assertFullWindow(bounds: ManualCaptureBounds, width: number, height: number): void {
  assertRecord(bounds, 'source.captureBounds');
  if (
    bounds.x !== 0
    || bounds.y !== 0
    || bounds.width !== width
    || bounds.height !== height
  ) {
    throw new Error('Manual recording capture bounds must preserve the entire product window.');
  }
}

function parseApplicationRoute(route: string): URL | undefined {
  if (!route.startsWith('/') || route.startsWith('//') || route.includes('://') || route.includes('#')) {
    return undefined;
  }

  try {
    const parsed = new URL(route, 'https://capture.invalid');
    return `${parsed.pathname}${parsed.search}` === route ? parsed : undefined;
  } catch {
    return undefined;
  }
}

function routePattern(pathname: string): RegExp {
  const escaped = pathname
    .split('/')
    .map((segment) => (/^\[[^\]]+\]$/.test(segment) ? '[^/]+' : segment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    .join('/');
  return new RegExp(`^${escaped}/?$`);
}

function routeMatches(actualRoute: string, plannedRoute: string): boolean {
  const actual = parseApplicationRoute(actualRoute);
  const planned = parseApplicationRoute(plannedRoute);
  if (!actual || !planned) return false;

  return routePattern(planned.pathname).test(actual.pathname)
    && actual.search === planned.search;
}

export function validateManualCaptureCheckpoints(
  checkpoints: readonly ManualCaptureCheckpoint[],
  demo: DemoVideo,
): void {
  const required = demo.captureCheckpoints ?? [];
  if (demo.priority === 'phase-one' && required.length < 3) {
    throw new Error(`${demo.id} must define at least 3 exact capture checkpoints.`);
  }

  const requiredLabels = new Set<string>();
  for (const [index, checkpoint] of required.entries()) {
    const label = checkpoint.label.trim();
    const action = checkpoint.action.trim();
    const visibleResult = checkpoint.visibleResult.trim();
    const looksGeneric = /^(?:checkpoint|generic|page|placeholder)\b/i.test(label)
      || /^(?:open|inspect|show|view) (?:a|the) (?:application )?page[.!]?$/i.test(action)
      || /^(?:a|the) (?:application )?page is visible[.!]?$/i.test(visibleResult);
    if (label.length < 4 || action.length < 12 || visibleResult.length < 12 || looksGeneric) {
      throw new Error(
        `${demo.id} captureCheckpoints[${index}] must define a meaningful label, action, and visible result.`,
      );
    }

    const normalizedLabel = label.toLocaleLowerCase('en-US');
    if (requiredLabels.has(normalizedLabel)) {
      throw new Error(`${demo.id} capture checkpoint labels must be unique: ${label}.`);
    }
    requiredLabels.add(normalizedLabel);

    const parsedRoute = parseApplicationRoute(checkpoint.route.trim());
    if (!parsedRoute || /\[[^\]]+\]/.test(parsedRoute.pathname)) {
      throw new Error(
        `${demo.id} captureCheckpoints[${index}].route must be an exact resolved application route.`,
      );
    }
    if (!demo.routePlan.some((plannedRoute) => routeMatches(checkpoint.route.trim(), plannedRoute))) {
      throw new Error(
        `${demo.id} capture checkpoint route ${checkpoint.route} is not part of its route plan.`,
      );
    }
  }

  const minimumCheckpoints = Math.max(demo.priority === 'hero' ? 6 : 1, required.length);
  if (checkpoints.length < minimumCheckpoints) {
    throw new Error(`${demo.id} requires at least ${minimumCheckpoints} product checkpoints.`);
  }

  const labels = new Set<string>();
  let previousAtSeconds = -1;
  for (const [index, checkpoint] of checkpoints.entries()) {
    assertRecord(checkpoint, `checkpoints[${index}]`);
    const label = typeof checkpoint.label === 'string' ? checkpoint.label.trim() : '';
    const route = typeof checkpoint.route === 'string' ? checkpoint.route.trim() : '';
    const action = typeof checkpoint.action === 'string' ? checkpoint.action.trim() : '';
    const visibleResult = typeof checkpoint.visibleResult === 'string'
      ? checkpoint.visibleResult.trim()
      : '';
    if (!label) {
      throw new Error(`checkpoints[${index}].label is required.`);
    }
    const normalizedLabel = label.toLocaleLowerCase('en-US');
    if (labels.has(normalizedLabel)) {
      throw new Error(`Manual capture checkpoint labels must be unique: ${label}.`);
    }
    labels.add(normalizedLabel);
    const parsedRoute = parseApplicationRoute(route);
    if (!parsedRoute) {
      throw new Error(
        `checkpoints[${index}].route must be an application-relative route with only its planned query.`,
      );
    }
    let decodedPathname: string;
    try {
      decodedPathname = decodeURIComponent(parsedRoute.pathname);
    } catch {
      throw new Error(`checkpoints[${index}].route must be a valid application route.`);
    }
    if (
      /[\[\]\\\s?#:]/.test(decodedPathname)
      || decodedPathname.includes('//')
      || decodedPathname.split('/').some((segment) => segment === '.' || segment === '..')
    ) {
      throw new Error(`checkpoints[${index}].route must be a resolved application pathname.`);
    }
    if (!demo.routePlan.some((plannedRoute) => routeMatches(route, plannedRoute))) {
      throw new Error(`Checkpoint route ${route} is not part of ${demo.id}'s route plan.`);
    }
    if (!action) {
      throw new Error(`checkpoints[${index}].action is required.`);
    }
    if (!visibleResult) {
      throw new Error(`checkpoints[${index}].visibleResult is required.`);
    }
    if (!Number.isFinite(checkpoint.atSeconds) || checkpoint.atSeconds < 0) {
      throw new Error(`checkpoints[${index}].atSeconds must be a non-negative number.`);
    }
    if (checkpoint.atSeconds <= previousAtSeconds) {
      throw new Error('Manual capture checkpoint atSeconds values must be strictly increasing.');
    }
    previousAtSeconds = checkpoint.atSeconds;
    if (!/^[0-9a-f]{64}$/i.test(checkpoint.frameSha256)) {
      throw new Error(`checkpoints[${index}].frameSha256 must be a full SHA-256 checksum.`);
    }
  }

  let searchFrom = 0;
  for (const requiredCheckpoint of required) {
    const foundAt = checkpoints.findIndex(
      (checkpoint, index) => index >= searchFrom
        && checkpoint.label.trim() === requiredCheckpoint.label
        && routeMatches(checkpoint.route, requiredCheckpoint.route)
        && checkpoint.action.trim() === requiredCheckpoint.action
        && checkpoint.visibleResult.trim() === requiredCheckpoint.visibleResult,
    );
    if (foundAt === -1) {
      throw new Error(
        `Manual capture is missing the ordered checkpoint ${requiredCheckpoint.label} (${requiredCheckpoint.route}).`,
      );
    }
    searchFrom = foundAt + 1;
  }
}

function gitOutput(args: readonly string[]): string {
  const result = spawnSync('git', args, {
    cwd: resolveFromRepo(),
    encoding: 'utf8',
    maxBuffer: 1024 * 1024,
  });
  if (result.error || result.status !== 0) {
    throw new Error(`Git could not verify the recording build for the manual receipt.`);
  }
  return result.stdout.trim();
}

function gitExitStatus(args: readonly string[]): number {
  const result = spawnSync('git', args, {
    cwd: resolveFromRepo(),
    encoding: 'utf8',
    maxBuffer: 1024 * 1024,
  });
  if (result.error || result.status === null) {
    throw new Error('Git could not verify the recording build for the manual receipt.');
  }
  return result.status;
}

function assertAvailableCleanRecordingBuild(
  receiptCommit: string,
  options: ManualDemoVideoValidationOptions,
): string {
  gitOutput(['cat-file', '-e', `${receiptCommit}^{commit}`]);
  const head = gitOutput(['rev-parse', 'HEAD']);
  if (
    receiptCommit !== head
    && gitExitStatus(['merge-base', '--is-ancestor', receiptCommit, head]) !== 0
  ) {
    throw new Error('Manual recording commit must be an ancestor of current HEAD.');
  }
  if (options.allowStagedPublicationChanges) {
    const unstagedChanges = gitOutput(['diff', '--name-only']);
    const untrackedChanges = gitOutput(['ls-files', '--others', '--exclude-standard']);
    if (unstagedChanges || untrackedChanges) {
      throw new Error(
        'Staged publication validation rejects unstaged or untracked changes.',
      );
    }
  } else {
    const worktreeChanges = gitOutput(['status', '--porcelain', '--untracked-files=all']);
    if (worktreeChanges) {
      throw new Error('Manual recording validation requires a clean worktree.');
    }
  }
  return receiptCommit;
}

function assertIsoDateTime(value: string, label: string): number {
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)
    || !Number.isFinite(Date.parse(value))
  ) {
    throw new Error(`${label} must be an ISO date-time.`);
  }

  return Date.parse(value);
}

function assertRuntimeBuildIdentity(receipt: ManualDemoVideoCaptureReceipt): void {
  assertRecord(receipt.runtimeBuildIdentity, 'runtimeBuildIdentity');
  const runtime = receipt.runtimeBuildIdentity;
  if (runtime.identitySelector !== 'meta[name="tsw-app-build-commit"]') {
    throw new Error('Runtime build identity must be read from the public app-build meta marker.');
  }
  if (runtime.observedCommit !== receipt.appBuildCommit) {
    throw new Error('The served runtime build commit does not match the recording commit.');
  }

  let origin: URL;
  try {
    origin = new URL(runtime.origin);
  } catch {
    throw new Error('runtimeBuildIdentity.origin must be a valid HTTP(S) origin.');
  }
  if (
    !['http:', 'https:'].includes(origin.protocol)
    || origin.username
    || origin.password
    || origin.origin !== runtime.origin
  ) {
    throw new Error('runtimeBuildIdentity.origin must be an HTTP(S) origin without credentials or a path.');
  }
  if (!['localhost', '127.0.0.1', '[::1]'].includes(origin.hostname)) {
    throw new Error('runtimeBuildIdentity.origin must identify the isolated local capture server.');
  }

  const verifiedAt = assertIsoDateTime(runtime.verifiedAt, 'runtimeBuildIdentity.verifiedAt');
  const recordedAt = Date.parse(receipt.recordedAt);
  if (verifiedAt > Date.now() + 5 * 60 * 1000) {
    throw new Error('runtimeBuildIdentity.verifiedAt cannot be in the future.');
  }
  if (Math.abs(recordedAt - verifiedAt) > 24 * 60 * 60 * 1000) {
    throw new Error('Runtime build identity must be verified within 24 hours of the recording.');
  }

  const environmentCommit = process.env.NEXT_PUBLIC_APP_BUILD_COMMIT;
  if (environmentCommit && environmentCommit !== runtime.observedCommit) {
    throw new Error('NEXT_PUBLIC_APP_BUILD_COMMIT does not match the served build in the receipt.');
  }
}

function assertReceiptContract(receipt: ManualDemoVideoCaptureReceipt): void {
  if (receipt.schemaVersion !== 2) {
    throw new Error('Manual capture receipt schemaVersion must be 2.');
  }
  if (receipt.captureMethod !== 'manual-visible-browser') {
    throw new Error('Demo video must be captured in a manually driven visible browser.');
  }
  const recordedAt = assertIsoDateTime(receipt.recordedAt, 'Manual capture receipt recordedAt');
  if (recordedAt > Date.now() + 5 * 60 * 1000) {
    throw new Error('Manual capture receipt recordedAt cannot be in the future.');
  }
  if (!/^[0-9a-f]{40}$/i.test(receipt.appBuildCommit)) {
    throw new Error('Manual capture receipt appBuildCommit must be a full Git commit hash.');
  }
  assertRuntimeBuildIdentity(receipt);

  assertRecord(receipt.source, 'source');
  assertRecord(receipt.operatorAttestation, 'operatorAttestation');
  assertTrue(receipt.operatorAttestation.browserWasVisible, 'operatorAttestation.browserWasVisible');
  assertTrue(receipt.operatorAttestation.interactionsWereManual, 'operatorAttestation.interactionsWereManual');
  assertFalse(
    receipt.operatorAttestation.scriptedBrowserCaptureWasUsed,
    'operatorAttestation.scriptedBrowserCaptureWasUsed',
  );
  assertTrue(receipt.operatorAttestation.fullWindowWasVisible, 'operatorAttestation.fullWindowWasVisible');
  assertTrue(
    receipt.operatorAttestation.browserAddressBarWasHidden,
    'operatorAttestation.browserAddressBarWasHidden',
  );
  assertTrue(
    receipt.operatorAttestation.realCustomerDataWasExcluded,
    'operatorAttestation.realCustomerDataWasExcluded',
  );
  assertFalse(
    receipt.operatorAttestation.sideEffectsWereTriggered,
    'operatorAttestation.sideEffectsWereTriggered',
  );

  if (!Array.isArray(receipt.checkpoints) || receipt.checkpoints.length === 0) {
    throw new Error('Manual capture receipt must list visibly reviewed product checkpoints.');
  }

  assertRecord(receipt.review, 'review');
  if (!Number.isInteger(receipt.review.reviewedFrameCount) || receipt.review.reviewedFrameCount < 3) {
    throw new Error('Manual capture receipt must confirm review of at least three frames.');
  }
  if (receipt.review.rawFrameReview !== 'approved') {
    throw new Error('Manual recording requires approved raw-frame review.');
  }
  if (receipt.review.publicSafetyReview !== 'approved') {
    throw new Error('Manual recording requires approved public-safety review.');
  }
}

function validateCheckpointFrames(
  checkpoints: readonly ManualCaptureCheckpoint[],
  artifactPath: string,
  durationSeconds: number,
): void {
  for (const [index, checkpoint] of checkpoints.entries()) {
    if (checkpoint.atSeconds >= durationSeconds) {
      throw new Error(
        `checkpoints[${index}].atSeconds must be before the end of the manual recording.`,
      );
    }

    const extractedFrameSha256 = extractVideoFrameSha256(artifactPath, checkpoint.atSeconds);
    if (extractedFrameSha256 !== checkpoint.frameSha256.toLowerCase()) {
      throw new Error(
        `Reviewed frame checksum does not match the MP4 at ${checkpoint.atSeconds.toFixed(3)} seconds (${checkpoint.label}).`,
      );
    }
  }
}

export function validateManualDemoVideo(
  receiptPath = resolveFromRepo(
    'output',
    'demo-videos',
    'receipts',
    'planner-command-center-walkthrough.json',
  ),
  options: ManualDemoVideoValidationOptions = {},
): ManualDemoVideoValidation {
  const receipt = readReceipt(receiptPath);
  assertReceiptContract(receipt);

  const demo = getDemoVideoById(receipt.demoId);
  const requirement = getDemoVideoProductionRequirementById(receipt.demoId);
  if (!demo || !requirement) {
    throw new Error(`Unknown demo id in manual capture receipt: ${receipt.demoId}`);
  }
  assertDedicatedChannelTake(demo, receipt.operatorAttestation);
  validateManualCaptureCheckpoints(receipt.checkpoints, demo);
  if (receipt.review.reviewedFrameCount < receipt.checkpoints.length) {
    throw new Error('Manual capture review must include at least one frame from every product checkpoint.');
  }

  const appBuildCommit = options.verifyGitAncestry === false
    ? receipt.appBuildCommit
    : assertAvailableCleanRecordingBuild(receipt.appBuildCommit, options);
  const expectedArtifactPath = resolveFromRepo(requirement.rawRecordingPath);
  const artifactPath = resolveFromRepo(receipt.source.artifactPath);
  if (artifactPath !== expectedArtifactPath) {
    throw new Error(`Manual recording must use ${requirement.rawRecordingPath} for ${receipt.demoId}.`);
  }
  if (!fs.existsSync(artifactPath) || !fs.statSync(artifactPath).isFile()) {
    throw new Error(`Manual recording does not exist: ${artifactPath}`);
  }
  if (fs.lstatSync(artifactPath).isSymbolicLink()) {
    throw new Error('Manual recording must be a direct file, not a symbolic link.');
  }

  const bytes = fs.readFileSync(artifactPath);
  const stat = fs.statSync(artifactPath);
  const artifactSha256 = sha256(bytes);
  if (receipt.source.artifactSha256 !== artifactSha256) {
    throw new Error('Manual recording checksum does not match its capture receipt.');
  }
  if (receipt.source.byteLength !== stat.size) {
    throw new Error('Manual recording byte length does not match its capture receipt.');
  }

  const probe = probeVideo(artifactPath);
  if (receipt.source.width !== probe.width || receipt.source.height !== probe.height) {
    throw new Error('Manual recording dimensions do not match its capture receipt.');
  }
  if (probe.width !== 1440 || probe.height !== 900) {
    throw new Error('Manual recording must preserve the approved 1440x900 full-window capture.');
  }
  if (Math.abs(receipt.source.durationSeconds - probe.durationSeconds) > 0.25) {
    throw new Error('Manual recording duration does not match its capture receipt.');
  }

  const { minimumDuration, maximumDuration } = getManualRecordingDurationBounds(demo);
  if (probe.durationSeconds < minimumDuration || probe.durationSeconds > maximumDuration) {
    throw new Error(
      `Manual recording duration must stay within ${minimumDuration}-${maximumDuration} seconds for ${receipt.demoId}.`,
    );
  }
  assertFullWindow(receipt.source.captureBounds, probe.width, probe.height);
  validateCheckpointFrames(receipt.checkpoints, artifactPath, probe.durationSeconds);

  return {
    demoId: receipt.demoId,
    artifactPath: path.relative(resolveFromRepo(), artifactPath),
    artifactSha256,
    byteLength: stat.size,
    width: probe.width,
    height: probe.height,
    durationSeconds: probe.durationSeconds,
    checkpointCount: receipt.checkpoints.length,
    appBuildCommit,
  };
}

function main(): void {
  const args = parseCliArgs(process.argv.slice(2));
  const receiptPath = args.values.get('receipt')
    ? path.resolve(args.values.get('receipt')!)
    : resolveFromRepo(
        'output',
        'demo-videos',
        'receipts',
        'planner-command-center-walkthrough.json',
      );
  const validation = validateManualDemoVideo(receiptPath);
  console.log(
    `Validated manually driven ${validation.demoId} recording: ${validation.width}x${validation.height}, ${validation.durationSeconds.toFixed(2)}s, ${validation.checkpointCount} checkpoints, commit ${validation.appBuildCommit.slice(0, 12)}.`,
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
