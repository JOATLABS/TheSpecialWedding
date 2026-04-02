'use client';
import React, { Suspense, useCallback, useContext, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { WeddingContext } from '@/contexts/WeddingContext';
import { LandingLayout } from '@/components/landing-page/LandingLayout';
import { GalleryImage } from '@/types/landing';
import GuestVerificationModal from '@/components/GuestVerificationModal';
import {
  buildPublicGalleryAccess,
  fetchPublicGalleryPage,
  type PublicGalleryAccess,
} from '@/utils/publicGallery';
import { exchangeGuestInviteToken, fetchGuestSessionAccess } from '@/utils/guestAccess';

function WeddingLandingContent() {
 const contextWedding = useContext(WeddingContext);
 const params = useParams();
 const searchParams = useSearchParams();
 const slug = params.slug as string;

 // Legacy compatibility for already-issued invite links.
 const rsvpTokenParam = searchParams.get('rsvp_token');

 const [wedding, setWedding] = useState<any>(null);
 const [guest, setGuest] = useState<any>(null);
 const [images, setImages] = useState<GalleryImage[]>([]);
 const [accessGranted, setAccessGranted] = useState(false);
 const [loading, setLoading] = useState(true);
 const [galleryAccess, setGalleryAccess] = useState<PublicGalleryAccess | null>(null);
 const [openGuestRsvpOnLoad, setOpenGuestRsvpOnLoad] = useState(false);

 const hydrateGuestSession = useCallback(async () => {
   const data = await fetchGuestSessionAccess(slug);
   if (!data?.wedding) {
     return false;
   }

   const weddingForContext = {
     ...data.wedding,
     id: data.wedding.id || data.wedding._id || slug,
     slug: data.wedding.slug || slug,
   };

   setWedding(weddingForContext);
   setGuest(data.guest ?? null);
   setGalleryAccess(buildPublicGalleryAccess(data.guest));
   setAccessGranted(true);
   return true;
 }, [slug]);

 useEffect(() => {
   let cancelled = false;

   const loadWedding = async () => {
     setLoading(true);

     try {
       let shouldAutoOpenRsvp = false;

       if (rsvpTokenParam) {
         try {
           await exchangeGuestInviteToken(slug, rsvpTokenParam);
           shouldAutoOpenRsvp = true;
         } finally {
           window.history.replaceState({}, '', `/${slug}`);
         }
       } else if (typeof window !== 'undefined' && window.location.hash === '#rsvp') {
         shouldAutoOpenRsvp = true;
         window.history.replaceState({}, '', `/${slug}`);
       }

       const hasSessionAccess = await hydrateGuestSession();
       if (cancelled) {
         return;
       }

       if (hasSessionAccess) {
         setOpenGuestRsvpOnLoad(shouldAutoOpenRsvp);
         return;
       }

       if (contextWedding?.privacy_mode === 'public') {
         setWedding(contextWedding);
         setGuest(null);
         setGalleryAccess(buildPublicGalleryAccess(null));
         setAccessGranted(true);
       } else {
         setAccessGranted(false);
       }
     } catch (err: any) {
       console.error('Failed to load wedding access:', err);
       if (contextWedding?.privacy_mode === 'public') {
         setWedding(contextWedding);
         setGuest(null);
         setGalleryAccess(buildPublicGalleryAccess(null));
         setAccessGranted(true);
       } else {
         setAccessGranted(false);
       }
     } finally {
       if (!cancelled) {
         setLoading(false);
       }
     }
   };

   void loadWedding();

   return () => {
     cancelled = true;
   };
 }, [contextWedding, hydrateGuestSession, rsvpTokenParam, slug]);

 const handleGuestVerified = (
  weddingData: any,
  guestData?: any,
  accessData?: PublicGalleryAccess | null,
 ) => {
 setWedding(weddingData);
 setGuest(guestData);
 setGalleryAccess(accessData ?? buildPublicGalleryAccess(guestData));
 setAccessGranted(true);
 };

 const fetchGallery = useCallback(
 async () => {
  if (!slug || !wedding) return;

  try {
    const galleryPage = await fetchPublicGalleryPage({
      slug,
      privacyMode: wedding.privacy_mode,
      access: galleryAccess,
      limit: 12,
    });
    setImages(galleryPage.items);
  } catch (err: any) {
    console.warn('Gallery could not be loaded:', err);
    setImages([]); // Continue without gallery instead of showing error
  }
 },
 [galleryAccess, slug, wedding]
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

 // Show verification modal if access not granted
 if (!accessGranted) {
 return (
 <div className="min-h-screen bg-gradient-to-br from-rose-50 to-pink-50 dark:from-slate-900 dark:to-slate-800">
 <GuestVerificationModal
 slug={slug}
 onVerified={handleGuestVerified}
 privacyInfo={contextWedding}
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

 return <LandingLayout wedding={wedding} images={images} guest={guest} openGuestRsvpOnLoad={openGuestRsvpOnLoad} />;
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
