import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Features — 18 Tools for Professional Wedding Planners',
  description:
    'Guest management, couple portal, seating charts, AI contracts, SMS reminders, vendor CRM, budget tracking, photo gallery, calendar sync, and more. See how The Special Wedding compares to HoneyBook, Aisle Planner, and Planning Pod.',
  metadataBase: new URL('https://thespecialwedding.io'),
  alternates: {
    canonical: '/features',
  },
  openGraph: {
    title: 'Features — 18 AI-Powered Tools for Professional Wedding Planners | The Special Wedding',
    description:
      'Couple portal, guest management, seating charts, AI contracts, SMS reminders, vendor CRM, budget tracking, photo gallery, and more. See how we compare to HoneyBook and Aisle Planner.',
    url: 'https://thespecialwedding.io/features',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding — 18 tools for wedding planners',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Features — 18 AI-Powered Tools for Professional Wedding Planners | The Special Wedding',
    description:
      'Couple portal, AI contracts, SMS reminders, seating charts, vendor CRM, budget tracking, photo gallery, and more — all in one wedding planning platform.',
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
