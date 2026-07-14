import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';
import {
  MARKETING_CAPTURE_BUILD,
  MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
  MARKETING_CAPTURE_MANIFEST,
  MARKETING_CAPTURE_RUNTIME_ORIGIN,
  MARKETING_CAPTURE_SAFETY_ASSERTIONS,
  MARKETING_CAPTURE_VIEWPORT,
  type MarketingCaptureEntry,
} from '../../app/data/marketingCaptureManifest';
import { PHASE_ONE_PRODUCT_STORIES } from '../../app/data/phaseOneProductProof';
import { MARKETING_FEATURES } from '../../app/data/marketingFeatures';
import {
  assertManualFullWindowContract,
  validateApprovedProductImage,
  validatePublishedProductImages,
} from '../../scripts/demo-videos/validate-manual-product-images';

const ROOT = process.cwd();

function source(relativePath: string): string {
  return readFileSync(path.join(ROOT, relativePath), 'utf8');
}

function approvedEntry(entry: MarketingCaptureEntry): MarketingCaptureEntry {
  const approved = JSON.parse(JSON.stringify(entry)) as MarketingCaptureEntry;
  approved.status = 'approved';
  approved.source.reviewReceipt = {
    schemaVersion: 1,
    featureId: approved.featureId,
    capturedAt: '2026-07-14T12:00:00.000Z',
    reviewedAt: '2026-07-14T12:05:00.000Z',
    reviewer: 'Visible frontend capture review',
    appBuildCommit: approved.build,
    artifactSha256: approved.source.checksum,
    runtimeBuildIdentity: {
      origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
      identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
      observedCommit: approved.build,
      verifiedAt: '2026-07-14T11:59:00.000Z',
    },
    browser: 'Google Chrome',
    browserWasVisible: true,
    interactionsWereManual: true,
    scriptedBrowserCaptureWasUsed: false,
    pageZoomPercent: 100,
    viewportMode: 'Responsive',
    devicePixelRatio: 1,
    captureCommand: 'Capture screenshot',
    fullSizeScreenshotWasUsed: false,
    originalPngReviewed: true,
    postCaptureTransformsApplied: false,
  };
  return approved;
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
    assert.match(manifest, /captureMethod: 'manual-visible-browser'/);
    assert.match(manifest, /pageZoomPercent: 100/);
    assert.match(manifest, /devicePixelRatio: 1/);
    assert.match(manifest, /captureCommand: 'Capture screenshot'/);
    assert.match(manifest, /scriptedBrowserCaptureWasUsed: false/);
    assert.match(manifest, /reviewReceipt: spec\.reviewReceipt \?\? null/);
    assert.match(manifest, /framing: 'full-window'/);
    assert.match(manifest, /fit: 'contain'/);
    assert.match(manifest, /zoom: false/);
    assert.match(manifest, /checksum/);
    assert.match(manifest, /build/);
    assert.match(manifest, /status: spec\.status/);
    const approvedEntries = Object.values(MARKETING_CAPTURE_MANIFEST)
      .filter((entry) => entry.status === 'approved');
    assert.ok(approvedEntries.length > 0, 'manual capture approval receipts are missing');
    for (const entry of Object.values(MARKETING_CAPTURE_MANIFEST)) {
      if (entry.status === 'approved') {
        assert.ok(entry.source.reviewReceipt, `${entry.featureId} is missing its approval receipt`);
      } else {
        assert.equal(entry.source.reviewReceipt, null, `${entry.featureId} has a premature receipt`);
      }
    }
  });

  it('refuses to publish fewer than the 15 already reviewed product proofs', async () => {
    const approvedEntries = Object.values(MARKETING_CAPTURE_MANIFEST)
      .filter((entry) => entry.status === 'approved');
    assert.ok(
      approvedEntries.length >= 15,
      'the reviewed publication floor must never move backwards',
    );

    const demotedEntries = approvedEntries.slice(14);
    const originalStatuses = demotedEntries.map((entry) => entry.status);
    try {
      for (const entry of demotedEntries) {
        entry.status = 'pending';
      }
      await assert.rejects(
        () => validatePublishedProductImages(),
        /at least 15 approved product proofs/,
      );
    } finally {
      demotedEntries.forEach((entry, index) => {
        entry.status = originalStatuses[index];
      });
    }
  });

  it('pins every scene to its exact build, session, stable state, viewport, and safety review', () => {
    const expectedSceneContext = {
      dashboard: ['planner', 'Welcome back, Marigold & Co. Weddings!'],
      'real-time': ['planner', 'The Glasshouse at Riverbend'],
      'couple-portal': ['couple', '24 guests added so far'],
      'wedding-website': ['public', 'The Glasshouse at Riverbend'],
      'wedding-configuration': ['planner', 'RSVP Configuration'],
      'gallery-management': ['planner', 'Garden terrace portrait'],
      'guest-management': ['planner', 'Guest Management'],
      'seating-orchestrator': ['planner', '70%'],
      'guest-memories': ['couple', 'Review queue'],
      inbox: ['planner', 'Sofia & Daniel'],
      'book-the-client': ['planner', 'Payment Milestones'],
      'payments-autopilot': ['planner', 'Money'],
      budget: ['planner', '$82,500'],
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

      assert.match(entry.build, /^[0-9a-f]{40}$/, `${featureId} has the wrong capture build`);
      assert.equal(entry.requiredSession, requiredSession, `${featureId} has the wrong session`);
      assert.match(entry.sourceRoute, /^\//, `${featureId} must use an application route`);
      assert.doesNotMatch(entry.sourceRoute, /\[[^\]]+\]/, `${featureId} route must resolve fixture parameters`);
      assert.deepEqual(entry.stableState, {
        selector: entry.source.focalLocator,
        expectedVisibleText,
      });
      assert.deepEqual(entry.viewport, MARKETING_CAPTURE_VIEWPORT);
      assert.deepEqual(entry.safetyAssertions, MARKETING_CAPTURE_SAFETY_ASSERTIONS);
      if (entry.status === 'approved') {
        assert.ok(entry.source.reviewReceipt, `${featureId} is missing its manual review receipt`);
        assert.doesNotThrow(() => assertManualFullWindowContract(featureId, entry));
      } else {
        assert.equal(entry.build, MARKETING_CAPTURE_BUILD, `${featureId} pending build drifted`);
        assert.equal(entry.source.reviewReceipt, null, `${featureId} has a generated receipt`);
        assert.throws(
          () => assertManualFullWindowContract(featureId, { ...entry, status: 'approved' }),
          /explicit per-image manual review receipt/,
        );
        assert.doesNotThrow(() => assertManualFullWindowContract(featureId, approvedEntry(entry)));
      }
    }

    for (const featureId of [
      'real-time',
      'wedding-website',
      'wedding-configuration',
      'gallery-management',
      'guest-management',
      'seating-orchestrator',
      'guest-memories',
      'book-the-client',
      'forms',
    ] as const) {
      assert.ok(
        MARKETING_CAPTURE_MANIFEST[featureId].safeInteraction,
        `${featureId} must declare the manual interaction needed to reach its stable state`,
      );
    }

    assert.equal(
      MARKETING_CAPTURE_MANIFEST.inbox.safeInteraction,
      undefined,
      'the inbox still must remain on its populated list so capture does not mark a thread read',
    );

    assert.equal(
      MARKETING_CAPTURE_MANIFEST.budget.sourceRoute,
      '/admin/budget?wedding_id=wedding_marketing_capture_sofia_daniel',
      'the budget proof must open its populated seeded wedding directly',
    );
  });

  it('rejects incomplete or self-consistent-but-wrong manual capture receipts', async () => {
    const cloneDashboard = (): MarketingCaptureEntry => approvedEntry(
      MARKETING_CAPTURE_MANIFEST.dashboard,
    );

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
        label: 'unsupported session',
        mutate: (entry) => {
          entry.requiredSession = 'vendor' as MarketingCaptureEntry['requiredSession'];
        },
        message: /browser session required/,
      },
      {
        label: 'wrong receipt schema',
        mutate: (entry) => {
          (entry.source.reviewReceipt as { schemaVersion: number }).schemaVersion = 2;
        },
        message: /unsupported schema version/,
      },
      {
        label: 'wrong receipt feature',
        mutate: (entry) => {
          (entry.source.reviewReceipt as { featureId: string }).featureId = 'inbox';
        },
        message: /same capture feature/,
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
      {
        label: 'non-default browser zoom',
        mutate: (entry) => {
          (entry.source.reviewReceipt as { pageZoomPercent: number }).pageZoomPercent = 125;
        },
        message: /browser zoom must be exactly 100%/,
      },
      {
        label: 'high-DPI capture',
        mutate: (entry) => {
          (entry.source.reviewReceipt as { devicePixelRatio: number }).devicePixelRatio = 2;
        },
        message: /device pixel ratio must be 1/,
      },
      {
        label: 'full-size screenshot command',
        mutate: (entry) => {
          (entry.source.reviewReceipt as { captureCommand: string }).captureCommand = 'Capture full size screenshot';
        },
        message: /Chrome DevTools Capture screenshot command/,
      },
      {
        label: 'scripted capture attestation',
        mutate: (entry) => {
          (entry.source.reviewReceipt as { scriptedBrowserCaptureWasUsed: boolean })
            .scriptedBrowserCaptureWasUsed = true;
        },
        message: /scripted browser capture must be false/,
      },
      {
        label: 'receipt checksum drift',
        mutate: (entry) => {
          if (entry.source.reviewReceipt) {
            entry.source.reviewReceipt.artifactSha256 = '0'.repeat(64);
          }
        },
        message: /receipt must match the captured PNG checksum/,
      },
      {
        label: 'receipt build drift',
        mutate: (entry) => {
          if (entry.source.reviewReceipt) {
            entry.source.reviewReceipt.appBuildCommit = '0'.repeat(40);
          }
        },
        message: /receipt must match the exact captured Git build/,
      },
      {
        label: 'served runtime build drift',
        mutate: (entry) => {
          if (entry.source.reviewReceipt) {
            entry.source.reviewReceipt.runtimeBuildIdentity.observedCommit = '0'.repeat(40);
          }
        },
        message: /runtime identity must match the isolated capture build/,
      },
      {
        label: 'runtime verified after capture',
        mutate: (entry) => {
          if (entry.source.reviewReceipt) {
            entry.source.reviewReceipt.runtimeBuildIdentity.verifiedAt = '2026-07-14T12:01:00.000Z';
          }
        },
        message: /must be verified within 24 hours before capture/,
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

    const unknownBuild = cloneDashboard();
    unknownBuild.build = '0000000000000000000000000000000000000000';
    if (!unknownBuild.source.reviewReceipt) {
      throw new Error('approved test fixture is missing its receipt');
    }
    unknownBuild.source.reviewReceipt.appBuildCommit = unknownBuild.build;
    unknownBuild.source.reviewReceipt.runtimeBuildIdentity.observedCommit = unknownBuild.build;

    await assert.doesNotReject(
      () => validateApprovedProductImage('dashboard', unknownBuild),
      'the Docker-safe artifact validator must not invoke Git by default',
    );
    await assert.rejects(
      () => validateApprovedProductImage(
        'dashboard',
        unknownBuild,
        { verifyGitAncestry: true },
      ),
      /capture build does not exist in this Git repository/,
    );

    const dashboardPath = path.join(
      ROOT,
      'public',
      MARKETING_CAPTURE_MANIFEST.dashboard.source.path
        .split('?', 1)[0]
        .replace(/^\//, ''),
    );
    const truncatedBytes = readFileSync(dashboardPath).subarray(0, 24);
    const truncatedChecksum = createHash('sha256').update(truncatedBytes).digest('hex');
    const truncatedName = `.truncated-capture-${process.pid}-${Date.now()}.png`;
    const truncatedPath = path.join(
      ROOT,
      'public',
      'marketing',
      'product-proof',
      truncatedName,
    );
    const truncatedEntry = cloneDashboard();
    truncatedEntry.source.path = `/marketing/product-proof/${truncatedName}?v=${truncatedChecksum.slice(0, 12)}`;
    truncatedEntry.source.checksum = truncatedChecksum;
    if (!truncatedEntry.source.reviewReceipt) {
      throw new Error('approved test fixture is missing its receipt');
    }
    truncatedEntry.source.reviewReceipt.artifactSha256 = truncatedChecksum;

    writeFileSync(truncatedPath, truncatedBytes);
    try {
      await assert.rejects(
        () => validateApprovedProductImage('dashboard', truncatedEntry),
        /cannot be fully decoded as PNG/,
        'a self-consistent checksum and IHDR must not approve a truncated PNG',
      );
    } finally {
      unlinkSync(truncatedPath);
    }
  });

  it('uses one shared frame that never crops or zooms product proof', () => {
    const framePath = path.join(ROOT, 'app/components/landing-page/ProductProofWindow.tsx');
    assert.equal(existsSync(framePath), true, 'shared product-proof frame is missing');

    const frame = source('app/components/landing-page/ProductProofWindow.tsx');
    assert.match(frame, /object-contain/);
    assert.match(frame, /unoptimized/);
    assert.doesNotMatch(frame, /quality=\{/);
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

  it('keeps every product-proof PNG structurally valid and receipt-gated', () => {
    const pngSignature = '89504e470d0a1a0a';

    for (const entry of Object.values(MARKETING_CAPTURE_MANIFEST)) {
      assert.ok(entry.source.checksum, `${entry.featureId} is missing a checksum`);
      assert.equal(entry.source.framing, 'full-window');
      assert.equal(entry.source.captureMethod, 'manual-visible-browser');
      if (entry.status === 'approved') {
        assert.ok(entry.source.reviewReceipt, `${entry.featureId} is missing its review receipt`);
        assert.doesNotThrow(() => assertManualFullWindowContract(entry.featureId, entry));
      } else {
        assert.equal(entry.source.reviewReceipt, null);
      }
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
