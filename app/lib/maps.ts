'use client';

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
