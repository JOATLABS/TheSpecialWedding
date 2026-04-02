import type { Metadata } from 'next';

import CoupleSetupPageClient from '../CoupleSetupPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Couple Account Setup',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function CoupleSetupCanonicalPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;

  return <CoupleSetupPageClient initialToken={token} />;
}
