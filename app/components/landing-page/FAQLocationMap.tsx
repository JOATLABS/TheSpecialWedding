'use client';

import React, { useState, useEffect } from 'react';
import { ThemeConfig } from '@/types/wedding';
import { useMapEmbed } from '@/hooks/useMapEmbed';
import { openLocationInMaps } from '@/lib/maps';

interface FAQLocationMapProps {
  address: string;
  theme?: ThemeConfig;
}

export const FAQLocationMap: React.FC<FAQLocationMapProps> = ({ address, theme }) => {
  const trimmedAddress = address.trim();
  const { mapUrl, loading, error } = useMapEmbed(trimmedAddress);
  const [mapLoaded, setMapLoaded] = useState(false);

  useEffect(() => {
    setMapLoaded(false);
  }, [trimmedAddress, mapUrl]);

  if (!trimmedAddress) {
    return null;
  }

  const handleClick = () => {
    openLocationInMaps(trimmedAddress);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3 text-gray-700">
        <span className="mt-0.5 text-wedding-rose">📍</span>
        <p className="leading-relaxed whitespace-pre-line">{trimmedAddress}</p>
      </div>

      <div
        className="relative overflow-hidden rounded-lg border border-gray-200 h-64 group cursor-pointer"
        onClick={handleClick}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            handleClick();
          }
        }}
      >
        {mapUrl ? (
          <>
            <iframe
              src={mapUrl}
              width="100%"
              height="100%"
              style={{ border: 0 }}
              loading="lazy"
              allowFullScreen
              referrerPolicy="no-referrer-when-downgrade"
              onLoad={() => setMapLoaded(true)}
              title={`Map for ${trimmedAddress}`}
            />
            <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all duration-300 flex items-center justify-center pointer-events-none">
              <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-white bg-opacity-90 px-4 py-2 rounded-lg shadow-lg text-sm font-medium text-gray-800">
                Click to open in Maps
              </div>
            </div>
            {!mapLoaded && !loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
                <div className="animate-spin rounded-full h-10 w-10 border-4 border-gray-300 border-t-transparent" />
              </div>
            )}
          </>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
            {loading ? (
              <div className="animate-spin rounded-full h-10 w-10 border-4 border-gray-300 border-t-transparent" />
            ) : (
              <p className="text-gray-500">
                Map unavailable{error ? `: ${error}` : '. Please verify the address.'}
              </p>
            )}
          </div>
        )}
        <span className="sr-only">View this location in Google Maps</span>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => openLocationInMaps(trimmedAddress)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-white font-semibold hover:opacity-90 transition-colors"
          style={{ backgroundColor: theme?.primary_color || '#1e3a5f' }}
        >
          Open in Maps
          <span aria-hidden="true">↗</span>
        </button>
      </div>
    </div>
  );
};
