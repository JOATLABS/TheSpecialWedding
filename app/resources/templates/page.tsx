import type { Metadata } from 'next';

import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import { serializeJsonLd } from '@/seo/jsonLd';

import ResourcesClient from '../ResourcesClient';
import { loadResourceBlogPosts } from '../blogListData';
import { MARKETING_TEMPLATES } from './manifest';

const SITE_URL = 'https://thespecialwedding.io';
const TEMPLATES_PATH = '/resources/templates';
const TEMPLATES_URL = `${SITE_URL}${TEMPLATES_PATH}`;

export const revalidate = 60;

export const metadata: Metadata = {
  title: 'Free Wedding Planner Templates | Download 9 Planner PDFs',
  description:
    'Download free wedding planner templates for client intake, wedding timelines, vendor onboarding, guest needs, shot lists, and day-of contacts.',
  alternates: {
    canonical: TEMPLATES_PATH,
  },
  openGraph: {
    title: 'Free Wedding Planner Templates',
    description:
      'Nine production-ready wedding planning templates for intake, timelines, vendors, guests, shot lists, and day-of contacts.',
    url: TEMPLATES_URL,
    siteName: 'The Special Wedding',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Free Wedding Planner Templates',
    description:
      'Download 9 free wedding planner templates built for real client and vendor workflows.',
  },
  robots: {
    index: true,
    follow: true,
  },
};

const templatesJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'CollectionPage',
      '@id': TEMPLATES_URL,
      url: TEMPLATES_URL,
      name: 'Free Wedding Planner Templates',
      description:
        'A collection of free wedding planner templates for intake, timelines, vendor onboarding, guest needs, shot lists, and day-of contacts.',
      mainEntity: {
        '@id': `${TEMPLATES_URL}#template-list`,
      },
    },
    {
      '@type': 'ItemList',
      '@id': `${TEMPLATES_URL}#template-list`,
      name: 'Free Wedding Planner Templates',
      numberOfItems: MARKETING_TEMPLATES.length,
      itemListElement: MARKETING_TEMPLATES.map((template, index) => ({
        '@type': 'ListItem',
        position: index + 1,
        item: {
          '@id': `${TEMPLATES_URL}#${template.id}`,
        },
      })),
    },
    ...MARKETING_TEMPLATES.map((template) => ({
      '@type': 'CreativeWork',
      '@id': `${TEMPLATES_URL}#${template.id}`,
      url: `${TEMPLATES_URL}#${template.id}`,
      name: template.name,
      description: template.description,
      genre: template.category,
      isAccessibleForFree: true,
      publisher: {
        '@type': 'Organization',
        name: 'The Special Wedding',
        url: SITE_URL,
      },
    })),
  ],
};

export default async function PublicTemplatesPage() {
  const { initialBlogPosts, initialBlogUnavailable } = await loadResourceBlogPosts(50);

  return (
    <>
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Resources', href: '/resources/blog' },
          { name: 'Templates', href: TEMPLATES_PATH },
        ]}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(templatesJsonLd) }}
      />
      <ResourcesClient
        initialTab="templates"
        initialBlogPosts={initialBlogPosts}
        initialBlogUnavailable={initialBlogUnavailable}
      />
    </>
  );
}
