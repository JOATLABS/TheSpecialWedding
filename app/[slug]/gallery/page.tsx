// app/[slug]/gallery/page.tsx
'use client';

import { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { GalleryGrid } from '@/components/GalleryGrid';
import { formatDate } from '@/utils/dateFormat';
import { WeddingContext } from '@/contexts/WeddingContext';
import GuestVerificationModal from '@/components/GuestVerificationModal';
import type { GalleryImage } from '@/types/landing';
import {
  buildPublicGalleryAccess,
  fetchPublicGalleryPage,
  type PublicGalleryAccess,
} from '@/utils/publicGallery';
import { fetchGuestSessionAccess } from '@/utils/guestAccess';

export default function GalleryPage() {
  const contextWedding = useContext(WeddingContext);
  const params = useParams();
  const slug = params.slug as string;
  const hasPublicAccess = contextWedding?.privacy_mode === 'public';

  const [wedding, setWedding] = useState<any>(hasPublicAccess ? contextWedding : null);
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [accessGranted, setAccessGranted] = useState(Boolean(hasPublicAccess));
  const [galleryAccess, setGalleryAccess] = useState<PublicGalleryAccess | null>(null);
  const [galleryLoading, setGalleryLoading] = useState(Boolean(hasPublicAccess));
  const [galleryError, setGalleryError] = useState(false);
  const [checkingSessionAccess, setCheckingSessionAccess] = useState(!hasPublicAccess);
  const [loadingMore, setLoadingMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const galleryRequestRef = useRef<AbortController | null>(null);

  const handleGuestVerified = (
    weddingData: any,
    guestData?: any,
    accessData?: PublicGalleryAccess | null,
  ) => {
    setWedding(weddingData);
    setGalleryAccess(accessData ?? buildPublicGalleryAccess(guestData));
    setGalleryLoading(true);
    setAccessGranted(true);
  };

  const fetchGallery = useCallback(
    async (cursor?: string | null, append = false) => {
      galleryRequestRef.current?.abort();
      galleryRequestRef.current = null;

      if (!slug || !wedding) {
        if (append) {
          setLoadingMore(false);
        } else {
          setGalleryLoading(false);
        }
        return;
      }

      const controller = new AbortController();
      galleryRequestRef.current = controller;

      setGalleryError(false);
      if (append) {
        setLoadingMore(true);
      } else {
        setImages([]);
        setNextCursor(null);
        setHasMore(false);
        setGalleryLoading(true);
      }

      try {
        const galleryPage = await fetchPublicGalleryPage({
          slug,
          privacyMode: wedding.privacy_mode,
          access: galleryAccess,
          limit: 60,
          cursor,
          signal: controller.signal,
        });

        if (controller.signal.aborted || galleryRequestRef.current !== controller) {
          return;
        }

        setImages((currentImages) => append ? [...currentImages, ...galleryPage.items] : galleryPage.items);
        setNextCursor(galleryPage.nextCursor);
        setHasMore(galleryPage.hasMore);
      } catch (err: unknown) {
        if (
          controller.signal.aborted
          || galleryRequestRef.current !== controller
          || (err instanceof Error && err.name === 'AbortError')
        ) {
          return;
        }

        console.warn('Gallery could not be loaded:', err);
        setGalleryError(true);
        if (!append) {
          setImages([]);
          setNextCursor(null);
          setHasMore(false);
        }
      } finally {
        if (galleryRequestRef.current === controller) {
          galleryRequestRef.current = null;
          if (append) {
            setLoadingMore(false);
          } else {
            setGalleryLoading(false);
          }
        }
      }
    },
    [galleryAccess, slug, wedding]
  );

  useEffect(() => {
    if (!accessGranted || !wedding) {
      return;
    }

    void fetchGallery();

    return () => {
      const activeRequest = galleryRequestRef.current;
      activeRequest?.abort();
      if (galleryRequestRef.current === activeRequest) {
        galleryRequestRef.current = null;
      }
    };
  }, [accessGranted, fetchGallery, wedding]);

  const handleLoadMore = () => {
    if (!nextCursor || loadingMore) {
      return;
    }

    void fetchGallery(nextCursor, true);
  };

  useEffect(() => {
    if (hasPublicAccess) {
      setCheckingSessionAccess(false);
      return;
    }

    let cancelled = false;

    const loadSessionAccess = async () => {
      try {
        const sessionData = await fetchGuestSessionAccess(slug);
        if (cancelled || !sessionData?.wedding) {
          return;
        }

        setWedding(sessionData.wedding);
        setGalleryAccess(buildPublicGalleryAccess(sessionData.guest));
        setAccessGranted(true);
        setGalleryLoading(true);
      } catch (err) {
        console.warn('Gallery session access unavailable:', err);
      } finally {
        if (!cancelled) {
          setCheckingSessionAccess(false);
        }
      }
    };

    void loadSessionAccess();

    return () => {
      cancelled = true;
    };
  }, [hasPublicAccess, slug]);

  if (checkingSessionAccess && !accessGranted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Checking gallery access...</p>
        </div>
      </div>
    );
  }

  if (accessGranted && galleryLoading && images.length === 0) {
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
          privacyInfo={contextWedding}
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
            <p className="text-lg text-blue-200 mt-2">
              {typeof displayWedding.venue === 'string'
                ? displayWedding.venue
                : displayWedding.venue?.name}
            </p>
          )}
        </div>
      </div>

      {/* Gallery */}
      <section className="px-4 py-12 max-w-7xl mx-auto">
        {galleryError ? (
          <div
            className="mx-auto mb-8 max-w-2xl rounded-xl border border-amber-200 bg-amber-50 px-6 py-7 text-center"
            role="alert"
          >
            <h2 className="text-xl font-semibold text-amber-950">
              Gallery temporarily unavailable
            </h2>
            <p className="mt-2 text-amber-800">
              {images.length > 0
                ? 'We couldn\'t load more photos. The photos already loaded are still available.'
                : 'We couldn\'t load these photos. Please try again.'}
            </p>
            <button
              type="button"
              onClick={() => {
                if (images.length > 0 && nextCursor) {
                  void fetchGallery(nextCursor, true);
                  return;
                }
                void fetchGallery();
              }}
              className="mt-5 rounded-lg border border-amber-700 px-5 py-2.5 font-semibold text-amber-900 transition-colors hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-700 focus:ring-offset-2"
            >
              Try gallery again
            </button>
          </div>
        ) : null}
        {images.length > 0 ? (
          <>
            <p className="text-center text-gray-600 mb-8">
              {images.length} photo{images.length !== 1 ? 's' : ''}
            </p>
            <GalleryGrid images={images} />
            {hasMore && !galleryError && (
              <div className="mt-8 text-center">
                <button
                  type="button"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="inline-flex items-center rounded-lg bg-wedding-navy px-6 py-3 font-semibold text-white transition-colors hover:bg-wedding-navy/90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loadingMore ? 'Loading more...' : 'Load more photos'}
                </button>
              </div>
            )}
          </>
        ) : galleryError ? null : (
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
