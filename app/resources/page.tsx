import ResourcesClient from './ResourcesClient';
import { fetchPublishedBlogArticles } from './blog/serverApi';
import {
  allowStaticFallback,
  apiArticleToBlogPost,
  fallbackBlogCards,
} from './resourcesShared';

export const revalidate = 60;

type ResourcesTab = 'blog' | 'templates' | 'faq';

function parseInitialTab(value: string | string[] | undefined): ResourcesTab {
  const tab = Array.isArray(value) ? value[0] : value;
  return tab === 'templates' || tab === 'faq' ? tab : 'blog';
}

export default async function ResourcesPage({
  searchParams,
}: {
  searchParams?: Promise<{ tab?: string | string[] }>;
}) {
  const params = searchParams ? await searchParams : {};
  const { articles, unavailable } = await fetchPublishedBlogArticles(50);
  const initialBlogPosts =
    articles.length > 0
      ? articles.map(apiArticleToBlogPost)
      : allowStaticFallback
        ? fallbackBlogCards
        : [];

  return (
    <ResourcesClient
      initialTab={parseInitialTab(params.tab)}
      initialBlogPosts={initialBlogPosts}
      initialBlogUnavailable={unavailable && !allowStaticFallback}
    />
  );
}
