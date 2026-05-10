import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

import { getCompareSupportedSlugs } from '../../app/compare/data';
import { buildSitemapEntries } from '../../app/sitemapEntries';

const baseUrl = 'https://thespecialwedding.io';
const now = new Date('2026-05-10T00:00:00.000Z');
const staleStaticBlogSlugs = [
  'the-built-in-wedding-website',
  'your-vendor-network-inside-the-platform',
  'why-your-couples-stop-texting-you',
  'real-time-planning-not-email-tag',
  'the-ops-layer-nobody-sees',
];

function urlsFor(prefix: string, urls: string[]) {
  return urls.filter((url) => url.startsWith(`${baseUrl}${prefix}`));
}

describe('sitemap entries', () => {
  it('emits blog URLs only from API-published slugs', () => {
    const publishedBlogSlugs = [
      'how-to-price-wedding-planning-services',
      'managing-200-guests',
    ];

    const entries = buildSitemapEntries({
      baseUrl,
      now,
      compareSlugs: getCompareSupportedSlugs(),
      blogSlugs: publishedBlogSlugs,
      vendorIds: ['vendor_1', 'vendor_2'],
    });
    const urls = entries.map((entry) => entry.url);

    assert.deepEqual(
      urlsFor('/resources/blog/', urls),
      publishedBlogSlugs.map((slug) => `${baseUrl}/resources/blog/${slug}`)
    );
    for (const slug of staleStaticBlogSlugs) {
      assert.equal(
        urls.includes(`${baseUrl}/resources/blog/${slug}`),
        false,
        `stale static-only blog slug leaked into sitemap: ${slug}`
      );
    }
  });

  it('emits compare and vendor URLs from their canonical sources', () => {
    const compareSlugs = getCompareSupportedSlugs();
    const vendorIds = ['vendor_1', 'vendor_2'];
    const entries = buildSitemapEntries({
      baseUrl,
      now,
      compareSlugs,
      blogSlugs: ['how-to-price-wedding-planning-services'],
      vendorIds,
    });
    const urls = entries.map((entry) => entry.url);

    assert.deepEqual(
      urlsFor('/compare/', urls),
      compareSlugs.map((slug) => `${baseUrl}/compare/${slug}`)
    );
    assert.deepEqual(
      urlsFor('/vendors/', urls),
      vendorIds.map((id) => `${baseUrl}/vendors/${id}`)
    );
  });

  it('does not keep a hardcoded blog fallback list in the runtime sitemap', () => {
    const source = readFileSync('app/sitemap.ts', 'utf8');

    assert.equal(source.includes('FALLBACK_BLOG_SLUGS'), false);
    for (const slug of staleStaticBlogSlugs) {
      assert.equal(source.includes(slug), false, `stale slug still appears in app/sitemap.ts: ${slug}`);
    }
  });
});
