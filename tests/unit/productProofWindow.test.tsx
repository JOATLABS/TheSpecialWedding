import assert from 'node:assert/strict';
import { after, afterEach, before, describe, it } from 'node:test';
import React from 'react';
import { cleanup, render } from '@testing-library/react';

import {
  MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
  MARKETING_CAPTURE_RUNTIME_ORIGIN,
  getMarketingCaptureAsset,
  isMarketingCaptureAssetApproved,
  type MarketingCaptureAsset,
} from '../../app/data/marketingCaptureManifest';
import { installDom } from './testDom';

let ProductProofWindow: typeof import('../../app/components/landing-page/ProductProofWindow').ProductProofWindow;
let domHandle: ReturnType<typeof installDom> | null = null;

function approvedDashboardAsset(): MarketingCaptureAsset {
  const asset = getMarketingCaptureAsset('dashboard', 'hero');
  return {
    ...asset,
    status: 'approved',
    reviewReceipt: {
      schemaVersion: 1,
      featureId: 'dashboard',
      capturedAt: '2026-07-14T12:00:00.000Z',
      reviewedAt: '2026-07-14T12:05:00.000Z',
      reviewer: 'Visible frontend capture review',
      appBuildCommit: asset.build,
      artifactSha256: asset.checksum,
      runtimeBuildIdentity: {
        origin: MARKETING_CAPTURE_RUNTIME_ORIGIN,
        identitySelector: MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR,
        observedCommit: asset.build,
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
    },
  };
}

describe('ProductProofWindow publication gate', () => {
  before(async () => {
    domHandle = installDom();
    ({ ProductProofWindow } = await import('../../app/components/landing-page/ProductProofWindow'));
  });

  afterEach(() => cleanup());

  after(() => {
    domHandle?.cleanup();
  });

  it('does not render a pending stale screenshot', () => {
    const asset = {
      ...getMarketingCaptureAsset('dashboard', 'hero'),
      status: 'pending' as const,
    };
    const view = render(
      <ProductProofWindow
        asset={asset}
        alt="Planner dashboard"
        label="Planner workspace"
        sizes="100vw"
        variant="hero"
      />,
    );

    assert.equal(view.container.querySelector('img'), null);
    assert.ok(view.getByText('Current product image is being refreshed'));
  });

  it('renders the image only after its manifest entry is approved', () => {
    const asset = approvedDashboardAsset();
    const view = render(
      <ProductProofWindow
        asset={asset}
        alt="Planner dashboard"
        label="Planner workspace"
        sizes="100vw"
        variant="hero"
      />,
    );

    assert.ok(view.getByRole('img', { name: 'Planner dashboard' }));
    assert.equal(view.queryByText('Current product image is being refreshed'), null);
  });

  it('keeps receipt drift and non-manual captures behind the placeholder', () => {
    const invalidAssets = [
      {
        ...approvedDashboardAsset(),
        checksum: '0'.repeat(64),
      },
      {
        ...approvedDashboardAsset(),
        build: '0'.repeat(40),
      },
      {
        ...approvedDashboardAsset(),
        reviewReceipt: {
          ...approvedDashboardAsset().reviewReceipt!,
          interactionsWereManual: false as true,
        },
      },
    ];

    for (const asset of invalidAssets) {
      assert.equal(isMarketingCaptureAssetApproved(asset), false);
      const view = render(
        <ProductProofWindow
          asset={asset}
          alt="Planner dashboard"
          label="Planner workspace"
          sizes="100vw"
          variant="hero"
        />,
      );
      assert.equal(view.container.querySelector('img'), null);
      assert.ok(view.getByText('Current product image is being refreshed'));
      cleanup();
    }
  });
});
