import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Special Wedding - Professional Wedding Planning Platform',
  description: 'The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.',
  keywords: 'wedding planning, wedding planner software, wedding management, wedding website builder, AI wedding tools',
  openGraph: {
    title: 'Special Wedding - Professional Wedding Planning Platform',
    description: 'Transform your wedding planning business with our comprehensive platform featuring AI-powered tools, vendor collaboration, and beautiful wedding websites.',
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
    title: 'Special Wedding - Professional Wedding Planning Platform',
    description: 'Transform your wedding planning business with our comprehensive platform featuring AI-powered tools, vendor collaboration, and beautiful wedding websites.',
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