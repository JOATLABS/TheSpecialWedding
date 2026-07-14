const ABSOLUTE_URL_PATTERN = /^[a-z][a-z\d+\-.]*:/i;
const REPOSITORY_STATIC_MEDIA_PREFIX = '/demo-gallery/';
const REPOSITORY_STATIC_MEDIA_PATHS = new Set([
  '/demo-gallery/elegant-ceremony-aisle.svg',
  '/demo-gallery/elegant-couple-stairs.svg',
  '/demo-gallery/elegant-reception-table.svg',
  '/demo-gallery/sofia-daniel-ceremony.webp',
  '/demo-gallery/sofia-daniel-reception.webp',
  '/demo-gallery/sofia-daniel-terrace.webp',
]);

export function resolveMediaUrl(value?: string | null): string | undefined {
  const normalized = value?.trim();
  if (!normalized) {
    return undefined;
  }

  if (normalized.startsWith('//') || ABSOLUTE_URL_PATTERN.test(normalized)) {
    return normalized;
  }

  if (normalized.startsWith(REPOSITORY_STATIC_MEDIA_PREFIX)) {
    return REPOSITORY_STATIC_MEDIA_PATHS.has(normalized) ? normalized : undefined;
  }

  const mediaDomain = process.env.NEXT_PUBLIC_MEDIA_DOMAIN?.replace(/\/+$/, '');
  const normalizedKey = normalized.replace(/^\/+/, '');

  if (!mediaDomain) {
    return normalizedKey;
  }

  return `${mediaDomain}/${normalizedKey}`;
}
