import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'The Special Wedding — Software for Professional Wedding Planners',
  description: 'Manage multiple weddings, coordinate vendors, track budgets, and run your planning business — all from one AI-powered platform built for professional planners.',
  keywords: 'wedding planner software, wedding planning business software, wedding vendor management, wedding planner CRM, AI wedding tools, HoneyBook alternative',
  openGraph: {
    title: 'The Special Wedding — Software for Professional Wedding Planners',
    description: 'Manage multiple weddings, coordinate vendors, track budgets, and run your planning business from one AI-powered platform.',
    type: 'website',
    images: [
      {
        url: '/images/saas-og-image.jpg',
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
    images: ['/images/saas-og-image.jpg'],
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