import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildWeddingMediaOptions,
  getWeddingMediaAvailabilityText,
  getWeddingMediaLoadNotice,
  parseWeddingMediaList,
} from '../../app/admin/weddings/[id]/weddingMediaAvailability';

test('permission-denied media state never masquerades as an empty library', () => {
  const text = getWeddingMediaAvailabilityText({
    kind: 'story',
    count: 0,
    loading: false,
    error: 'permission',
  });
  const notice = getWeddingMediaLoadNotice('permission');

  assert.match(text, /Manage Gallery permission is required/);
  assert.doesNotMatch(text, /0 uploaded/);
  assert.deepEqual(notice, {
    role: 'status',
    title: 'Gallery access required',
    description:
      'Your current photo selections are preserved, but Manage Gallery permission is required to browse uploaded images.',
  });
});

test('unavailable media state is distinct from a real empty result', () => {
  assert.match(
    getWeddingMediaAvailabilityText({
      kind: 'wedding-party',
      count: 0,
      loading: false,
      error: 'unavailable',
    }),
    /temporarily unavailable/,
  );
  assert.deepEqual(getWeddingMediaLoadNotice('unavailable'), {
    role: 'alert',
    title: 'Uploaded media is temporarily unavailable',
    description:
      'Your current photo selections are preserved. Reopen the Story tab to try loading the media library again.',
  });
});

test('successful media state reports loading and genuine counts', () => {
  assert.equal(
    getWeddingMediaAvailabilityText({
      kind: 'story',
      count: 0,
      loading: true,
      error: null,
    }),
    'Loading uploaded story images...',
  );
  assert.equal(
    getWeddingMediaAvailabilityText({
      kind: 'wedding-party',
      count: 1,
      loading: false,
      error: null,
    }),
    '1 uploaded wedding-party image available',
  );
  assert.equal(getWeddingMediaLoadNotice(null), null);
});

test('current selections remain available when browsing is denied or unavailable', () => {
  assert.deepEqual(
    buildWeddingMediaOptions([], 'our-story/sofia-and-daniel/current.webp'),
    [
      {
        value: 'our-story/sofia-and-daniel/current.webp',
        label: 'Current selection: current.webp (our-story)',
      },
    ],
  );
});

test('media-list parsing rejects malformed success payloads instead of reporting zero images', () => {
  assert.throws(() => parseWeddingMediaList({ items: [] }), /must be an array/);
  assert.throws(
    () => parseWeddingMediaList([{ url: '/missing-key.webp' }]),
    /valid storage key/,
  );
  assert.deepEqual(
    parseWeddingMediaList([
      { key: 'our-story/sofia-and-daniel/one.webp', size: 1024 },
    ]),
    [{ key: 'our-story/sofia-and-daniel/one.webp', size: 1024 }],
  );
});
