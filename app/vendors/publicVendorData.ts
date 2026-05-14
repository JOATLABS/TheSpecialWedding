import { getServerApiBaseUrl } from '@/utils/env';
import {
  type DirectoryQuery,
  type DirectoryResponse,
  type PublicVendor,
  SITE_URL,
  VENDOR_DIRECTORY_PAGE_SIZE,
  getVendorCategoryLabel,
} from './publicVendorShared';

export type { DirectoryQuery, DirectoryResponse, PublicVendor } from './publicVendorShared';
export {
  SITE_URL,
  VENDOR_DIRECTORY_PAGE_SIZE,
  formatCategory,
  getVendorCategoryLabel,
} from './publicVendorShared';

function normalizeStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function normalizePublicVendor(raw: Partial<PublicVendor>): PublicVendor {
  return {
    ...raw,
    _id: String(raw._id || ''),
    business_name: String(raw.business_name || ''),
    service_category: String(raw.service_category || 'other'),
    service_subcategories: normalizeStringArray(raw.service_subcategories),
    portfolio_urls: normalizeStringArray(raw.portfolio_urls),
    currency: raw.currency || 'USD',
    is_preferred: Boolean(raw.is_preferred),
    weddings_count: Number(raw.weddings_count || 0),
  };
}

function normalizeDirectoryResponse(raw: Partial<DirectoryResponse>): DirectoryResponse {
  const vendors = Array.isArray(raw.vendors) ? raw.vendors.map(normalizePublicVendor) : [];
  const limit = Number(raw.page_size || VENDOR_DIRECTORY_PAGE_SIZE);
  return {
    vendors,
    total: Number(raw.total || vendors.length),
    categories: normalizeStringArray(raw.categories),
    page: Number(raw.page || 1),
    page_size: limit,
  };
}

function buildQueryString(query: DirectoryQuery): string {
  const params = new URLSearchParams();
  if (query.category) params.set('category', query.category);
  if (query.location) params.set('location', query.location);
  if (query.search) params.set('search', query.search);
  params.set('limit', String(query.limit || VENDOR_DIRECTORY_PAGE_SIZE));
  params.set('skip', String(query.skip || 0));
  return params.toString();
}

function emptyDirectoryResponse(limit = VENDOR_DIRECTORY_PAGE_SIZE): DirectoryResponse {
  return {
    vendors: [],
    total: 0,
    categories: [],
    page: 1,
    page_size: limit,
  };
}

export async function fetchPublicVendorDirectory(query: DirectoryQuery = {}): Promise<DirectoryResponse> {
  const limit = query.limit || VENDOR_DIRECTORY_PAGE_SIZE;

  try {
    const baseUrl = getServerApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/vendors/directory?${buildQueryString(query)}`, {
      next: { revalidate: 3600 },
    });

    if (!res.ok) {
      return emptyDirectoryResponse(limit);
    }

    return normalizeDirectoryResponse(await res.json());
  } catch {
    return emptyDirectoryResponse(limit);
  }
}

export async function fetchPublicVendorProfile(id: string): Promise<PublicVendor | null> {
  const baseUrl = getServerApiBaseUrl();
  const res = await fetch(`${baseUrl}/api/v1/vendors/${encodeURIComponent(id)}/public`, {
    next: { revalidate: 3600 },
  });

  if (res.status === 404) {
    return null;
  }

  if (!res.ok) {
    throw new Error(`Failed to fetch public vendor profile: ${res.status}`);
  }

  return normalizePublicVendor(await res.json());
}

export function buildVendorDirectoryItemList(vendors: PublicVendor[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: 'Wedding Vendor Directory',
    itemListElement: vendors.map((vendor, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      url: `${SITE_URL}/vendors/${vendor._id}`,
      name: vendor.business_name,
      item: {
        '@type': 'ProfessionalService',
        '@id': `${SITE_URL}/vendors/${vendor._id}#vendor`,
        name: vendor.business_name,
        url: `${SITE_URL}/vendors/${vendor._id}`,
        description: vendor.service_description,
        image: vendor.logo_url,
        serviceType: getVendorCategoryLabel(vendor),
        address: buildPostalAddress(vendor),
      },
    })),
  };
}

export function buildVendorProfileJsonLd(vendor: PublicVendor) {
  return {
    '@context': 'https://schema.org',
    '@type': 'ProfessionalService',
    '@id': `${SITE_URL}/vendors/${vendor._id}#vendor`,
    name: vendor.business_name,
    url: `${SITE_URL}/vendors/${vendor._id}`,
    image: vendor.logo_url,
    description: vendor.service_description,
    telephone: vendor.phone,
    email: vendor.email,
    address: buildPostalAddress(vendor),
    areaServed: buildAreaServed(vendor),
    serviceType: getVendorCategoryLabel(vendor),
    priceRange: buildPriceRange(vendor),
    sameAs: vendor.website ? [vendor.website] : undefined,
  };
}

function buildPostalAddress(vendor: PublicVendor) {
  if (!vendor.address && !vendor.city && !vendor.state && !vendor.country) {
    return undefined;
  }

  return {
    '@type': 'PostalAddress',
    streetAddress: vendor.address,
    addressLocality: vendor.city,
    addressRegion: vendor.state,
    addressCountry: vendor.country,
  };
}

function buildAreaServed(vendor: PublicVendor) {
  const location = [vendor.city, vendor.state, vendor.country].filter(Boolean).join(', ');
  if (!location && !vendor.service_radius_miles) return undefined;

  return {
    '@type': 'Place',
    name: vendor.service_radius_miles
      ? `${location || 'Service area'} within ${vendor.service_radius_miles} miles`
      : location,
  };
}

function buildPriceRange(vendor: PublicVendor): string | undefined {
  if (!vendor.typical_price_min && !vendor.typical_price_max) return undefined;
  const currency = vendor.currency || 'USD';
  if (vendor.typical_price_min && vendor.typical_price_max) {
    return `${currency} ${vendor.typical_price_min}-${vendor.typical_price_max}`;
  }
  if (vendor.typical_price_min) return `${currency} ${vendor.typical_price_min}+`;
  return `${currency} up to ${vendor.typical_price_max}`;
}
