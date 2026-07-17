/**
 * One-shot maintenance script: migrate manual-capture receipts from the brittle
 * byte-exact `frameSha256` checkpoint field to the version-stable
 * `framePerceptualHash` (dHash). It computes each checkpoint's perceptual hash
 * from the actual MP4 using the same extractor the validator uses, so the
 * regenerated receipts are self-consistent and pass on any ffmpeg build.
 *
 * Usage: tsx scripts/demo-videos/regenerate-checkpoint-perceptual-hashes.ts
 */
import fs from 'node:fs';
import path from 'node:path';

import { resolveFromRepo } from './cli';
import { extractVideoFramePerceptualHash } from './validate-manual-demo-video';

const RECEIPTS_DIR = resolveFromRepo('output', 'demo-videos', 'receipts');

function main(): void {
  const files = fs
    .readdirSync(RECEIPTS_DIR)
    .filter((name) => name.endsWith('.json'))
    .sort();

  if (files.length === 0) {
    throw new Error(`No receipts found under ${RECEIPTS_DIR}`);
  }

  let updated = 0;
  for (const file of files) {
    const receiptPath = path.join(RECEIPTS_DIR, file);
    const receipt = JSON.parse(fs.readFileSync(receiptPath, 'utf8')) as Record<string, unknown>;
    const source = receipt.source as { artifactPath?: string } | undefined;
    const artifactPath = source?.artifactPath;
    if (!artifactPath) {
      throw new Error(`${file}: missing source.artifactPath`);
    }
    const resolvedArtifact = resolveFromRepo(artifactPath);
    const checkpoints = receipt.checkpoints;
    if (!Array.isArray(checkpoints)) {
      throw new Error(`${file}: checkpoints missing or not an array`);
    }

    for (const checkpoint of checkpoints as Array<Record<string, unknown>>) {
      const atSeconds = Number(checkpoint.atSeconds);
      if (!Number.isFinite(atSeconds)) {
        throw new Error(`${file}: checkpoint missing numeric atSeconds`);
      }
      const perceptualHash = extractVideoFramePerceptualHash(resolvedArtifact, atSeconds);
      checkpoint.framePerceptualHash = perceptualHash;
      delete checkpoint.frameSha256;
    }

    fs.writeFileSync(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
    updated += 1;
    process.stdout.write(`${file}: ${(checkpoints as unknown[]).length} checkpoints rehashed\n`);
  }

  process.stdout.write(`\nRegenerated perceptual hashes for ${updated} receipts.\n`);
}

main();
