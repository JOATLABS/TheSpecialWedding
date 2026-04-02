import type { Metadata } from 'next';

import ResetPasswordPageClient from '../ResetPasswordPageClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Reset Password',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function ResetPasswordCanonicalPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;

  return <ResetPasswordPageClient initialToken={token} />;
}
