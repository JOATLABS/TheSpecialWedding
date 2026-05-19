import type { Metadata } from 'next';

import ResourcesClient from '../ResourcesClient';
import { loadResourceBlogPosts } from '../blogListData';

const BLOG_PATH = '/resources/blog';
const BLOG_URL = `https://thespecialwedding.io${BLOG_PATH}`;

export const revalidate = 60;

export const metadata: Metadata = {
  title: 'Wedding Planner Blog | The Special Wedding',
  description:
    'Read The Special Wedding blog for wedding planner pricing strategies, workflow tips, AI planning guidance, and software comparisons.',
  alternates: {
    canonical: BLOG_PATH,
  },
  openGraph: {
    title: 'Wedding Planner Blog | The Special Wedding',
    description:
      'Pricing strategies, workflow tips, AI planning guidance, and software comparisons for professional wedding planners.',
    url: BLOG_URL,
    siteName: 'The Special Wedding',
    type: 'website',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding blog',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Wedding Planner Blog | The Special Wedding',
    description:
      'Pricing strategies, workflow tips, AI planning guidance, and software comparisons for professional wedding planners.',
    images: ['/og-image.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default async function ResourcesBlogPage() {
  const { initialBlogPosts, initialBlogUnavailable } = await loadResourceBlogPosts(50);

  return (
    <ResourcesClient
      initialTab="blog"
      initialBlogPosts={initialBlogPosts}
      initialBlogUnavailable={initialBlogUnavailable}
    />
  );
}
