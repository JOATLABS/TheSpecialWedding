import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';

import {
  buildGuestOtpVerifyUrl,
  getPublicFrontendBaseUrl,
} from '../../app/utils/rsvpLinks';

const originalSiteUrl = process.env.NEXT_PUBLIC_SITE_URL;
const originalFrontendUrl = process.env.FRONTEND_URL;
const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');

function restoreEnv(name: 'NEXT_PUBLIC_SITE_URL' | 'FRONTEND_URL', value: string | undefined) {
  if (value === undefined) {
    delete process.env[name];
  } else {
    process.env[name] = value;
  }
}

afterEach(() => {
  restoreEnv('NEXT_PUBLIC_SITE_URL', originalSiteUrl);
  restoreEnv('FRONTEND_URL', originalFrontendUrl);

  if (originalWindow) {
    Object.defineProperty(globalThis, 'window', originalWindow);
  } else {
    Reflect.deleteProperty(globalThis, 'window');
  }
});

test('RSVP link helper uses current browser origin when no public URL is configured', () => {
  delete process.env.NEXT_PUBLIC_SITE_URL;
  delete process.env.FRONTEND_URL;
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { location: { origin: 'http://localhost:3100' } },
  });

  assert.equal(getPublicFrontendBaseUrl(), 'http://localhost:3100');
  assert.equal(
    buildGuestOtpVerifyUrl({ slug: 'ava-and-noah', token: 'guest-token' }),
    'http://localhost:3100/otp/verify?slug=ava-and-noah&token=guest-token',
  );
});

test('RSVP link helper prefers configured public site URL over browser origin', () => {
  process.env.NEXT_PUBLIC_SITE_URL = 'https://staging.thespecialwedding.io/';
  delete process.env.FRONTEND_URL;
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { location: { origin: 'http://localhost:3100' } },
  });

  assert.equal(getPublicFrontendBaseUrl(), 'https://staging.thespecialwedding.io');
});
