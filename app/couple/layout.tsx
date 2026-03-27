import type { Metadata, Viewport } from 'next';
import CoupleLayoutClient from './components/CoupleLayoutClient';
import CoupleRouteGuard from '@/components/CoupleRouteGuard';
import { CoupleAuthProvider } from '@/contexts/CoupleAuthContext';

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
    <CoupleAuthProvider>
      <CoupleLayoutClient>
        <CoupleRouteGuard>{children}</CoupleRouteGuard>
      </CoupleLayoutClient>
    </CoupleAuthProvider>
  );
}
