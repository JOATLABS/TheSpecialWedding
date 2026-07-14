import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

function readSource(relativePath: string): string {
  return readFileSync(new URL(`../../${relativePath}`, import.meta.url), 'utf8');
}

describe('public gallery page request lifecycle', () => {
  for (const pagePath of ['app/[slug]/page.tsx', 'app/[slug]/gallery/page.tsx']) {
    it(`${pagePath} aborts obsolete requests and rejects stale responses`, () => {
      const source = readSource(pagePath);

      assert.match(source, /useRef<AbortController \| null>/);
      assert.match(source, /galleryRequestRef\.current\?\.abort\(\)/);
      assert.match(source, /signal: controller\.signal/);
      assert.match(source, /galleryRequestRef\.current !== controller/);
      assert.match(source, /activeRequest\?\.abort\(\)/);
    });
  }

  it('keeps the landing preview error state distinct from a true empty gallery', () => {
    const pageSource = readSource('app/[slug]/page.tsx');
    const layoutSource = readSource('app/components/landing-page/LandingLayout.tsx');

    assert.match(pageSource, /setGalleryError\(true\)/);
    assert.match(pageSource, /galleryError=\{galleryError\}/);
    assert.match(pageSource, /onGalleryRetry=\{\(\) => void fetchGallery\(\)\}/);
    assert.match(layoutSource, /error=\{galleryError\}/);
  });

  it('does not render the full-gallery empty state when fetching failed', () => {
    const source = readSource('app/[slug]/gallery/page.tsx');

    assert.match(source, /Gallery temporarily unavailable/);
    assert.match(source, /galleryError \? null : \(/);
    assert.match(source, /No photos yet/);
  });
});
