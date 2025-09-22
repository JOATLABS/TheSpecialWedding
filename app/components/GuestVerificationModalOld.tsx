'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';

interface VerifiedGuestData {
	id?: string;
	name?: string;
	phone?: string;
	token?: string;
}

interface VerifiedWeddingData {
	couple_names?: string;
	[key: string]: unknown; // legacy modal passes through dynamic fields; keep loose but not any
}

interface GuestVerificationModalProps {
 slug: string;
 onVerified: (weddingData: VerifiedWeddingData, guestData?: VerifiedGuestData) => void;
 onCancel?: () => void;
}

interface PrivacyInfo {
 couple_names: string;
 privacy_mode: string;
 requires_password: boolean;
 requires_guest_verification: boolean;
 verification_requirements: {
 require_phone: boolean;
 require_name: boolean;
 };
}

export default function GuestVerificationModal({ 
 slug, 
 onVerified, 
 onCancel 
}: GuestVerificationModalProps) {
 const [privacyInfo, setPrivacyInfo] = useState<PrivacyInfo | null>(null);
 const [loading, setLoading] = useState(true);
 const [verifying, setVerifying] = useState(false);
 const [error, setError] = useState('');

 // Form states
 const [name, setName] = useState('');
 const [phone, setPhone] = useState('');
 const [password, setPassword] = useState('');
 const [token, setToken] = useState('');

 const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
 const API_URL = API_BASE_URL.replace('/admin', ''); // Remove /admin for public endpoints

 useEffect(() => {
 fetchPrivacyInfo();
 }, [slug]);

 const fetchPrivacyInfo = async () => {
 try {
 const response = await fetch(`${API_URL}/weddings/privacy-info/${slug}`);
 if (!response.ok) {
 throw new Error('Failed to load wedding information');
 }
 const data = await response.json();
 setPrivacyInfo(data);
 } catch (err) {
 const message = err instanceof Error ? err.message : 'Failed to load wedding information';
 setError(message);
 } finally {
 setLoading(false);
 }
 };

 const handleVerification = async (e: React.FormEvent) => {
 e.preventDefault();
 setVerifying(true);
 setError('');

 try {
 const verificationData: Record<string, string> = {};
 
 if (privacyInfo?.privacy_mode === 'password' && password) {
 verificationData.password = password;
 } else if (privacyInfo?.privacy_mode === 'private') {
 if (token) {
 verificationData.token = token;
 } else {
 if (name) verificationData.name = name.trim();
 if (phone) verificationData.phone = phone.trim();
 }
 }

 const response = await fetch(`${API_URL}/weddings/verify-guest-access/${slug}`, {
 method: 'POST',
 headers: {
 'Content-Type': 'application/json',
 },
 body: JSON.stringify(verificationData),
 });

 if (!response.ok) {
 const errorData = await response.json();
 throw new Error(errorData.detail || 'Verification failed');
 }

 const result = await response.json();
 onVerified(result.wedding, result.guest);

 } catch (err) {
 const message = err instanceof Error ? err.message : 'Verification failed. Please check your information and try again.';
 setError(message);
 } finally {
 setVerifying(false);
 }
 };

 if (loading) {
 return (
 <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
 <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
 <p className="text-gray-600">Loading wedding information...</p>
 </div>
 </div>
 </div>
 );
 }

 if (!privacyInfo) {
 return (
 <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
 <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4">
 <div className="text-center">
 <div className="text-4xl mb-4 text-red-500"></div>
 <h2 className="text-xl font-semibold text-gray-900 mb-2">Unable to Load Wedding</h2>
 <p className="text-gray-600 mb-4">{error}</p>
 {onCancel && (
 <Button onClick={onCancel} variant="secondary">
 Go Back
 </Button>
 )}
 </div>
 </div>
 </div>
 );
 }

 // If wedding is public, don't show modal
 if (privacyInfo.privacy_mode === 'public') {
 // This shouldn't happen, but just in case
 useEffect(() => {
 onVerified({ couple_names: privacyInfo.couple_names });
 }, []);
 return null;
 }

 const requiresName = privacyInfo.verification_requirements?.require_name ?? true;
 const requiresPhone = privacyInfo.verification_requirements?.require_phone ?? true;

 return (
 <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
 <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
 <div className="p-6">
 <div className="text-center mb-6">
 <h2 className="text-2xl font-bold text-gray-900 mb-2">
 {privacyInfo.couple_names}
 </h2>
 <div className="w-16 h-1 bg-rose-400 mx-auto mb-4"></div>
 <p className="text-gray-600">
 {privacyInfo.privacy_mode === 'password' 
 ? 'This wedding is password protected'
 : 'Guest verification required'
 }
 </p>
 </div>

 <form onSubmit={handleVerification} className="space-y-4">
 {privacyInfo.privacy_mode === 'password' ? (
 <div>
 <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
 Wedding Password
 </label>
 <input
 type="password"
 id="password"
 value={password}
 onChange={(e) => setPassword(e.target.value)}
 className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
 placeholder="Enter wedding password"
 required
 />
 </div>
 ) : (
 <>
 <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
 <p className="text-sm text-blue-800">
 <strong>Having trouble?</strong> You can also use your invitation token if you have one.
 </p>
 </div>

 <div>
 <label htmlFor="token" className="block text-sm font-medium text-gray-700 mb-2">
 Invitation Token (Optional)
 </label>
 <input
 type="text"
 id="token"
 value={token}
 onChange={(e) => {
 setToken(e.target.value);
 if (e.target.value) {
 setName('');
 setPhone('');
 }
 }}
 className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
 placeholder="Enter your invitation token"
 />
 </div>

 {!token && (
 <>
 <div className="text-center text-gray-500 text-sm">
 - OR -
 </div>

 {requiresName && (
 <div>
 <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
 Your Name {requiresName ? '*' : ''}
 </label>
 <input
 type="text"
 id="name"
 value={name}
 onChange={(e) => setName(e.target.value)}
 className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
 placeholder="Enter your full name"
 required={requiresName && !token}
 />
 </div>
 )}

 {requiresPhone && (
 <div>
 <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-2">
 Phone Number {requiresPhone ? '*' : ''}
 </label>
 <input
 type="tel"
 id="phone"
 value={phone}
 onChange={(e) => setPhone(e.target.value)}
 className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
 placeholder="(555) 123-4567"
 required={requiresPhone && !token}
 />
 </div>
 )}

 <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
 <p className="text-sm text-gray-600">
 <strong>Tip:</strong> Use the same name and phone number from your original invitation.
 </p>
 </div>
 </>
 )}
 </>
 )}

 {error && (
 <div className="bg-red-50 border border-red-200 rounded-lg p-4">
 <p className="text-sm text-red-600">{error}</p>
 </div>
 )}

 <div className="flex space-x-3 pt-4">
 {onCancel && (
 <Button
 type="button"
 onClick={onCancel}
 variant="secondary"
 className="flex-1"
 >
 Cancel
 </Button>
 )}
 <Button
 type="submit"
 disabled={verifying}
 className="flex-1 bg-rose-600 hover:bg-rose-700"
 >
 {verifying ? (
 <>
 <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
 Verifying...
 </>
 ) : (
 'Access Wedding'
 )}
 </Button>
 </div>
 </form>

 <div className="mt-6 text-center">
 <p className="text-xs text-gray-500">
 Having trouble accessing the wedding? Please contact the couple directly.
 </p>
 </div>
 </div>
 </div>
 </div>
 );
}