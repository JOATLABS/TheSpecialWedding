import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Features — 22 Tools for Professional Wedding Planners',
  description:
    'Planner CRM, couple portal, built-in wedding microsite, vendor network, AI contracts, SMS reminders, seating charts, budget tracking, and more — the complete workspace for planners, couples, and vendors. See how The Special Wedding compares to HoneyBook, Aisle Planner, and Planning Pod.',
  metadataBase: new URL('https://thespecialwedding.io'),
  alternates: {
    canonical: '/features',
  },
  openGraph: {
    title: 'Features — 22 AI-Powered Tools for Professional Wedding Planners | The Special Wedding',
    description:
      'Planner CRM, couple portal, built-in wedding microsite, vendor network, AI contracts, SMS reminders, and more. See how we compare to HoneyBook and Aisle Planner.',
    url: 'https://thespecialwedding.io/features',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding — 22 tools for wedding planners',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Features — 22 AI-Powered Tools for Professional Wedding Planners | The Special Wedding',
    description:
      'Planner CRM, couple portal, built-in wedding microsite, vendor network, AI contracts, SMS reminders, and more — the complete wedding workspace.',
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
