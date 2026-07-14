import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const pageSource = readFileSync(
  new URL('../../app/admin/gallery/upload/page.tsx', import.meta.url),
  'utf8'
);

describe('admin gallery upload failure contract', () => {
  it('uses the all-folder client instead of accepting partial prefix success', () => {
    assert.match(pageSource, /fetchGalleryImagesForWedding\(/);
    assert.doesNotMatch(pageSource, /const folders = \['gallery', 'our-story', 'wedding-party'\]/);
    assert.doesNotMatch(pageSource, /allImages\.push/);
  });

  it('renders failed loads as an error rather than the empty-gallery success state', () => {
    assert.match(pageSource, /role="alert"/);
    assert.match(pageSource, /Gallery images are temporarily unavailable/);
    assert.match(pageSource, /galleryLoadError \?/);
    assert.doesNotMatch(pageSource, /catch \(err\)[\s\S]{0,180}setUploadedImages\(\[\]\)/);
  });

  it('ignores a stale folder load after the planner selects another wedding', () => {
    assert.match(pageSource, /useRef\(0\)/);
    assert.match(pageSource, /const requestId = \+\+galleryLoadRequestRef\.current/);
    assert.match(pageSource, /if \(requestId !== galleryLoadRequestRef\.current\) return/);
  });
});
