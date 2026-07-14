import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const pageSource = readFileSync(
  new URL('../../app/admin/weddings/[id]/page.tsx', import.meta.url),
  'utf8',
);

test('wedding editor treats Gallery permission as an independent media-read boundary', () => {
  assert.match(pageSource, /canManageGallery\(userProfile\)/);
  assert.ok(
    pageSource.match(/if \(!canBrowseGalleryMedia\)/g)?.length === 2,
    'both the request callback and Story-tab effect must fail closed',
  );
  assert.match(pageSource, /setUploadedMediaLoadError\('permission'\)/);
  assert.match(pageSource, /response\.status === 403/);
});

test('wedding editor renders permission and outage truth instead of false zero counts', () => {
  assert.match(pageSource, /getWeddingMediaLoadNotice\(uploadedMediaLoadError\)/);
  assert.match(pageSource, /getWeddingMediaAvailabilityText\(\{/);
  assert.doesNotMatch(
    pageSource,
    /catch \(err\)[\s\S]{0,240}setUploadedMedia\(\[\]\)[\s\S]{0,240}`\$\{ourStoryImages\.length\} uploaded/,
  );
});

test('wedding editor fences stale media responses across permission and wedding changes', () => {
  assert.match(pageSource, /useRef\(0\)/);
  assert.match(pageSource, /\+\+uploadedMediaRequestRef\.current/);
  assert.match(
    pageSource,
    /requestId !== uploadedMediaRequestRef\.current/g,
  );
  assert.match(pageSource, /parseWeddingMediaList\(await response\.json\(\)\)/);
  assert.match(
    pageSource,
    /setUploadedMedia\(\[\]\);\s*setLoadingUploadedMedia\(true\);\s*setUploadedMediaLoadError\(null\);/,
    'a new wedding load must remove the previous wedding media before fetching',
  );
});
