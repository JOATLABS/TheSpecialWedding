import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import PublicContractPageClient from './PublicContractPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Vendor Contract',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function PublicContractLegacyPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const { id } = await params;
  const resolvedSearchParams = await searchParams;
  const queryToken = Array.isArray(resolvedSearchParams.token)
    ? resolvedSearchParams.token[0]
    : resolvedSearchParams.token;

  if (queryToken) {
    redirect(`/vendor-contract/${id}/${encodeURIComponent(queryToken)}`);
  }

  return <PublicContractPageClient />;
}
