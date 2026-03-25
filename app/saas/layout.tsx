import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'The Special Wedding — Software for Professional Wedding Planners',
  description: 'Manage multiple weddings, coordinate vendors, track budgets, and run your planning business — all from one AI-powered platform built for professional planners.',
  keywords: 'wedding planner software, wedding planning business software, wedding vendor management, wedding planner CRM, AI wedding tools, HoneyBook alternative',
  metadataBase: new URL('https://thespecialwedding.io'),
  alternates: {
    canonical: '/saas',
  },
  openGraph: {
    title: 'The Special Wedding — Software for Professional Wedding Planners',
    description: 'Manage multiple weddings, coordinate vendors, track budgets, and run your planning business from one AI-powered platform.',
    type: 'website',
    url: 'https://thespecialwedding.io/saas',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Special Wedding Platform',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'The Special Wedding — Software for Professional Wedding Planners',
    description: 'Manage multiple weddings, coordinate vendors, track budgets, and run your planning business from one AI-powered platform.',
    images: ['/og-image.png'],
  },
};

export default function SaasLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="saas-layout">
      {children}
    </div>
  );
}
