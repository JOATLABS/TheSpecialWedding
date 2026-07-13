import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Features — One Connected Wedding Planner Workspace',
  description:
    'See how one planner-owned record connects the planner command center, couple experience, guests, seating, vendors, contracts, budgets, and wedding website.',
  metadataBase: new URL('https://thespecialwedding.io'),
  alternates: {
    canonical: '/features',
  },
  openGraph: {
    title: 'Features — One Connected Wedding Planner Workspace | The Special Wedding',
    description:
      'See the connected operating outcomes that protect planner time and give couples a calmer experience.',
    url: 'https://thespecialwedding.io/features',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding connected operating system for wedding planners',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Features — One Connected Wedding Planner Workspace | The Special Wedding',
    description:
      'See the connected operating outcomes that protect planner time and give couples a calmer experience.',
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
