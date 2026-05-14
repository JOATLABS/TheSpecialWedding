import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Vendor Directory',
  description: 'Browse wedding vendors by category — photographers, caterers, florists, venues, and more. View profiles, pricing, and portfolios.',
  metadataBase: new URL('https://thespecialwedding.io'),
  alternates: {
    canonical: '/vendors',
  },
  openGraph: {
    title: 'Vendor Directory | The Special Wedding',
    description: 'Browse wedding vendors by category — photographers, caterers, florists, venues, and more. View profiles, pricing, and portfolios.',
    url: 'https://thespecialwedding.io/vendors',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding vendor directory',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@thespecialwedding',
    title: 'Vendor Directory | The Special Wedding',
    description: 'Browse wedding vendors by category — photographers, caterers, florists, venues, and more. View profiles, pricing, and portfolios.',
    images: ['/og-image.png'],
  },
};

export default function VendorsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
