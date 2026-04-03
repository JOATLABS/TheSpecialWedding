import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import CoupleResetPasswordPageClient from './CoupleResetPasswordPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Couple Password Reset',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function CoupleResetPasswordLegacyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const resolvedSearchParams = await searchParams;
  const queryToken = Array.isArray(resolvedSearchParams.token)
    ? resolvedSearchParams.token[0]
    : resolvedSearchParams.token;

  if (queryToken) {
    redirect(`/couple/reset-password/${encodeURIComponent(queryToken)}`);
  }

  return <CoupleResetPasswordPageClient initialToken={null} />;
}
