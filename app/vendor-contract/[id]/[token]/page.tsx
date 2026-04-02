import type { Metadata } from 'next';

import PublicContractPageClient from '../PublicContractPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Vendor Contract',
  robots: {
    index: false,
    follow: false,
  },
};

export default function PublicContractPage() {
  return <PublicContractPageClient />;
}
