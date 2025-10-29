'use client';

const normalizeLocation = (location: string) => location.trim();

export const getGoogleMapsUrl = (location: string) => {
  const encoded = encodeURIComponent(location);
  return `https://www.google.com/maps/search/?api=1&query=${encoded}`;
};

export const getAppleMapsUrl = (location: string) => {
  const encoded = encodeURIComponent(location);
  return `https://maps.apple.com/?q=${encoded}`;
};

export const openLocationInMaps = (location: string) => {
  if (!location) return;

  const isIOS = typeof navigator !== 'undefined' && /iPad|iPhone|iPod/.test(navigator.userAgent);

  if (isIOS) {
    window.open(getAppleMapsUrl(location), '_blank');
  } else {
    window.open(getGoogleMapsUrl(location), '_blank');
  }
};

export const fetchMapEmbedUrl = async (rawLocation: string): Promise<string> => {
  const normalizedLocation = normalizeLocation(rawLocation);

  if (!normalizedLocation) {
    return '';
  }

  const response = await fetch(`/api/maps?location=${encodeURIComponent(normalizedLocation)}`);

  if (!response.ok) {
    throw new Error('Failed to load map');
  }

  const data = await response.json();
  const embedUrl = typeof data.embedUrl === 'string' ? data.embedUrl : '';

  if (!embedUrl) {
    throw new Error('Map unavailable for this location');
  }

  return embedUrl;
};
