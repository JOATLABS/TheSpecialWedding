import type { Metadata } from 'next';

import VendorFormPageClient from '../VendorFormPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Vendor Form',
  robots: {
    index: false,
    follow: false,
  },
};

export default function PublicVendorFormPage() {
  return <VendorFormPageClient />;
}
