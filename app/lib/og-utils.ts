import { getApiBaseUrl } from '@/utils/env';
import type { PublicBlogApiArticle } from '@/resources/resourcesShared';

export type OgTarget =
  | { type: 'blog'; slug: string }
  | { type: 'vendor'; id: string };

export type OgCardData = {
  title: string;
  subtitle: string;
  kicker: string;
  badge: string;
  footer: string;
  accent: 'rose' | 'gold';
};

const BLOG_FALLBACK: OgCardData = {
  title: 'The Special Wedding',
  subtitle: 'Wedding planning software for professional planners',
  kicker: 'Marketing Platform',
  badge: 'TSW',
  footer: 'thespecialwedding.io',
  accent: 'rose',
};

const VENDOR_FALLBACK: OgCardData = {
  title: 'Vendor profile unavailable',
  subtitle: 'Wedding vendor directory',
  kicker: 'Public Vendor',
  badge: 'TSW',
  footer: 'thespecialwedding.io/vendors',
  accent: 'gold',
};

export function truncateText(value: string, maxLength: number): string {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }

  const slice = normalized.slice(0, maxLength - 1);
  const lastSpace = slice.lastIndexOf(' ');

  if (lastSpace > maxLength * 0.6) {
    return `${slice.slice(0, lastSpace)}…`;
  }

  return `${slice.trimEnd()}…`;
}

export function formatOgDate(value?: string | null): string {
  if (!value) {
    return '';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '';
  }

  return parsed.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function normalizeCategory(category?: string | null): string {
  if (!category) {
    return 'Wedding vendor';
  }

  return category.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function resolveBlogSubtitle(article: PublicBlogApiArticle): string {
  const dateSource = article.published_at || article.created_at || article.date || '';
  const formattedDate = formatOgDate(dateSource);
  return formattedDate ? `${formattedDate} • Blog post` : 'Blog post';
}

export function buildBlogFallbackCard(): OgCardData {
  return BLOG_FALLBACK;
}

export function buildVendorFallbackCard(): OgCardData {
  return VENDOR_FALLBACK;
}

export function buildBlogCardData(article: PublicBlogApiArticle): OgCardData {
  const titleSource = article.meta_title || article.title;
  const subtitle = resolveBlogSubtitle(article);

  return {
    title: truncateText(titleSource || BLOG_FALLBACK.title, 88),
    subtitle,
    kicker: article.category ? normalizeCategory(article.category) : 'Blog',
    badge: 'Blog',
    footer: article.author_name ? `By ${article.author_name}` : BLOG_FALLBACK.footer,
    accent: 'rose',
  };
}

export function buildVendorCardData(vendor: {
  business_name?: string;
  service_category?: string;
  custom_service_category?: string;
  city?: string;
  state?: string;
}): OgCardData {
  const categoryLabel =
    vendor.service_category === 'other' && vendor.custom_service_category?.trim()
      ? vendor.custom_service_category.trim()
      : vendor.service_category
        ? normalizeCategory(vendor.service_category)
        : 'Wedding vendor';

  const location = [vendor.city, vendor.state].filter(Boolean).join(', ');

  return {
    title: truncateText(vendor.business_name || VENDOR_FALLBACK.title, 88),
    subtitle: location ? `${location} • Vendor profile` : 'Vendor profile',
    kicker: categoryLabel,
    badge: 'Vendor',
    footer: 'The Special Wedding vendor directory',
    accent: 'gold',
  };
}

export async function fetchBlogArticleForOg(slug: string): Promise<PublicBlogApiArticle | null> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/v1/blog/articles/slug/${encodeURIComponent(slug)}`, {
    next: { revalidate: 600 },
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as PublicBlogApiArticle;
}

export async function fetchVendorForOg(id: string): Promise<{
  business_name?: string;
  service_category?: string;
  custom_service_category?: string;
  city?: string;
  state?: string;
} | null> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/v1/vendors/${encodeURIComponent(id)}/public`, {
    next: { revalidate: 600 },
  });

  if (!response.ok) {
    return null;
  }

  return await response.json();
}
