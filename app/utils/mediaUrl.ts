const ABSOLUTE_URL_PATTERN = /^[a-z][a-z\d+\-.]*:/i;

export function resolveMediaUrl(value?: string | null): string | undefined {
  const normalized = value?.trim();
  if (!normalized) {
    return undefined;
  }

  if (normalized.startsWith('//') || ABSOLUTE_URL_PATTERN.test(normalized)) {
    return normalized;
  }

  const mediaDomain = process.env.NEXT_PUBLIC_MEDIA_DOMAIN?.replace(/\/+$/, '');
  const normalizedKey = normalized.replace(/^\/+/, '');

  if (!mediaDomain) {
    return normalizedKey;
  }

  return `${mediaDomain}/${normalizedKey}`;
}
