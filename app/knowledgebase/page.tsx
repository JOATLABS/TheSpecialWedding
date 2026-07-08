import type { Metadata } from 'next';

import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import MarketingFooter from '@/components/saas/MarketingFooter';
import SaasNav from '@/components/saas/SaasNav';
import { serializeJsonLd } from '@/seo/jsonLd';
import KnowledgebaseClient from './KnowledgebaseClient';
import {
  fetchPublicKBArticleBySlug,
  fetchPublicKBArticles,
  fetchPublicKBCategories,
} from './serverApi';

const KNOWLEDGEBASE_PATH = '/knowledgebase';
const KNOWLEDGEBASE_URL = `https://thespecialwedding.io${KNOWLEDGEBASE_PATH}`;

export const revalidate = 60;

export const metadata: Metadata = {
  title: 'Knowledgebase | The Special Wedding',
  description:
    'Public read-only documentation for The Special Wedding planner workflows, calendar setup, billing, troubleshooting, and platform guides.',
  alternates: {
    canonical: KNOWLEDGEBASE_PATH,
  },
  openGraph: {
    title: 'Knowledgebase | The Special Wedding',
    description:
      'Read published setup guides, calendar help, billing notes, and planner workflow documentation without signing in.',
    url: KNOWLEDGEBASE_URL,
    siteName: 'The Special Wedding',
    type: 'website',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding knowledgebase',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Knowledgebase | The Special Wedding',
    description:
      'Read published setup guides, calendar help, billing notes, and planner workflow documentation.',
    images: ['/og-image.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
};

const collectionJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'CollectionPage',
  '@id': KNOWLEDGEBASE_URL,
  url: KNOWLEDGEBASE_URL,
  name: 'The Special Wedding Knowledgebase',
  description:
    'Published help documentation and platform guides for The Special Wedding.',
};

function getSearchParam(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value || '').trim();
}

export default async function KnowledgebasePage({
  searchParams,
}: {
  searchParams?: Promise<{
    article?: string | string[];
    category?: string | string[];
    q?: string | string[];
  }>;
}) {
  const params = searchParams ? await searchParams : {};
  const initialArticleSlug = getSearchParam(params.article);
  const initialCategory = getSearchParam(params.category) || 'all';
  const initialQuery = getSearchParam(params.q);

  const [{ data: articlesData, unavailable: articlesUnavailable }, { data: categoriesData, unavailable: categoriesUnavailable }, initialArticle] =
    await Promise.all([
      fetchPublicKBArticles({
        category: initialCategory,
        search: initialQuery,
      }),
      fetchPublicKBCategories(),
      initialArticleSlug ? fetchPublicKBArticleBySlug(initialArticleSlug) : Promise.resolve(null),
    ]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Knowledgebase', href: KNOWLEDGEBASE_PATH },
        ]}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(collectionJsonLd) }}
      />
      <KnowledgebaseClient
        initialArticles={articlesData}
        initialCategories={categoriesData?.categories ?? []}
        initialArticle={initialArticle}
        initialCategory={initialCategory}
        initialQuery={initialQuery}
        initialUnavailable={articlesUnavailable || categoriesUnavailable}
      />
      <MarketingFooter />
    </main>
  );
}
