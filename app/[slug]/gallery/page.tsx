// app/[slug]/gallery/page.tsx
'use client';

import { useCallback, useContext, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { GalleryGrid } from '@/components/GalleryGrid';
import { formatDate } from '@/utils/dateFormat';
import { WeddingContext } from '@/contexts/WeddingContext';
import GuestVerificationModal from '@/components/GuestVerificationModal';

type GalleryImage = {
  key: string;
  url: string;
};

const API_BASE_URL = getApiBaseUrl();
const API_URL = API_BASE_URL.replace('/admin', ''); // Remove /admin for public endpoints

export default function GalleryPage() {
  const contextWedding = useContext(WeddingContext);
  const params = useParams();
  const slug = params.slug as string;

  const [wedding, setWedding] = useState<any>(null);
  const [guest, setGuest] = useState<any>(null);
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [accessGranted, setAccessGranted] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if wedding requires authentication
    if (contextWedding?.privacy_mode === 'public') {
      // Wedding is explicitly set to public, grant access immediately
      setWedding(contextWedding);
      setAccessGranted(true);
      setLoading(false);
    } else {
      // Wedding requires authentication (default: private)
      setLoading(false);
    }
  }, [contextWedding]);

  const handleGuestVerified = (weddingData: any, guestData?: any) => {
    setWedding(weddingData);
    setGuest(guestData);
    setAccessGranted(true);
  };

  const fetchGallery = useCallback(
    async (weddingData?: any, guestData?: any) => {
      if (!slug) return;

      const targetWedding = weddingData || wedding;
      const targetGuest = guestData || guest;

      try {
        // For public weddings, use the simple gallery endpoint
        // For private/password weddings, use the verified endpoint with query params
        const isPublic = targetWedding?.privacy_mode === 'public';

        let galleryUrl: string;
        if (isPublic) {
          // Public gallery endpoint
          galleryUrl = `${API_URL}/gallery?wedding_slug=${encodeURIComponent(slug)}`;
        } else {
          // Build query params for verified endpoint
          const params = new URLSearchParams({ wedding_slug: slug });

          // Add authentication parameters based on what we have
          if (targetGuest?.token) {
            params.append('token', targetGuest.token);
          } else if (targetGuest?.name) {
            params.append('name', targetGuest.name);
            if (targetGuest.phone) {
              params.append('phone', targetGuest.phone);
            }
          }

          galleryUrl = `${API_URL}/gallery/verified?${params.toString()}`;
        }

        const res = await fetch(galleryUrl, {
          method: isPublic ? 'GET' : 'POST',
        });

        if (res.ok) {
          const data = await res.json();
          setImages(data.map((img: any) => ({ key: img.key, url: img.url })));
        } else {
          // If gallery fails, don't show error - just continue without images
          console.warn('Gallery access failed, continuing without images');
          setImages([]);
        }
      } catch (err: any) {
        console.warn('Gallery could not be loaded:', err);
        setImages([]); // Continue without gallery instead of showing error
      }
    },
    [guest, slug, wedding]
  );

  // Fetch gallery when access is granted
  useEffect(() => {
    if (accessGranted && wedding) {
      fetchGallery();
    }
  }, [accessGranted, fetchGallery, wedding]);

  // Also fetch gallery after verification with the new data
  useEffect(() => {
    if (accessGranted && guest) {
      fetchGallery(wedding, guest);
    }
  }, [accessGranted, guest, wedding, fetchGallery]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading gallery...</p>
        </div>
      </div>
    );
  }

  // Show verification modal if access not granted (private wedding)
  if (!accessGranted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-rose-50 to-pink-50">
        <GuestVerificationModal
          slug={slug}
          onVerified={handleGuestVerified}
        />
      </div>
    );
  }

  const displayWedding = wedding || contextWedding;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with wedding info */}
      <div className="bg-wedding-navy text-white py-12">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            {displayWedding?.couple_names || "Wedding"} Gallery
          </h1>
          {displayWedding?.date && (
            <p className="text-xl text-blue-100">
              {formatDate(displayWedding.date, {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          )}
          {displayWedding?.venue && (
            <p className="text-lg text-blue-200 mt-2">{displayWedding.venue}</p>
          )}
        </div>
      </div>

      {/* Gallery */}
      <section className="px-4 py-12 max-w-7xl mx-auto">
        {images.length > 0 ? (
          <>
            <p className="text-center text-gray-600 mb-8">
              {images.length} photo{images.length !== 1 ? 's' : ''}
            </p>
            <GalleryGrid images={images} />
          </>
        ) : (
          <div className="text-center py-24">
            <div className="text-gray-400">
              <svg className="mx-auto h-24 w-24 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-xl font-medium text-gray-600 mb-2">No photos yet</h3>
            <p className="text-gray-500">Photos from the wedding will appear here soon!</p>
          </div>
        )}
      </section>

      {/* Back to home */}
      <div className="text-center pb-12">
        <a
          href={`/${slug}`}
          className="inline-flex items-center bg-wedding-rose text-white px-6 py-3 rounded-lg font-semibold hover:bg-opacity-90 transition-colors"
        >
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Wedding Page
        </a>
      </div>
    </div>
  );
}
