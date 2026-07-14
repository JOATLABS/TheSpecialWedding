import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

import {
  MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
  MARKETING_CAPTURE_SAFETY_ASSERTIONS,
  MARKETING_CAPTURE_SESSIONS,
  MARKETING_CAPTURE_RUNTIME_ORIGIN,
  MARKETING_CAPTURE_VIEWPORT,
  MARKETING_CAPTURE_MANIFEST,
  isMarketingCaptureAssetApproved,
  type MarketingCaptureEntry,
} from '../../app/data/marketingCaptureManifest';
import { resolveFromRepo } from './cli';

const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
const VERIFIED_CAPTURE_BUILDS = new Set<string>();
export const MINIMUM_PUBLISHED_PRODUCT_PROOF_COUNT = 17;

export type ManualProductImageValidation = {
  featureId: string;
  artifactPath: string;
  width: number;
  height: number;
  checksum: string;
};

function sha256(bytes: Buffer): string {
  return createHash('sha256').update(bytes).digest('hex');
}

export function assertCaptureBuildAncestry(featureId: string, build: string): void {
  if (VERIFIED_CAPTURE_BUILDS.has(build)) {
    return;
  }

  try {
    execFileSync('git', ['cat-file', '-e', `${build}^{commit}`], {
      cwd: resolveFromRepo(),
      stdio: 'ignore',
    });
  } catch {
    throw new Error(`${featureId} capture build does not exist in this Git repository.`);
  }

  try {
    execFileSync('git', ['merge-base', '--is-ancestor', build, 'HEAD'], {
      cwd: resolveFromRepo(),
      stdio: 'ignore',
    });
  } catch {
    throw new Error(`${featureId} capture build must be an ancestor of current HEAD.`);
  }

  VERIFIED_CAPTURE_BUILDS.add(build);
}

function artifactPathFromPublicUrl(publicUrl: string): string {
  const pathname = publicUrl.split('?', 1)[0];
  if (!pathname.startsWith('/') || !pathname.toLowerCase().endsWith('.png')) {
    throw new Error(`Marketing image path must be an absolute PNG public path: ${publicUrl}`);
  }

  const publicRoot = resolveFromRepo('public');
  const artifactPath = path.resolve(publicRoot, `.${pathname}`);
  if (!artifactPath.startsWith(`${publicRoot}${path.sep}`)) {
    throw new Error(`Marketing image path escapes the public directory: ${publicUrl}`);
  }

  return artifactPath;
}

async function decodePngDimensions(
  bytes: Buffer,
  artifactPath: string,
): Promise<{ width: number; height: number }> {
  if (bytes.byteLength < 24 || !bytes.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)) {
    throw new Error(`Marketing image is not a valid PNG file: ${artifactPath}`);
  }

  const ihdrChunkType = bytes.subarray(12, 16).toString('ascii');
  if (ihdrChunkType !== 'IHDR') {
    throw new Error(`Marketing image does not begin with a PNG IHDR chunk: ${artifactPath}`);
  }

  const headerWidth = bytes.readUInt32BE(16);
  const headerHeight = bytes.readUInt32BE(20);

  try {
    const metadata = await sharp(bytes, { failOn: 'warning' }).metadata();
    if (metadata.format !== 'png') {
      throw new Error('decoded format is not PNG');
    }

    const { info } = await sharp(bytes, { failOn: 'warning' })
      .raw()
      .toBuffer({ resolveWithObject: true });
    if (info.width !== headerWidth || info.height !== headerHeight) {
      throw new Error('decoded dimensions do not match the PNG header');
    }

    return { width: info.width, height: info.height };
  } catch {
    throw new Error(`Marketing image cannot be fully decoded as PNG: ${artifactPath}`);
  }
}

export function assertManualFullWindowContract(
  featureId: string,
  entry: MarketingCaptureEntry,
): void {
  const { source } = entry;
  if (entry.status !== 'approved') {
    throw new Error(`${featureId} has not been approved after manual visual review.`);
  }
  if (source.captureMethod !== 'manual-visible-browser') {
    throw new Error(`${featureId} must be captured manually in a visible browser.`);
  }
  const receipt = source.reviewReceipt;
  if (!receipt) {
    throw new Error(`${featureId} requires an explicit per-image manual review receipt.`);
  }
  if (entry.featureId !== featureId || receipt.featureId !== featureId) {
    throw new Error(`${featureId} receipt must identify the same capture feature.`);
  }
  if (receipt.schemaVersion !== 1) {
    throw new Error(`${featureId} receipt uses an unsupported schema version.`);
  }
  if (!/^[0-9a-f]{40}$/.test(entry.build)) {
    throw new Error(`${featureId} must identify the exact captured Git build.`);
  }
  if (receipt.appBuildCommit !== entry.build) {
    throw new Error(`${featureId} receipt must match the exact captured Git build.`);
  }
  if (receipt.artifactSha256 !== source.checksum) {
    throw new Error(`${featureId} receipt must match the captured PNG checksum.`);
  }
  if (!/^[0-9a-f]{64}$/.test(source.checksum)) {
    throw new Error(`${featureId} must identify the captured PNG with a full SHA-256 checksum.`);
  }
  const capturedAt = Date.parse(receipt.capturedAt);
  const reviewedAt = Date.parse(receipt.reviewedAt);
  if (
    !Number.isFinite(capturedAt)
    || !Number.isFinite(reviewedAt)
    || reviewedAt < capturedAt
    || new Date(capturedAt).toISOString() !== receipt.capturedAt
    || new Date(reviewedAt).toISOString() !== receipt.reviewedAt
    || !receipt.reviewer.trim()
  ) {
    throw new Error(`${featureId} receipt must record a valid capture and human review.`);
  }
  const runtime = receipt.runtimeBuildIdentity;
  if (!runtime) {
    throw new Error(`${featureId} receipt must record the served runtime build identity.`);
  }
  if (
    runtime.origin !== MARKETING_CAPTURE_RUNTIME_ORIGIN
    || runtime.identitySelector !== MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR
    || runtime.observedCommit !== entry.build
  ) {
    throw new Error(`${featureId} receipt runtime identity must match the isolated capture build.`);
  }
  const runtimeVerifiedAt = Date.parse(runtime.verifiedAt);
  if (
    !Number.isFinite(runtimeVerifiedAt)
    || new Date(runtimeVerifiedAt).toISOString() !== runtime.verifiedAt
    || runtimeVerifiedAt > capturedAt
    || capturedAt - runtimeVerifiedAt > 24 * 60 * 60 * 1000
  ) {
    throw new Error(`${featureId} runtime build identity must be verified within 24 hours before capture.`);
  }
  if (receipt.browser !== 'Google Chrome' || !receipt.browserWasVisible) {
    throw new Error(`${featureId} must use a visible Google Chrome window.`);
  }
  if (!receipt.interactionsWereManual) {
    throw new Error(`${featureId} frontend interactions must be driven manually.`);
  }
  if (receipt.scriptedBrowserCaptureWasUsed) {
    throw new Error(`${featureId} scripted browser capture must be false.`);
  }
  if (receipt.pageZoomPercent !== 100) {
    throw new Error(`${featureId} browser zoom must be exactly 100%.`);
  }
  if (receipt.viewportMode !== 'Responsive') {
    throw new Error(`${featureId} must use Chrome DevTools Responsive viewport mode.`);
  }
  if (receipt.devicePixelRatio !== 1) {
    throw new Error(`${featureId} device pixel ratio must be 1.`);
  }
  if (
    receipt.captureCommand !== 'Capture screenshot'
    || receipt.fullSizeScreenshotWasUsed
  ) {
    throw new Error(`${featureId} must use the Chrome DevTools Capture screenshot command.`);
  }
  if (!receipt.originalPngReviewed) {
    throw new Error(`${featureId} must require review of the original PNG.`);
  }
  if (receipt.postCaptureTransformsApplied) {
    throw new Error(`${featureId} must not allow post-capture crop, resize, or stitching.`);
  }
  if (!MARKETING_CAPTURE_SESSIONS.includes(entry.requiredSession)) {
    throw new Error(`${featureId} must declare the browser session required for capture.`);
  }
  if (!entry.sourceRoute.startsWith('/') || /\[[^\]]+\]/.test(entry.sourceRoute)) {
    throw new Error(`${featureId} must declare a resolved application route for manual capture.`);
  }
  if (!entry.stableState.selector.trim() || !entry.stableState.expectedVisibleText.trim()) {
    throw new Error(`${featureId} must declare a populated stable-state selector and visible text.`);
  }
  if (entry.stableState.selector !== source.focalLocator) {
    throw new Error(`${featureId} stable-state selector must match the captured focal locator.`);
  }
  if (
    entry.viewport.width !== MARKETING_CAPTURE_VIEWPORT.width
    || entry.viewport.height !== MARKETING_CAPTURE_VIEWPORT.height
    || entry.viewport.width !== source.width
    || entry.viewport.height !== source.height
  ) {
    throw new Error(`${featureId} viewport must match the full-window source dimensions.`);
  }
  if (
    entry.safetyAssertions.some((item) => !item.trim())
    || MARKETING_CAPTURE_SAFETY_ASSERTIONS.some(
      (requiredAssertion) => !entry.safetyAssertions.includes(requiredAssertion),
    )
  ) {
    throw new Error(`${featureId} must declare the manual public-safety review assertions.`);
  }
  if (source.framing !== 'full-window') {
    throw new Error(`${featureId} must preserve the full product window.`);
  }
  if (
    source.captureBounds.x !== 0
    || source.captureBounds.y !== 0
    || source.captureBounds.width !== source.width
    || source.captureBounds.height !== source.height
  ) {
    throw new Error(`${featureId} capture bounds must cover the entire source image.`);
  }

  for (const [target, render] of Object.entries(entry.renders)) {
    if (render.fit !== 'contain' || render.zoom !== false || render.frameAspectRatio !== '16:10') {
      throw new Error(`${featureId}/${target} must render contained at 16:10 without zoom.`);
    }
  }

  if (!isMarketingCaptureAssetApproved({
    ...entry.source,
    featureId: entry.featureId,
    status: entry.status,
    build: entry.build,
    render: entry.renders.features,
  })) {
    throw new Error(`${featureId} does not satisfy the browser publication receipt gate.`);
  }
}

export async function validateApprovedProductImage(
  featureId: string,
  entry: MarketingCaptureEntry,
  options: { verifyGitAncestry?: boolean } = {},
): Promise<ManualProductImageValidation> {
  assertManualFullWindowContract(featureId, entry);
  if (options.verifyGitAncestry) {
    assertCaptureBuildAncestry(featureId, entry.build);
  }

  const artifactPath = artifactPathFromPublicUrl(entry.source.path);
  if (!fs.existsSync(artifactPath) || !fs.statSync(artifactPath).isFile()) {
    throw new Error(`Marketing PNG is missing for ${featureId}: ${artifactPath}`);
  }

  const bytes = fs.readFileSync(artifactPath);
  const dimensions = await decodePngDimensions(bytes, artifactPath);
  if (dimensions.width !== entry.source.width || dimensions.height !== entry.source.height) {
    throw new Error(
      `${featureId} PNG dimensions ${dimensions.width}x${dimensions.height} do not match manifest ${entry.source.width}x${entry.source.height}.`,
    );
  }

  const checksum = sha256(bytes);
  if (checksum !== entry.source.checksum) {
    throw new Error(`${featureId} PNG checksum does not match the marketing capture manifest.`);
  }

  return {
    featureId,
    artifactPath: path.relative(resolveFromRepo(), artifactPath),
    width: dimensions.width,
    height: dimensions.height,
    checksum,
  };
}

export async function validatePublishedProductImages(
  options: { verifyGitAncestry?: boolean } = {},
): Promise<ManualProductImageValidation[]> {
  const approvedEntries = Object.entries(MARKETING_CAPTURE_MANIFEST)
    .filter(([, entry]) => entry.status === 'approved');
  if (approvedEntries.length < MINIMUM_PUBLISHED_PRODUCT_PROOF_COUNT) {
    throw new Error(
      `Marketing publication requires at least ${MINIMUM_PUBLISHED_PRODUCT_PROOF_COUNT} approved product proofs; found ${approvedEntries.length}.`,
    );
  }
  return Promise.all(approvedEntries
    .map(([featureId, entry]) => validateApprovedProductImage(featureId, entry, options)));
}

export async function validateManualProductImages(
  options: { verifyGitAncestry?: boolean } = {},
): Promise<ManualProductImageValidation[]> {
  return Promise.all(Object.entries(MARKETING_CAPTURE_MANIFEST)
    .map(([featureId, entry]) => validateApprovedProductImage(featureId, entry, options)));
}

async function main(): Promise<void> {
  const args = new Set(process.argv.slice(2));
  const supportedArgs = new Set(['--published', '--verify-git-ancestry']);
  const unsupportedArgs = [...args].filter((arg) => !supportedArgs.has(arg));
  if (unsupportedArgs.length > 0) {
    throw new Error(`Unsupported manual product-image validator argument: ${unsupportedArgs.join(', ')}`);
  }

  const publishedOnly = args.has('--published');
  const verifyGitAncestry = args.has('--verify-git-ancestry');
  const options = { verifyGitAncestry };
  const validations = publishedOnly
    ? await validatePublishedProductImages(options)
    : await validateManualProductImages(options);
  const scope = publishedOnly ? 'published' : 'manually captured full-window';
  const ancestryScope = verifyGitAncestry ? ' with Git ancestry' : '';
  console.log(`Validated ${validations.length} ${scope} marketing PNGs${ancestryScope}.`);
}

const isMainModule = process.argv[1]
  ? path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))
  : false;

if (isMainModule) {
  void main().catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
