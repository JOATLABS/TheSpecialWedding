import { getServerApiBaseUrl } from '@/utils/env';

import type { PublicStorefrontData } from './storefrontTypes';

interface StorefrontFetchOptions {
  preview?: boolean;
  adminToken?: string | null;
  apiBaseUrl?: string;
  fetchImpl?: typeof fetch;
}

interface NextFetchOptions extends RequestInit {
  next?: { revalidate: number };
}

export async function getStorefrontData(
  identifier: string,
  {
    preview = false,
    adminToken = null,
    apiBaseUrl = getServerApiBaseUrl(),
    fetchImpl = fetch,
  }: StorefrontFetchOptions = {},
): Promise<PublicStorefrontData | null> {
  const normalizedBaseUrl = apiBaseUrl.replace(/\/+$/, '');
  const encodedIdentifier = encodeURIComponent(identifier);

  if (preview && !adminToken?.trim()) {
    return null;
  }

  const url = preview
    ? `${normalizedBaseUrl}/admin/storefront/preview/${encodedIdentifier}`
    : `${normalizedBaseUrl}/api/storefront/${encodedIdentifier}`;
  const init: NextFetchOptions = preview
    ? {
        cache: 'no-store',
        headers: { Authorization: `Bearer ${adminToken?.trim()}` },
      }
    : { next: { revalidate: 60 } };

  try {
    const response = await fetchImpl(url, init);
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as PublicStorefrontData;
  } catch {
    return null;
  }
}
