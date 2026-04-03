import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import CoupleSetupPageClient from './CoupleSetupPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Couple Account Setup',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function CoupleSetupLegacyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const resolvedSearchParams = await searchParams;
  const queryToken = Array.isArray(resolvedSearchParams.token)
    ? resolvedSearchParams.token[0]
    : resolvedSearchParams.token;

  if (queryToken) {
    redirect(`/couple/setup/${encodeURIComponent(queryToken)}`);
  }

  return <CoupleSetupPageClient initialToken={null} />;
}
