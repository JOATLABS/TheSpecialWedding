import type { Metadata, Viewport } from 'next';

export const metadata: Metadata = {
  title: 'Wedding Portal | The Special Wedding',
  description: 'Your personal wedding planning portal — manage registry, FAQs, schedule, and more',
  robots: {
    index: false,
    follow: false,
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'Wedding Portal',
  },
  manifest: '/manifest.json',
};

export const viewport: Viewport = {
  themeColor: '#0f172a',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

export default function CoupleLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      {children}
    </div>
  );
}
