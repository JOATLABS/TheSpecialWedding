import 'server-only';

import { getApiBaseUrl } from '@/utils/env';
import type { PublicBlogApiArticle } from '../resourcesShared';

const BLOG_REVALIDATE_SECONDS = 60;
const isProduction = process.env.NODE_ENV === 'production';

function resolveBlogApiBaseUrl(failHard = false): string | null {
  try {
    return getApiBaseUrl();
  } catch (error) {
    if (failHard && isProduction) {
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

export interface PublishedBlogArticlesResult {
  articles: PublicBlogApiArticle[];
  unavailable: boolean;
}

export async function fetchPublishedBlogArticles(limit = 50): Promise<PublishedBlogArticlesResult> {
  const baseUrl = resolveBlogApiBaseUrl();
  if (!baseUrl) {
    return { articles: [], unavailable: true };
  }

  try {
    const response = await fetch(`${baseUrl}/api/v1/blog/articles?limit=${limit}`, {
      next: { revalidate: BLOG_REVALIDATE_SECONDS },
    });

    if (!response.ok) {
      return { articles: [], unavailable: true };
    }

    const data = await response.json();
    if (!Array.isArray(data?.articles)) {
      return { articles: [], unavailable: true };
    }

    return { articles: data.articles, unavailable: false };
  } catch {
    return { articles: [], unavailable: true };
  }
}

export async function fetchArticleFromAPI(slug: string): Promise<PublicBlogApiArticle | null> {
  const baseUrl = resolveBlogApiBaseUrl(true);
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
      return [];
    }

    const data = await response.json();
    const slugs = Array.isArray(data) ? data : data?.slugs;
    return Array.isArray(slugs) ? slugs : [];
  } catch {
    return [];
  }
}
