export interface GalleryUploadResult {
  key: string;
}

interface UploadGalleryFileOptions {
  baseUrl: string;
  token: string;
  file: File;
  weddingSlug: string;
  folder: string;
  fetchImpl?: typeof fetch;
}

async function readErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const payload = await response.json();
      if (typeof payload?.detail === 'string') return payload.detail;
      if (typeof payload?.message === 'string') return payload.message;
    }
    const text = await response.text();
    return text || fallback;
  } catch {
    return fallback;
  }
}

export async function uploadGalleryFileViaPresignedUrl({
  baseUrl,
  token,
  file,
  weddingSlug,
  folder,
  fetchImpl = fetch,
}: UploadGalleryFileOptions): Promise<GalleryUploadResult> {
  const params = new URLSearchParams({
    filename: file.name,
    wedding_slug: weddingSlug,
    folder,
  });

  const presignResponse = await fetchImpl(`${baseUrl}/admin/gallery/upload-url?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!presignResponse.ok) {
    throw new Error(
      await readErrorMessage(
        presignResponse,
        `Upload URL request failed: ${presignResponse.status}`
      )
    );
  }

  const presignPayload = await presignResponse.json();
  const uploadUrl = presignPayload?.upload_url;
  const key = presignPayload?.key;
  if (typeof uploadUrl !== 'string' || !uploadUrl || typeof key !== 'string' || !key) {
    throw new Error('Upload URL response was incomplete');
  }

  const uploadResponse = await fetchImpl(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': file.type || 'application/octet-stream',
    },
  });

  if (!uploadResponse.ok) {
    throw new Error(
      await readErrorMessage(
        uploadResponse,
        `Storage upload failed: ${uploadResponse.status}`
      )
    );
  }

  return { key };
}
