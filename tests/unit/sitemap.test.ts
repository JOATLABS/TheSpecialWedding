import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';

import { getCompareSupportedSlugs } from '../../app/compare/data';
import { buildSitemapEntries } from '../../app/sitemapEntries';

const baseUrl = 'https://thespecialwedding.io';
const now = new Date('2026-05-10T00:00:00.000Z');
const objectIdVendorIds = [
  '507f1f77bcf86cd799439011', // pragma: allowlist secret
  '64f1f77bcf86cd7994390123', // pragma: allowlist secret
];
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

function routeCandidatesFor(pathname: string): string[] {
  const segments = pathname.split('/').filter(Boolean);

  if (segments.length === 0) {
    return ['app/page.tsx'];
  }

  if (segments[0] === 'compare' && segments.length === 2) {
    return ['app/compare/[competitor]/page.tsx'];
  }

  if (segments[0] === 'resources' && segments[1] === 'blog' && segments.length === 3) {
    return ['app/resources/blog/[slug]/page.tsx'];
  }

  if (segments[0] === 'vendors' && segments.length === 2) {
    return ['app/vendors/[id]/page.tsx'];
  }

  return [path.join('app', ...segments, 'page.tsx')];
}

describe('sitemap entries', () => {
  it('emits resources templates as a canonical static route', () => {
    const entries = buildSitemapEntries({
      baseUrl,
      now,
      compareSlugs: [],
      blogSlugs: [],
      vendorIds: [],
    });
    const urls = entries.map((entry) => entry.url);

    assert.equal(urls.includes(`${baseUrl}/resources`), true);
    assert.equal(urls.includes(`${baseUrl}/resources/templates`), true);
    assert.equal(urls.includes(`${baseUrl}/resources?tab=templates`), false);
  });

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
      vendorIds: objectIdVendorIds,
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
    const vendorIds = objectIdVendorIds;
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

  it('filters dynamic entries that cannot resolve as public routes', () => {
    const entries = buildSitemapEntries({
      baseUrl,
      now,
      compareSlugs: ['honeybook', 'missing-competitor'],
      blogSlugs: [
        'how-to-price-wedding-planning-services',
        '../private',
        'bad slug',
        '',
      ],
      vendorIds: [
        objectIdVendorIds[0],
        'vendor_1',
        '../admin',
        '',
      ],
    });
    const urls = entries.map((entry) => entry.url);

    assert.equal(urls.includes(`${baseUrl}/compare/missing-competitor`), false);
    assert.deepEqual(urlsFor('/resources/blog/', urls), [
      `${baseUrl}/resources/blog/how-to-price-wedding-planning-services`,
    ]);
    assert.deepEqual(urlsFor('/vendors/', urls), [
      `${baseUrl}/vendors/${objectIdVendorIds[0]}`,
    ]);
  });

  it('emits only canonical public route URLs that map to App Router pages', () => {
    const entries = buildSitemapEntries({
      baseUrl,
      now,
      compareSlugs: getCompareSupportedSlugs(),
      blogSlugs: ['how-to-price-wedding-planning-services'],
      vendorIds: objectIdVendorIds,
    });

    const privatePrefixes = [
      '/admin',
      '/api',
      '/couple',
      '/portal',
      '/pay',
      '/forms',
      '/vendor-form',
      '/vendor-contract',
      '/reset-password',
      '/setup-account',
      '/otp',
    ];

    for (const entry of entries) {
      const url = new URL(entry.url);
      assert.equal(url.origin, baseUrl);
      assert.equal(url.search, '', `sitemap URLs must not contain query strings: ${entry.url}`);
      assert.equal(url.hash, '', `sitemap URLs must not contain hashes: ${entry.url}`);
      assert.equal(
        privatePrefixes.some((prefix) => url.pathname.startsWith(prefix)),
        false,
        `private or token route leaked into sitemap: ${entry.url}`,
      );
      assert.equal(
        routeCandidatesFor(url.pathname).some((candidate) => existsSync(candidate)),
        true,
        `sitemap URL does not map to a public App Router page: ${entry.url}`,
      );
    }
  });

  it('does not keep a hardcoded blog fallback list in the runtime sitemap', () => {
    const source = readFileSync('app/sitemap.ts', 'utf8');

    assert.equal(source.includes('FALLBACK_BLOG_SLUGS'), false);
    for (const slug of staleStaticBlogSlugs) {
      assert.equal(source.includes(slug), false, `stale slug still appears in app/sitemap.ts: ${slug}`);
    }
  });
});
