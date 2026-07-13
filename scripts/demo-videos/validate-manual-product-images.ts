import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  MARKETING_CAPTURE_MANIFEST,
  type MarketingCaptureEntry,
} from '../../app/data/marketingCaptureManifest';
import { resolveFromRepo } from './cli';

const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

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

function readPngDimensions(bytes: Buffer, artifactPath: string): { width: number; height: number } {
  if (bytes.byteLength < 24 || !bytes.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)) {
    throw new Error(`Marketing image is not a valid PNG file: ${artifactPath}`);
  }

  const ihdrChunkType = bytes.subarray(12, 16).toString('ascii');
  if (ihdrChunkType !== 'IHDR') {
    throw new Error(`Marketing image does not begin with a PNG IHDR chunk: ${artifactPath}`);
  }

  return {
    width: bytes.readUInt32BE(16),
    height: bytes.readUInt32BE(20),
  };
}

function assertManualFullWindowContract(featureId: string, entry: MarketingCaptureEntry): void {
  const { source } = entry;
  if (entry.status !== 'approved') {
    throw new Error(`${featureId} has not been approved after manual visual review.`);
  }
  if (source.captureMethod !== 'manual-in-app-browser') {
    throw new Error(`${featureId} must be captured manually in the in-app browser.`);
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
}

export function validateManualProductImages(): ManualProductImageValidation[] {
  const validations: ManualProductImageValidation[] = [];

  for (const [featureId, entry] of Object.entries(MARKETING_CAPTURE_MANIFEST)) {
    assertManualFullWindowContract(featureId, entry);

    const artifactPath = artifactPathFromPublicUrl(entry.source.path);
    if (!fs.existsSync(artifactPath) || !fs.statSync(artifactPath).isFile()) {
      throw new Error(`Marketing PNG is missing for ${featureId}: ${artifactPath}`);
    }

    const bytes = fs.readFileSync(artifactPath);
    const dimensions = readPngDimensions(bytes, artifactPath);
    if (dimensions.width !== entry.source.width || dimensions.height !== entry.source.height) {
      throw new Error(
        `${featureId} PNG dimensions ${dimensions.width}x${dimensions.height} do not match manifest ${entry.source.width}x${entry.source.height}.`,
      );
    }

    const checksum = sha256(bytes);
    if (checksum !== entry.source.checksum) {
      throw new Error(`${featureId} PNG checksum does not match the marketing capture manifest.`);
    }

    validations.push({
      featureId,
      artifactPath: path.relative(resolveFromRepo(), artifactPath),
      width: dimensions.width,
      height: dimensions.height,
      checksum,
    });
  }

  return validations;
}

function main(): void {
  const validations = validateManualProductImages();
  console.log(`Validated ${validations.length} manually captured full-window marketing PNGs.`);
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
