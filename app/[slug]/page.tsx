'use client';
import React, { Suspense, useCallback, useContext, useEffect, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useParams, useSearchParams } from 'next/navigation';
import { WeddingContext } from '@/contexts/WeddingContext';
import { LandingLayout } from '@/components/landing-page/LandingLayout';
import { GalleryImage } from '@/types/landing';
import GuestVerificationModal from '@/components/GuestVerificationModal';

const API_BASE_URL = getApiBaseUrl();
const API_URL = API_BASE_URL.replace('/admin', ''); // Remove /admin for public endpoints

function WeddingLandingContent() {
 const contextWedding = useContext(WeddingContext);
 const params = useParams();
 const searchParams = useSearchParams();
 const slug = params.slug as string;

 // Read rsvp_token from URL query param
 const rsvpTokenParam = searchParams.get('rsvp_token');

 const [wedding, setWedding] = useState<any>(null);
 const [guest, setGuest] = useState<any>(null);
 const [images, setImages] = useState<GalleryImage[]>([]);
 const [error, setError] = useState<string | null>(null);
 const [accessGranted, setAccessGranted] = useState(false);
 const [loading, setLoading] = useState(true);
 const [rsvpToken, setRsvpToken] = useState<string | null>(null);

 // Fetch wedding data using RSVP token (bypasses privacy verification)
 const fetchWeddingByToken = useCallback(async (tokenValue: string) => {
   try {
     const res = await fetch(`${API_URL}/weddings/guest-access/${slug}/${tokenValue}`);
     if (!res.ok) {
       const errorData = await res.json().catch(() => ({}));
       throw new Error(errorData.detail || 'Failed to access wedding');
     }
     const data = await res.json();
     const { wedding: weddingResult, guest: guestResult } = data;

     // Map _id to id for WeddingContext compatibility
     const weddingForContext = {
       ...weddingResult,
       id: weddingResult.id || weddingResult._id || slug,
       slug: weddingResult.slug || slug,
     };

     setWedding(weddingForContext);
     setGuest(guestResult);
     setAccessGranted(true);
   } catch (err: any) {
     console.error('Failed to load wedding via token:', err);
     // Fall back to normal flow on token failure
     if (contextWedding?.privacy_mode === 'public') {
       setWedding(contextWedding);
       setAccessGranted(true);
     }
   } finally {
     setLoading(false);
   }
 }, [slug, contextWedding]);

 useEffect(() => {
   if (rsvpTokenParam && !accessGranted) {
     // Store token in state and clean URL to prevent refresh issues
     // Guard: only fetch once (accessGranted prevents re-fetch if contextWedding updates)
     setRsvpToken(rsvpTokenParam);
     // Persist token in sessionStorage so it survives page refresh
     try { sessionStorage.setItem('rsvp_token_' + slug, rsvpTokenParam); } catch {}
     window.history.replaceState({}, '', `/${slug}`);
     fetchWeddingByToken(rsvpTokenParam);
   } else if (!rsvpTokenParam && !accessGranted) {
     // Check sessionStorage for a persisted token (survives page refresh)
     let storedToken: string | null = null;
     try { storedToken = sessionStorage.getItem('rsvp_token_' + slug); } catch {}
     if (storedToken) {
       setRsvpToken(storedToken);
       fetchWeddingByToken(storedToken);
     } else if (contextWedding?.privacy_mode === 'public') {
       // Wedding is explicitly set to public, grant access immediately
       setWedding(contextWedding);
       setAccessGranted(true);
       setLoading(false);
     } else {
       // Wedding requires authentication (default: private)
       setLoading(false);
     }
   }
 // eslint-disable-next-line react-hooks/exhaustive-deps
 }, [contextWedding, rsvpTokenParam, slug]);

 const handleGuestVerified = (weddingData: any, guestData?: any) => {
 setWedding(weddingData);
 setGuest(guestData);
 setAccessGranted(true);

 // Fetch gallery for verified users
 fetchGallery(weddingData, guestData);
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

 // Fetch gallery when access is granted and we have wedding data
 useEffect(() => {
 if (accessGranted && wedding) {
 fetchGallery();
 }
 }, [accessGranted, fetchGallery, wedding]);

 if (loading) {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 to-pink-50 dark:from-slate-900 dark:to-slate-800">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-600 dark:border-rose-400 mx-auto mb-4"></div>
 <p className="text-gray-600 dark:text-gray-300">Loading wedding...</p>
 </div>
 </div>
 );
 }

 if (error) {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 to-pink-50 dark:from-slate-900 dark:to-slate-800">
 <div className="text-center bg-white dark:bg-slate-800 p-8 rounded-lg shadow-sm dark:shadow-slate-900/50 max-w-md">
 <div className="text-4xl mb-4 text-red-500 dark:text-red-400"></div>
 <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Unable to Load Wedding</h2>
 <p className="text-gray-600 dark:text-gray-300 mb-4">{error}</p>
 </div>
 </div>
 );
 }

 // Show verification modal if access not granted
 if (!accessGranted) {
 return (
 <div className="min-h-screen bg-gradient-to-br from-rose-50 to-pink-50 dark:from-slate-900 dark:to-slate-800">
 <GuestVerificationModal
 slug={slug}
 onVerified={handleGuestVerified}
 />
 </div>
 );
 }

 if (!wedding) {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 to-pink-50 dark:from-slate-900 dark:to-slate-800">
 <div className="text-center">
 <p className="text-gray-600 dark:text-gray-300">Wedding not found</p>
 </div>
 </div>
 );
 }

 return <LandingLayout wedding={wedding} images={images} guest={guest} rsvpToken={rsvpToken} />;
}

export default function WeddingLandingPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 to-pink-50 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-600 dark:border-rose-400 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-300">Loading wedding...</p>
        </div>
      </div>
    }>
      <WeddingLandingContent />
    </Suspense>
  );
}
