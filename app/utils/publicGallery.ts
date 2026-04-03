import type { GalleryImage } from '@/types/landing';
import { getApiBaseUrl } from '@/utils/env';

const API_BASE_URL = getApiBaseUrl();
const API_URL = API_BASE_URL.replace('/admin', '');

export interface PublicGalleryAccess {
  session?: true;
}

export interface PublicGalleryPage {
  items: GalleryImage[];
  nextCursor: string | null;
  hasMore: boolean;
}

interface GalleryImageResponse {
  key: string;
  url: string;
}

interface GalleryResponseEnvelope {
  items?: GalleryImageResponse[];
  next_cursor?: string | null;
  has_more?: boolean;
}

interface FetchPublicGalleryPageOptions {
  slug: string;
  privacyMode?: string | null;
  access?: PublicGalleryAccess | null;
  limit?: number;
  cursor?: string | null;
}

const EMPTY_GALLERY_PAGE: PublicGalleryPage = {
  items: [],
  nextCursor: null,
  hasMore: false,
};

function normalizeGalleryItems(items: GalleryImageResponse[] = []): GalleryImage[] {
  return items.map((image) => ({
    key: image.key,
    url: image.url,
  }));
}

export function buildPublicGalleryAccess(
  _guest?: unknown,
): PublicGalleryAccess | null {
  return { session: true };
}

export async function fetchPublicGalleryPage({
  slug,
  privacyMode,
  access,
  limit = 60,
  cursor,
}: FetchPublicGalleryPageOptions): Promise<PublicGalleryPage> {
  if (!slug) {
    return EMPTY_GALLERY_PAGE;
  }

  const isPublic = privacyMode === 'public';

  if (!isPublic && !access) {
    return EMPTY_GALLERY_PAGE;
  }

  let response: Response;

  if (isPublic) {
    const params = new URLSearchParams({
      wedding_slug: slug,
      limit: String(limit),
    });
    if (cursor) {
      params.set('cursor', cursor);
    }

    response = await fetch(`${API_URL}/gallery?${params.toString()}`);
  } else {
    response = await fetch(`${API_URL}/gallery/verified`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        wedding_slug: slug,
        limit,
        ...(cursor ? { cursor } : {}),
      }),
    });
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Gallery access failed');
  }

  const data = await response.json() as GalleryResponseEnvelope | GalleryImageResponse[];

  if (Array.isArray(data)) {
    return {
      items: normalizeGalleryItems(data),
      nextCursor: null,
      hasMore: false,
    };
  }

  return {
    items: normalizeGalleryItems(data.items),
    nextCursor: data.next_cursor ?? null,
    hasMore: Boolean(data.has_more),
  };
}
