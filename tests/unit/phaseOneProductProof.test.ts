import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';
import { MARKETING_CAPTURE_MANIFEST } from '../../app/data/marketingCaptureManifest';
import { MARKETING_FEATURES } from '../../app/data/marketingFeatures';

const ROOT = process.cwd();

function source(relativePath: string): string {
  return readFileSync(path.join(ROOT, relativePath), 'utf8');
}

describe('Phase 1 product-proof marketing composition', () => {
  it('uses one populated hero proof instead of the stale rotating screenshot stack', () => {
    const page = source('app/page.tsx');

    assert.match(page, /PhaseOneHeroProof/);
    assert.doesNotMatch(page, /StackStage/);
    assert.match(page, /built specifically for wedding planners/i);
  });

  it('defines exactly four outcome-led stories for the homepage and features page', () => {
    const proofDataPath = path.join(ROOT, 'app/data/phaseOneProductProof.ts');
    assert.equal(existsSync(proofDataPath), true, 'Phase 1 product-proof data module is missing');

    const proofData = source('app/data/phaseOneProductProof.ts');
    for (const outcome of [
      'Connection Over Tools',
      'Disorganization Tax',
      'Couple Experience',
      'Built for Planners',
    ]) {
      assert.match(proofData, new RegExp(outcome, 'i'));
    }
    assert.match(proofData, /satisfies readonly \[/);
  });

  it('uses intentional product-proof assets for every marketed capability', () => {
    const marketingFeatures = source('app/data/marketingFeatures.ts');

    assert.doesNotMatch(marketingFeatures, /image: '\/(?:dashboard|calendar_management|couple_portal_dashboard|seating|reminders)\.webp'/);
    assert.match(marketingFeatures, /featureCapturePath/);

    for (const feature of MARKETING_FEATURES) {
      assert.ok(feature.id in MARKETING_CAPTURE_MANIFEST, `${feature.id} has no approved capture`);
      const entry = MARKETING_CAPTURE_MANIFEST[feature.id as keyof typeof MARKETING_CAPTURE_MANIFEST];
      assert.equal(feature.image, entry.targets.features.path);
    }
  });

  it('removes the comparison-first table from the Features page', () => {
    const featuresPage = source('app/features/page.tsx');

    assert.doesNotMatch(featuresPage, /const comparison/);
    assert.doesNotMatch(featuresPage, /HoneyBook|Aisle Planner|Planning Pod/);
    assert.match(featuresPage, /PhaseOneProductStories/);
    assert.match(featuresPage, /\/compare/);
  });

  it('declares three render contexts from one approved source capture', () => {
    const manifestPath = path.join(ROOT, 'app/data/marketingCaptureManifest.ts');
    assert.equal(existsSync(manifestPath), true, 'marketing capture manifest is missing');

    const manifest = source('app/data/marketingCaptureManifest.ts');
    for (const target of ['hero', 'homepage', 'features']) {
      assert.match(manifest, new RegExp(`['\"]${target}['\"]`));
    }
    assert.match(manifest, /features\.png\?v=\$\{spec\.checksum\.slice\(0, 12\)\}/);
    assert.doesNotMatch(manifest, /\$\{root\}\/(?:hero|homepage)\.png/);
    assert.match(manifest, /checksum/);
    assert.match(manifest, /build/);
  });

  it('cache-busts approved captures without blocking existing local images', () => {
    const nextConfig = source('next.config.js');

    assert.match(nextConfig, /pathname: '\/\*\*',\s*search: ''/);
    assert.match(nextConfig, /pathname: '\/marketing\/product-proof\/\*\*'/);
  });

  it('ships every approved capture as a valid PNG matching its receipt', () => {
    const pngSignature = '89504e470d0a1a0a';

    for (const entry of Object.values(MARKETING_CAPTURE_MANIFEST)) {
      assert.equal(entry.status, 'approved', `${entry.featureId} is not approved`);
      assert.ok(entry.checksum, `${entry.featureId} is missing a checksum`);

      const targets = Object.values(entry.targets);
      assert.equal(new Set(targets.map((target) => target.path)).size, 1);
      assert.deepEqual(
        targets.map((target) => target.aspectRatio),
        ['10:7', '16:9', '16:10'],
      );

      for (const target of targets) {
        const [publicPath, version] = target.path.split('?v=');
        assert.equal(version, entry.checksum.slice(0, 12), `${target.path} has a stale cache key`);
        const assetPath = path.join(ROOT, 'public', publicPath.replace(/^\//, ''));
        assert.equal(existsSync(assetPath), true, `${target.path} is missing`);

        const image = readFileSync(assetPath);
        assert.equal(image.subarray(0, 8).toString('hex'), pngSignature, `${target.path} is not a PNG`);
        assert.equal(image.readUInt32BE(16), target.width, `${target.path} has the wrong width`);
        assert.equal(image.readUInt32BE(20), target.height, `${target.path} has the wrong height`);
        assert.equal(
          createHash('sha256').update(image).digest('hex'),
          entry.checksum,
          `${target.path} does not match its approved checksum`,
        );
      }
    }
  });
});
