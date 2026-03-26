import 'server-only';

import { getApiBaseUrl } from '@/utils/env';
import type { PublicBlogApiArticle } from '../resourcesShared';

const BLOG_REVALIDATE_SECONDS = 60;
const isProduction = process.env.NODE_ENV === 'production';

function resolveBlogApiBaseUrl(): string | null {
  try {
    return getApiBaseUrl();
  } catch (error) {
    if (isProduction) {
      throw error;
    }

    return null;
  }
}

function handleBlogFetchError<T>(fallbackValue: T, message: string, error?: unknown): T {
  if (isProduction) {
    if (error instanceof Error) {
      throw error;
    }

    throw new Error(message);
  }

  return fallbackValue;
}

export async function fetchPublishedBlogArticles(limit = 50): Promise<PublicBlogApiArticle[]> {
  const baseUrl = resolveBlogApiBaseUrl();
  if (!baseUrl) {
    return [];
  }

  try {
    const response = await fetch(`${baseUrl}/api/v1/blog/articles?limit=${limit}`, {
      next: { revalidate: BLOG_REVALIDATE_SECONDS },
    });

    if (!response.ok) {
      return handleBlogFetchError(
        [],
        `Failed to fetch published blog articles: HTTP ${response.status}`
      );
    }

    const data = await response.json();
    return Array.isArray(data?.articles) ? data.articles : [];
  } catch (error) {
    return handleBlogFetchError([], 'Failed to fetch published blog articles', error);
  }
}

export async function fetchArticleFromAPI(slug: string): Promise<PublicBlogApiArticle | null> {
  const baseUrl = resolveBlogApiBaseUrl();
  if (!baseUrl) {
    return null;
  }

  try {
    const response = await fetch(`${baseUrl}/api/v1/blog/articles/slug/${slug}`, {
      next: { revalidate: BLOG_REVALIDATE_SECONDS },
    });

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      return handleBlogFetchError(
        null,
        `Failed to fetch blog article "${slug}": HTTP ${response.status}`
      );
    }

    return await response.json();
  } catch (error) {
    return handleBlogFetchError(null, `Failed to fetch blog article "${slug}"`, error);
  }
}

export async function fetchPublishedBlogSlugs(): Promise<string[]> {
  const baseUrl = resolveBlogApiBaseUrl();
  if (!baseUrl) {
    return [];
  }

  try {
    const response = await fetch(`${baseUrl}/api/v1/blog/slugs`, {
      next: { revalidate: 3600 },
    });

    if (!response.ok) {
      return handleBlogFetchError(
        [],
        `Failed to fetch published blog slugs: HTTP ${response.status}`
      );
    }

    const data = await response.json();
    const slugs = Array.isArray(data) ? data : data?.slugs;
    return Array.isArray(slugs) ? slugs : [];
  } catch (error) {
    return handleBlogFetchError([], 'Failed to fetch published blog slugs', error);
  }
}
