'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Wedding } from '@/types/wedding';
import { GlassCard } from '@/components/ui/GlassCard';
import { formatDate as formatDisplayDate } from '@/utils/dateFormat';

interface EventLocationSectionProps {
  wedding: Wedding;
}

export const EventLocationSection: React.FC<EventLocationSectionProps> = ({ wedding }) => {
  const [selectedEventType, setSelectedEventType] = useState<string>('');
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapUrl, setMapUrl] = useState<string>('');

  // Get events with location details
  const eventsWithLocation = useMemo(() => {
    return wedding.events?.filter(event =>
      event.details?.location && event.details.location.trim() !== ''
    ) || [];
  }, [wedding.events]);

  // Set initial selected event
  useEffect(() => {
    if (eventsWithLocation.length > 0 && !selectedEventType) {
      setSelectedEventType(eventsWithLocation[0].type);
    }
  }, [eventsWithLocation, selectedEventType]);

  // Get selected event details
  const selectedEvent = eventsWithLocation.find(e => e.type === selectedEventType);

  // Fetch secure map URL when location changes
  useEffect(() => {
    const fetchMapUrl = async () => {
      if (selectedEvent?.details?.location) {
        try {
          const response = await fetch(`/api/maps?location=${encodeURIComponent(selectedEvent.details.location)}`);
          if (response.ok) {
            const data = await response.json();
            setMapUrl(data.embedUrl);
          }
        } catch (error) {
          console.error('Failed to load map:', error);
        }
      }
    };

    fetchMapUrl();
  }, [selectedEvent?.details?.location]);

  // Format event type for display
  const formatEventType = (type: string) => {
    return type.replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Generate Google Maps URL
  const getGoogleMapsUrl = (location: string) => {
    const encoded = encodeURIComponent(location);
    return `https://www.google.com/maps/search/?api=1&query=${encoded}`;
  };

  // Generate Apple Maps URL
  const getAppleMapsUrl = (location: string) => {
    const encoded = encodeURIComponent(location);
    return `https://maps.apple.com/?q=${encoded}`;
  };

  // Handle map click
  const handleMapClick = () => {
    if (!selectedEvent?.details?.location) return;

    const location = selectedEvent.details.location;

    // Check if on iOS
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);

    if (isIOS) {
      // On iOS, prefer Apple Maps
      window.open(getAppleMapsUrl(location), '_blank');
    } else {
      // On Android and desktop, use Google Maps
      window.open(getGoogleMapsUrl(location), '_blank');
    }
  };

  // Don't render if no events with locations
  if (eventsWithLocation.length === 0) {
    return null;
  }

  const theme = wedding.theme_config;

  return (
    <GlassCard className="max-w-4xl mx-auto p-6" depth="near" theme={wedding.theme_config}>
      <h2 className="text-4xl font-bold text-center mb-8 theme-primary">Wedding Details</h2>
      <div className="flex flex-col space-y-3">

      {/* Event dropdown */}
      <div>
        <div className="bg-white/70 dark:bg-gray-800/70 rounded-lg p-4 flex items-center transition-colors duration-300">
          <select
            value={selectedEventType}
            onChange={(e) => setSelectedEventType(e.target.value)}
            className="w-full px-4 py-2 bg-transparent border-2 rounded-lg font-medium text-lg focus:outline-none focus:ring-2 focus:ring-wedding-rose transition-all theme-primary theme-border-primary"
          >
            {eventsWithLocation.map((event) => (
              <option key={event.type} value={event.type} className="dark:bg-gray-800 dark:text-gray-100">
                {formatEventType(event.type)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Event details */}
      <div>
        <div className="bg-white/70 dark:bg-gray-800/70 rounded-lg p-4 sm:p-6 transition-colors duration-300">
          {selectedEvent && (
            <div className="flex flex-col gap-4">
              {/* Venue name - full width */}
              <h3
                className="text-xl sm:text-2xl font-bold break-words theme-primary"
              >
                {selectedEvent.details?.venue_name || formatEventType(selectedEvent.type)}
              </h3>

              {/* Details row: info on left, dress code on right */}
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                {/* Left side - time, date, address */}
                <div className="space-y-2 min-w-0">
                  <div className="flex flex-wrap gap-x-6 gap-y-2 text-gray-700 dark:text-gray-200">
                    {selectedEvent.details?.time && (
                      <p className="flex items-center gap-2 text-sm sm:text-base">
                        <svg className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {selectedEvent.details.time}
                      </p>
                    )}
                    <p className="flex items-center gap-2 text-sm sm:text-base">
                      <svg className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      {formatDisplayDate(selectedEvent.date, {
                        weekday: 'long',
                        month: 'long',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </p>
                  </div>
                  {selectedEvent.details?.location && (
                    <p className="flex items-start gap-2 text-gray-600 dark:text-gray-300 text-sm sm:text-base">
                      <svg className="w-4 h-4 sm:w-5 sm:h-5 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span className="break-words">{selectedEvent.details.location}</span>
                    </p>
                  )}
                </div>

                {/* Right side - Attire */}
                {selectedEvent.details?.attire && (
                  <div className="md:text-right md:max-w-[45%] flex-shrink-0">
                    <p className="text-xs sm:text-sm font-semibold text-gray-600 dark:text-gray-400 mb-1">Dress Code</p>
                    <p className="text-base sm:text-lg font-medium theme-primary">
                      {selectedEvent.details.attire}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="h-[400px] sm:h-[450px]">
        <div className="bg-white/70 dark:bg-gray-800/70 rounded-lg overflow-hidden h-full relative group cursor-pointer transition-colors duration-300" onClick={handleMapClick}>
          {selectedEvent?.details?.location && mapUrl ? (
            <>
              <iframe
                width="100%"
                height="100%"
                style={{ border: 0 }}
                loading="lazy"
                allowFullScreen
                referrerPolicy="no-referrer-when-downgrade"
                src={mapUrl}
                onLoad={() => setMapLoaded(true)}
              />

              {/* Overlay with instructions */}
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-all duration-300 flex items-center justify-center">
                <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-white/90 dark:bg-gray-800/90 px-6 py-3 rounded-lg shadow-lg">
                  <p className="text-gray-800 dark:text-gray-100 font-medium flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                    </svg>
                    Click to open in Maps
                  </p>
                </div>
              </div>

              {/* Loading spinner */}
              {!mapLoaded && (
                <div className="absolute inset-0 flex items-center justify-center bg-gray-100 dark:bg-gray-700">
                  <div className="animate-spin rounded-full h-12 w-12 border-4 border-gray-300 dark:border-gray-500 border-t-transparent"></div>
                </div>
              )}
            </>
          ) : selectedEvent?.details?.location && !mapUrl ? (
            <div className="h-full flex items-center justify-center bg-gray-100 dark:bg-gray-700">
              <div className="animate-spin rounded-full h-12 w-12 border-4 border-gray-300 dark:border-gray-500 border-t-transparent"></div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center bg-gray-100 dark:bg-gray-700">
              <p className="text-gray-500 dark:text-gray-400">No location available</p>
            </div>
          )}
        </div>
      </div>
    </div>
    </GlassCard>
  );
};