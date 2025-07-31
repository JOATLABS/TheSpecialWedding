'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Wedding, WeddingEvent } from '@/types/wedding';
import { Card } from '@/components/ui/Card';

interface EventLocationSectionProps {
  wedding: Wedding;
}

export const EventLocationSection: React.FC<EventLocationSectionProps> = ({ wedding }) => {
  const [selectedEventType, setSelectedEventType] = useState<string>('');
  const [mapLoaded, setMapLoaded] = useState(false);
  
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

  // Format event type for display
  const formatEventType = (type: string) => {
    return type.replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Format date
  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    const [year, month, day] = dateStr.split('-');
    const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    });
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
    <div className="max-w-4xl mx-auto">
      {/* Glass panel container */}
      <Card className="bg-white bg-opacity-60 backdrop-blur-lg p-6 overflow-hidden">
        <div className="flex flex-col h-[600px]">
          
          {/* Top card - Event dropdown (10%) */}
          <div className="h-[10%] mb-2">
            <div className="bg-white bg-opacity-70 rounded-lg p-4 h-full flex items-center">
              <select
                value={selectedEventType}
                onChange={(e) => setSelectedEventType(e.target.value)}
                className="w-full px-4 py-2 bg-transparent border-2 rounded-lg font-medium text-lg focus:outline-none focus:ring-2 focus:ring-wedding-rose transition-all"
                style={{ 
                  borderColor: theme?.primary_color || '#1e3a5f',
                  color: theme?.primary_color || '#1e3a5f'
                }}
              >
                {eventsWithLocation.map((event) => (
                  <option key={event.type} value={event.type}>
                    {formatEventType(event.type)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Middle card - Event details (25%) */}
          <div className="h-[25%] mb-2">
            <div className="bg-white bg-opacity-70 rounded-lg p-6 h-full">
              {selectedEvent && (
                <div className="space-y-2">
                  <h3 
                    className="text-2xl font-bold"
                    style={{ color: theme?.primary_color || '#1e3a5f' }}
                  >
                    {selectedEvent.details?.venue_name || formatEventType(selectedEvent.type)}
                  </h3>
                  <div className="flex flex-col sm:flex-row sm:gap-6 text-gray-700">
                    {selectedEvent.details?.time && (
                      <p className="flex items-center gap-2">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {selectedEvent.details.time}
                      </p>
                    )}
                    <p className="flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      {formatDate(selectedEvent.date)}
                    </p>
                  </div>
                  {selectedEvent.details?.location && (
                    <p className="flex items-start gap-2 text-gray-600">
                      <svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span className="break-words">{selectedEvent.details.location}</span>
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Bottom card - Map (65%) */}
          <div className="h-[65%]">
            <div className="bg-white bg-opacity-70 rounded-lg overflow-hidden h-full relative group cursor-pointer" onClick={handleMapClick}>
              {selectedEvent?.details?.location ? (
                <>
                  <iframe
                    width="100%"
                    height="100%"
                    style={{ border: 0 }}
                    loading="lazy"
                    allowFullScreen
                    src={`https://www.google.com/maps/embed/v1/place?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || ''}&q=${encodeURIComponent(selectedEvent.details.location)}`}
                    onLoad={() => setMapLoaded(true)}
                  />
                  
                  {/* Overlay with instructions */}
                  <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all duration-300 flex items-center justify-center">
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-white bg-opacity-90 px-6 py-3 rounded-lg shadow-lg">
                      <p className="text-gray-800 font-medium flex items-center gap-2">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                        </svg>
                        Click to open in Maps
                      </p>
                    </div>
                  </div>

                  {/* Loading spinner */}
                  {!mapLoaded && (
                    <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
                      <div className="animate-spin rounded-full h-12 w-12 border-4 border-gray-300 border-t-transparent"></div>
                    </div>
                  )}
                </>
              ) : (
                <div className="h-full flex items-center justify-center bg-gray-100">
                  <p className="text-gray-500">No location available</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};