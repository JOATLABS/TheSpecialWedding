import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import VendorFormPageClient from './VendorFormPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Vendor Form',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function PublicVendorFormLegacyPage({
  params,
  searchParams,
}: {
  params: Promise<{ form_id: string }>;
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const { form_id } = await params;
  const resolvedSearchParams = await searchParams;
  const queryToken = Array.isArray(resolvedSearchParams.token)
    ? resolvedSearchParams.token[0]
    : resolvedSearchParams.token;

  if (queryToken) {
    redirect(`/vendor-form/${form_id}/${encodeURIComponent(queryToken)}`);
  }

  return <VendorFormPageClient />;
}
