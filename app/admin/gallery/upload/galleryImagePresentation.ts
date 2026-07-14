export interface GalleryImagePresentationSource {
  alt?: string | null;
  display_name?: string | null;
  filename?: string | null;
  key?: string | null;
}

function normalizedText(value?: string | null): string | undefined {
  const normalized = value?.trim();
  return normalized || undefined;
}

function humanizeFileReference(value?: string | null): string | undefined {
  const normalized = normalizedText(value);
  if (!normalized) {
    return undefined;
  }

  const basename = normalized.split(/[\\/]/).filter(Boolean).at(-1);
  const withoutExtension = basename?.replace(/\.[A-Za-z0-9]{1,10}$/, '');
  const withoutCaptureDate = withoutExtension?.replace(/^\d{8,14}[-_]+/, '');
  const words = withoutCaptureDate
    ?.replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  if (!words) {
    return undefined;
  }

  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function getGalleryImageLabel(
  image: GalleryImagePresentationSource,
  index: number,
): string {
  return (
    normalizedText(image.display_name)
    ?? humanizeFileReference(image.filename)
    ?? humanizeFileReference(image.key)
    ?? `Gallery image ${index + 1}`
  );
}

export function getGalleryImageAlt(
  image: GalleryImagePresentationSource,
  index: number,
): string {
  return normalizedText(image.alt) ?? getGalleryImageLabel(image, index);
}
