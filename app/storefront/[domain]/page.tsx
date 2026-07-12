import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';

import { StorefrontView } from '@/components/storefront/StorefrontView';

import StorefrontInquiryForm from '../StorefrontInquiryForm.client';
import { getStorefrontData } from '../storefrontData';

interface StorefrontPageProps {
  params: Promise<{ domain: string }>;
  searchParams: Promise<{ preview?: string | string[] }>;
}

export default async function StorefrontPage({
  params,
  searchParams,
}: StorefrontPageProps) {
  const { domain: identifier } = await params;
  const query = await searchParams;
  const preview = query.preview === '1';

  // Reading the admin cookie is deliberately confined to the explicit preview
  // branch. Public storefront fetches never receive owner credentials.
  const adminToken = preview
    ? (await cookies()).get('admin_token')?.value ?? null
    : null;
  const data = await getStorefrontData(identifier, { preview, adminToken });

  if (!data) {
    notFound();
  }

  return (
    <StorefrontView
      data={data}
      previewMode={preview}
      inquiryForm={
        preview ? undefined : (
          <StorefrontInquiryForm
            identifier={identifier}
            themeColor={data.storefront.theme_color}
          />
        )
      }
    />
  );
}
