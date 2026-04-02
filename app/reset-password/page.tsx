import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import ResetPasswordPageClient from './ResetPasswordPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Reset Password',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function ResetPasswordLegacyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const resolvedSearchParams = await searchParams;
  const queryToken = Array.isArray(resolvedSearchParams.token)
    ? resolvedSearchParams.token[0]
    : resolvedSearchParams.token;

  if (queryToken) {
    redirect(`/reset-password/${encodeURIComponent(queryToken)}`);
  }

  return <ResetPasswordPageClient initialToken={null} />;
}
