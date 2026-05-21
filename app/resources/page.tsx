import { permanentRedirect } from 'next/navigation';

type ResourcesTab = 'blog' | 'templates' | 'faq';

const RESOURCES_TAB_PATHS: Record<ResourcesTab, string> = {
  blog: '/resources/blog',
  templates: '/resources/templates',
  faq: '/resources/faq',
};

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
  permanentRedirect(RESOURCES_TAB_PATHS[parseInitialTab(params.tab)]);
}
