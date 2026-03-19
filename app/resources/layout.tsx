import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Resources — Blog & FAQ for Wedding Planners',
  description:
    'Articles, guides, and answers for professional wedding planners. Pricing strategies, workflow tips, tool comparisons, and frequently asked questions.',
  openGraph: {
    title: 'Resources — Blog & FAQ for Wedding Planners | The Special Wedding',
    description:
      'Articles, guides, and answers for professional wedding planners. Pricing strategies, workflow tips, tool comparisons, and FAQs.',
  },
};

export default function ResourcesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
