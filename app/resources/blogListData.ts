import 'server-only';

import { fetchPublishedBlogArticles } from './blog/serverApi';
import {
  allowStaticFallback,
  apiArticleToBlogPost,
  fallbackBlogCards,
} from './resourcesShared';
import type { BlogPost } from './resourcesShared';

export async function loadResourceBlogPosts(limit = 50): Promise<{
  initialBlogPosts: BlogPost[];
  initialBlogUnavailable: boolean;
}> {
  const { articles, unavailable } = await fetchPublishedBlogArticles(limit);
  const initialBlogPosts =
    articles.length > 0
      ? articles.map(apiArticleToBlogPost)
      : allowStaticFallback
        ? fallbackBlogCards
        : [];

  return {
    initialBlogPosts,
    initialBlogUnavailable: unavailable && !allowStaticFallback,
  };
}
