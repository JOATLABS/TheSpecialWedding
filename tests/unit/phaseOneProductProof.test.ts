import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';

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
    assert.match(marketingFeatures, /\/marketing\/product-proof\//);
  });

  it('removes the comparison-first table from the Features page', () => {
    const featuresPage = source('app/features/page.tsx');

    assert.doesNotMatch(featuresPage, /const comparison/);
    assert.doesNotMatch(featuresPage, /HoneyBook|Aisle Planner|Planning Pod/);
    assert.match(featuresPage, /PhaseOneProductStories/);
    assert.match(featuresPage, /\/compare/);
  });

  it('renders distinct hero, homepage, and features crops from a capture manifest', () => {
    const manifestPath = path.join(ROOT, 'app/data/marketingCaptureManifest.ts');
    assert.equal(existsSync(manifestPath), true, 'marketing capture manifest is missing');

    const manifest = source('app/data/marketingCaptureManifest.ts');
    for (const target of ['hero', 'homepage', 'features']) {
      assert.match(manifest, new RegExp(`['\"]${target}['\"]`));
    }
    assert.match(manifest, /checksum/);
    assert.match(manifest, /build/);
  });
});

