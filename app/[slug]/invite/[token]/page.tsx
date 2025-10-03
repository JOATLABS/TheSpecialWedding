// app/[slug]/invite/[token]/page.tsx

import React from 'react';
import { notFound } from 'next/navigation';
import RSVPForm from '@/components/RSVPForm';
import { formatDate } from '@/utils/dateFormat';
// Force dynamic rendering for this page
export const dynamic = 'force-dynamic';

export default async function InvitePage({ params }: { params: Promise<{ slug: string, token: string }> }) {
 const { slug, token } = await params;
 
 try {
 // Fetch data inline to avoid any potential export detection issues
 const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 // Remove /admin if present since these are public endpoints
 const apiUrl = base.replace('/admin', '');
 
 const weddingRes = await fetch(`${apiUrl}/weddings/slug/${slug}`, { cache: 'no-store' });
 if (!weddingRes.ok) {
 console.error(`Wedding not found: ${slug}`);
 notFound();
 }
 const wedding = await weddingRes.json();

 const guestRes = await fetch(`${apiUrl}/guest/invite/${token}?wedding_id=${wedding._id}`, { cache: 'no-store' });
 if (!guestRes.ok) {
 console.error(`Guest not found: token=${token}, wedding_id=${wedding._id}`);
 notFound();
 }
 const guest = await guestRes.json();

 return (
 <div className="min-h-screen bg-gradient-to-br from-wedding-blush to-white">
 <div className="max-w-3xl mx-auto p-6 space-y-8">
 {/* Header */}
 <div className="text-center bg-white rounded-lg shadow-lg p-8 mt-8">
 <h1 className="text-4xl md:text-5xl font-bold text-wedding-navy mb-4">
 {wedding.couple_names}'s Wedding
 </h1>
 <div className="w-24 h-1 bg-wedding-rose mx-auto mb-6"></div>
 <p className="text-2xl text-gray-700 mb-2">Hi {guest.name}!</p>
 <p className="text-lg text-gray-600">You're invited to celebrate with us.</p>
 </div>

 {/* Wedding Details */}
 <div className="bg-white rounded-lg shadow-lg p-8">
 <h2 className="text-2xl font-bold text-wedding-navy mb-6 text-center">Wedding Details</h2>

 {wedding.events && wedding.events.length > 0 && (
 <div>
 <h3 className="font-semibold text-gray-800 mb-4 text-center">Event Schedule</h3>
 <div className="space-y-3">
 {wedding.events.map((event: any, index: number) => (
 <div key={index} className="flex flex-col sm:flex-row sm:justify-between sm:items-center p-4 bg-gray-50 rounded-lg">
 <div className="mb-2 sm:mb-0">
 <span className="font-medium capitalize text-lg">{event.type.replace('_', ' ')}</span>
              <div className="text-sm text-gray-600 mt-1">
                {formatDate(event.date, {
                  weekday: 'long',
                  month: 'long',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </div>
 </div>
 <div className="text-right">
 <span className="text-gray-900 font-medium">{event.details?.time || 'Time TBA'}</span>
 {event.details?.venue_name && (
 <div className="text-sm text-gray-600">{event.details.venue_name}</div>
 )}
 </div>
 </div>
 ))}
 </div>
 </div>
 )}
 </div>

 {/* RSVP Form */}
 <div className="bg-white rounded-lg shadow-lg p-8">
 <h2 className="text-2xl font-bold text-wedding-navy mb-6 text-center">RSVP</h2>
 <RSVPForm guest={guest} token={token} />
 </div>

 {/* Footer */}
 <div className="text-center text-gray-600">
 <p>Questions? Contact us at (555) 123-4567</p>
 <p className="mt-2">We can't wait to celebrate with you! </p>
 </div>
 </div>
 </div>
 );
 } catch (error) {
 console.error('Error in InvitePage:', error);
 notFound();
 }
}
