import { MetadataRoute } from 'next';
import { getApiBaseUrl } from '@/utils/env';
import { fetchPublishedBlogSlugs } from './resources/blog/serverApi';
import { getCompareSupportedSlugs } from './compare/data';

/**
 * Hardcoded fallback so the blog never disappears from the sitemap if the
 * backend API is down or slow at sitemap regeneration time. Update this list
 * when a new blog post ships, alongside `app/resources/blog/data.tsx`.
 */
const FALLBACK_BLOG_SLUGS = [
  'introducing-the-special-wedding',
  'how-to-price-wedding-planning-services',
  'honeybook-vs-aisle-planner',
  'wedding-planner-contract-essentials',
  'ai-changing-wedding-planning',
  'seating-chart-strategy',
  'the-built-in-wedding-website',
  'your-vendor-network-inside-the-platform',
  'why-your-couples-stop-texting-you',
  'real-time-planning-not-email-tag',
  'the-ops-layer-nobody-sees',
] as const;

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

  // Top-level marketing surfaces
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
      // Phase C marketing page — Free Wedding Planner Templates.
      // Static catalog of 9 downloadable templates; rebuilds rarely.
      url: `${baseUrl}/resources/templates`,
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
    // Legal + utility pages — low priority but discoverable
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

  // Per-competitor comparison pages — high commercial intent ("X alternative")
  const compareSlugs = getCompareSupportedSlugs();
  const comparePages: MetadataRoute.Sitemap = compareSlugs.map((slug) => ({
    url: `${baseUrl}/compare/${slug}`,
    lastModified: now,
    changeFrequency: 'monthly' as const,
    priority: 0.9,
  }));

  // Blog post pages — dynamic from API with hardcoded fallback so the blog can
  // never disappear when the backend is unreachable at sitemap regen time.
  const apiSlugs = await fetchPublishedBlogSlugs();
  const blogSlugSet = new Set<string>(apiSlugs);
  for (const slug of FALLBACK_BLOG_SLUGS) {
    blogSlugSet.add(slug);
  }
  const blogPages: MetadataRoute.Sitemap = Array.from(blogSlugSet).map((slug) => ({
    url: `${baseUrl}/resources/blog/${slug}`,
    lastModified: now,
    changeFrequency: 'monthly' as const,
    priority: 0.7,
  }));

  // Public vendor profile pages
  const vendorIds = await fetchVendorIds();
  const vendorPages: MetadataRoute.Sitemap = vendorIds.map((id) => ({
    url: `${baseUrl}/vendors/${id}`,
    lastModified: now,
    changeFrequency: 'weekly' as const,
    priority: 0.6,
  }));

  return [...staticPages, ...comparePages, ...blogPages, ...vendorPages];
}
