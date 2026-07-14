import assert from 'node:assert/strict';
import { test } from 'node:test';
import { NextRequest } from 'next/server';

import sceneContract from '../../app/data/marketingCaptureScenes.json';
import { MARKETING_CAPTURE_MANIFEST } from '../../app/data/marketingCaptureManifest';
import { proxy } from '../../proxy';

test('planner capture routes reproduce the proxy 307 without admin_token', () => {
  const priorFrontendUrl = process.env.FRONTEND_URL;
  process.env.FRONTEND_URL = 'http://127.0.0.1:3100';
  try {
    const unauthenticated = proxy(
      new NextRequest('http://127.0.0.1:3100/admin/planner', {
        headers: { host: '127.0.0.1:3100' },
      }),
    );
    assert.equal(unauthenticated.status, 307);
    assert.equal(
      new URL(unauthenticated.headers.get('location') ?? '').pathname,
      '/admin/login',
    );

    const authenticated = proxy(
      new NextRequest('http://127.0.0.1:3100/admin/planner', {
        headers: {
          host: '127.0.0.1:3100',
          cookie: 'admin_token=seeded-planner-token',
        },
      }),
    );
    assert.equal(authenticated.headers.get('location'), null);
  } finally {
    if (priorFrontendUrl === undefined) {
      delete process.env.FRONTEND_URL;
    } else {
      process.env.FRONTEND_URL = priorFrontendUrl;
    }
  }
});

test('canonical capture scenes stay in exact parity with the product manifest', () => {
  assert.equal(sceneContract.schemaVersion, 1);
  assert.equal(sceneContract.scenes.length, 17);

  const canonicalFeatureIds = sceneContract.scenes.map((scene) => scene.featureId);
  assert.equal(new Set(canonicalFeatureIds).size, canonicalFeatureIds.length);
  assert.deepEqual(
    [...canonicalFeatureIds].sort(),
    Object.keys(MARKETING_CAPTURE_MANIFEST).sort(),
  );

  for (const scene of sceneContract.scenes) {
    const featureId = scene.featureId as keyof typeof MARKETING_CAPTURE_MANIFEST;
    const manifestEntry = MARKETING_CAPTURE_MANIFEST[featureId];

    assert.ok(manifestEntry, `${scene.featureId} is missing from the manifest`);
    assert.equal(manifestEntry.featureId, scene.featureId);
    assert.equal(manifestEntry.requiredSession, scene.session);
    assert.equal(manifestEntry.sourceRoute, scene.route);
    assert.equal(
      manifestEntry.stableState.expectedVisibleText,
      scene.expectedVisibleText,
    );
    assert.equal(manifestEntry.safeInteraction ?? null, scene.safeInteraction);
    assert.ok(scene.title.trim(), `${scene.featureId} is missing its title`);
    assert.ok(
      scene.expectation.trim(),
      `${scene.featureId} is missing its visible expectation`,
    );
  }
});

test('canonical gallery assets pin the reviewed WebP contract', () => {
  assert.deepEqual(
    sceneContract.galleryAssets.map((asset) => asset.path).sort(),
    [
      '/demo-gallery/sofia-daniel-ceremony.webp',
      '/demo-gallery/sofia-daniel-reception.webp',
      '/demo-gallery/sofia-daniel-terrace.webp',
    ],
  );
  for (const asset of sceneContract.galleryAssets) {
    assert.match(asset.sha256, /^[0-9a-f]{64}$/);
    assert.equal(asset.width, 1600);
    assert.equal(asset.height, 1000);
  }
});
