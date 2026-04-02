import type { Metadata } from 'next';

import CoupleResetPasswordPageClient from '../CoupleResetPasswordPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Couple Password Reset',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function CoupleResetPasswordCanonicalPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;

  return <CoupleResetPasswordPageClient initialToken={token} />;
}
