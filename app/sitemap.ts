import { MetadataRoute } from 'next';
import { getApiBaseUrl } from '@/utils/env';

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

  const staticPages: MetadataRoute.Sitemap = [
    {
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 1,
    },
    {
      url: `${baseUrl}/features`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.9,
    },
    {
      url: `${baseUrl}/resources`,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/vendors`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.8,
    },
  ];

  // Blog post pages
  const blogSlugs = [
    'introducing-the-special-wedding',
    'how-to-price-wedding-planning-services',
    'managing-200-guests',
    'honeybook-vs-aisle-planner',
    'wedding-planner-contract-essentials',
    'ai-changing-wedding-planning',
    'seating-chart-strategy',
  ];
  const blogPages: MetadataRoute.Sitemap = blogSlugs.map((slug) => ({
    url: `${baseUrl}/resources/blog/${slug}`,
    lastModified: new Date(),
    changeFrequency: 'monthly' as const,
    priority: 0.7,
  }));

  // Dynamically include vendor profile pages
  const vendorIds = await fetchVendorIds();
  const vendorPages: MetadataRoute.Sitemap = vendorIds.map((id) => ({
    url: `${baseUrl}/vendors/${id}`,
    lastModified: new Date(),
    changeFrequency: 'weekly' as const,
    priority: 0.6,
  }));

  return [...staticPages, ...blogPages, ...vendorPages];
}
