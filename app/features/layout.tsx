import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Features — 13 Tools for Professional Wedding Planners',
  description:
    'Guest management, seating charts, AI contracts, vendor CRM, budget tracking, and more. See how The Special Wedding compares to HoneyBook, Aisle Planner, and Planning Pod.',
  metadataBase: new URL('https://thespecialwedding.io'),
  alternates: {
    canonical: '/features',
  },
  openGraph: {
    title: 'Features — 13 Tools for Professional Wedding Planners | The Special Wedding',
    description:
      'Guest management, seating charts, AI contracts, vendor CRM, budget tracking, and more. See how we compare to HoneyBook and Aisle Planner.',
    url: 'https://thespecialwedding.io/features',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding feature overview',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Features — 13 Tools for Professional Wedding Planners | The Special Wedding',
    description:
      'Explore planner dashboards, couple portals, forms, payments, contracts, and more in one wedding planning platform.',
    images: ['/og-image.png'],
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
