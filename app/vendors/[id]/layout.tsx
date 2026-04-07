import type { Metadata } from 'next';
import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import { getApiBaseUrl } from '@/utils/env';

interface VendorMeta {
  business_name: string;
  service_category: string;
  custom_service_category?: string;
  city?: string;
  state?: string;
  service_description?: string;
}

function getVendorCategoryLabel(vendor: Pick<VendorMeta, 'service_category' | 'custom_service_category'>): string {
  if (vendor.service_category === 'other' && vendor.custom_service_category?.trim()) {
    return vendor.custom_service_category.trim();
  }
  if (vendor.service_category === 'mc') {
    return 'MC / Host';
  }
  return vendor.service_category.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

async function fetchVendorMeta(id: string): Promise<VendorMeta | null> {
  try {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/vendors/${id}/public`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const vendor = await fetchVendorMeta(id);
  const canonicalUrl = `https://thespecialwedding.io/vendors/${id}`;
  const dynamicOgImage = `/api/og?type=vendor&id=${encodeURIComponent(id)}`;

  if (!vendor) {
    return {
      title: 'Vendor Profile',
      description: 'View wedding vendor services, pricing, portfolio, and contact details on The Special Wedding.',
      robots: { index: false, follow: true },
      metadataBase: new URL('https://thespecialwedding.io'),
      alternates: {
        canonical: `/vendors/${id}`,
      },
      openGraph: {
        title: 'Vendor Profile | The Special Wedding',
        description: 'View wedding vendor services, pricing, portfolio, and contact details on The Special Wedding.',
        url: canonicalUrl,
        type: 'website',
        images: [
          {
            url: dynamicOgImage,
            width: 1200,
            height: 630,
            alt: 'The Special Wedding vendor profile',
          },
        ],
      },
      twitter: {
        card: 'summary_large_image',
        site: '@thespecialwedding',
        title: 'Vendor Profile | The Special Wedding',
        description: 'View wedding vendor services, pricing, portfolio, and contact details on The Special Wedding.',
        images: [dynamicOgImage],
      },
    };
  }

  const location = [vendor.city, vendor.state].filter(Boolean).join(', ');
  const categoryLabel = getVendorCategoryLabel(vendor);
  const title = location
    ? `${vendor.business_name} — ${categoryLabel} in ${location}`
    : `${vendor.business_name} — ${categoryLabel}`;

  const description = vendor.service_description
    ? vendor.service_description.slice(0, 155)
    : `${vendor.business_name} is a ${categoryLabel.toLowerCase()}${location ? ` based in ${location}` : ''}. View services, pricing, and portfolio.`;

  return {
    title,
    description,
    robots: { index: true, follow: true },
    metadataBase: new URL('https://thespecialwedding.io'),
    alternates: {
      canonical: `/vendors/${id}`,
    },
    openGraph: {
      title: `${title} | The Special Wedding`,
      description,
      url: canonicalUrl,
      type: 'website',
      images: [
        {
          url: dynamicOgImage,
          width: 1200,
          height: 630,
          alt: `${title} | The Special Wedding`,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      site: '@thespecialwedding',
      title: `${title} | The Special Wedding`,
      description,
      images: [dynamicOgImage],
    },
  };
}

export default async function VendorProfileLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const vendor = await fetchVendorMeta(id);

  return (
    <>
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Vendors', href: '/vendors' },
          { name: vendor?.business_name || 'Vendor Profile', href: `/vendors/${id}` },
        ]}
      />
      {children}
    </>
  );
}
