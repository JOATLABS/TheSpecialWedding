import type { Metadata } from 'next';
import SaasNav from '../components/saas/SaasNav';
import { COMPARE_AUDIT_STAMP } from './data';

export const metadata: Metadata = {
  title: 'Compare The Special Wedding | HoneyBook and Aisle Planner Alternatives',
  description:
    `Side-by-side comparisons for wedding planners evaluating The Special Wedding against HoneyBook and Aisle Planner. Updated against official competitor sources reviewed on ${COMPARE_AUDIT_STAMP}.`,
  keywords: [
    'HoneyBook alternative',
    'Aisle Planner alternative',
    'wedding planner comparison',
    'wedding planning software comparison',
  ],
  metadataBase: new URL('https://thespecialwedding.io'),
  alternates: {
    canonical: '/compare',
  },
  openGraph: {
    title: 'Compare The Special Wedding',
    description:
      'Side-by-side comparisons for wedding planners evaluating The Special Wedding against HoneyBook and Aisle Planner.',
    url: 'https://thespecialwedding.io/compare',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Special Wedding comparison pages',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@thespecialwedding',
    title: 'Compare The Special Wedding',
    description:
      'Side-by-side comparisons for wedding planners evaluating The Special Wedding against HoneyBook and Aisle Planner.',
    images: ['/og-image.png'],
  },
};

export default function CompareLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      {children}
    </div>
  );
}
