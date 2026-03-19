import { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = 'https://thespecialwedding.io';

  return [
    {
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 1,
    },
    {
      url: `${baseUrl}/vendors`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/admin/login`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.3,
    },
    // Dynamic wedding pages (/{slug}) are generated per-wedding and
    // should be added dynamically if you want them indexed.
    // Dynamic vendor profiles (/vendors/{id}) are generated per-vendor
    // and should be added dynamically if you want them indexed.
  ];
}
