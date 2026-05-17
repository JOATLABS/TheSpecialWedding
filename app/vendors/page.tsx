import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import VendorsDirectoryClient from './VendorsDirectoryClient';
import {
  buildVendorDirectoryItemList,
  fetchPublicVendorDirectory,
} from './publicVendorData';
import { serializeJsonLd } from '@/seo/jsonLd';

export default async function VendorsPage() {
  const initialDirectory = await fetchPublicVendorDirectory();
  const itemListJsonLd = buildVendorDirectoryItemList(initialDirectory.vendors);

  return (
    <>
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Vendor Directory', href: '/vendors' },
        ]}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(itemListJsonLd) }}
      />
      <VendorsDirectoryClient initialDirectory={initialDirectory} />
    </>
  );
}
