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
    const hero = source('app/components/landing-page/PhaseOneHeroProof.tsx');

    assert.match(page, /PhaseOneHeroProof/);
    assert.doesNotMatch(page, /StackStage/);
    assert.match(page, /built specifically for wedding planners/i);
    assert.match(hero, /ProductProofWindow/);
    assert.doesNotMatch(hero, /<Image/);
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

    const stories = source('app/components/landing-page/PhaseOneProductStories.tsx');
    assert.match(stories, /ProductProofWindow/);
    assert.doesNotMatch(stories, /<Image/);
  });

  it('uses intentional product-proof assets for every marketed capability', () => {
    const marketingFeatures = source('app/data/marketingFeatures.ts');

    assert.doesNotMatch(marketingFeatures, /image: '\/(?:dashboard|calendar_management|couple_portal_dashboard|seating|reminders)\.webp'/);
    assert.match(marketingFeatures, /featureCapture/);

    for (const feature of MARKETING_FEATURES) {
      assert.ok(feature.id in MARKETING_CAPTURE_MANIFEST, `${feature.id} has no approved capture`);
      const entry = MARKETING_CAPTURE_MANIFEST[feature.id as keyof typeof MARKETING_CAPTURE_MANIFEST];
      assert.equal(feature.image.path, entry.source.path);
    }
  });

  it('removes the comparison-first table from the Features page', () => {
    const featuresPage = source('app/features/page.tsx');

    assert.doesNotMatch(featuresPage, /const comparison/);
    assert.doesNotMatch(featuresPage, /HoneyBook|Aisle Planner|Planning Pod/);
    assert.match(featuresPage, /PhaseOneProductStories/);
    assert.match(featuresPage, /ProductProofWindow/);
    assert.doesNotMatch(featuresPage, /<Image/);
    assert.match(featuresPage, /\/compare/);
  });

  it('declares one manual full-window source and three non-cropping render contexts', () => {
    const manifestPath = path.join(ROOT, 'app/data/marketingCaptureManifest.ts');
    assert.equal(existsSync(manifestPath), true, 'marketing capture manifest is missing');

    const manifest = source('app/data/marketingCaptureManifest.ts');
    for (const target of ['hero', 'homepage', 'features']) {
      assert.match(manifest, new RegExp(`['\"]${target}['\"]`));
    }
    assert.match(manifest, /features\.png\?v=\$\{spec\.checksum\.slice\(0, 12\)\}/);
    assert.doesNotMatch(manifest, /\$\{root\}\/(?:hero|homepage)\.png/);
    assert.match(manifest, /captureMethod: 'manual-in-app-browser'/);
    assert.match(manifest, /framing: 'full-window'/);
    assert.match(manifest, /fit: 'contain'/);
    assert.match(manifest, /zoom: false/);
    assert.match(manifest, /checksum/);
    assert.match(manifest, /build/);
    assert.match(manifest, /status: spec\.status/);
    assert.equal(
      (manifest.match(/status: 'approved'/g) ?? []).length,
      Object.keys(MARKETING_CAPTURE_MANIFEST).length,
      'each manually reviewed capture must opt into approval explicitly',
    );
  });

  it('uses one shared frame that never crops or zooms product proof', () => {
    const framePath = path.join(ROOT, 'app/components/landing-page/ProductProofWindow.tsx');
    assert.equal(existsSync(framePath), true, 'shared product-proof frame is missing');

    const frame = source('app/components/landing-page/ProductProofWindow.tsx');
    assert.match(frame, /object-contain/);
    assert.match(frame, /unoptimized/);
    assert.match(frame, /quality=\{90\}/);
    assert.match(frame, /const preload = priority \|\| variant === 'story'/);
    assert.match(frame, /loading=\{preload \? 'eager' : 'lazy'\}/);
    assert.match(frame, /priority=\{preload\}/);
    assert.match(frame, /data-proof-fit=\{asset\.render\.fit\}/);
    assert.match(frame, /data-proof-zoom=\{String\(asset\.render\.zoom\)\}/);
    assert.doesNotMatch(frame, /object-cover/);
    assert.doesNotMatch(frame, /(?:group-)?hover:scale|scale-\[/);
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
      assert.ok(entry.source.checksum, `${entry.featureId} is missing a checksum`);
      assert.equal(entry.source.framing, 'full-window');
      assert.equal(entry.source.captureMethod, 'manual-in-app-browser');
      assert.equal(entry.source.width, 1440, `${entry.featureId} is not a 1440px-wide full window`);
      assert.equal(entry.source.height, 900, `${entry.featureId} is not a 900px-tall full window`);
      assert.deepEqual(entry.source.captureBounds, {
        x: 0,
        y: 0,
        width: entry.source.width,
        height: entry.source.height,
      });

      for (const render of Object.values(entry.renders)) {
        assert.equal(render.frameAspectRatio, '16:10');
        assert.equal(render.fit, 'contain');
        assert.equal(render.zoom, false);
      }

      const [publicPath, version] = entry.source.path.split('?v=');
      assert.equal(
        version,
        entry.source.checksum.slice(0, 12),
        `${entry.source.path} has a stale cache key`,
      );
      const assetPath = path.join(ROOT, 'public', publicPath.replace(/^\//, ''));
      assert.equal(existsSync(assetPath), true, `${entry.source.path} is missing`);

      const image = readFileSync(assetPath);
      assert.equal(image.subarray(0, 8).toString('hex'), pngSignature, `${entry.source.path} is not a PNG`);
      assert.equal(image.readUInt32BE(16), entry.source.width, `${entry.source.path} has the wrong width`);
      assert.equal(image.readUInt32BE(20), entry.source.height, `${entry.source.path} has the wrong height`);
      assert.equal(
        createHash('sha256').update(image).digest('hex'),
        entry.source.checksum,
        `${entry.source.path} does not match its approved checksum`,
      );
    }
  });
});
