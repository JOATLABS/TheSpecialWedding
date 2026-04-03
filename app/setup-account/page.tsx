import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import SetupAccountPageClient from './SetupAccountPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Account Setup',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function SetupAccountLegacyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const resolvedSearchParams = await searchParams;
  const queryToken = Array.isArray(resolvedSearchParams.token)
    ? resolvedSearchParams.token[0]
    : resolvedSearchParams.token;

  if (queryToken) {
    redirect(`/setup-account/${encodeURIComponent(queryToken)}`);
  }

  return <SetupAccountPageClient initialToken={null} />;
}
