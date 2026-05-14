export const VENDOR_DIRECTORY_PAGE_SIZE = 24;
export const SITE_URL = 'https://thespecialwedding.io';

export interface PublicVendor {
  _id: string;
  business_name: string;
  contact_name?: string;
  email?: string;
  phone?: string;
  website?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  service_category: string;
  custom_service_category?: string;
  service_subcategories?: string[];
  service_description?: string;
  portfolio_urls?: string[];
  logo_url?: string;
  typical_price_min?: number;
  typical_price_max?: number;
  currency: string;
  lead_time_days?: number;
  service_radius_miles?: number;
  is_preferred: boolean;
  weddings_count: number;
}

export interface DirectoryResponse {
  vendors: PublicVendor[];
  total: number;
  categories: string[];
  page: number;
  page_size: number;
}

export interface DirectoryQuery {
  category?: string;
  location?: string;
  search?: string;
  limit?: number;
  skip?: number;
}

export function formatCategory(cat: string): string {
  return cat.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

export function getVendorCategoryLabel(vendor: Pick<PublicVendor, 'service_category' | 'custom_service_category'>): string {
  if (vendor.service_category === 'other' && vendor.custom_service_category?.trim()) {
    return vendor.custom_service_category.trim();
  }
  if (vendor.service_category === 'mc') {
    return 'MC / Host';
  }
  return formatCategory(vendor.service_category);
}
