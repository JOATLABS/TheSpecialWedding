export interface GalleryImage {
  key?: string | null;
  url?: string | null;
  file_url?: string | null;
  filename?: string | null;
  size?: number;
  display_name?: string | null;
  alt?: string | null;
}

interface FetchGalleryImagesOptions {
  baseUrl: string;
  token: string;
  weddingSlug: string;
  fetchImpl?: typeof fetch;
}

const GALLERY_FOLDERS = [
  { folder: 'gallery', label: 'Public Gallery' },
  { folder: 'our-story', label: 'Our Story' },
  { folder: 'wedding-party', label: 'Wedding Party' },
] as const;

async function readResponseError(response: Response): Promise<string | null> {
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const payload = await response.json();
      if (typeof payload?.detail === 'string' && payload.detail.trim()) {
        return payload.detail.trim();
      }
      if (typeof payload?.message === 'string' && payload.message.trim()) {
        return payload.message.trim();
      }
      return null;
    }

    const body = (await response.text()).trim();
    return body || null;
  } catch {
    return null;
  }
}

export async function fetchGalleryImagesForWedding(
  {
    baseUrl,
    token,
    weddingSlug,
    fetchImpl = fetch,
  }: FetchGalleryImagesOptions
): Promise<GalleryImage[]> {
  const images: GalleryImage[] = [];

  for (const { folder, label } of GALLERY_FOLDERS) {
    const query = new URLSearchParams({ prefix: `${folder}/${weddingSlug}/` });
    const response = await fetchImpl(`${baseUrl}/admin/gallery/list?${query.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      const detail = await readResponseError(response);
      throw new Error(
        `${label} images could not be loaded (${response.status})${detail ? `: ${detail}` : ''}`
      );
    }

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new Error(`${label} images returned an invalid response`);
    }
    if (!Array.isArray(payload)) {
      throw new Error(`${label} images returned an invalid response`);
    }
    images.push(...(payload as GalleryImage[]));
  }

  return images;
}
