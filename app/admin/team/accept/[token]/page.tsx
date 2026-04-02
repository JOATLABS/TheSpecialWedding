import type { Metadata } from 'next';

import AcceptInvitePageClient from '../AcceptInvitePageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Accept Team Invitation',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function AcceptInviteCanonicalPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;

  return <AcceptInvitePageClient initialToken={token} />;
}
