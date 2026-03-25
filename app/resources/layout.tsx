import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Resources — Blog & FAQ for Wedding Planners',
  description:
    'Articles, guides, and answers for professional wedding planners. Pricing strategies, workflow tips, tool comparisons, and frequently asked questions.',
  metadataBase: new URL('https://thespecialwedding.io'),
  alternates: {
    canonical: '/resources',
  },
  openGraph: {
    title: 'Resources — Blog & FAQ for Wedding Planners | The Special Wedding',
    description:
      'Articles, guides, and answers for professional wedding planners. Pricing strategies, workflow tips, tool comparisons, and FAQs.',
    url: 'https://thespecialwedding.io/resources',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding resources hub',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Resources — Blog & FAQ for Wedding Planners | The Special Wedding',
    description:
      'Articles, guides, and answers for professional wedding planners. Pricing strategies, workflow tips, tool comparisons, and FAQs.',
    images: ['/og-image.png'],
  },
};

export default function ResourcesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
