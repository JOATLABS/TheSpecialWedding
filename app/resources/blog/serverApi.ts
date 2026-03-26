import 'server-only';

import type { PublicBlogApiArticle } from '../resourcesShared';

const BLOG_REVALIDATE_SECONDS = 60;

export async function fetchPublishedBlogArticles(limit = 50): Promise<PublicBlogApiArticle[]> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!baseUrl) {
      return [];
    }

    const response = await fetch(`${baseUrl}/api/v1/blog/articles?limit=${limit}`, {
      next: { revalidate: BLOG_REVALIDATE_SECONDS },
    });

    if (!response.ok) {
      return [];
    }

    const data = await response.json();
    return Array.isArray(data?.articles) ? data.articles : [];
  } catch {
    return [];
  }
}

export async function fetchArticleFromAPI(slug: string): Promise<PublicBlogApiArticle | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!baseUrl) {
      return null;
    }

    const response = await fetch(`${baseUrl}/api/v1/blog/articles/slug/${slug}`, {
      next: { revalidate: BLOG_REVALIDATE_SECONDS },
    });

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch {
    return null;
  }
}
