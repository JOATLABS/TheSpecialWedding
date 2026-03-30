import type { Metadata } from 'next';

import GuestMemoriesUploadClient from './upload-client';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Share Wedding Memories',
  description: 'Upload wedding photos and videos for the couple.',
  robots: {
    index: false,
    follow: false,
  },
};

export default async function GuestMemoriesUploadPage({
  params,
}: {
  params: Promise<{ slug: string; uploadToken: string }>;
}) {
  const { slug, uploadToken } = await params;
  return <GuestMemoriesUploadClient slug={slug} uploadToken={uploadToken} />;
}
