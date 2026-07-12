export const MAX_STOREFRONT_IMAGE_BYTES = 5 * 1024 * 1024;

export const STOREFRONT_IMAGE_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
] as const;

export type StorefrontImageType = (typeof STOREFRONT_IMAGE_TYPES)[number];
export type StorefrontImageSlot = 'hero' | 'about';

export type StorefrontApiTransport = <T = unknown>(
  path: string,
  method?: string,
  body?: unknown,
) => Promise<T | undefined>;

export interface StorefrontAccess {
  plan_id: string | null;
  storefront_enabled: boolean;
  custom_domain_enabled: boolean;
}

export interface StorefrontSettings {
  slug: string;
  title: string | null;
  description: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  hero_asset_id: string | null;
  about_asset_id: string | null;
  theme_color: string;
  packages_enabled: boolean;
  reviews_enabled: boolean;
  is_published: boolean;
  published_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  revision: number;
  slug_editable: boolean;
  slug_persisted: boolean;
}

export interface StorefrontSettingsUpdate {
  slug?: string;
  title?: string | null;
  description?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  hero_asset_id?: string | null;
  about_asset_id?: string | null;
  theme_color?: string;
  packages_enabled?: boolean;
  reviews_enabled?: boolean;
  is_published?: boolean;
}

export type StorefrontPublicSettings = PublicStorefrontSettings;
export type StorefrontPlanner = PublicStorefrontPlanner;
export type StorefrontPackageService = PublicStorefrontPackageService;
export type StorefrontPackage = PublicStorefrontPackage;
export type StorefrontReview = PublicStorefrontReview;
export type StorefrontPreviewData = PublicStorefrontData;

export interface StorefrontOwnershipVerification {
  type: string | null;
  name: string | null;
  value: string | null;
}

export interface StorefrontOwnershipVerificationHttp {
  http_url: string | null;
  http_body: string | null;
}

export interface StorefrontSslValidationRecord {
  status: string | null;
  txt_name: string | null;
  txt_value: string | null;
  cname_name: string | null;
  cname_target: string | null;
}

export interface StorefrontDomain {
  hostname: string;
  status: string;
  provider_status: string;
  ssl_status: string;
  ownership_verification: StorefrontOwnershipVerification | null;
  ownership_verification_http: StorefrontOwnershipVerificationHttp | null;
  ssl_validation_records: StorefrontSslValidationRecord[];
  cname_target: string | null;
  deletion_status: string | null;
  last_error: string | null;
}

export interface StorefrontUploadReservation {
  asset_id: string;
  upload_url: string;
  cdn_url: string;
  key: string;
  max_size_bytes: number;
}

export interface StorefrontAsset {
  asset_id: string;
  slot: StorefrontImageSlot;
  state: string;
  key: string;
  cdn_url: string;
  content_type: StorefrontImageType;
  size_bytes: number;
}

export interface StorefrontAssetDeleteResponse {
  status: string;
  asset_id: string;
}

function requireResponse<T>(value: T | undefined, operation: string): T {
  if (value === undefined) {
    throw new Error(`Storefront ${operation} returned an empty response`);
  }
  return value;
}

export async function getStorefrontAccess(
  transport: StorefrontApiTransport,
): Promise<StorefrontAccess> {
  return requireResponse(
    await transport<StorefrontAccess>('/admin/storefront/access', 'GET'),
    'access request',
  );
}

export async function getStorefrontSettings(
  transport: StorefrontApiTransport,
): Promise<StorefrontSettings | null> {
  const response = requireResponse(
    await transport<{ settings: StorefrontSettings | null }>(
      '/admin/storefront/settings',
      'GET',
    ),
    'settings request',
  );
  return response.settings;
}

export async function saveStorefrontSettings(
  settings: StorefrontSettingsUpdate,
  transport: StorefrontApiTransport,
): Promise<StorefrontSettings> {
  const response = requireResponse(
    await transport<{ status: string; settings: StorefrontSettings }>(
      '/admin/storefront/settings',
      'POST',
      settings,
    ),
    'settings save',
  );
  return response.settings;
}

export function getStorefrontPreviewUrl(slug: string): string {
  return `/storefront/${encodeURIComponent(slug)}?preview=1`;
}

export async function getStorefrontPreviewData(
  slug: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontPreviewData> {
  return requireResponse(
    await transport<StorefrontPreviewData>(
      `/admin/storefront/preview/${encodeURIComponent(slug)}`,
      'GET',
    ),
    'preview request',
  );
}

export async function connectCustomDomain(
  domain: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomain> {
  return requireResponse(
    await transport<StorefrontDomain>(
      '/admin/storefront/custom-domain',
      'POST',
      { domain },
    ),
    'custom-domain connect',
  );
}

export async function refreshCustomDomain(
  transport: StorefrontApiTransport,
): Promise<StorefrontDomain | null> {
  const response = await transport<StorefrontDomain | null>(
    '/admin/storefront/custom-domain/status',
    'GET',
  );
  if (response === undefined) {
    throw new Error('Storefront custom-domain refresh returned an empty response');
  }
  return response;
}

export async function removeCustomDomain(
  transport: StorefrontApiTransport,
): Promise<void> {
  await transport('/admin/storefront/custom-domain', 'DELETE');
}

export async function deleteStorefrontUpload(
  assetId: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontAssetDeleteResponse> {
  return requireResponse(
    await transport<StorefrontAssetDeleteResponse>(
      `/admin/storefront/upload?asset_id=${encodeURIComponent(assetId)}`,
      'DELETE',
    ),
    'upload cleanup',
  );
}

function validateStorefrontImage(file: File): asserts file is File & {
  type: StorefrontImageType;
} {
  if (!(STOREFRONT_IMAGE_TYPES as readonly string[]).includes(file.type)) {
    throw new Error('Choose a JPEG, PNG, or WebP image');
  }
  if (file.size <= 0) {
    throw new Error('Choose a non-empty image');
  }
  if (file.size > MAX_STOREFRONT_IMAGE_BYTES) {
    throw new Error('Storefront images must be 5 MB or smaller');
  }
}

async function bestEffortCleanup(
  assetId: string,
  transport: StorefrontApiTransport,
): Promise<void> {
  try {
    await deleteStorefrontUpload(assetId, transport);
  } catch {
    // The durable backend reservation lifecycle also expires abandoned rows.
    // Preserve the original upload/finalize error for the caller.
  }
}

export async function uploadStorefrontImage(
  file: File,
  slot: StorefrontImageSlot,
  transport: StorefrontApiTransport,
  fetchImpl: typeof fetch = fetch,
): Promise<StorefrontAsset> {
  validateStorefrontImage(file);

  const query = new URLSearchParams({
    filename: file.name,
    slot,
    content_type: file.type,
    size_bytes: String(file.size),
  });
  const reservation = requireResponse(
    await transport<StorefrontUploadReservation>(
      `/admin/storefront/upload-url?${query.toString()}`,
      'GET',
    ),
    'upload reservation',
  );

  try {
    const uploadResponse = await fetchImpl(reservation.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': file.type },
      body: file,
    });
    if (!uploadResponse.ok) {
      const detail = (await uploadResponse.text()).trim();
      throw new Error(detail || 'Storefront image upload failed');
    }

    return requireResponse(
      await transport<StorefrontAsset>(
        '/admin/storefront/upload-complete',
        'POST',
        { asset_id: reservation.asset_id },
      ),
      'upload finalize',
    );
  } catch (error) {
    await bestEffortCleanup(reservation.asset_id, transport);
    throw error;
  }
}
import type {
  PublicStorefrontData,
  PublicStorefrontPackage,
  PublicStorefrontPackageService,
  PublicStorefrontPlanner,
  PublicStorefrontReview,
  PublicStorefrontSettings,
} from '@/storefront/storefrontTypes';

export type {
  PublicStorefrontData,
  PublicStorefrontPackage,
  PublicStorefrontPackageService,
  PublicStorefrontPlanner,
  PublicStorefrontReview,
  PublicStorefrontSettings,
} from '@/storefront/storefrontTypes';
