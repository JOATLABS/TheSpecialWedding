import type { MetadataRoute } from 'next';

export type SitemapBuildInput = {
  baseUrl: string;
  now: Date;
  compareSlugs: readonly string[];
  blogSlugs: readonly string[];
  vendorIds: readonly string[];
};

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
      // First-class Resources tab for the free planner-template catalog.
      url: `${baseUrl}/resources?tab=templates`,
      lastModified: now,
      changeFrequency: 'monthly',
      priority: 0.9,
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

  const comparePages: MetadataRoute.Sitemap = compareSlugs.map((slug) => ({
    url: `${baseUrl}/compare/${slug}`,
    lastModified: now,
    changeFrequency: 'monthly' as const,
    priority: 0.9,
  }));

  const blogPages: MetadataRoute.Sitemap = blogSlugs.map((slug) => ({
    url: `${baseUrl}/resources/blog/${slug}`,
    lastModified: now,
    changeFrequency: 'monthly' as const,
    priority: 0.7,
  }));

  const vendorPages: MetadataRoute.Sitemap = vendorIds.map((id) => ({
    url: `${baseUrl}/vendors/${id}`,
    lastModified: now,
    changeFrequency: 'weekly' as const,
    priority: 0.6,
  }));

  return [...staticPages, ...comparePages, ...blogPages, ...vendorPages];
}
