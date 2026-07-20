import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';

function readSource(relativePath: string): string {
  return readFileSync(new URL(`../../${relativePath}`, import.meta.url), 'utf8');
}

describe('public microsite footer route parity', () => {
  it('uses the shared platform footer on the landing page and full gallery', () => {
    const landingSource = readSource('app/components/landing-page/LandingLayout.tsx');
    const gallerySource = readSource('app/[slug]/gallery/page.tsx');

    assert.match(landingSource, /<PublicMicrositeFooter/);
    assert.match(gallerySource, /<PublicMicrositeFooter\s*\/>/);
    assert.match(gallerySource, /useTheme\(wedding \|\| contextWedding\)/);
  });

  it('removes the former unlinked credit and fixed legal pills', () => {
    const landingSource = readSource('app/components/landing-page/LandingLayout.tsx');

    assert.doesNotMatch(landingSource, /TheSpecialWedding/);
    assert.doesNotMatch(landingSource, /Developed by JOAT LABS/);
    assert.doesNotMatch(landingSource, /fixed bottom-0 left-0 right-0/);
  });
});
