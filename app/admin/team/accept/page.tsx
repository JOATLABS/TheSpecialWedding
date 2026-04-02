import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import AcceptInvitePageClient from './AcceptInvitePageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Accept Team Invitation',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function AcceptInviteLegacyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const resolvedSearchParams = await searchParams;
  const queryToken = Array.isArray(resolvedSearchParams.token)
    ? resolvedSearchParams.token[0]
    : resolvedSearchParams.token;

  if (queryToken) {
    redirect(`/admin/team/accept/${encodeURIComponent(queryToken)}`);
  }

  return <AcceptInvitePageClient initialToken={null} />;
}
