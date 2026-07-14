export type WeddingMediaLoadError = 'permission' | 'unavailable' | null;

export interface WeddingMediaItem {
  key: string;
  url?: string;
  size?: number;
}

export interface WeddingMediaOption {
  value: string;
  label: string;
}

type WeddingMediaKind = 'story' | 'wedding-party';

interface WeddingMediaAvailabilityOptions {
  kind: WeddingMediaKind;
  count: number;
  loading: boolean;
  error: WeddingMediaLoadError;
}

interface WeddingMediaLoadNotice {
  role: 'status' | 'alert';
  title: string;
  description: string;
}

function buildWeddingMediaLabel(value: string): string {
  const parts = value.split('/').filter(Boolean);
  const filename = parts[parts.length - 1] || value;
  return parts.length >= 2 ? `${filename} (${parts[0]})` : filename;
}

export function buildWeddingMediaOptions(
  items: WeddingMediaItem[],
  currentValue?: string,
): WeddingMediaOption[] {
  const options = items.map((item) => ({
    value: item.key,
    label: buildWeddingMediaLabel(item.key),
  }));

  const normalizedCurrentValue = currentValue?.trim();
  if (
    normalizedCurrentValue &&
    !options.some((option) => option.value === normalizedCurrentValue)
  ) {
    options.unshift({
      value: normalizedCurrentValue,
      label: `Current selection: ${buildWeddingMediaLabel(normalizedCurrentValue)}`,
    });
  }

  return options;
}

export function parseWeddingMediaList(payload: unknown): WeddingMediaItem[] {
  if (!Array.isArray(payload)) {
    throw new TypeError('Wedding media response must be an array');
  }

  for (const item of payload) {
    if (
      typeof item !== 'object' ||
      item === null ||
      typeof item.key !== 'string' ||
      item.key.trim().length === 0
    ) {
      throw new TypeError('Every wedding media item must have a valid storage key');
    }
  }

  return payload as WeddingMediaItem[];
}

export function getWeddingMediaAvailabilityText({
  kind,
  count,
  loading,
  error,
}: WeddingMediaAvailabilityOptions): string {
  if (loading) {
    return `Loading uploaded ${kind} images...`;
  }

  if (error === 'permission') {
    return `Manage Gallery permission is required to browse uploaded ${kind} images`;
  }

  if (error === 'unavailable') {
    return `Uploaded ${kind} images are temporarily unavailable`;
  }

  return `${count} uploaded ${kind} image${count === 1 ? '' : 's'} available`;
}

export function getWeddingMediaLoadNotice(
  error: WeddingMediaLoadError,
): WeddingMediaLoadNotice | null {
  if (error === 'permission') {
    return {
      role: 'status',
      title: 'Gallery access required',
      description:
        'Your current photo selections are preserved, but Manage Gallery permission is required to browse uploaded images.',
    };
  }

  if (error === 'unavailable') {
    return {
      role: 'alert',
      title: 'Uploaded media is temporarily unavailable',
      description:
        'Your current photo selections are preserved. Reopen the Story tab to try loading the media library again.',
    };
  }

  return null;
}
