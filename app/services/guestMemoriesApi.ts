'use client';

import { coupleFetch } from '@/couple/lib/auth';
import { getApiBaseUrl } from '@/utils/env';

export const NOT_SURE_EVENT_VALUE = 'not_sure';

export interface GuestMemoriesEventOption {
  value: string;
  label: string;
  date?: string | null;
}

export interface GuestMemoriesSummary {
  pending_count: number;
  kept_count: number;
  rejected_count: number;
  processing_videos: number;
  enabled: boolean;
  link_status: 'open' | 'closed';
  upload_closes_at?: string | null;
  storage_ready: boolean;
  storage_status?: 'ready' | 'unconfigured' | 'unavailable';
  storage_issue?: string | null;
  stream_configured: boolean;
}

export interface GuestMemoriesSettings extends GuestMemoriesSummary {
  upload_url: string;
  upload_token_last_rotated_at?: string | null;
  event_options: GuestMemoriesEventOption[];
  wedding: {
    slug: string;
    couple_names: string;
  };
}

export interface PublicGuestMemoriesContext {
  wedding: {
    slug: string;
    couple_names: string;
    date?: string | null;
  };
  guest_media: {
    enabled: boolean;
    upload_closes_at?: string | null;
    link_status: 'open';
    storage_ready: boolean;
    storage_status?: 'ready' | 'unconfigured' | 'unavailable';
    storage_issue?: string | null;
    stream_configured: boolean;
  };
  events: GuestMemoriesEventOption[];
  limits: {
    max_files_per_batch: number;
    max_image_size_bytes: number;
    max_video_size_bytes: number;
    max_batch_size_bytes: number;
    accepted_types: string[];
    not_sure_value: string;
  };
}

export interface GuestMemoriesUploadPlanFile {
  filename: string;
  content_type: string;
  size_bytes: number;
  event_type?: string | null;
}

export interface GuestMemoriesUploadPlanAsset {
  asset_id: string;
  upload_url: string;
  key: string;
  content_type: string;
  media_type: 'image' | 'video';
  event_type: string;
  filename: string;
}

export interface GuestMemoriesUploadPlanResponse {
  upload_batch_id: string;
  assets: GuestMemoriesUploadPlanAsset[];
}

export interface CoupleMemoryAsset {
  id: string;
  wedding_id: string;
  wedding_slug: string;
  upload_batch_id: string;
  uploader_name: string;
  event_type: string;
  media_type: 'image' | 'video';
  mime_type: string;
  size_bytes: number;
  original_filename: string;
  stream_status?: 'queued' | 'ingesting' | 'processing' | 'ready' | 'failed' | 'unconfigured' | null;
  review_status: 'pending' | 'kept' | 'rejected';
  visibility: 'couple_only';
  upload_status: 'reserved' | 'uploaded' | 'failed';
  uploaded_at?: string | null;
  reviewed_at?: string | null;
  preview_path?: string;
  player_path?: string | null;
  thumbnail_path?: string | null;
  preview_url?: string;
  player_url?: string | null;
  thumbnail_url?: string | null;
  download_ready: boolean;
}

export interface CoupleMemoriesListResponse {
  items: CoupleMemoryAsset[];
  page: number;
  limit: number;
  total: number;
  pages: number;
  summary: GuestMemoriesSummary;
}

export interface CoupleMemoriesExportJob {
  id: string;
  wedding_id: string;
  wedding_slug: string;
  requested_by: string;
  asset_ids: string[];
  asset_count: number;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  review_status: 'all' | 'pending' | 'kept' | 'rejected';
  export_bucket: string;
  export_key: string;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  error?: string | null;
  download_url?: string;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return response.json() as Promise<T>;
  }

  let message = 'Request failed';
  try {
    const payload = await response.json();
    const detail = payload?.detail;
    if (typeof detail === 'string') {
      message = detail;
    } else if (detail?.message) {
      message = detail.message;
    }
  } catch {
    try {
      const text = await response.text();
      if (text) {
        message = text;
      }
    } catch {
      // Ignore secondary parsing failure.
    }
  }

  throw new Error(message);
}

function withApiBase(path?: string | null): string | undefined {
  if (!path) {
    return undefined;
  }
  return `${getApiBaseUrl()}${path}`;
}

async function adminFetch(token: string, path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${token}`);

  const hasBody = init.body != null;
  if (hasBody && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    credentials: 'include',
    cache: 'no-store',
  });
}

function hydrateCoupleMemoryAsset(asset: CoupleMemoryAsset): CoupleMemoryAsset {
  return {
    ...asset,
    preview_url: withApiBase(asset.preview_path),
    player_url: withApiBase(asset.player_path),
    thumbnail_url: withApiBase(asset.thumbnail_path),
  };
}

export async function fetchPublicGuestMemoriesContext(
  slug: string,
  uploadToken: string,
): Promise<PublicGuestMemoriesContext> {
  const response = await fetch(`${getApiBaseUrl()}/guest-media/public/${slug}/${uploadToken}`, {
    credentials: 'include',
    cache: 'no-store',
  });
  return parseResponse<PublicGuestMemoriesContext>(response);
}

export async function createPublicGuestMemoriesUploadPlan(
  slug: string,
  uploadToken: string,
  payload: {
    uploader_name: string;
    batch_event_type?: string | null;
    files: GuestMemoriesUploadPlanFile[];
  },
): Promise<GuestMemoriesUploadPlanResponse> {
  const response = await fetch(`${getApiBaseUrl()}/guest-media/public/${slug}/${uploadToken}/upload-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  });
  return parseResponse<GuestMemoriesUploadPlanResponse>(response);
}

export async function finalizePublicGuestMemoriesUpload(
  slug: string,
  uploadToken: string,
  payload: {
    upload_batch_id: string;
    asset_ids: string[];
  },
): Promise<{ uploaded_count: number; failed_count: number; assets: string[]; failed_assets: Array<{ asset_id: string; reason: string }> }> {
  const response = await fetch(`${getApiBaseUrl()}/guest-media/public/${slug}/${uploadToken}/finalize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function fetchCoupleMemoriesSettings(): Promise<GuestMemoriesSettings> {
  return parseResponse<GuestMemoriesSettings>(await coupleFetch('/couple/portal/memories/settings'));
}

export async function updateCoupleMemoriesSettings(payload: {
  enabled?: boolean;
  upload_closes_at?: string | null;
}): Promise<GuestMemoriesSettings> {
  return parseResponse<GuestMemoriesSettings>(await coupleFetch('/couple/portal/memories/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  }));
}

export async function rotateCoupleMemoriesLink(): Promise<GuestMemoriesSettings> {
  return parseResponse<GuestMemoriesSettings>(await coupleFetch('/couple/portal/memories/rotate-link', {
    method: 'POST',
  }));
}

export async function fetchCoupleMemoriesQrBlob(): Promise<Blob> {
  const response = await coupleFetch('/couple/portal/memories/qr-code');
  if (!response.ok) {
    await parseResponse(response);
  }
  return response.blob();
}

export async function fetchCoupleMemories(params: {
  reviewStatus?: 'all' | 'pending' | 'kept' | 'rejected';
  mediaType?: 'all' | 'image' | 'video';
  eventType?: string;
  uploaderQuery?: string;
  page?: number;
  limit?: number;
} = {}): Promise<CoupleMemoriesListResponse> {
  const search = new URLSearchParams();
  if (params.reviewStatus) search.set('review_status', params.reviewStatus);
  if (params.mediaType) search.set('media_type', params.mediaType);
  if (params.eventType) search.set('event_type', params.eventType);
  if (params.uploaderQuery) search.set('uploader_query', params.uploaderQuery);
  if (params.page) search.set('page', String(params.page));
  if (params.limit) search.set('limit', String(params.limit));

  const suffix = search.toString() ? `?${search.toString()}` : '';
  const payload = await parseResponse<CoupleMemoriesListResponse>(await coupleFetch(`/couple/portal/memories${suffix}`));
  return {
    ...payload,
    items: payload.items.map(hydrateCoupleMemoryAsset),
  };
}

export async function reviewCoupleMemory(
  assetId: string,
  reviewStatus: 'pending' | 'kept' | 'rejected',
): Promise<CoupleMemoryAsset> {
  const payload = await parseResponse<CoupleMemoryAsset>(await coupleFetch(`/couple/portal/memories/${assetId}/review`, {
    method: 'PATCH',
    body: JSON.stringify({ review_status: reviewStatus }),
  }));
  return hydrateCoupleMemoryAsset(payload);
}

export async function fetchCoupleMemoryDownload(assetId: string): Promise<{ download_url: string; filename: string }> {
  return parseResponse<{ download_url: string; filename: string }>(await coupleFetch(`/couple/portal/memories/${assetId}/download`));
}

export async function createCoupleMemoriesExport(payload: {
  asset_ids?: string[];
  review_status?: 'all' | 'pending' | 'kept' | 'rejected';
} = {}): Promise<{ export_id: string; status: 'queued'; asset_count: number }> {
  return parseResponse(await coupleFetch('/couple/portal/memories/exports', {
    method: 'POST',
    body: JSON.stringify(payload),
  }));
}

export async function fetchCoupleMemoriesExport(exportId: string): Promise<CoupleMemoriesExportJob> {
  return parseResponse<CoupleMemoriesExportJob>(await coupleFetch(`/couple/portal/memories/exports/${exportId}`));
}

export async function fetchPlannerMemoriesSettings(
  token: string,
  weddingId: string,
): Promise<GuestMemoriesSettings> {
  const search = new URLSearchParams({ wedding_id: weddingId });
  return parseResponse<GuestMemoriesSettings>(
    await adminFetch(token, `/admin/guest-memories/settings?${search.toString()}`),
  );
}

export async function updatePlannerMemoriesSettings(
  token: string,
  weddingId: string,
  payload: {
    enabled?: boolean;
    upload_closes_at?: string | null;
  },
): Promise<GuestMemoriesSettings> {
  const search = new URLSearchParams({ wedding_id: weddingId });
  return parseResponse<GuestMemoriesSettings>(
    await adminFetch(token, `/admin/guest-memories/settings?${search.toString()}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  );
}

export async function rotatePlannerMemoriesLink(
  token: string,
  weddingId: string,
): Promise<GuestMemoriesSettings> {
  const search = new URLSearchParams({ wedding_id: weddingId });
  return parseResponse<GuestMemoriesSettings>(
    await adminFetch(token, `/admin/guest-memories/rotate-link?${search.toString()}`, {
      method: 'POST',
    }),
  );
}

export async function fetchPlannerMemoriesQrBlob(token: string, weddingId: string): Promise<Blob> {
  const search = new URLSearchParams({ wedding_id: weddingId });
  const response = await adminFetch(token, `/admin/guest-memories/qr-code?${search.toString()}`);
  if (!response.ok) {
    await parseResponse(response);
  }
  return response.blob();
}

export async function fetchPlannerMemoriesSignPdfBlob(token: string, weddingId: string): Promise<Blob> {
  const search = new URLSearchParams({ wedding_id: weddingId });
  const response = await adminFetch(token, `/admin/guest-memories/sign-pdf?${search.toString()}`);
  if (!response.ok) {
    await parseResponse(response);
  }
  return response.blob();
}
