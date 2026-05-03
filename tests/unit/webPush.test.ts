import assert from 'node:assert/strict';
import test from 'node:test';

import {
  resolveCouplePushConfig,
  urlBase64ToUint8Array,
} from '../../app/utils/webPush';

test('urlBase64ToUint8Array decodes unpadded VAPID-style base64url keys', () => {
  assert.deepEqual(Array.from(urlBase64ToUint8Array('AQIDBA')), [1, 2, 3, 4]);
  assert.deepEqual(Array.from(urlBase64ToUint8Array('-_8')), [251, 255]);
});

test('urlBase64ToUint8Array rejects empty public keys', () => {
  assert.throws(() => urlBase64ToUint8Array('   '), /VAPID public key is required/);
});

test('resolveCouplePushConfig preserves server enabled/subscribed state and trims key material', () => {
  const config = resolveCouplePushConfig({
    enabled: true,
    subscribed: true,
    vapid_public_key: '  public-key  ',
    subscription_count: 2,
  });

  assert.deepEqual(config, {
    enabled: true,
    subscribed: true,
    vapidPublicKey: 'public-key',
    reason: null,
    subscriptionCount: 2,
  });
});

test('resolveCouplePushConfig keeps disabled status explicit when push is not configured', () => {
  const config = resolveCouplePushConfig({
    enabled: false,
    subscribed: false,
    reason: 'Push not configured',
  });

  assert.equal(config.enabled, false);
  assert.equal(config.subscribed, false);
  assert.equal(config.vapidPublicKey, null);
  assert.equal(config.reason, 'Push not configured');
});
