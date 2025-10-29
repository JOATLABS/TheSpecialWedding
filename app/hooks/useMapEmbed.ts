'use client';

import { useEffect, useState } from 'react';

interface UseMapEmbedResult {
  mapUrl: string;
  loading: boolean;
  error: string | null;
}

const normalizeLocation = (location?: string | null) => {
  if (!location) return '';
  const trimmed = location.trim();
  return trimmed;
};

export const useMapEmbed = (location?: string | null): UseMapEmbedResult => {
  const [mapUrl, setMapUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    const fetchMap = async () => {
      const normalizedLocation = normalizeLocation(location);
      if (!normalizedLocation) {
        setMapUrl('');
        setError(null);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/maps?location=${encodeURIComponent(normalizedLocation)}`);
        if (!response.ok) {
          throw new Error('Failed to fetch map');
        }
        const data = await response.json();
        if (!ignore) {
          setMapUrl(typeof data.embedUrl === 'string' ? data.embedUrl : '');
        }
      } catch (err) {
        if (!ignore) {
          setMapUrl('');
          setError(err instanceof Error ? err.message : 'Failed to fetch map');
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };

    fetchMap();

    return () => {
      ignore = true;
    };
  }, [location]);

  return { mapUrl, loading, error };
};
