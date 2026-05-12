import { MetadataRoute } from 'next';
import { getApiBaseUrl } from '@/utils/env';
import { fetchPublishedBlogSlugs } from './resources/blog/serverApi';
import { getCompareSupportedSlugs } from './compare/data';
import { buildSitemapEntries } from './sitemapEntries';

async function fetchVendorIds(): Promise<string[]> {
  try {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/vendors/sitemap-ids`, {
      next: { revalidate: 86400 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = 'https://thespecialwedding.io';
  const now = new Date();

  // Per-competitor comparison pages — high commercial intent ("X alternative")
  const compareSlugs = getCompareSupportedSlugs();

  // Blog post pages are API-published articles only. Static blog fallback
  // content is development-only and can produce production 404s if sitemaped.
  const blogSlugs = await fetchPublishedBlogSlugs();

  // Public vendor profile pages
  const vendorIds = await fetchVendorIds();

  return buildSitemapEntries({
    baseUrl,
    now,
    compareSlugs,
    blogSlugs,
    vendorIds,
  });
}
