import 'server-only';

import { getApiBaseUrl } from '@/utils/env';
import type {
  PublicKBArticle,
  PublicKBArticlesResponse,
  PublicKBCategoriesResponse,
} from './types';

const KNOWLEDGEBASE_REVALIDATE_SECONDS = 60;
const isProduction = process.env.NODE_ENV === 'production';

function resolveKnowledgebaseApiBaseUrl(failHard = false): string | null {
  try {
    return getApiBaseUrl();
  } catch (error) {
    if (failHard && isProduction) {
      throw error;
    }

    return null;
  }
}

function buildSearchParams(params: Record<string, string | number | undefined>): string {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      searchParams.set(key, String(value));
    }
  });

  return searchParams.toString();
}

export async function fetchPublicKBArticles({
  category,
  search,
  limit = 12,
}: {
  category?: string;
  search?: string;
  limit?: number;
} = {}): Promise<{ data: PublicKBArticlesResponse | null; unavailable: boolean }> {
  const baseUrl = resolveKnowledgebaseApiBaseUrl();
  if (!baseUrl) {
    return { data: null, unavailable: true };
  }

  const query = buildSearchParams({
    limit,
    category: category && category !== 'all' ? category : undefined,
    search: search && search.length >= 2 ? search : undefined,
  });

  try {
    const response = await fetch(`${baseUrl}/public/kb/articles?${query}`, {
      next: { revalidate: KNOWLEDGEBASE_REVALIDATE_SECONDS },
    });

    if (!response.ok) {
      return { data: null, unavailable: true };
    }

    const data = await response.json();
    if (!Array.isArray(data?.articles)) {
      return { data: null, unavailable: true };
    }

    return { data, unavailable: false };
  } catch {
    return { data: null, unavailable: true };
  }
}

export async function fetchPublicKBCategories(): Promise<{
  data: PublicKBCategoriesResponse | null;
  unavailable: boolean;
}> {
  const baseUrl = resolveKnowledgebaseApiBaseUrl();
  if (!baseUrl) {
    return { data: null, unavailable: true };
  }

  try {
    const response = await fetch(`${baseUrl}/public/kb/categories`, {
      next: { revalidate: KNOWLEDGEBASE_REVALIDATE_SECONDS },
    });

    if (!response.ok) {
      return { data: null, unavailable: true };
    }

    const data = await response.json();
    if (!Array.isArray(data?.categories)) {
      return { data: null, unavailable: true };
    }

    return { data, unavailable: false };
  } catch {
    return { data: null, unavailable: true };
  }
}

export async function fetchPublicKBArticleBySlug(slug: string): Promise<PublicKBArticle | null> {
  const baseUrl = resolveKnowledgebaseApiBaseUrl(true);
  if (!baseUrl) {
    return null;
  }

  try {
    const response = await fetch(`${baseUrl}/public/kb/articles/slug/${encodeURIComponent(slug)}`, {
      next: { revalidate: KNOWLEDGEBASE_REVALIDATE_SECONDS },
    });

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch (error) {
    if (isProduction && error instanceof Error) {
      throw error;
    }

    return null;
  }
}
