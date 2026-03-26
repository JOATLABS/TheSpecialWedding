import ResourcesClient from './ResourcesClient';
import { fetchPublishedBlogArticles } from './blog/serverApi';
import {
  allowStaticFallback,
  apiArticleToBlogPost,
  fallbackBlogCards,
} from './resourcesShared';

export const revalidate = 60;

export default async function ResourcesPage() {
  const articles = await fetchPublishedBlogArticles(50);
  const initialBlogPosts =
    articles.length > 0
      ? articles.map(apiArticleToBlogPost)
      : allowStaticFallback
        ? fallbackBlogCards
        : [];

  return <ResourcesClient initialBlogPosts={initialBlogPosts} />;
}
