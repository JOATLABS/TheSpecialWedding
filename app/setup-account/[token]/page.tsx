import type { Metadata } from 'next';

import SetupAccountPageClient from '../SetupAccountPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Account Setup',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function SetupAccountCanonicalPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;

  return <SetupAccountPageClient initialToken={token} />;
}
