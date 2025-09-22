'use client';
import React, { useContext, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { WeddingContext } from '@/contexts/WeddingContext';
import { Wedding } from '@/types/wedding';
import { LandingLayout } from '@/components/landing-page/LandingLayout';
import { GalleryImage } from '@/types/landing';
import GuestVerificationModal from '@/components/GuestVerificationModal';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/admin";
const API_URL = API_BASE_URL.replace('/admin', ''); // Remove /admin for public endpoints

// Guest subset of fields used in this page
interface VerifiedGuest {
	id?: string;
	name?: string;
	email?: string;
	phone?: string;
	token?: string; // verification token for gallery access
}

interface GalleryResponseItem { key: string; url: string }

// Runtime type guard for gallery API items
function isGalleryResponseItem(value: unknown): value is GalleryResponseItem {
 return (
	 typeof value === 'object' &&
	 value !== null &&
	 'key' in value &&
	 'url' in value &&
	 typeof (value as any).key === 'string' &&
	 typeof (value as any).url === 'string'
 );
}

export default function WeddingLandingPage() {
 const contextWedding = useContext(WeddingContext);
 const params = useParams();
 const slug = params.slug as string;
 
 const [wedding, setWedding] = useState<Wedding | null>(null);
 const [guest, setGuest] = useState<VerifiedGuest | null>(null);
 const [images, setImages] = useState<GalleryImage[]>([]);
 const [error, setError] = useState<string | null>(null);
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

 const handleGuestVerified = (weddingData: Wedding, guestData?: VerifiedGuest) => {
 setWedding(weddingData);
 setGuest(guestData ?? null);
 setAccessGranted(true);
 
 // Fetch gallery for verified users
 fetchGallery(weddingData, guestData);
 };

 const fetchGallery = async (weddingData?: Wedding | null, guestData?: VerifiedGuest | null) => {
 if (!slug) return;
 
 const targetWedding = weddingData || wedding;
 const targetGuest = guestData || guest;
 
 try {
 // Use the verified gallery endpoint
 const requestBody = new URLSearchParams({
 wedding_slug: slug,
 });

 // Add authentication parameters based on what we have
 if (targetGuest?.token) {
 requestBody.append('token', targetGuest.token);
 } else if (targetGuest?.name) {
 requestBody.append('name', targetGuest.name);
 if (targetGuest.phone) {
 requestBody.append('phone', targetGuest.phone);
 }
 }

 const res = await fetch(`${API_URL}/gallery/verified`, {
 method: 'POST',
 headers: {
 'Content-Type': 'application/x-www-form-urlencoded',
 },
 body: requestBody.toString(),
 });

 if (res.ok) {
 const data: unknown = await res.json();
 if (Array.isArray(data)) {
	 const mapped = data.filter(isGalleryResponseItem)
									 .map(img => ({ key: img.key, url: img.url }));
	 setImages(mapped);
 } else {
	 setImages([]);
 }
 } else {
 // If gallery fails, don't show error - just continue without images
 console.warn('Gallery access failed, continuing without images');
 setImages([]);
 }
 } catch (err) {
 console.warn('Gallery could not be loaded:', err);
 setImages([]); // Continue without gallery instead of showing error
 }
 };

 // Fetch gallery when access is granted and we have wedding data
 useEffect(() => {
 if (accessGranted && wedding) {
 fetchGallery();
 }
 }, [accessGranted, wedding, guest, slug]);

 if (loading) {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 to-pink-50">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-600 mx-auto mb-4"></div>
 <p className="text-gray-600">Loading wedding...</p>
 </div>
 </div>
 );
 }

 if (error) {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 to-pink-50">
 <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
 <div className="text-4xl mb-4 text-red-500"></div>
 <h2 className="text-xl font-semibold text-gray-900 mb-2">Unable to Load Wedding</h2>
 <p className="text-gray-600 mb-4">{error}</p>
 </div>
 </div>
 );
 }

 // Show verification modal if access not granted
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

 if (!wedding) {
 return (
 <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 to-pink-50">
 <div className="text-center">
 <p className="text-gray-600">Wedding not found</p>
 </div>
 </div>
 );
 }

 return <LandingLayout wedding={wedding} images={images} />;
}