import ResourcesClient from './ResourcesClient';
import { loadResourceBlogPosts } from './blogListData';

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
  const { initialBlogPosts, initialBlogUnavailable } = await loadResourceBlogPosts(50);

  return (
    <ResourcesClient
      initialTab={parseInitialTab(params.tab)}
      initialBlogPosts={initialBlogPosts}
      initialBlogUnavailable={initialBlogUnavailable}
    />
  );
}
