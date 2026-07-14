import assert from 'node:assert/strict';
import { afterEach, describe, it } from 'node:test';
import { NextRequest } from 'next/server';

import { GET } from '../../app/api/maps/route';

const originalGoogleMapsApiKey = process.env.GOOGLE_MAPS_API_KEY;

afterEach(() => {
  if (originalGoogleMapsApiKey === undefined) {
    delete process.env.GOOGLE_MAPS_API_KEY;
  } else {
    process.env.GOOGLE_MAPS_API_KEY = originalGoogleMapsApiKey;
  }
});

describe('maps route optional embed contract', () => {
  it('returns a clean directions-only response when an embed key is not configured', async () => {
    delete process.env.GOOGLE_MAPS_API_KEY;

    const response = await GET(new NextRequest(
      'https://thespecialwedding.io/api/maps?location=The%20Glasshouse%20at%20Riverbend',
    ));

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      embedUrl: null,
      mapAvailable: false,
    });
  });

  it('returns the secure embed URL when a key is configured', async () => {
    process.env.GOOGLE_MAPS_API_KEY = 'maps-test-key';

    const response = await GET(new NextRequest(
      'https://thespecialwedding.io/api/maps?location=The%20Glasshouse%20at%20Riverbend',
    ));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.mapAvailable, true);
    assert.match(payload.embedUrl, /key=maps-test-key/);
    assert.match(payload.embedUrl, /The%20Glasshouse%20at%20Riverbend/);
  });
});
