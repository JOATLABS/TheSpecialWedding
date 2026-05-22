import type { Metadata } from 'next';

import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import { serializeJsonLd } from '@/seo/jsonLd';

import ResourcesClient from '../ResourcesClient';
import { loadResourceBlogPosts } from '../blogListData';
import { faqs } from '../resourcesShared';

const SITE_URL = 'https://thespecialwedding.io';
const FAQ_PATH = '/resources/faq';
const FAQ_URL = `${SITE_URL}${FAQ_PATH}`;

export const revalidate = 60;

export const metadata: Metadata = {
  title: 'Wedding Planner FAQ | The Special Wedding',
  description:
    'Answers to common questions about The Special Wedding for professional wedding planners, including pricing, features, security, and day-of support.',
  alternates: {
    canonical: FAQ_PATH,
  },
  openGraph: {
    title: 'Wedding Planner FAQ | The Special Wedding',
    description:
      'Answers to common questions about pricing, features, security, and day-of support for professional wedding planners.',
    url: FAQ_URL,
    siteName: 'The Special Wedding',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Wedding Planner FAQ | The Special Wedding',
    description:
      'Answers to common questions about pricing, features, security, and day-of support.',
  },
  robots: {
    index: true,
    follow: true,
  },
};

const faqJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  '@id': FAQ_URL,
  url: FAQ_URL,
  mainEntity: faqs.map((faq) => ({
    '@type': 'Question',
    name: faq.question,
    acceptedAnswer: {
      '@type': 'Answer',
      text: faq.answer,
    },
  })),
};

export default async function ResourcesFaqPage() {
  const { initialBlogPosts, initialBlogUnavailable } = await loadResourceBlogPosts(50);

  return (
    <>
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Resources', href: '/resources/blog' },
          { name: 'FAQ', href: FAQ_PATH },
        ]}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(faqJsonLd) }}
      />
      <ResourcesClient
        initialTab="faq"
        initialBlogPosts={initialBlogPosts}
        initialBlogUnavailable={initialBlogUnavailable}
      />
    </>
  );
}
