import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';
import {
  MARKETING_CAPTURE_BUILD,
  MARKETING_CAPTURE_MANIFEST,
  MARKETING_CAPTURE_SAFETY_ASSERTIONS,
  MARKETING_CAPTURE_VIEWPORT,
  type MarketingCaptureEntry,
} from '../../app/data/marketingCaptureManifest';
import { PHASE_ONE_PRODUCT_STORIES } from '../../app/data/phaseOneProductProof';
import { MARKETING_FEATURES } from '../../app/data/marketingFeatures';
import { assertManualFullWindowContract } from '../../scripts/demo-videos/validate-manual-product-images';

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
    assert.match(stories, /story\.supportingImages\.map/);
    assert.doesNotMatch(stories, /<Image/);

    assert.equal(PHASE_ONE_PRODUCT_STORIES.length, 4);
    for (const story of PHASE_ONE_PRODUCT_STORIES) {
      assert.equal(
        story.supportingImages.length,
        2,
        `${story.id} must show both downstream surfaces behind its connected-workflow claim`,
      );
      assert.ok(
        story.supportingImages.every(({ image }) => image.render.fit === 'contain' && image.render.zoom === false),
        `${story.id} supporting proof must preserve every full product window`,
      );
    }
  });

  it('uses intentional product-proof assets for every marketed capability', () => {
    const marketingFeatures = source('app/data/marketingFeatures.ts');

    assert.doesNotMatch(marketingFeatures, /image: '\/(?:dashboard|calendar_management|couple_portal_dashboard|seating|reminders)\.webp'/);
    assert.match(marketingFeatures, /featureCapture/);

    for (const feature of MARKETING_FEATURES) {
      assert.ok(feature.id in MARKETING_CAPTURE_MANIFEST, `${feature.id} has no capture slot`);
      const entry = MARKETING_CAPTURE_MANIFEST[feature.id as keyof typeof MARKETING_CAPTURE_MANIFEST];
      assert.equal(feature.image.path, entry.source.path);
    }
  });

  it('keeps the Money proof credible for unlimited planner plans', () => {
    const moneyPage = source('app/admin/money/page.tsx');

    assert.match(moneyPage, /subscription\?\.weddings_total === -1/);
    assert.match(moneyPage, /Unlimited weddings included/);
    assert.match(moneyPage, /weddings_total \?\? 3/);
    assert.doesNotMatch(
      moneyPage,
      /\{subscription\.weddings_total - subscription\.weddings_used\} remaining/,
    );
  });

  it('never invents planner contact numbers in the wedding editor', () => {
    const weddingEditor = source('app/admin/weddings/[id]/page.tsx');
    const captureSeed = source('scripts/demo-videos/seed-demo-video-workspace.py');

    assert.match(weddingEditor, /phone_numbers: \[\]/);
    assert.doesNotMatch(weddingEditor, /\(405\) 529-6088|\(405\) 708-1076/);
    assert.match(captureSeed, /\(312\) 555-0142/);
    assert.match(captureSeed, /\(312\) 555-0168/);
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
      (manifest.match(/status: 'pending'/g) ?? []).length,
      Object.keys(MARKETING_CAPTURE_MANIFEST).length,
      'historical assets must remain pending until the final build is manually retaken',
    );
  });

  it('pins every scene to its exact build, session, stable state, viewport, and safety review', () => {
    const expectedSceneContext = {
      dashboard: ['planner', 'Welcome back, Marigold & Co. Weddings!'],
      'real-time': ['planner', 'Sofia & Daniel'],
      'couple-portal': ['couple', 'Sofia & Daniel'],
      'wedding-website': ['public', 'Sofia & Daniel'],
      'wedding-configuration': ['planner', 'RSVP Configuration'],
      'gallery-management': ['planner', 'Gallery Management'],
      'guest-management': ['planner', 'Guest Management'],
      'seating-orchestrator': ['planner', 'Seating Arrangement'],
      'guest-memories': ['couple', 'Guest Memories'],
      inbox: ['planner', 'Inbox'],
      'book-the-client': ['planner', 'Payment Milestones'],
      'payments-autopilot': ['planner', 'Money'],
      budget: ['planner', 'Budget Overview'],
      'vendor-network': ['planner', 'Vendor Management'],
      'knowledge-base': ['planner', 'Knowledge Base'],
      forms: ['planner', 'Couple Intake Questionnaire'],
      team: ['planner', 'Team Management'],
    } as const;

    assert.match(MARKETING_CAPTURE_BUILD, /^[0-9a-f]{40}$/);
    assert.deepEqual(
      Object.keys(MARKETING_CAPTURE_MANIFEST).sort(),
      Object.keys(expectedSceneContext).sort(),
    );

    for (const [featureId, [requiredSession, expectedVisibleText]] of Object.entries(expectedSceneContext)) {
      const entry = MARKETING_CAPTURE_MANIFEST[
        featureId as keyof typeof MARKETING_CAPTURE_MANIFEST
      ];

      assert.equal(entry.build, MARKETING_CAPTURE_BUILD, `${featureId} has the wrong capture build`);
      assert.equal(entry.requiredSession, requiredSession, `${featureId} has the wrong session`);
      assert.match(entry.sourceRoute, /^\//, `${featureId} must use an application route`);
      assert.doesNotMatch(entry.sourceRoute, /\[[^\]]+\]/, `${featureId} route must resolve fixture parameters`);
      assert.deepEqual(entry.stableState, {
        selector: entry.source.focalLocator,
        expectedVisibleText,
      });
      assert.deepEqual(entry.viewport, MARKETING_CAPTURE_VIEWPORT);
      assert.deepEqual(entry.safetyAssertions, MARKETING_CAPTURE_SAFETY_ASSERTIONS);
      assert.equal(entry.status, 'pending', `${featureId} must await the final manual retake`);
      assert.doesNotThrow(() => assertManualFullWindowContract(featureId, {
        ...entry,
        status: 'approved',
      }));
    }

    for (const featureId of ['wedding-configuration', 'gallery-management', 'guest-memories', 'book-the-client'] as const) {
      assert.ok(
        MARKETING_CAPTURE_MANIFEST[featureId].safeInteraction,
        `${featureId} must declare the manual interaction needed to reach its stable state`,
      );
    }

    assert.equal(
      MARKETING_CAPTURE_MANIFEST.budget.sourceRoute,
      '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
      'the budget proof must open its populated seeded wedding directly',
    );
  });

  it('rejects incomplete or self-consistent-but-wrong manual capture receipts', () => {
    const cloneDashboard = (): MarketingCaptureEntry => ({
      ...JSON.parse(JSON.stringify(MARKETING_CAPTURE_MANIFEST.dashboard)) as MarketingCaptureEntry,
      status: 'approved',
    });

    const invalidReceipts: Array<{
      label: string;
      mutate: (entry: MarketingCaptureEntry) => void;
      message: RegExp;
    }> = [
      {
        label: 'symbolic build label',
        mutate: (entry) => { entry.build = 'phase-1-2026-07-12'; },
        message: /exact captured Git build/,
      },
      {
        label: 'unknown Git build',
        mutate: (entry) => { entry.build = '0000000000000000000000000000000000000000'; },
        message: /capture build does not exist in this Git repository/,
      },
      {
        label: 'unsupported session',
        mutate: (entry) => {
          entry.requiredSession = 'vendor' as MarketingCaptureEntry['requiredSession'];
        },
        message: /browser session required/,
      },
      {
        label: 'unresolved route parameter',
        mutate: (entry) => { entry.sourceRoute = '/admin/weddings/[id]'; },
        message: /resolved application route/,
      },
      {
        label: 'selector drift',
        mutate: (entry) => { entry.stableState.selector = '[data-capture-ready]'; },
        message: /must match the captured focal locator/,
      },
      {
        label: 'empty stable text',
        mutate: (entry) => { entry.stableState.expectedVisibleText = ' '; },
        message: /populated stable-state selector and visible text/,
      },
      {
        label: 'smaller viewport and source',
        mutate: (entry) => {
          (entry.viewport as { width: number; height: number }).width = 1024;
          entry.source.width = 1024;
          entry.source.captureBounds.width = 1024;
        },
        message: /viewport must match the full-window source dimensions/,
      },
      {
        label: 'missing localhost safety assertion',
        mutate: (entry) => {
          entry.safetyAssertions = entry.safetyAssertions.slice(1);
        },
        message: /manual public-safety review assertions/,
      },
    ];

    for (const { label, mutate, message } of invalidReceipts) {
      const entry = cloneDashboard();
      mutate(entry);
      assert.throws(
        () => assertManualFullWindowContract('dashboard', entry),
        message,
        label,
      );
    }
  });

  it('uses one shared frame that never crops or zooms product proof', () => {
    const framePath = path.join(ROOT, 'app/components/landing-page/ProductProofWindow.tsx');
    assert.equal(existsSync(framePath), true, 'shared product-proof frame is missing');

    const frame = source('app/components/landing-page/ProductProofWindow.tsx');
    assert.match(frame, /object-contain/);
    assert.match(frame, /unoptimized/);
    assert.match(frame, /quality=\{90\}/);
    assert.match(frame, /const preload = priority/);
    assert.match(frame, /loading=\{preload \? 'eager' : 'lazy'\}/);
    assert.match(frame, /priority=\{preload\}/);
    assert.match(frame, /data-proof-fit=\{asset\.render\.fit\}/);
    assert.match(frame, /data-proof-zoom=\{String\(asset\.render\.zoom\)\}/);
    assert.match(frame, /data-proof-matte/);
    assert.match(frame, /data-proof-frame/);
    assert.match(frame, /style=\{\{ aspectRatio: frameAspectRatio \}\}/);
    assert.match(frame, /min-w-0/);
    assert.doesNotMatch(frame, /object-cover/);
    assert.doesNotMatch(frame, /(?:group-)?hover:scale|scale-\[/);

    const stories = source('app/components/landing-page/PhaseOneProductStories.tsx');
    assert.match(stories, /grid-cols-\[minmax\(0,1fr\)\]/);
    assert.match(stories, /className=\{`min-w-0 /);
  });

  it('cache-busts capture assets without blocking existing local images', () => {
    const nextConfig = source('next.config.js');

    assert.match(nextConfig, /pathname: '\/\*\*',\s*search: ''/);
    assert.match(nextConfig, /pathname: '\/marketing\/product-proof\/\*\*'/);
  });

  it('keeps every historical PNG structurally valid while its manual retake is pending', () => {
    const pngSignature = '89504e470d0a1a0a';

    for (const entry of Object.values(MARKETING_CAPTURE_MANIFEST)) {
      assert.equal(entry.status, 'pending', `${entry.featureId} must not claim approval`);
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
        `${entry.source.path} does not match its current historical checksum`,
      );
    }
  });
});
