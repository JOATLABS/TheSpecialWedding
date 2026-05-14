import type { MetadataRoute } from 'next';
import { getComparePageData } from './compare/data';

export type SitemapBuildInput = {
  baseUrl: string;
  now: Date;
  compareSlugs: readonly string[];
  blogSlugs: readonly string[];
  vendorIds: readonly string[];
};

const PUBLIC_SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const MONGO_OBJECT_ID_PATTERN = /^[a-f0-9]{24}$/i;

function uniqueRouteKeys(values: readonly string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function validPublicSlug(slug: string): boolean {
  return PUBLIC_SLUG_PATTERN.test(slug);
}

function hasCanonicalSitemapUrl(url: string): boolean {
  try {
    const parsedUrl = new URL(url);
    return parsedUrl.search === '' && parsedUrl.hash === '';
  } catch {
    return false;
  }
}

export function buildSitemapEntries({
  baseUrl,
  now,
  compareSlugs,
  blogSlugs,
  vendorIds,
}: SitemapBuildInput): MetadataRoute.Sitemap {
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: baseUrl,
      lastModified: now,
      changeFrequency: 'weekly',
      priority: 1,
    },
    {
      url: `${baseUrl}/features`,
      lastModified: now,
      changeFrequency: 'monthly',
      priority: 0.9,
    },
    {
      url: `${baseUrl}/compare`,
      lastModified: now,
      changeFrequency: 'monthly',
      priority: 0.9,
    },
    {
      url: `${baseUrl}/resources`,
      lastModified: now,
      changeFrequency: 'weekly',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/resources/templates`,
      lastModified: now,
      changeFrequency: 'weekly',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/vendors`,
      lastModified: now,
      changeFrequency: 'daily',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/privacy`,
      lastModified: now,
      changeFrequency: 'yearly',
      priority: 0.3,
    },
    {
      url: `${baseUrl}/terms`,
      lastModified: now,
      changeFrequency: 'yearly',
      priority: 0.3,
    },
    {
      url: `${baseUrl}/support`,
      lastModified: now,
      changeFrequency: 'monthly',
      priority: 0.4,
    },
    {
      url: `${baseUrl}/google-calendar`,
      lastModified: now,
      changeFrequency: 'yearly',
      priority: 0.2,
    },
    {
      url: `${baseUrl}/google-data-deletion`,
      lastModified: now,
      changeFrequency: 'yearly',
      priority: 0.2,
    },
  ];

  const comparePages: MetadataRoute.Sitemap = uniqueRouteKeys(compareSlugs)
    .filter((slug) => validPublicSlug(slug) && getComparePageData(slug))
    .map((slug) => ({
      url: `${baseUrl}/compare/${slug}`,
      lastModified: now,
      changeFrequency: 'monthly' as const,
      priority: 0.9,
    }));

  const blogPages: MetadataRoute.Sitemap = uniqueRouteKeys(blogSlugs)
    .filter(validPublicSlug)
    .map((slug) => ({
      url: `${baseUrl}/resources/blog/${slug}`,
      lastModified: now,
      changeFrequency: 'monthly' as const,
      priority: 0.7,
    }));

  const vendorPages: MetadataRoute.Sitemap = uniqueRouteKeys(vendorIds)
    .filter((id) => MONGO_OBJECT_ID_PATTERN.test(id))
    .map((id) => ({
      url: `${baseUrl}/vendors/${id}`,
      lastModified: now,
      changeFrequency: 'weekly' as const,
      priority: 0.6,
    }));

  return [...staticPages, ...comparePages, ...blogPages, ...vendorPages].filter((entry) =>
    hasCanonicalSitemapUrl(entry.url)
  );
}
