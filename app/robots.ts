import { MetadataRoute } from 'next';

/**
 * robots.txt source.
 *
 * Pairs with ``app/main.py::add_robots_headers``. Non-public surfaces
 * (admin/auth/api/couple-portal) are NOT Disallow'd here — if we block
 * crawling, Googlebot can't fetch them to read the
 * ``X-Robots-Tag: noindex`` header that actually removes them from the
 * index. Once GSC reports them as de-indexed we can re-add Disallow for
 * crawl-budget protection.
 *
 * See docs/seo/INDEXING.md for the full reasoning and the GSC "Some
 * fixes failed" forensic trail (2026-05-14).
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        // Intentionally minimal: the X-Robots-Tag middleware is the
        // primary de-indexing mechanism. ``/admin/login`` stays
        // crawlable + indexable (public sign-in landing). Everything
        // else under /admin, /api, /otp, /setup-account,
        // /reset-password, /forgot-password, /token, /auth,
        // /couple-portal, /couple/, /vendor-contract is served with
        // ``X-Robots-Tag: noindex, nofollow`` so Google removes it
        // from the index on re-crawl.
        disallow: [],
      },
    ],
    sitemap: 'https://thespecialwedding.io/sitemap.xml',
  };
}
