import type { Metadata } from 'next';
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

  if (!vendor) {
    return {
      title: 'Vendor Profile',
      description: 'View this wedding vendor\u2019s services, pricing, portfolio, and contact details.',
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
    openGraph: {
      title: `${title} | The Special Wedding`,
      description,
    },
  };
}

export default function VendorProfileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
