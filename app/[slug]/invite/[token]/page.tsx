// app/[slug]/invite/[token]/page.tsx

import React from 'react';
import { notFound } from 'next/navigation';
import RSVPForm from '@/components/RSVPForm';

export default async function InvitePage({ params }: { params: Promise<{ slug: string, token: string }> }) {
  const { slug, token } = await params;
  
  // Fetch data inline to avoid any potential export detection issues
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  const weddingRes = await fetch(`${base}/weddings/slug/${slug}`);
  if (!weddingRes.ok) notFound();
  const wedding = await weddingRes.json();

  const guestRes = await fetch(`${base}/invite/${token}?wedding_id=${wedding._id}`);
  if (!guestRes.ok) notFound();
  const guest = await guestRes.json();

  const data = { guest, wedding };
  const { guest: guestData, wedding: weddingData } = data;

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
          <div className="grid md:grid-cols-2 gap-6">
            {wedding.date && (
              <div className="text-center">
                <div className="text-wedding-rose mb-2">
                  <svg className="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h3 className="font-semibold text-gray-800">Date</h3>
                <p className="text-gray-600">
                  {new Date(wedding.date).toLocaleDateString('en-US', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </p>
              </div>
            )}
            
            {wedding.venue && (
              <div className="text-center">
                <div className="text-wedding-rose mb-2">
                  <svg className="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <h3 className="font-semibold text-gray-800">Venue</h3>
                <p className="text-gray-600">{wedding.venue}</p>
              </div>
            )}
          </div>

          {wedding.events && wedding.events.length > 0 && (
            <div className="mt-8">
              <h3 className="font-semibold text-gray-800 mb-4 text-center">Event Schedule</h3>
              <div className="space-y-3">
                {wedding.events.map((event: any, index: number) => (
                  <div key={index} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                    <span className="font-medium capitalize">{event.type.replace('_', ' ')}</span>
                    <span className="text-gray-600">{event.time || 'Time TBA'}</span>
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
          <p className="mt-2">We can't wait to celebrate with you! ❤️</p>
        </div>
      </div>
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
          <div className="grid md:grid-cols-2 gap-6">
            {wedding.date && (
              <div className="text-center">
                <div className="text-wedding-rose mb-2">
                  <svg className="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h3 className="font-semibold text-gray-800">Date</h3>
                <p className="text-gray-600">
                  {new Date(wedding.date).toLocaleDateString('en-US', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </p>
              </div>
            )}
            
            {wedding.venue && (
              <div className="text-center">
                <div className="text-wedding-rose mb-2">
                  <svg className="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <h3 className="font-semibold text-gray-800">Venue</h3>
                <p className="text-gray-600">{wedding.venue}</p>
              </div>
            )}
          </div>

          {wedding.events && wedding.events.length > 0 && (
            <div className="mt-8">
              <h3 className="font-semibold text-gray-800 mb-4 text-center">Event Schedule</h3>
              <div className="space-y-3">
                {wedding.events.map((event: any, index: number) => (
                  <div key={index} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                    <span className="font-medium capitalize">{event.type.replace('_', ' ')}</span>
                    <span className="text-gray-600">{event.time || 'Time TBA'}</span>
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
          <p className="mt-2">We can't wait to celebrate with you! ❤️</p>
        </div>
      </div>
    </div>
  );
}
